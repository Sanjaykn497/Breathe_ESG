# ESG Platform — Service Layer & Ingestion Pipeline Design

---

## 1. Folder Structure

```
emissions/
├── models.py                  # (already designed)
├── enums.py                   # (already designed)
├── admin.py
├── urls.py
├── serializers/
│   ├── __init__.py
│   ├── ingestion.py           # DataSource + RawRecord write serializers
│   ├── emission.py            # EmissionRecord read + review serializers
│   └── audit.py               # AuditLog read serializer
├── services/
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseIngestionService (shared pipeline)
│   │   ├── sap.py             # SAP-specific parser + normalizer
│   │   ├── utility.py         # Utility-specific parser + normalizer
│   │   └── travel.py          # Travel-specific parser + normalizer
│   ├── normalization.py       # Unit conversion + scope assignment
│   ├── emission_factors.py    # Emission factor registry
│   ├── confidence.py          # Confidence scoring logic
│   ├── anomaly.py             # Anomaly detection rules
│   ├── review.py              # Approval workflow: approve / reject / lock
│   └── audit.py               # AuditLog writer utility
├── views/
│   ├── __init__.py
│   ├── ingestion.py
│   ├── emission.py
│   └── audit.py
└── tests/
    ├── test_sap_parser.py
    ├── test_utility_parser.py
    ├── test_confidence.py
    └── test_review_workflow.py
```

**Design principle:** Views are thin. They validate HTTP input, call one service function, and return a response. All business logic lives in `services/`.

---

## 2. Emission Factor Registry

```python
# emissions/services/emission_factors.py
"""
Hardcoded emission factor registry.
In production, extract to a versioned DB table (EmissionFactor model).
Keys are (source_type, category, unit). Values are kg CO2e per unit.
"""

from decimal import Decimal

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

# Unit conversion table → target unit: kg CO2e-compatible
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
    """Returns (converted_value, normalized_unit). No-op if unit already normalized."""
    if raw_unit in UNIT_CONVERSION:
        target_unit, multiplier = UNIT_CONVERSION[raw_unit]
        return value * multiplier, target_unit
    return value, raw_unit
```

---

## 3. Normalization Service

```python
# emissions/services/normalization.py

from decimal import Decimal
from emissions.enums import EmissionScope, SourceType
from .emission_factors import get_factor, convert_unit


SCOPE_MAP: dict[str, EmissionScope] = {
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
    Returns a normalized dict ready to populate EmissionRecord fields.
    Raises ValueError if factor not found (triggers NEEDS_REVIEW or INVALID).
    """
    quantity_norm, unit_norm = convert_unit(quantity_raw, unit_raw)
    factor_entry = get_factor(source_type, category, unit_norm)

    if factor_entry is None:
        raise ValueError(
            f"No emission factor for ({source_type}, {category}, {unit_norm})"
        )

    co2e_kg = (quantity_norm * factor_entry["factor"]).quantize(Decimal("0.0001"))
    scope = SCOPE_MAP[source_type]

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
```

---

## 4. Confidence Scoring

```python
# emissions/services/confidence.py
"""
Confidence scoring: 0–100 integer.

Rules (each deducts from 100):
  -30  emission factor not found (fallback used or estimation)
  -20  unit required conversion (non-canonical input unit)
  -20  any required field missing (quantity, category, period)
  -15  period_start == period_end  (likely a default, not real billing period)
  -10  source_row_index is None (no traceability to original file row)

Score bands → review_status:
  80–100  AUTO_APPROVED
  50–79   NEEDS_REVIEW
  0–49    NEEDS_REVIEW + anomaly_flag = True (consider INVALID via downstream rule)
"""

from emissions.enums import ReviewStatus


def score_record(context: dict) -> tuple[int, ReviewStatus]:
    """
    context keys: factor_found, unit_converted, missing_fields,
                  degenerate_period, no_row_index
    Returns (confidence_score, review_status)
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

    if score >= 80:
        status = ReviewStatus.AUTO_APPROVED
    else:
        status = ReviewStatus.NEEDS_REVIEW

    return score, status
```

