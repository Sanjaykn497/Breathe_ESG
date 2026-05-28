#!/usr/bin/env bash
set -o errexit

# ── 1. Python dependencies ──────────────────────────────
pip install -r requirements.txt

# ── 2. Build React frontend ─────────────────────────────
cd frontend
npm install
npm run build
cd ..

# ── 3. Collect static files (React build + Django admin) ─
python manage.py collectstatic --no-input

# ── 4. Run database migrations ──────────────────────────
python manage.py migrate

# ── 5. Seed demo data (idempotent — skips if data exists)
python populate_demo_data.py
