from emissions.models import AuditLog


def log_change(
    organization_id,
    object_type: str,
    object_id,
    action: str,
    changed_by,
    field_name: str = "",
    before_value=None,
    after_value=None,
    note: str = "",
) -> AuditLog:
    return AuditLog.objects.create(
        organization_id=organization_id,
        object_type=object_type,
        object_id=object_id,
        action=action,
        changed_by=changed_by,
        field_name=field_name,
        before_value=before_value,
        after_value=after_value,
        note=note,
    )


def log_field_changes(
    organization_id,
    record,
    old_data: dict,
    new_data: dict,
    changed_by,
):
    """Diffs old vs new and writes one AuditLog per changed field."""
    for field, new_val in new_data.items():
        old_val = old_data.get(field)
        if str(old_val) != str(new_val):
            log_change(
                organization_id=organization_id,
                object_type="EmissionRecord",
                object_id=record.id,
                action="FIELD_EDIT",
                changed_by=changed_by,
                field_name=field,
                before_value=str(old_val),
                after_value=str(new_val),
            )