---

## 5. Anomaly Detection

```python
# emissions/services/anomaly.py
"""
Anomaly rules applied after normalization.
Anomaly does NOT change review_status — it sets anomaly_flag and anomaly_reason.
Analysts see both the status and the flag independently.
"""

from decimal import Decimal
from django.db.models import Avg
from emissions.models import EmissionRecord


ANOMALY_THRESHOLD_PERCENT = 200  # >200% of rolling avg triggers flag


def check_anomaly(
    organization_id,
    scope: str,
    category: str,
    reporting_year: int,
    co2e_kg: Decimal,
) -> tuple[bool, str]:
    """
    Compare new co2e_kg against the rolling average of the last 3 periods
    for the same (org, scope, category).
    Returns (anomaly_flag, anomaly_reason).
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

    baseline = avg_result["avg"]
    if baseline is None or baseline == 0:
        return False, ""  # No history to compare against

    pct_change = ((co2e_kg - baseline) / baseline) * 100

    if pct_change > ANOMALY_THRESHOLD_PERCENT:
        reason = (
            f"CO2e ({co2e_kg} kg) is {pct_change:.1f}% above the "
            f"3-period average ({baseline:.2f} kg) for {category}/{scope}."
        )
        return True, reason

    return False, ""
```

---

## 6. Audit Logger Utility

```python
# emissions/services/audit.py
"""
Single entry point for writing AuditLog records.
Call this from service functions — never from views or serializers.
"""

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
):
    AuditLog.objects.create(
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
    record,        # EmissionRecord instance
    old_data: dict,
    new_data: dict,
    changed_by,
):
    """
    Diff two dicts and write one AuditLog entry per changed field.
    Serialize values to JSON-safe types before storing.
    """
    for field, new_val in new_data.items():
        old_val = old_data.get(field)
        if old_val != new_val:
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
```

---

## 7. Base Ingestion Pipeline

