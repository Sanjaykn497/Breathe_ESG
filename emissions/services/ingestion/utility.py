import csv
import io
from decimal import Decimal
from datetime import date

from .base import BaseIngestionService


class UtilityIngestionService(BaseIngestionService):
    source_type = "UTILITY"

    def parse_rows(self, raw_input: str) -> list[dict]:
        """Accepts CSV string from utility provider export."""
        reader = csv.DictReader(io.StringIO(raw_input))
        return [dict(row) for row in reader]

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
