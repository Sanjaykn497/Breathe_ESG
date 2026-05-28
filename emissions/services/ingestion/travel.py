from decimal import Decimal
from datetime import date

from .base import BaseIngestionService


# DEFRA short-haul distance cutoff (km)
HAUL_DISTANCE_THRESHOLD_KM = Decimal("3700")


from django.core.exceptions import ValidationError as DjangoValidationError

class TravelIngestionService(BaseIngestionService):
    source_type = "TRAVEL"

    def parse_rows(self, raw_input) -> list[dict]:
        """Accepts a list of dicts from the mock travel API."""
        if not raw_input:
            raise DjangoValidationError("Travel payload is empty.")
            
        if isinstance(raw_input, list):
            rows = raw_input
        elif isinstance(raw_input, dict):
            rows = raw_input.get("records", [])
        else:
            raise DjangoValidationError("Invalid travel records format: expected list or JSON object.")

        if not rows:
            raise DjangoValidationError("Travel payload contains no records.")

        first_row = rows[0]
        if not isinstance(first_row, dict):
            raise DjangoValidationError("Travel records must be JSON objects.")

        required = {"travel_type", "travel_date"}
        missing = required - set(first_row.keys())
        if missing:
            raise DjangoValidationError(f"Missing required fields in travel records: {', '.join(missing)}")

        return rows

    def extract_fields(self, row: dict) -> dict:
        travel_type = row.get("travel_type", "").upper()

        if travel_type == "FLIGHT":
            distance_km = Decimal(str(row.get("distance_km", "0")))
            category    = (
                "FLIGHT_SHORT_HAUL"
                if distance_km <= HAUL_DISTANCE_THRESHOLD_KM
                else "FLIGHT_LONG_HAUL"
            )
            return {"category": category, "quantity": distance_km, "unit": "km"}

        elif travel_type == "HOTEL":
            nights = Decimal(str(row.get("nights", "1")))
            return {"category": "HOTEL_NIGHT", "quantity": nights, "unit": "night"}

        elif travel_type in ("CAR", "GROUND"):
            distance_km = Decimal(str(row.get("distance_km", "0")))
            return {"category": "CAR_RENTAL", "quantity": distance_km, "unit": "km"}

        return {"category": "UNKNOWN", "quantity": Decimal("0"), "unit": "unknown"}

    def get_period(self, row: dict) -> tuple[date, date]:
        travel_date = date.fromisoformat(str(row.get("travel_date", "")).strip())
        return travel_date, travel_date
