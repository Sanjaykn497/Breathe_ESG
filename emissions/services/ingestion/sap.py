import csv
import io
from decimal import Decimal
from datetime import date

from .base import BaseIngestionService


# Maps SAP plant codes to fuel category names
PLANT_CODE_MAP: dict[str, str] = {
    "PLT001": "DIESEL",
    "PLT002": "NATURAL_GAS",
    "PLT003": "PETROL",
    "PLT004": "NATURAL_GAS",
}


from django.core.exceptions import ValidationError as DjangoValidationError

class SAPIngestionService(BaseIngestionService):
    source_type = "SAP"

    def parse_rows(self, raw_input: str) -> list[dict]:
        """Accepts CSV string as received from SAP export."""
        if not raw_input or not raw_input.strip():
            raise DjangoValidationError("SAP upload file is empty.")
        
        try:
            reader = csv.DictReader(io.StringIO(raw_input))
            rows = [dict(row) for row in reader]
        except Exception as e:
            raise DjangoValidationError(f"Invalid CSV format: {e}")

        if not rows:
            raise DjangoValidationError("SAP upload CSV contains no data rows.")

        first_row = rows[0]
        required = {"plant_code", "quantity", "document_date"}
        missing = required - set(first_row.keys())
        if missing:
            raise DjangoValidationError(f"Missing required CSV columns: {', '.join(missing)}")

        return rows

    def extract_fields(self, row: dict) -> dict:
        plant_code = row.get("plant_code", "").strip()
        category   = PLANT_CODE_MAP.get(plant_code, "UNKNOWN")
        quantity   = Decimal(row.get("quantity", "0").replace(",", ""))
        unit       = row.get("unit", "L").strip()
        return {"category": category, "quantity": quantity, "unit": unit}

    def get_period(self, row: dict) -> tuple[date, date]:
        # SAP records are point-in-time; use document_date for both bounds
        doc_date = date.fromisoformat(row.get("document_date", "").strip())
        return doc_date, doc_date
