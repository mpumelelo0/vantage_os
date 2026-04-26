# VANTAGE OS — Setup Guide

## What this is
A full business operating system for Vantage. Runs locally on your laptop.
Handles orders, stock, payments, security, analytics, and auto WhatsApp messages.

---

## Setup (one time)

### 1. Install Python
Download Python 3.11+ from https://python.org if you don't have it.

### 2. Open PyCharm
Open the `vantage_os` folder as a project in PyCharm.

### 3. Install dependencies
Open the PyCharm terminal (bottom of screen) and run:
```
pip install flask
```

### 4. Put your store front in the folder
Copy your `index.html` (the Vantage store website) into the `vantage_os` folder.

### 5. Change your admin password
Open `app.py` and find these two lines near the top:
```python
ADMIN_USER = 'vantage_admin'
ADMIN_PASS = 'Vantage@2026!'
```
Change them to something only you know. Keep it strong.

### 6. Add your bank details
Open the Admin panel after starting → Settings → fill in your FNB details.

---

## Running the system

In PyCharm terminal:
```
python app.py
```

Then open your browser and go to:
- **Store front:** http://localhost:5000
- **Admin login:** http://localhost:5000/login
- **Admin panel:** http://localhost:5000/admin

---

## File structure
```
vantage_os/
├── app.py              ← Main system (Flask backend)
├── index.html          ← Your store website (paste here)
├── requirements.txt    ← Dependencies
├── database/
│   └── vantage.db      ← Auto-created, stores all data
├── logs/
│   └── vantage.log     ← System logs
└── static/
    ├── login.html      ← Admin login page
    └── admin.html      ← Admin dashboard
```

---

## What the system does automatically

| Time | Action |
|------|--------|
| Every 30 mins | Checks stock levels, alerts you if low |
| Every hour | Flags unpaid orders older than 24h |
| 21:00 daily | Generates daily report (orders, revenue, low stock) |

All alerts are logged with WhatsApp links you can click to send.

---

## Security features
- IP-based login rate limiting (5 attempts → 15 min lockout)
- All login attempts logged with IP and timestamp
- Session-based authentication (expires after 8 hours)
- Input sanitisation on all order forms
- Store closed outside 08:00 - 22:00 (no orders accepted)
- Full security event log in Admin → Security tab

---

## How orders work
1. Customer visits your store, clicks "Order via WhatsApp"
2. System logs the order, generates a reference (VTG-XXXXX)
3. Customer gets a pre-typed WhatsApp message with your bank details
4. You receive payment, go to Admin → Orders → click "Verify EFT"
5. System generates a WhatsApp confirmation link to send the customer
6. Update order to "Shipped" when you hand it over → system generates delivery WA message

---

## To deploy online later
When you're ready to go live, this same code works on PythonAnywhere or any VPS.
Just upload the folder, install flask, and point the web app to `app.py`.