```python
# emissions/services/ingestion/base.py

import hashlib, json
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from emissions.models import DataSource, RawRecord, EmissionRecord
from emissions.enums import IngestionStatus
from ..normalization import normalize_record
from ..confidence import score_record
from ..anomaly import check_anomaly
from ..audit import log_change


class BaseIngestionService:
    """
    Template method pattern.
    Subclasses override: parse_rows(), extract_fields(), get_period()
    Pipeline is fixed: create_datasource → store_raw → normalize → score → flag → persist
    """
    source_type: str  # set by subclass

    def __init__(self, organization, user, reporting_year: int):
        self.organization   = organization
        self.user           = user
        self.reporting_year = reporting_year

    # ── Entry point ──────────────────────────────────────────────
    @transaction.atomic
    def ingest(self, source_name: str, external_ref: str, raw_input) -> DataSource:
        data_source = self._create_data_source(source_name, external_ref)
        rows        = self.parse_rows(raw_input)

        success, errors = 0, []

        for idx, row in enumerate(rows):
            try:
                raw_record = self._store_raw(data_source, row, idx)
                self._process_row(data_source, raw_record, row)
                success += 1
            except Exception as exc:
                errors.append({"row": idx, "error": str(exc)})

        data_source.row_count      = success
        data_source.ingestion_status = (
            IngestionStatus.COMPLETED if not errors else IngestionStatus.FAILED
        )
        data_source.error_summary  = errors or None
        data_source.save(update_fields=["row_count", "ingestion_status", "error_summary"])

        log_change(
            organization_id=self.organization.id,
            object_type="DataSource",
            object_id=data_source.id,
            action="INGEST",
            changed_by=self.user,
            note=f"{success} rows ingested, {len(errors)} errors.",
        )
        return data_source

    # ── Step 1: DataSource ────────────────────────────────────────
    def _create_data_source(self, name: str, external_ref: str) -> DataSource:
        return DataSource.objects.create(
            organization=self.organization,
            source_type=self.source_type,
            name=name,
            external_ref=external_ref,
            reporting_year=self.reporting_year,
            ingested_by=self.user,
            ingestion_status=IngestionStatus.PROCESSING,
        )

    # ── Step 2: Store raw (immutable) ────────────────────────────
    def _store_raw(self, data_source: DataSource, row: dict, idx: int) -> RawRecord:
        payload_bytes = json.dumps(row, sort_keys=True, default=str).encode()
        checksum      = hashlib.sha256(payload_bytes).hexdigest()

        raw, created = RawRecord.objects.get_or_create(
            data_source=data_source,
            checksum=checksum,
            defaults={
                "organization":     self.organization,
                "raw_payload":      row,
                "source_row_index": idx,
                "received_at":      timezone.now(),
            },
        )
        if not created:
            raise ValueError(f"Duplicate row detected at index {idx} (checksum: {checksum})")
        return raw

    # ── Steps 3–8: Normalize + score + anomaly + persist ─────────
    def _process_row(self, data_source: DataSource, raw_record: RawRecord, row: dict):
        fields       = self.extract_fields(row)       # subclass extracts typed data
        period_start, period_end = self.get_period(row)  # subclass extracts period

        # Normalization (raises ValueError if factor missing)
        norm_context   = {"factor_found": True, "unit_converted": False,
                          "missing_fields": False, "degenerate_period": False,
                          "no_row_index": raw_record.source_row_index is None}
        try:
            norm = normalize_record(
                source_type=self.source_type,
                category=fields["category"],
                quantity_raw=fields["quantity"],
                unit_raw=fields["unit"],
            )
            if fields["unit"] != norm["unit_normalized"]:
                norm_context["unit_converted"] = True
        except ValueError:
            norm_context["factor_found"] = False
            norm = self._fallback_norm(fields)

        if period_start == period_end:
            norm_context["degenerate_period"] = True

        confidence, review_status = score_record(norm_context)

        anomaly_flag, anomaly_reason = check_anomaly(
            organization_id=self.organization.id,
            scope=norm["scope"],
            category=fields["category"],
            reporting_year=self.reporting_year,
            co2e_kg=norm["co2e_kg"],
        )

        EmissionRecord.objects.create(
            organization=self.organization,
            raw_record=raw_record,
            data_source=data_source,
            reporting_year=self.reporting_year,
            period_start=period_start,
            period_end=period_end,
            source_type=self.source_type,
            confidence_score=confidence,
            review_status=review_status,
            anomaly_flag=anomaly_flag,
            anomaly_reason=anomaly_reason,
            **norm,
        )

    def _fallback_norm(self, fields: dict) -> dict:
        """Used when no factor is found. Stores zero emission, flags for review."""
        from decimal import Decimal
        from emissions.enums import EmissionScope
        return {
            "scope": EmissionScope.SCOPE_1,
            "category": fields.get("category", "UNKNOWN"),
            "quantity_raw": fields.get("quantity", Decimal("0")),
            "unit_raw": fields.get("unit", "unknown"),
            "quantity_normalized": fields.get("quantity", Decimal("0")),
            "unit_normalized": "kg_CO2e",
            "emission_factor": Decimal("0"),
            "emission_factor_source": "NOT_FOUND",
            "co2e_kg": Decimal("0"),
        }

    # ── Subclass interface ────────────────────────────────────────
    def parse_rows(self, raw_input) -> list[dict]:
        raise NotImplementedError

    def extract_fields(self, row: dict) -> dict:
        """Return dict with keys: category, quantity (Decimal), unit (str)"""
        raise NotImplementedError

    def get_period(self, row: dict) -> tuple:
        """Return (period_start: date, period_end: date)"""
        raise NotImplementedError
```

---

## 8. Source-Specific Parsers

### SAP Parser

