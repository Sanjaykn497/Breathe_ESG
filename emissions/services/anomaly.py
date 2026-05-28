from decimal import Decimal
from django.db.models import Avg
from emissions.models import EmissionRecord

ANOMALY_THRESHOLD_PERCENT = Decimal("200")


def check_anomaly(
    organization_id,
    scope: str,
    category: str,
    reporting_year: int,
    co2e_kg: Decimal,
) -> tuple[bool, str]:
    """
    Compares new co2e_kg against the rolling 3-period average for the
    same (org, scope, category). Returns (anomaly_flag, anomaly_reason).
    """
    avg_result = (
        EmissionRecord.objects
        .filter(
            organization_id=organization_id,
            scope=scope,
            category=category,
            reporting_year__lt=reporting_year,
        )
        .order_by("-reporting_year")[:3]
        .aggregate(avg=Avg("co2e_kg"))
    )

    baseline = avg_result.get("avg")
    if baseline is None or baseline == 0:
        return False, ""

    pct_change = ((co2e_kg - Decimal(str(baseline))) / Decimal(str(baseline))) * 100

    if pct_change > ANOMALY_THRESHOLD_PERCENT:
        reason = (
            f"CO2e ({co2e_kg} kg) is {pct_change:.1f}% above the "
            f"3-period average ({baseline:.2f} kg) for {category}/{scope}."
        )
        return True, reason

    return False, ""
