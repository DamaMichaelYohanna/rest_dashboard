# Moniepoint POS Restaurant Payment Monitor 💳📊

A modern, real-time **Django Web Application** built for monitoring restaurant revenue, card payments, and bank transfers processed through **Moniepoint POS Terminals** and **Moniepoint Business Account Transfers**.

Developed for **YOHANNA DAMA MICHAEL**.

---

## 🌟 Key Features

* **⚡ Real-Time Payment Ingestion**: Listens for incoming Moniepoint webhooks and updates dashboard metrics, hourly trend charts, and transaction feeds instantly with audio/visual alerts.
* **💳 Dual Payment Ingestion**:
  * **POS Terminal Hardware Payments**: Card inserts, taps, and terminal-initiated transfers (`V1_POS_TRANSACTION`, `V1_POS_PURCHASE_TRANSACTION`, `V1_POS_CARD_TRANSFER_TRANSACTION`).
  * **Direct Bank Transfers**: Instant credit notifications when customers transfer from mobile banking apps (OPay, PalmPay, Kuda, GTBank, Zenith, etc.) to your Moniepoint account (`V1_TRANSFER_TRANSACTION`, `V1_POS_TRANSFER_TRANSACTION`).
* **📊 Live Money Dashboard (`/`)**:
  * **Today's Revenue (₦)** with percentage growth vs yesterday.
  * **Transaction Count**, Success Rate (%), and Average Ticket Size per order.
  * **Hourly Sales Trend Chart**: Interactive Chart.js line graph visualizing peak revenue hours.
  * **Payment Method Split**: Breakdown between Card Payments and Bank Transfers.
  * **POS Terminal Revenue Breakdown**: Bar chart showing total daily sales per terminal location.
* **📱 POS Fleet Auto-Discovery (`/terminals/`)**:
  * Automatically registers and tracks physical POS terminals (e.g. *Main Bar*, *Dining Room*, *VIP Terrace*) as webhooks arrive.
* **🔎 Searchable Transaction Log & Reports (`/transactions/`)**:
  * Filter by Reference, RRN, Customer/Sender Name, Payment Method, Date Range, or POS Terminal.
  * Single-click **Printable POS Receipt Modal** displaying Retrieval Reference Number (RRN), card details, and status.
  * **CSV Export**: One-click export for financial accounting and audit reconciliation.
* **🔒 Enterprise Security**:
  * Credentials stored securely in a local `.env` environment file.
  * Moniepoint HMAC SHA256 / SHA512 signature verification on all incoming webhook payloads.
  * Idempotency handling (`update_or_create`) to gracefully process retry attempts without duplicate entries.

---

## 🏗️ Project Architecture

```
[ Customer POS / Bank Transfer ]
             │
             ▼
    Moniepoint API Platform
             │
             │ (Instant Webhook POST)
             ▼
   https://your-domain.com/api/webhooks/moniepoint/
             │
             ▼
   Django Backend (payments/services.py)
   ├── Signature Verification (HMAC SHA256/512)
   ├── DB Ingestion (Transaction & Terminal Models)
   └── Real-time Feed API (/api/live-feed/)
             │
             ▼
   Dark Glassmorphic UI Dashboard (Chart.js + Audio Chimes)
```

---

## 🛠️ Tech Stack

* **Backend**: Python 3.12, Django 5.x, SQLite, `requests`, `python-dotenv`.
* **Frontend**: Vanilla CSS Design System with dark glassmorphism styling, Chart.js for data visualization, and responsive mobile-ready layout.

---

## 📦 Installation & Setup Guide

### 1. Clone the Repository
```bash
git clone https://github.com/DamaMichaelYohanna/rest_dashboard.git
cd rest_dashboard
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env`)
Create a `.env` file in the root directory (or copy from `.env.example`):
```env
# Moniepoint POS API Credentials
MONIEPOINT_API_KEY=your_moniepoint_api_key_here
MONIEPOINT_BUSINESS_ID=43845617
MONIEPOINT_WEBHOOK_SECRET=your_webhook_secret_here
MONIEPOINT_ENVIRONMENT=PRODUCTION  # SANDBOX or PRODUCTION

DJANGO_SECRET_KEY=your_custom_django_secret_key
```

### 5. Run Database Migrations
```bash
python manage.py makemigrations payments
python manage.py migrate
```

---

## 🚀 Running the Application

### 1. Start the Django Server
```bash
python manage.py runserver 8000
```
Access the application at `http://127.0.0.1:8000/`.

### 2. Expose Endpoint via Ngrok (For Live Webhook Delivery)
In a separate terminal window:
```bash
ngrok http 8000
```
Copy your generated HTTPS forwarding URL (e.g. `https://xxxx.ngrok-free.dev`).

### 3. Register Webhook in Moniepoint Merchant Portal
In your **Moniepoint Merchant Dashboard** under **Webhook Subscriptions**:
* **Endpoint URL**: `https://xxxx.ngrok-free.dev/api/webhooks/moniepoint/`
* **Subscribed Event Types**:
  * `V1_POS_TRANSACTION`
  * `V1_POS_PURCHASE_TRANSACTION`
  * `V1_POS_CARD_TRANSFER_TRANSACTION`
  * `V1_POS_TRANSFER_TRANSACTION`
  * `V1_TRANSFER_TRANSACTION`
  * `V1_POS_WITHDRAWAL_TRANSACTION`
  * `V1_POS_BILL_PAYMENT_TRANSACTION`
  * `V1_POS_AIRTIME_TRANSACTION`

---

## 📂 Project Structure

```
rest_dashboard/
├── .env.example              # Sample environment variables template
├── .gitignore                # Excludes secrets, venv, and sqlite db
├── manage.py                 # Django management script
├── requirements.txt          # Python dependencies
├── README.md                 # Project Documentation
├── moniepoint_dashboard/     # Core Django Project Configuration
│   ├── settings.py           # Configured for .env loading & app settings
│   ├── urls.py               # Main URL router
│   └── wsgi.py               # WSGI application entrypoint
└── payments/                 # Payments Application
    ├── models.py             # MoniepointConfig, Terminal, Transaction, WebhookLog
    ├── services.py           # Moniepoint API Client & Webhook Processor
    ├── views.py              # Dashboard, Transactions, Settings & API views
    ├── urls.py               # Application endpoints
    ├── static/css/
    │   └── dashboard.css     # Dark glassmorphic design system
    └── templates/
        ├── base.html         # Main layout wrapper
        └── payments/
            ├── dashboard.html    # Analytics dashboard & live ticker
            ├── transactions.html # Filterable table & receipt modal
            ├── terminals.html    # POS fleet overview
            └── settings.html     # Credentials & webhook logs page
```

---

## 🛡️ License

Private Application for **YOHANNA DAMA MICHAEL**. All rights reserved.