```python
# emissions/services/ingestion/sap.py

import csv, io
from decimal import Decimal
from datetime import date
from .base import BaseIngestionService
from ..emission_factors import convert_unit

PLANT_CODE_MAP = {
    "PLT001": "DIESEL",
    "PLT002": "NATURAL_GAS",
    "PLT003": "PETROL",
}


class SAPIngestionService(BaseIngestionService):
    source_type = "SAP"

    def parse_rows(self, raw_input) -> list[dict]:
        reader = csv.DictReader(io.StringIO(raw_input))
        return [row for row in reader]

    def extract_fields(self, row: dict) -> dict:
        plant_code = row.get("plant_code", "").strip()
        category   = PLANT_CODE_MAP.get(plant_code, "UNKNOWN")
        quantity   = Decimal(row.get("quantity", "0").replace(",", ""))
        unit       = row.get("unit", "L").strip()
        return {"category": category, "quantity": quantity, "unit": unit}

    def get_period(self, row: dict) -> tuple:
        # SAP records are point-in-time; use document date for both
        doc_date = date.fromisoformat(row.get("document_date"))
        return doc_date, doc_date
```

### Utility Parser

```python
# emissions/services/ingestion/utility.py

import csv, io
from decimal import Decimal
from datetime import date
from .base import BaseIngestionService


class UtilityIngestionService(BaseIngestionService):
    source_type = "UTILITY"

    def parse_rows(self, raw_input) -> list[dict]:
        reader = csv.DictReader(io.StringIO(raw_input))
        return [row for row in reader]

    def extract_fields(self, row: dict) -> dict:
        return {
            "category": "ELECTRICITY",
            "quantity": Decimal(row["kwh_usage"].replace(",", "")),
            "unit":     "kWh",
        }

    def get_period(self, row: dict) -> tuple:
        return (
            date.fromisoformat(row["period_start"]),
            date.fromisoformat(row["period_end"]),
        )
```

### Travel Parser

```python
# emissions/services/ingestion/travel.py

from decimal import Decimal
from datetime import date
from .base import BaseIngestionService

HAUL_DISTANCE_THRESHOLD_KM = 3700  # DEFRA short-haul cutoff


class TravelIngestionService(BaseIngestionService):
    source_type = "TRAVEL"

    def parse_rows(self, raw_input) -> list[dict]:
        # raw_input is a list of dicts from the mock API response
        return raw_input if isinstance(raw_input, list) else raw_input.get("records", [])

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

    def get_period(self, row: dict) -> tuple:
        travel_date = date.fromisoformat(row["travel_date"])
        return travel_date, travel_date
```

---

## 9. Review Workflow Service

```python
# emissions/services/review.py
"""
State machine enforced in Python (not DB triggers).
Valid transitions:
  NEEDS_REVIEW / AUTO_APPROVED → APPROVED  (analyst)
  NEEDS_REVIEW / AUTO_APPROVED → REJECTED  (analyst)
  APPROVED                     → LOCKED    (admin only)
  LOCKED                       → (nothing) terminal
"""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError

from emissions.models import EmissionRecord
from emissions.enums import ReviewStatus, UserRole
from .audit import log_change, log_field_changes

ALLOWED_TRANSITIONS = {
    ReviewStatus.NEEDS_REVIEW:  {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.AUTO_APPROVED: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.APPROVED:      {ReviewStatus.LOCKED},
    ReviewStatus.REJECTED:      {ReviewStatus.NEEDS_REVIEW},  # re-open allowed
    ReviewStatus.LOCKED:        set(),  # terminal
}


def _guard_not_locked(record: EmissionRecord):
    if record.review_status == ReviewStatus.LOCKED:
        raise PermissionDenied(
            f"Record {record.id} is locked and cannot be modified."
        )


def _guard_transition(current: str, target: str):
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValidationError(
            f"Transition {current} → {target} is not permitted."
        )


@transaction.atomic
def approve_record(record: EmissionRecord, analyst, notes: str = ""):
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


@transaction.atomic
def reject_record(record: EmissionRecord, analyst, notes: str = ""):
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


@transaction.atomic
def lock_record(record: EmissionRecord, admin_user):
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


@transaction.atomic
def edit_emission_record(record: EmissionRecord, analyst, new_data: dict):
    """
    Allows analysts to manually correct fields (e.g., wrong category, wrong quantity).
    Records field-level AuditLog entries for every changed field.
    """
    _guard_not_locked(record)

    EDITABLE_FIELDS = {
        "category", "quantity_raw", "unit_raw",
        "quantity_normalized", "unit_normalized",
        "emission_factor", "co2e_kg",
        "scope", "review_notes", "anomaly_reason",
    }
    invalid = set(new_data) - EDITABLE_FIELDS
    if invalid:
        raise ValidationError(f"Fields not editable: {invalid}")

    old_data = {f: str(getattr(record, f)) for f in new_data}

    for field, value in new_data.items():
        setattr(record, field, value)

    # Any manual edit resets to NEEDS_REVIEW unless already APPROVED
    if record.review_status == ReviewStatus.AUTO_APPROVED:
        record.review_status = ReviewStatus.NEEDS_REVIEW
        new_data["review_status"] = ReviewStatus.NEEDS_REVIEW
        old_data["review_status"] = ReviewStatus.AUTO_APPROVED

    record.save()

    log_field_changes(
        organization_id=record.organization_id,
        record=record,
        old_data=old_data,
        new_data={f: str(v) for f, v in new_data.items()},
        changed_by=analyst,
    )
```

