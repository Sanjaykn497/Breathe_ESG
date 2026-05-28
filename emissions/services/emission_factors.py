from decimal import Decimal

# ─────────────────────────────────────────────
# Emission factor registry
# Keys: (source_type, category, unit)
# Values: { factor: Decimal kg CO2e / unit, source: str }
# ─────────────────────────────────────────────
EMISSION_FACTORS: dict[tuple, dict] = {
    # SAP — Scope 1 Stationary Combustion
    ("SAP", "DIESEL",       "L"):   {"factor": Decimal("2.6840"), "source": "DEFRA 2024"},
    ("SAP", "NATURAL_GAS",  "MJ"):  {"factor": Decimal("0.0561"), "source": "DEFRA 2024"},
    ("SAP", "PETROL",       "L"):   {"factor": Decimal("2.3100"), "source": "DEFRA 2024"},

    # Utility — Scope 2 Electricity
    ("UTILITY", "ELECTRICITY", "kWh"): {"factor": Decimal("0.2330"), "source": "EPA eGRID 2023"},

    # Travel — Scope 3
    ("TRAVEL", "FLIGHT_SHORT_HAUL", "km"): {"factor": Decimal("0.2550"), "source": "DEFRA 2024"},
    ("TRAVEL", "FLIGHT_LONG_HAUL",  "km"): {"factor": Decimal("0.1950"), "source": "DEFRA 2024"},
    ("TRAVEL", "HOTEL_NIGHT",     "night"):{"factor": Decimal("20.600"), "source": "DEFRA 2024"},
    ("TRAVEL", "CAR_RENTAL",      "km"):   {"factor": Decimal("0.1710"), "source": "DEFRA 2024"},
}

# Unit conversion: raw_unit → (normalized_unit, multiplier)
UNIT_CONVERSION: dict[str, tuple[str, Decimal]] = {
    "gallons": ("L",   Decimal("3.78541")),
    "kBTU":    ("MJ",  Decimal("1.05506")),
    "BTU":     ("MJ",  Decimal("0.00105506")),
    "MWh":     ("kWh", Decimal("1000")),
    "miles":   ("km",  Decimal("1.60934")),
}


def get_factor(source_type: str, category: str, unit: str) -> dict | None:
    return EMISSION_FACTORS.get((source_type, category, unit))


def convert_unit(value: Decimal, raw_unit: str) -> tuple[Decimal, str]:
    """Returns (converted_value, normalized_unit). No-op if already canonical."""
    if raw_unit in UNIT_CONVERSION:
        target_unit, multiplier = UNIT_CONVERSION[raw_unit]
        return value * multiplier, target_unit
    return value, raw_unit
