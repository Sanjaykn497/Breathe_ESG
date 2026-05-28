from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.test import APITestCase
from rest_framework import status

from emissions.models import Organization, User, DataSource, EmissionRecord
from emissions.enums import UserRole, IngestionStatus
from emissions.services.ingestion.sap import SAPIngestionService
from emissions.services.ingestion.utility import UtilityIngestionService
from emissions.services.ingestion.travel import TravelIngestionService


class IngestionValidationTests(APITestCase):
    def setUp(self):
        # Create organization
        self.org = Organization.objects.create(
            name="Test Breathe Corp",
            slug="breathe-corp",
        )
        # Create user
        self.user = User.objects.create(
            email="analyst@breathe.io",
            organization=self.org,
            role=UserRole.ANALYST,
            is_active=True,
        )
        # Authenticate user for API view testing
        self.client.force_authenticate(user=self.user)

    # ── Service Layer Tests ──────────────────────────────────────────

    def test_sap_valid_csv(self):
        csv_data = (
            "plant_code,quantity,unit,document_date\n"
            "PLT001,500,L,2024-01-15\n"
            "PLT002,1200,MJ,2024-02-15\n"
        )
        svc = SAPIngestionService(self.org, self.user, 2026)
        ds = svc.ingest("SAP Upload", "SAP-2026-Q1", csv_data)
        
        self.assertEqual(ds.ingestion_status, IngestionStatus.COMPLETED)
        self.assertEqual(ds.row_count, 2)
        self.assertIsNone(ds.error_summary)
        self.assertEqual(EmissionRecord.objects.filter(data_source=ds).count(), 2)

    def test_sap_empty_csv(self):
        svc = SAPIngestionService(self.org, self.user, 2026)
        with self.assertRaises(DjangoValidationError) as context:
            svc.ingest("SAP Empty", "SAP-EMPTY", "")
        self.assertIn("SAP upload file is empty.", str(context.exception))

    def test_sap_missing_columns(self):
        # Missing plant_code
        csv_data = (
            "quantity,unit,document_date\n"
            "500,L,2024-01-15\n"
        )
        svc = SAPIngestionService(self.org, self.user, 2026)
        with self.assertRaises(DjangoValidationError) as context:
            svc.ingest("SAP Bad Headers", "SAP-BAD-HEAD", csv_data)
        self.assertIn("Missing required CSV columns", str(context.exception))

    def test_sap_all_rows_invalid(self):
        # All rows have negative quantity
        csv_data = (
            "plant_code,quantity,unit,document_date\n"
            "PLT001,-500,L,2024-01-15\n"
            "PLT002,-1200,MJ,2024-02-15\n"
        )
        svc = SAPIngestionService(self.org, self.user, 2026)
        with self.assertRaises(DjangoValidationError) as context:
            svc.ingest("SAP Negative", "SAP-NEG", csv_data)
        self.assertIn("Entire file is invalid. First error: Quantity cannot be negative", str(context.exception))

    def test_sap_mixed_rows(self):
        # Succeeded: 2 rows, Failed: 1 row (negative quantity)
        csv_data = (
            "plant_code,quantity,unit,document_date\n"
            "PLT001,500,L,2024-01-15\n"
            "PLT002,-1200,MJ,2024-02-15\n"
            "PLT001,200,L,2024-03-10\n"
        )
        svc = SAPIngestionService(self.org, self.user, 2026)
        ds = svc.ingest("SAP Mixed", "SAP-MIXED", csv_data)
        
        self.assertEqual(ds.ingestion_status, IngestionStatus.COMPLETED)
        self.assertEqual(ds.row_count, 2)
        self.assertIsNotNone(ds.error_summary)
        self.assertEqual(len(ds.error_summary), 1)
        self.assertEqual(ds.error_summary[0]["row"], 1)
        self.assertIn("Quantity cannot be negative", ds.error_summary[0]["error"])
        
        # Verify 2 records saved in DB
        self.assertEqual(EmissionRecord.objects.filter(data_source=ds).count(), 2)

    def test_utility_invalid_date_ordering(self):
        # Row 1 is valid, Row 2 has period_end < period_start
        csv_data = (
            "kwh_usage,period_start,period_end\n"
            "8000,2024-01-01,2024-01-31\n"
            "8500,2024-02-28,2024-02-01\n"
        )
        svc = UtilityIngestionService(self.org, self.user, 2026)
        ds = svc.ingest("Utility Date Order", "UTIL-DATE", csv_data)
        
        self.assertEqual(ds.ingestion_status, IngestionStatus.COMPLETED)
        self.assertEqual(ds.row_count, 1)
        self.assertEqual(len(ds.error_summary), 1)
        self.assertEqual(ds.error_summary[0]["row"], 1)
        self.assertIn("cannot be before start date", ds.error_summary[0]["error"])

    def test_travel_malformed_input(self):
        svc = TravelIngestionService(self.org, self.user, 2026)
        with self.assertRaises(DjangoValidationError) as context:
            # String instead of array or dict
            svc.ingest("Travel String", "TRAVEL-STR", "invalid payload")
        self.assertIn("Invalid travel records format", str(context.exception))


    # ── API Endpoint Tests ───────────────────────────────────────────

    def test_api_sap_upload_success(self):
        payload = {
            "name": "SAP Ingest API Test",
            "external_ref": "SAP-API-REF",
            "reporting_year": 2024,
            "csv_text": (
                "plant_code,quantity,unit,document_date\n"
                "PLT001,500,L,2024-01-15\n"
            )
        }
        res = self.client.post("/api/ingest/sap/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["row_count"], 1)
        self.assertEqual(res.data["ingestion_status"], "COMPLETED")

    def test_api_sap_upload_completely_malformed(self):
        payload = {
            "name": "SAP Ingest API Test Bad",
            "reporting_year": 2024,
            "csv_text": (
                "incorrect_header1,incorrect_header2\n"
                "val1,val2\n"
            )
        }
        res = self.client.post("/api/ingest/sap/", payload, format="json")
        # Should return HTTP 400 Bad Request instead of 500
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing required CSV columns", res.data["detail"][0])

    def test_api_utility_upload_all_negative(self):
        payload = {
            "name": "Utility Negative Ingest API Test",
            "reporting_year": 2024,
            "csv_text": (
                "kwh_usage,period_start,period_end\n"
                "-1500,2024-01-01,2024-01-31\n"
            )
        }
        res = self.client.post("/api/ingest/utility/", payload, format="json")
        # Since all rows are negative, it should raise a ValidationError on ingestion and return 400
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Quantity cannot be negative", res.data["detail"][0])
