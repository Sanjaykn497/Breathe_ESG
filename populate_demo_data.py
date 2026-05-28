"""
Idempotent demo data population script.
Safe to re-run on every deploy — skips if data already exists.
"""
import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from emissions.models import Organization, User, DataSource, EmissionRecord
from emissions.enums import UserRole, ReviewStatus
from emissions.services.ingestion.sap import SAPIngestionService
from emissions.services.ingestion.utility import UtilityIngestionService
from emissions.services.ingestion.travel import TravelIngestionService
from emissions.services.review import approve_record, lock_record


def populate():
    # Check if demo data already exists — skip if so
    if Organization.objects.filter(slug="breathe-corp").exists():
        record_count = EmissionRecord.objects.count()
        if record_count > 0:
            print(f"Demo data already exists ({record_count} records). Skipping.")
            return
    
    print("Populating demo data...")

    # 1. Setup mock organization and users
    org, _ = Organization.objects.get_or_create(
        slug="breathe-corp",
        defaults={"name": "Breathe Corp"},
    )

    analyst_user, _ = User.objects.get_or_create(
        email="analyst@breathe.io",
        defaults={
            "organization": org,
            "role": UserRole.ANALYST,
            "is_active": True,
        },
    )

    admin_user, _ = User.objects.get_or_create(
        email="admin@breathe.io",
        defaults={
            "organization": org,
            "role": UserRole.ADMIN,
            "is_active": True,
        },
    )

    print("Users and Organization ready!")

    # 2. Ingest SAP CSV
    sap_csv = """plant_code,quantity,unit,document_date
PLT001,500,L,2024-01-15
PLT002,1200,MJ,2024-02-15
PLT001,200,L,2024-03-10
PLT002,1000,kBTU,2024-04-15"""

    sap_service = SAPIngestionService(org, analyst_user, 2026)
    sap_service.ingest("SAP Upload", "SAP-2026-Q1", sap_csv)
    print("SAP CSV Ingested!")

    # 3. Ingest Utility CSV (Baseline 2025)
    utility_csv_2025 = """kwh_usage,period_start,period_end
8000,2024-01-01,2024-01-31
8500,2024-02-01,2024-02-29
8300,2024-03-01,2024-03-31"""

    utility_service_2025 = UtilityIngestionService(org, analyst_user, 2025)
    utility_service_2025.ingest("Utility Base 2025", "UTIL-2025", utility_csv_2025)
    print("Utility Base 2025 Ingested!")

    # 4. Ingest Utility CSV (Spike 2026 — triggers anomaly detection)
    utility_csv_2026 = """kwh_usage,period_start,period_end
25000,2024-04-01,2024-04-30"""

    utility_service_2026 = UtilityIngestionService(org, analyst_user, 2026)
    utility_service_2026.ingest("Utility Spike 2026", "UTIL-2026", utility_csv_2026)
    print("Utility Spike 2026 Ingested!")

    # 5. Ingest Travel JSON
    travel_records = [
        {"travel_type": "FLIGHT", "distance_km": 850, "travel_date": "2024-03-10"},
        {"travel_type": "FLIGHT", "distance_km": 8200, "travel_date": "2024-03-15"},
        {"travel_type": "HOTEL", "nights": 3, "travel_date": "2024-03-20"},
        {"travel_type": "CAR", "distance_km": 120, "travel_date": "2024-03-22"},
    ]

    travel_service = TravelIngestionService(org, analyst_user, 2026)
    travel_service.ingest("Travel Ingest", "TRAVEL-2026", travel_records)
    print("Travel JSON Ingested!")

    # 6. Apply workflow changes for a realistic dashboard mix
    records = list(EmissionRecord.objects.all().order_by("created_at"))

    # Approve one record
    rec_to_approve = next(
        (r for r in records if r.review_status in (ReviewStatus.AUTO_APPROVED, ReviewStatus.NEEDS_REVIEW)),
        None,
    )
    if rec_to_approve:
        approve_record(rec_to_approve, analyst_user, notes="Verified by Analyst.")
        print(f"Record {rec_to_approve.id} approved!")

    # Lock one record (must be APPROVED first)
    rec_to_lock = next(
        (r for r in records if r.id != (rec_to_approve.id if rec_to_approve else None)),
        None,
    )
    if rec_to_lock:
        approve_record(rec_to_lock, analyst_user, notes="Verified for lock.")
        lock_record(rec_to_lock, admin_user)
        print(f"Record {rec_to_lock.id} locked by Admin!")

    print("\n--- Current Record Statuses ---")
    for r in EmissionRecord.objects.all().order_by("period_start"):
        print(
            f"Period: {r.period_start} | Category: {r.category} | "
            f"Qty: {r.quantity_raw} {r.unit_raw} | CO2e: {r.co2e_kg} | "
            f"Status: {r.review_status} | Anomaly: {r.anomaly_flag}"
        )

    print(f"\nDone! {EmissionRecord.objects.count()} records populated.")


if __name__ == "__main__":
    populate()
