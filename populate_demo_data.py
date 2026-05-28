import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from emissions.models import Organization, User, DataSource, RawRecord, EmissionRecord, AuditLog
from emissions.enums import UserRole, ReviewStatus
from emissions.services.ingestion.sap import SAPIngestionService
from emissions.services.ingestion.utility import UtilityIngestionService
from emissions.services.ingestion.travel import TravelIngestionService
from emissions.services.review import approve_record, lock_record

# 1. Clear database completely
EmissionRecord.objects.all().delete()
RawRecord.objects.all().delete()
DataSource.objects.all().delete()
AuditLog.objects.all().delete()
User.objects.all().delete()
Organization.objects.all().delete()

print("Database cleared!")

# 2. Setup mock organization and users
org = Organization.objects.create(
    name="Breathe Corp",
    slug="breathe-corp",
)

analyst_user = User.objects.create(
    email="analyst@breathe.io",
    organization=org,
    role=UserRole.ANALYST,
)

admin_user = User.objects.create(
    email="admin@breathe.io",
    organization=org,
    role=UserRole.ADMIN,
)

print("Users and Organization created!")

# 3. Ingest corrected SAP CSV
sap_csv = """plant_code,quantity,unit,document_date
PLT001,500,L,2024-01-15
PLT002,1200,MJ,2024-02-15
PLT001,200,L,2024-03-10
PLT002,1000,kBTU,2024-04-15"""

sap_service = SAPIngestionService(org, analyst_user, 2026)
sap_ds = sap_service.ingest("SAP Upload", "SAP-2026-Q1", sap_csv)
print("SAP CSV Ingested!")

# 4. Ingest Anomaly Utility CSV (Baseline in 2025, Spike in 2026)
utility_csv_2025 = """kwh_usage,period_start,period_end
8000,2024-01-01,2024-01-31
8500,2024-02-01,2024-02-29
8300,2024-03-01,2024-03-31"""

utility_service_2025 = UtilityIngestionService(org, analyst_user, 2025)
util_ds_2025 = utility_service_2025.ingest("Utility Base 2025", "UTIL-2025", utility_csv_2025)
print("Utility Base 2025 Ingested!")

utility_csv_2026 = """kwh_usage,period_start,period_end
25000,2024-04-01,2024-04-30"""

utility_service_2026 = UtilityIngestionService(org, analyst_user, 2026)
util_ds_2026 = utility_service_2026.ingest("Utility Spike 2026", "UTIL-2026", utility_csv_2026)
print("Utility Spike 2026 Ingested!")

# 5. Ingest Travel JSON
travel_records = [
    {"travel_type": "FLIGHT", "distance_km": 850, "travel_date": "2024-03-10"},
    {"travel_type": "FLIGHT", "distance_km": 8200, "travel_date": "2024-03-15"},
    {"travel_type": "HOTEL", "nights": 3, "travel_date": "2024-03-20"},
    {"travel_type": "CAR", "distance_km": 120, "travel_date": "2024-03-22"}
]

travel_service = TravelIngestionService(org, analyst_user, 2026)
travel_ds = travel_service.ingest("Travel Ingest", "TRAVEL-2026", travel_records)
print("Travel JSON Ingested!")

# 6. Apply workflow changes to get a perfect dashboard mix
records = list(EmissionRecord.objects.all().order_by("created_at"))

# Let's approve a record
rec_to_approve = next(r for r in records if r.review_status == ReviewStatus.AUTO_APPROVED or r.review_status == ReviewStatus.NEEDS_REVIEW)
approve_record(rec_to_approve, analyst_user, notes="Verified by Analyst.")
print(f"Record {rec_to_approve.id} approved!")

# Let's lock a record (must be APPROVED first)
rec_to_lock = next(r for r in records if r.id != rec_to_approve.id)
approve_record(rec_to_lock, analyst_user, notes="Verified for lock.")
lock_record(rec_to_lock, admin_user)
print(f"Record {rec_to_lock.id} locked by Admin!")

print("\n--- Current Record Statuses ---")
for r in EmissionRecord.objects.all().order_by("period_start"):
    print(f"Period: {r.period_start} | Category: {r.category} | Qty: {r.quantity_raw} {r.unit_raw} | CO2e: {r.co2e_kg} | Status: {r.review_status} | Anomaly: {r.anomaly_flag}")
