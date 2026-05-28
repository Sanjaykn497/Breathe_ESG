import csv
import io
from decimal import Decimal
from datetime import date

from .base import BaseIngestionService


from django.core.exceptions import ValidationError as DjangoValidationError

class UtilityIngestionService(BaseIngestionService):
    source_type = "UTILITY"

    def parse_rows(self, raw_input: str) -> list[dict]:
        """Accepts CSV string from utility provider export."""
        if not raw_input or not raw_input.strip():
            raise DjangoValidationError("Utility upload file is empty.")
        
        try:
            reader = csv.DictReader(io.StringIO(raw_input))
            rows = [dict(row) for row in reader]
        except Exception as e:
            raise DjangoValidationError(f"Invalid CSV format: {e}")

        if not rows:
            raise DjangoValidationError("Utility upload CSV contains no data rows.")

        first_row = rows[0]
        required = {"kwh_usage", "period_start", "period_end"}
        missing = required - set(first_row.keys())
        if missing:
            raise DjangoValidationError(f"Missing required CSV columns: {', '.join(missing)}")

        return rows

    def extract_fields(self, row: dict) -> dict:
        return {
            "category": "ELECTRICITY",
            "quantity": Decimal(row["kwh_usage"].replace(",", "").strip()),
            "unit":     "kWh",
        }

    def get_period(self, row: dict) -> tuple[date, date]:
        return (
            date.fromisoformat(row["period_start"].strip()),
            date.fromisoformat(row["period_end"].strip()),
        )