---

## 10. Serializer Strategy

```python
# emissions/serializers/emission.py

from rest_framework import serializers
from emissions.models import EmissionRecord, AuditLog
from emissions.enums import ReviewStatus


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Lightweight — for the review queue list view."""
    class Meta:
        model  = EmissionRecord
        fields = [
            "id", "source_type", "scope", "category",
            "co2e_kg", "confidence_score", "review_status",
            "anomaly_flag", "period_start", "period_end",
        ]


class EmissionRecordDetailSerializer(serializers.ModelSerializer):
    """Full detail — for the analyst review panel."""
    raw_payload = serializers.SerializerMethodField()

    class Meta:
        model  = EmissionRecord
        fields = "__all__"
        read_only_fields = [
            "id", "organization", "raw_record", "data_source",
            "review_status", "locked_at", "locked_by",
            "created_at", "updated_at",
        ]

    def get_raw_payload(self, obj):
        return obj.raw_record.raw_payload


class EmissionRecordEditSerializer(serializers.Serializer):
    """Write-only — for analyst edits. Only allows safe fields."""
    category            = serializers.CharField(required=False)
    quantity_raw        = serializers.DecimalField(max_digits=20, decimal_places=6, required=False)
    unit_raw            = serializers.CharField(required=False)
    emission_factor     = serializers.DecimalField(max_digits=20, decimal_places=8, required=False)
    co2e_kg             = serializers.DecimalField(max_digits=20, decimal_places=4, required=False)
    scope               = serializers.ChoiceField(
        choices=["SCOPE_1", "SCOPE_2", "SCOPE_3"], required=False
    )
    review_notes        = serializers.CharField(required=False, allow_blank=True)


class ReviewActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


# emissions/serializers/audit.py

class AuditLogSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source="changed_by.email", read_only=True)

    class Meta:
        model  = AuditLog
        fields = [
            "id", "object_type", "object_id", "action",
            "changed_by_email", "changed_at",
            "field_name", "before_value", "after_value", "note",
        ]
```

---

## 11. View Layer (Thin)

