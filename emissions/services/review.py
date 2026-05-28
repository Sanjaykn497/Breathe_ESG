from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError

from emissions.models import EmissionRecord
from emissions.enums import ReviewStatus, UserRole
from .audit import log_change, log_field_changes


# Valid state machine transitions
ALLOWED_TRANSITIONS: dict[str, set] = {
    ReviewStatus.NEEDS_REVIEW:  {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.AUTO_APPROVED: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.APPROVED:      {ReviewStatus.LOCKED},
    ReviewStatus.REJECTED:      {ReviewStatus.NEEDS_REVIEW},  # allow re-open
    ReviewStatus.LOCKED:        set(),                         # terminal
}


def _guard_not_locked(record: EmissionRecord):
    if record.review_status == ReviewStatus.LOCKED:
        raise PermissionDenied(f"Record {record.id} is locked and cannot be modified.")


def _guard_transition(current: str, target: str):
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValidationError(
            f"Transition '{current}' → '{target}' is not permitted. "
            f"Allowed: {allowed or 'none (terminal state)'}."
        )


@transaction.atomic
def approve_record(record: EmissionRecord, analyst, notes: str = "") -> EmissionRecord:
    _guard_not_locked(record)
    _guard_transition(record.review_status, ReviewStatus.APPROVED)

    old_status = record.review_status
    record.review_status = ReviewStatus.APPROVED
    record.reviewed_by   = analyst
    record.reviewed_at   = timezone.now()
    record.review_notes  = notes
    record.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_notes"])

    log_change(
        organization_id=record.organization_id,
        object_type="EmissionRecord",
        object_id=record.id,
        action="STATUS_CHANGE",
        changed_by=analyst,
        field_name="review_status",
        before_value=old_status,
        after_value=ReviewStatus.APPROVED,
        note=notes,
    )
    return record


@transaction.atomic
def reject_record(record: EmissionRecord, analyst, notes: str = "") -> EmissionRecord:
    _guard_not_locked(record)
    _guard_transition(record.review_status, ReviewStatus.REJECTED)

    old_status = record.review_status
    record.review_status = ReviewStatus.REJECTED
    record.reviewed_by   = analyst
    record.reviewed_at   = timezone.now()
    record.review_notes  = notes
    record.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_notes"])

    log_change(
        organization_id=record.organization_id,
        object_type="EmissionRecord",
        object_id=record.id,
        action="STATUS_CHANGE",
        changed_by=analyst,
        field_name="review_status",
        before_value=old_status,
        after_value=ReviewStatus.REJECTED,
        note=notes,
    )
    return record


@transaction.atomic
def lock_record(record: EmissionRecord, admin_user) -> EmissionRecord:
    if admin_user.role != UserRole.ADMIN:
        raise PermissionDenied("Only ADMIN users can lock records.")
    _guard_not_locked(record)
    _guard_transition(record.review_status, ReviewStatus.LOCKED)

    old_status = record.review_status
    record.review_status = ReviewStatus.LOCKED
    record.locked_at     = timezone.now()
    record.locked_by     = admin_user
    record.save(update_fields=["review_status", "locked_at", "locked_by"])

    log_change(
        organization_id=record.organization_id,
        object_type="EmissionRecord",
        object_id=record.id,
        action="LOCK",
        changed_by=admin_user,
        field_name="review_status",
        before_value=old_status,
        after_value=ReviewStatus.LOCKED,
    )
    return record


EDITABLE_FIELDS = frozenset({
    "category", "quantity_raw", "unit_raw",
    "quantity_normalized", "unit_normalized",
    "emission_factor", "co2e_kg",
    "scope", "review_notes", "anomaly_reason",
})


@transaction.atomic
def edit_emission_record(record: EmissionRecord, analyst, new_data: dict) -> EmissionRecord:
    """
    Allows analysts to manually correct fields.
    Writes per-field AuditLog entries.
    Resets AUTO_APPROVED → NEEDS_REVIEW on any manual edit.
    """
    _guard_not_locked(record)

    invalid_fields = set(new_data.keys()) - EDITABLE_FIELDS
    if invalid_fields:
        raise ValidationError(f"Fields not editable: {sorted(invalid_fields)}")

    old_data = {f: str(getattr(record, f)) for f in new_data}

    for field, value in new_data.items():
        setattr(record, field, value)

    # A manual edit invalidates an auto-approval
    if record.review_status == ReviewStatus.AUTO_APPROVED:
        old_data["review_status"] = record.review_status
        record.review_status = ReviewStatus.NEEDS_REVIEW
        new_data["review_status"] = ReviewStatus.NEEDS_REVIEW

    record.save()

    log_field_changes(
        organization_id=record.organization_id,
        record=record,
        old_data=old_data,
        new_data={f: str(v) for f, v in new_data.items()},
        changed_by=analyst,
    )
    return record
