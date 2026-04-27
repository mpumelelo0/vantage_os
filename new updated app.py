"""
VANTAGE OS — Flask Backend
Compatible with the new Vantage store (index.html)
Run: py app.py
Admin: http://localhost:5000/admin  (opens login modal on the store)
"""

import os, json, logging, secrets, hashlib, time
from datetime import datetime, timedelta
from functools import wraps
import requests
from flask import (
    Flask, request, jsonify, session,
    send_from_directory, redirect, url_for
)

# ─── CONFIG ────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=8)

# Yoco — paste your live secret key here or set YOCO_SECRET_KEY env var
YOCO_SECRET_KEY  = os.environ.get("YOCO_SECRET_KEY", "sk_test_59b83b630e7DVy2672f4c80a277a")
YOCO_CHECKOUT_URL = "https://payments.yoco.com/api/checkouts"

# Admin credentials — CHANGE THESE
ADMIN_USERNAME = os.environ.get("ADMIN_USER", "vantage_admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "Vantage@2026!")   # ← change this

# Simple IP rate-limit for login: 5 attempts then 15-min lockout
login_attempts = {}   # {ip: {"count": n, "locked_until": timestamp}}

# ─── LOGGING ────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/vantage.log",
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)

# ─── SIMPLE FILE DATABASE ───────────────────────────────────────────────
DB_DIR = "database"
os.makedirs(DB_DIR, exist_ok=True)