```python
# emissions/views/emission.py

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from emissions.models import EmissionRecord
from emissions.serializers.emission import (
    EmissionRecordListSerializer, EmissionRecordDetailSerializer,
    EmissionRecordEditSerializer, ReviewActionSerializer,
)
from emissions.services.review import approve_record, reject_record, lock_record, edit_emission_record


class EmissionRecordReviewView(APIView):
    """PATCH — analyst edit. POST to /approve, /reject, /lock."""

    def get_object(self, org, pk):
        return EmissionRecord.objects.select_related("raw_record").get(
            pk=pk, organization=org
        )

    def get(self, request, pk):
        record = self.get_object(request.user.organization, pk)
        return Response(EmissionRecordDetailSerializer(record).data)

    def patch(self, request, pk):
        record = self.get_object(request.user.organization, pk)
        ser    = EmissionRecordEditSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        edit_emission_record(record, request.user, ser.validated_data)
        return Response({"detail": "Updated."})


class ApproveRecordView(APIView):
    def post(self, request, pk):
        record = EmissionRecord.objects.get(pk=pk, organization=request.user.organization)
        ser    = ReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approve_record(record, request.user, notes=ser.validated_data.get("notes", ""))
        return Response({"detail": "Approved."}, status=status.HTTP_200_OK)


class RejectRecordView(APIView):
    def post(self, request, pk):
        record = EmissionRecord.objects.get(pk=pk, organization=request.user.organization)
        ser    = ReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reject_record(record, request.user, notes=ser.validated_data.get("notes", ""))
        return Response({"detail": "Rejected."})


class LockRecordView(APIView):
    def post(self, request, pk):
        record = EmissionRecord.objects.get(pk=pk, organization=request.user.organization)
        lock_record(record, request.user)
        return Response({"detail": "Locked."})
```

---

## 12. How Immutability is Enforced

RawRecord has no update or delete path in the service layer. Enforce at three levels:

**Level 1 — Model override (soft block)**
```python
# In RawRecord model
def save(self, *args, **kwargs):
    if self.pk is not None:
        raise PermissionDenied("RawRecord is immutable. Create a new record instead.")
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise PermissionDenied("RawRecord cannot be deleted.")
```

**Level 2 — No update endpoint.** The API has no PATCH/PUT/DELETE route for RawRecord. There is only GET (read-only serializer surfaced via `EmissionRecordDetailSerializer.raw_payload`).

**Level 3 — DB-level (optional, belt-and-suspenders)**
```sql
-- PostgreSQL rule prevents any UPDATE on the raw record table
CREATE RULE no_update_raw_record AS
ON UPDATE TO esg_raw_record DO INSTEAD NOTHING;
```

---

## 13. How Audit Lock is Enforced

At every service function that modifies `EmissionRecord`, the first line is:

```python
_guard_not_locked(record)  # raises PermissionDenied if LOCKED
```

This means:
- `edit_emission_record` → guarded
- `approve_record` → guarded
- `reject_record` → guarded

The `lock_record` function itself uses `_guard_not_locked` to prevent double-locking, and `_guard_transition` to prevent invalid APPROVED → LOCKED skip-overs.

The model's `save()` can additionally enforce this:
```python
# In EmissionRecord model
def save(self, *args, **kwargs):
    if self.pk:
        current = EmissionRecord.objects.filter(pk=self.pk).values_list("review_status", flat=True).first()
        if current == ReviewStatus.LOCKED:
            raise PermissionDenied("Cannot modify a LOCKED EmissionRecord.")
    super().save(*args, **kwargs)
```

---

## 14. Error Handling Strategy

| Layer | Tool | Rule |
|---|---|---|
| Parser (row-level) | `try/except` per row | Log error, skip row, continue batch |
| Normalization | `ValueError` on missing factor | Fallback norm used, confidence penalized |
| Transition guard | `ValidationError` | 400 response via DRF exception handler |
| Lock guard | `PermissionDenied` | 403 response |
| DB | `IntegrityError` (duplicate checksum) | 409 response or skip in ingestion |

DRF's default exception handler converts `ValidationError` → 400 and `PermissionDenied` → 403 automatically. No custom middleware needed.

---

## 15. Tradeoffs & What's Left Out

| Simplified | What to add in production |
|---|---|
| Synchronous ingestion in request cycle | Move to background worker (Celery/RQ) triggered by file upload |
| Hardcoded emission factors | `EmissionFactor` versioned DB table with year + region |
| Single anomaly rule (YoY %) | Rule engine: configurable thresholds per org per category |
| No PDF parsing for utility bills | Add `pdfplumber` or vendor API in `UtilityIngestionService.parse_rows` |
| Plant code → category is a static dict | Move to DB-backed `PlantCodeMapping` table, org-scoped |
| No pagination on review queue | Add `django-filters` + DRF `PageNumberPagination` |
| State machine in pure Python | Add `django-fsm` for declarative transitions and signal hooks |
