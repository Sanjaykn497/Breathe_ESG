from emissions.enums import ReviewStatus


def score_record(context: dict) -> tuple[int, str]:
    """
    Computes confidence score (0–100) and resulting review_status.

    context keys (all bool):
      factor_found       - emission factor was found
      unit_converted     - raw unit needed conversion
      missing_fields     - any required field was absent
      degenerate_period  - period_start == period_end (point-in-time, suspicious for utility)
      no_row_index       - source_row_index is None
    """
    score = 100

    if not context.get("factor_found"):
        score -= 30
    if context.get("unit_converted"):
        score -= 20
    if context.get("missing_fields"):
        score -= 20
    if context.get("degenerate_period"):
        score -= 15
    if context.get("no_row_index"):
        score -= 10

    score = max(0, score)

    status = ReviewStatus.AUTO_APPROVED if score >= 80 else ReviewStatus.NEEDS_REVIEW
    return score, status