def _read(name):
    path = os.path.join(DB_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _write(name, data):
    path = os.path.join(DB_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def _read_dict(name, default=None):
    path = os.path.join(DB_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default or {}

def _write_dict(name, data):
    path = os.path.join(DB_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

# ─── SEED DEFAULT DATA ──────────────────────────────────────────────────
def seed_defaults():
    if not _read("products"):
        _write("products", [
            {"id":1,"name":"Urban Sling Bag",            "category":"Bags",       "price":450,"description":"Designed for those who move. Sleek weather-resistant matte black finish with adjustable tactical straps.","stock":8, "is_new":False,"image_path":""},
            {"id":2,"name":"Essential Oversized Hoodie", "category":"Outerwear",  "price":850,"description":"Premium heavyweight cotton blend, signature boxy fit, double-lined hood. Built to last.","stock":12,"is_new":False,"image_path":""},
            {"id":3,"name":"Signature Boxy Tee — Black", "category":"Tops",       "price":400,"description":"High-density premium cotton, dropped shoulders, structured oversized fit. Minimalist branding.","stock":20,"is_new":False,"image_path":""},
            {"id":4,"name":"Signature Boxy Tee — Arctic","category":"Tops",       "price":400,"description":"Crisp arctic white edition. Same premium heavyweight cotton. Breathable, durable.","stock":3, "is_new":True, "image_path":""},
            {"id":5,"name":"Vantage Signature Beanie",   "category":"Accessories","price":250,"description":"Heavyweight ribbed knit in deep void black. One size.","stock":15,"is_new":True, "image_path":""},
        ])
    if not _read_dict("settings"):
        _write_dict("settings", {
            "bank_name":"FNB","account_holder":"Vantage",
            "account_number":"","branch_code":"",
            "yoco_public_key":"","store_url":"http://localhost:5000",
        })

seed_defaults()

# ─── HELPERS ────────────────────────────────────────────────────────────
def next_id(lst):
    return max((x["id"] for x in lst), default=0) + 1

def ref_code():
    return "VTG-" + str(int(time.time() * 1000))[-5:].zfill(5)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error":"Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def check_rate_limit(ip):
    now = time.time()
    info = login_attempts.get(ip, {"count":0,"locked_until":0})
    if info["locked_until"] > now:
        remaining = int(info["locked_until"] - now)
        return False, f"Too many attempts. Try again in {remaining}s."
    if info["count"] >= 5:
        login_attempts[ip] = {"count":0,"locked_until":now + 900}
        return False, "Account locked for 15 minutes."
    return True, ""

def record_attempt(ip, success):
    if success:
        login_attempts.pop(ip, None)
    else:
        info = login_attempts.get(ip, {"count":0,"locked_until":0})
        login_attempts[ip] = {"count":info["count"]+1,"locked_until":info["locked_until"]}

# ─── SERVE STORE ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# Payment success/cancel landing pages
@app.route("/payment/success")
def payment_success():
    order_ref = request.args.get("ref","")
    orders    = _read("orders")
    for o in orders:
        if o.get("order_ref") == order_ref:
            o["payment_status"] = "verified"
            o["status"] = "processing"
            logging.info(f"Payment SUCCESS: {order_ref}")
            break
    _write("orders", orders)
    # FIX: Decrease stock for the correct ordered product
    products = _read("products")
    order_obj = next((o for o in _read("orders") if o.get("order_ref") == order_ref), None)
    if order_obj:
            ordered_pid = order_obj.get("product_id")
            for p in products:
                if p.get("id") == ordered_pid and p.get("stock", 0) > 0:
                    p["stock"] -= 1
                    break                                    
    _write("products", products)
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'>

    <title>Payment Successful — Vantage</title>
    <link href='https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400&family=Raleway:wght@300;400&display=swap' rel='stylesheet'>
    <style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#020202;color:#d9d4ca;font-family:'Raleway',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:18px;padding:24px;text-align:center}}h1{{font-family:'Playfair Display',serif;font-size:clamp(32px,6vw,72px);color:#ede0c8;letter-spacing:8px}}.sub{{font-size:8px;letter-spacing:5px;text-transform:uppercase;color:#b5903f}}.ref{{font-size:10px;letter-spacing:3px;color:#74706b;margin-top:8px}}.btn{{margin-top:28px;padding:13px 36px;background:#b5903f;border:none;color:#020202;font-size:7px;letter-spacing:4px;text-transform:uppercase;cursor:pointer;text-decoration:none;display:inline-block;font-family:'Raleway',sans-serif}}</style>
    </head><body>
    <div class="sub">Payment Confirmed</div>
    <h1>Thank You</h1>
    <div class="ref">Order {order_ref}</div>
    <p style="font-size:10px;color:#74706b;max-width:340px;margin-top:12px">Your order is confirmed. We'll WhatsApp you shortly. Stay fresh. 🖤</p>
    <a href="/" class="btn">Continue Shopping</a>
    </body></html>"""

@app.route("/payment/cancel")
def payment_cancel():
    return """<!DOCTYPE html><html><head><meta charset='UTF-8'>
    <title>Payment Cancelled — Vantage</title>
    <link href='https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400&family=Raleway:wght@300;400&display=swap' rel='stylesheet'>
    <style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#020202;color:#d9d4ca;font-family:'Raleway',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:18px;padding:24px;text-align:center}}h1{{font-family:'Playfair Display',serif;font-size:clamp(32px,6vw,72px);color:#ede0c8;letter-spacing:8px}}.sub{{font-size:8px;letter-spacing:5px;text-transform:uppercase;color:#7a1515}}.btn{{margin-top:28px;padding:13px 36px;background:#b5903f;border:none;color:#020202;font-size:7px;letter-spacing:4px;text-transform:uppercase;cursor:pointer;text-decoration:none;display:inline-block;font-family:'Raleway',sans-serif}}</style>
    </head><body>
    <div class="sub">Payment Cancelled</div>
    <h1>No Problem</h1>
    <p style="font-size:10px;color:#74706b;max-width:340px;margin-top:12px">Your payment was cancelled. WhatsApp us on 073 084 0058 if you need help.</p>
    <a href="/" class="btn">Back to Store</a>
    </body></html>"""

# ─── AUTH ────────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    ip = request.remote_addr or "unknown"
    ok, msg = check_rate_limit(ip)
    if not ok:
        return jsonify({"error": msg}), 429

    data     = request.get_json(silent=True) or {}
    username = data.get("username","").strip()
    password = data.get("password","")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session.permanent = True
        session["admin"]  = True
        session["user"]   = username
        record_attempt(ip, True)
        logging.info(f"Admin login: {username} from {ip}")
        return jsonify({"success": True})
    else:
        record_attempt(ip, False)
        logging.warning(f"Failed login attempt: {username} from {ip}")
        return jsonify({"error": "Invalid credentials"}), 401

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/check")
def auth_check():
    return jsonify({"admin": bool(session.get("admin"))})

# ─── PRODUCTS ────────────────────────────────────────────────────────────
@app.route("/api/products")
def get_products():
    return jsonify(_read("products"))

@app.route("/api/admin/products", methods=["POST"])
@require_auth
def create_product():
    products = _read("products")
    data     = request.get_json(silent=True) or {}
    new_prod = {
        "id":          next_id(products),
        "name":        data.get("name","").strip(),
        "category":    data.get("category","Tops"),
        "price":       float(data.get("price",0)),
        "description": data.get("description",""),
        "stock":       int(data.get("stock",0)),
        "is_new":      bool(data.get("is_new",False)),
        "image_path":  data.get("image_path",""),
        "created_at":  datetime.now().isoformat(),
    }
    if not new_prod["name"] or new_prod["price"] <= 0:
        return jsonify({"error":"Name and price required"}), 400
    products.append(new_prod)
    _write("products", products)
    logging.info(f"Product added: {new_prod['name']}")
    return jsonify(new_prod), 201

@app.route("/api/admin/products/<int:pid>", methods=["PATCH","DELETE"])
@require_auth
def manage_product(pid):
    products = _read("products")
    prod     = next((p for p in products if p["id"] == pid), None)
    if not prod:
        return jsonify({"error":"Not found"}), 404

    if request.method == "DELETE":
        products = [p for p in products if p["id"] != pid]
        _write("products", products)
        return jsonify({"success":True})

    data = request.get_json(silent=True) or {}
    for field in ["name","category","price","description","stock","is_new","image_path"]:
        if field in data:
            prod[field] = data[field]
    _write("products", products)
    return jsonify(prod)

# ─── YOCO PAYMENT ────────────────────────────────────────────────────────
@app.route('/api/pay/create-checkout', methods=['POST'])
def create_yoco_checkout():
    try:
        data = request.get_json()
        pid = data.get('product_id')

        products = _read("products")
        product = next((p for p in products if p['id'] == pid), None)
        if not product:
            return jsonify({"error": "Product not found"}), 404

        order_ref = f"VTG-{secrets.token_hex(3).upper()}"

        new_order = {
            "id": int(time.time()),
            "order_ref": order_ref,
            "product_id": pid,  # FIX: save product_id so stock can be updated on success
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "customer_name": data.get('customer_name'),
            "customer_phone": data.get('customer_phone'),
            "items": f"{product['name']} ({data.get('size', 'M')})",
            "total": product['price'],
            "payment_status": "pending"
        }

        _write("orders", _read("orders") + [new_order])

        payload = {
            "amount": int(product['price'] * 100),
            "currency": "ZAR",
            "cancelUrl": f"{request.host_url}",
            "successUrl": f"{request.host_url}payment/success?ref={order_ref}"
        }

        headers = {
            "Authorization": f"Bearer {YOCO_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        r = requests.post("https://payments.yoco.com/api/checkouts", json=payload, headers=headers)

        if r.status_code in (200, 201):
            return jsonify({"redirectUrl": r.json()['redirectUrl']})
        else:
            return jsonify({"error": r.text}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── ORDERS ──────────────────────────────────────────────────────────────
@app.route("/api/admin/orders")
@require_auth
def get_orders():
    return jsonify(_read("orders"))

@app.route("/api/admin/orders/<int:oid>/status", methods=["PATCH"])
@require_auth
def update_order_status(oid):
    orders = _read("orders")
    order  = next((o for o in orders if o["id"] == oid), None)
    if not order: return jsonify({"error":"Not found"}), 404
    data   = request.get_json(silent=True) or {}
    order["status"] = data.get("status", order.get("status", "pending"))
    _write("orders", orders)
    return jsonify(order)

@app.route("/api/admin/orders/<int:oid>/payment", methods=["PATCH"])
@require_auth
def update_payment(oid):
    orders = _read("orders")
    order  = next((o for o in orders if o["id"] == oid), None)
    if not order: return jsonify({"error":"Not found"}), 404
    data   = request.get_json(silent=True) or {}
    order["payment_status"] = data.get("payment_status", order["payment_status"])
    order["payment_ref"]    = data.get("payment_ref","")
    _write("orders", orders)
    logging.info(f"Payment verified: {order['order_ref']}")
    return jsonify(order)

@app.route("/api/admin/orders/<int:oid>", methods=["DELETE"])
@require_auth
def delete_order(oid):
    orders = _read("orders")
    orders = [o for o in orders if o["id"] != oid]
    _write("orders", orders)
    return jsonify({"success":True})

# ─── SETTINGS ────────────────────────────────────────────────────────────
@app.route("/api/admin/settings", methods=["GET","POST"])
@require_auth
def settings_route():
    if request.method == "GET":
         return jsonify(_read_dict("settings"))
    data = request.get_json(silent=True) or {}
    current = _read_dict("settings")
    current.update(data)
    _write_dict("settings", current)
    return jsonify({"success":True})

# ─── RUN ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*52)
    print("  VANTAGE OS — Starting up")
    print("  Store:  http://localhost:5000")
    print("  Admin:  http://localhost:5000  (click Admin in nav)")
    print("="*52 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
