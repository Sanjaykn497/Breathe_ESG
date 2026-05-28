# breathe_ESG — Emissions Review Dashboard & Ingestion Platform

breathe_ESG is a multi-tenant enterprise ESG data ingestion and review platform built with **Django REST Framework** and **React + TypeScript + shadcn/ui**.

## 🚀 Quick Start (Local Setup)

### Prerequisites
* **Python**: 3.10+
* **Node.js**: 18+
* **PostgreSQL**: Running on port `5432` with a database named `breathe_esg` created.

### 1. Backend Server Setup
```bash
cd breathe_ESG
.venv\Scripts\activate

# Apply migrations and create superuser
python manage.py migrate
python manage.py createsuperuser

# Start Django server (http://127.0.0.1:8000)
python manage.py runserver
```

### 2. Frontend Client Setup
In a new terminal window:
```bash
cd breathe_ESG/frontend
npm install
npm run dev
# Start Vite client (http://localhost:5173)
```

## 🔐 Credentials for Demo
You can log in as either role directly in the visual card UI:
* **Analyst**: `analyst@breathe.io` / `password`
* **Admin**: `admin@breathe.io` / `password` *(only this role can Lock approved records)*
