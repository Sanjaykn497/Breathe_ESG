from decimal import Decimal
from emissions.enums import EmissionScope
from .emission_factors import get_factor, convert_unit


SCOPE_MAP: dict[str, str] = {
    "SAP":     EmissionScope.SCOPE_1,
    "UTILITY": EmissionScope.SCOPE_2,
    "TRAVEL":  EmissionScope.SCOPE_3,
}


def normalize_record(
    source_type: str,
    category: str,
    quantity_raw: Decimal,
    unit_raw: str,
) -> dict:
    """
    Returns normalized fields ready for EmissionRecord creation.
    Raises ValueError if no emission factor is found.
    """
    quantity_norm, unit_norm = convert_unit(quantity_raw, unit_raw)
    factor_entry = get_factor(source_type, category, unit_norm)

    if factor_entry is None:
        raise ValueError(
            f"No emission factor for ({source_type}, {category}, {unit_norm})"
        )

    co2e_kg = (quantity_norm * factor_entry["factor"]).quantize(Decimal("0.0001"))
    scope   = SCOPE_MAP[source_type]

    return {
        "scope":                  scope,
        "category":               category,
        "quantity_raw":           quantity_raw,
        "unit_raw":               unit_raw,
        "quantity_normalized":    quantity_norm,
        "unit_normalized":        unit_norm,
        "emission_factor":        factor_entry["factor"],
        "emission_factor_source": factor_entry["source"],
        "co2e_kg":                co2e_kg,
    }
