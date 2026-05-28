# ESG Platform — Django Data Model Design

## 1. Enum Definitions

Enums are defined as `models.TextChoices` to stay Pythonic, be readable in the DB, and avoid integer drift bugs.

```python
# emissions/enums.py

from django.db import models


class UserRole(models.TextChoices):
    ADMIN   = "ADMIN",   "Admin"
    ANALYST = "ANALYST", "Analyst"


class SourceType(models.TextChoices):
    SAP     = "SAP",     "SAP (Fuel & Procurement)"
    UTILITY = "UTILITY", "Utility (Electricity Bills)"
    TRAVEL  = "TRAVEL",  "Corporate Travel"


class EmissionScope(models.TextChoices):
    SCOPE_1 = "SCOPE_1", "Scope 1 — Direct"
    SCOPE_2 = "SCOPE_2", "Scope 2 — Indirect (Energy)"
    SCOPE_3 = "SCOPE_3", "Scope 3 — Value Chain"


class ReviewStatus(models.TextChoices):
    AUTO_APPROVED = "AUTO_APPROVED", "Auto-Approved"
    NEEDS_REVIEW  = "NEEDS_REVIEW",  "Needs Review"
    APPROVED      = "APPROVED",      "Approved"
    REJECTED      = "REJECTED",      "Rejected"
    LOCKED        = "LOCKED",        "Locked (Audited)"


class IngestionStatus(models.TextChoices):
    PENDING    = "PENDING",    "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED  = "COMPLETED",  "Completed"
    FAILED     = "FAILED",     "Failed"


class NormalizedUnit(models.TextChoices):
    KG_CO2E  = "kg_CO2e",  "Kilograms CO₂-equivalent"
    TONNE_CO2E = "tCO2e",  "Metric Tonnes CO₂-equivalent"
    KWH      = "kWh",      "Kilowatt-hours"
    MJ       = "MJ",       "Megajoules"
    LITRE    = "L",        "Litres"
    KM       = "km",       "Kilometres"
```

---

## 2. Model Definitions

```python
# emissions/models.py

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.postgres.indexes import BTreeIndex, GinIndex
from django.utils import timezone

from .enums import (
    UserRole, SourceType, EmissionScope,
    ReviewStatus, IngestionStatus, NormalizedUnit,
)


# ─────────────────────────────────────────────
# 1. Organization  (multi-tenant root)
# ─────────────────────────────────────────────
class Organization(models.Model):
    """
    Top-level tenant boundary. Every row in the system is scoped to one.
    Slug is used as a URL-safe identifier for routing without exposing PKs.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=255)
    slug       = models.SlugField(max_length=100, unique=True)
    country    = models.CharField(max_length=100, blank=True)
    industry   = models.CharField(max_length=100, blank=True)
    # Reporting year the tenant is currently working on
    active_reporting_year = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        db_table = "org_organization"

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# 2. User  (role-based, org-scoped)
# ─────────────────────────────────────────────
class User(AbstractBaseUser, PermissionsMixin):
    """
    Simplified user model. Auth boilerplate is intentionally omitted.
    Key design choice: a user belongs to exactly one organization.
    Cross-org access (e.g. auditors) is out of scope here.
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="users"
    )
    email        = models.EmailField(unique=True)
    role         = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.ANALYST)
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)  # Django admin access
    created_at   = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "org_user"
        indexes  = [BTreeIndex(fields=["organization", "role"])]

    def __str__(self):
        return self.email


# ─────────────────────────────────────────────
# 3. DataSource  (single ingestion event)
# ─────────────────────────────────────────────
class DataSource(models.Model):
    """
    Represents one ingestion event from one external system.
    Acts as the provenance anchor — every RawRecord links back here.

    source_type drives validation rules and normalization pipelines
    applied downstream. It is stored here (not on RawRecord) because
    the source type is an attribute of the feed, not of individual rows.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization    = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="data_sources"
    )
    source_type     = models.CharField(max_length=20, choices=SourceType.choices)
    name            = models.CharField(max_length=255, help_text="Human label, e.g. 'SAP Plant 42 Oct 2024'")
    external_ref    = models.CharField(
        max_length=255, blank=True,
        help_text="Original filename, API batch ID, or S3 key — for re-ingestion traceability"
    )
    ingestion_status = models.CharField(
        max_length=20, choices=IngestionStatus.choices, default=IngestionStatus.PENDING
    )
    reporting_year  = models.PositiveSmallIntegerField()
    ingested_by     = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="ingested_sources"
    )
    ingested_at     = models.DateTimeField(auto_now_add=True)
    row_count       = models.PositiveIntegerField(default=0)
    error_summary   = models.JSONField(null=True, blank=True)  # pipeline errors, not row-level

    class Meta:
        db_table = "esg_data_source"
        indexes  = [
            BTreeIndex(fields=["organization", "source_type", "reporting_year"]),
            BTreeIndex(fields=["ingestion_status"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.source_type}]"


# ─────────────────────────────────────────────
# 4. RawRecord  (immutable, source-of-truth store)
# ─────────────────────────────────────────────
class RawRecord(models.Model):
    """
    Stores data EXACTLY as received from the source system — no transformation.
    This is the legal and compliance anchor.

    Design rules enforced here:
    - No update/delete after creation (enforced at the service layer, see note below).
    - raw_payload is untyped JSONB to accommodate heterogeneous schemas
      (SAP XML-parsed dicts look nothing like utility CSV rows).
    - source_row_index lets us map back to the original file line for debugging.
    - checksum allows detection of accidental re-ingestion of duplicates.
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="raw_records"
    )
    data_source      = models.ForeignKey(
        DataSource, on_delete=models.PROTECT, related_name="raw_records"
    )
    raw_payload      = models.JSONField()          # unmodified source data
    source_row_index = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Row/line number in the original file for debugging"
    )
    checksum         = models.CharField(
        max_length=64,
        help_text="SHA-256 of raw_payload for duplicate detection"
    )
    received_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "esg_raw_record"
        # Prevent exact duplicate payloads from the same source
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "checksum"],
                name="uq_raw_record_source_checksum"
            )
        ]
        indexes = [
            BTreeIndex(fields=["organization", "data_source"]),
            BTreeIndex(fields=["checksum"]),
            # GIN index on raw_payload for ad-hoc JSONB querying during ingestion debugging
            GinIndex(fields=["raw_payload"], name="gin_raw_payload"),
        ]


# ─────────────────────────────────────────────
# 5. EmissionRecord  (normalized, reviewable)
# ─────────────────────────────────────────────
class EmissionRecord(models.Model):
    """
    The business-facing record produced by the normalization pipeline.
    This is what analysts review, approve, and audit.

    Key design decisions:
    - One-to-one with RawRecord (one raw row → one emission record).
      If a single invoice line spawns multiple emission types (e.g. Scope 1 + Scope 3),
      create multiple EmissionRecords pointing to the same RawRecord.
    - period_start / period_end support Utility billing cycles and
      travel booking windows. For point-in-time SAP records, set
      period_end = period_start.
    - quantity_raw + unit_raw preserve what the pipeline read before conversion.
    - quantity_normalized + unit_normalized are what go into reports.
    - emission_factor + emission_factor_source give auditors the calculation chain.
    - co2e_kg is always in kg for consistent aggregation across scopes.
    - review_status drives the approval workflow state machine.
    - locked_at / locked_by enforce the audit lock after APPROVED → LOCKED.
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="emission_records"
    )
    raw_record       = models.ForeignKey(
        RawRecord, on_delete=models.PROTECT, related_name="emission_records"
    )
    data_source      = models.ForeignKey(
        DataSource, on_delete=models.PROTECT, related_name="emission_records"
    )
    reporting_year   = models.PositiveSmallIntegerField()

    # ── Temporal coverage ────────────────────
    period_start     = models.DateField()
    period_end       = models.DateField()

    # ── Source classification ─────────────────
    source_type      = models.CharField(max_length=20, choices=SourceType.choices)
    scope            = models.CharField(max_length=10, choices=EmissionScope.choices)
    category         = models.CharField(
        max_length=100, blank=True,
        help_text="GHG Protocol category, e.g. 'Stationary Combustion', 'Business Travel — Air'"
    )

    # ── Raw quantity (pre-normalization) ──────
    quantity_raw     = models.DecimalField(max_digits=20, decimal_places=6)
    unit_raw         = models.CharField(max_length=50, help_text="As received, e.g. 'gallons', 'kBTU'")

    # ── Normalized quantity ───────────────────
    quantity_normalized = models.DecimalField(max_digits=20, decimal_places=6)
    unit_normalized     = models.CharField(max_length=20, choices=NormalizedUnit.choices)

    # ── Emission calculation ──────────────────
    emission_factor        = models.DecimalField(
        max_digits=20, decimal_places=8,
        help_text="Factor applied: e.g. kg CO2e / kWh"
    )
    emission_factor_source = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. 'DEFRA 2024', 'EPA eGRID 2023', 'IPCC AR6'"
    )
    co2e_kg                = models.DecimalField(
        max_digits=20, decimal_places=4,
        help_text="Final GHG impact always stored in kg CO2e for consistent aggregation"
    )

    # ── Quality signals ───────────────────────
    confidence_score = models.SmallIntegerField(
        default=100,
        help_text="0–100. Set by ingestion pipeline based on data completeness & source reliability."
    )
    anomaly_flag     = models.BooleanField(default=False)
    anomaly_reason   = models.TextField(blank=True)

    # ── Review workflow ───────────────────────
    review_status    = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.NEEDS_REVIEW
    )
    reviewed_by      = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_records"
    )
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    review_notes     = models.TextField(blank=True)

    # ── Audit lock ────────────────────────────
    locked_at        = models.DateTimeField(null=True, blank=True)
    locked_by        = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="locked_records"
    )

    # ── Metadata ──────────────────────────────
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "esg_emission_record"
        constraints = [
            # Prevent two normalized records for the same raw row in the same scope
            models.UniqueConstraint(
                fields=["raw_record", "scope"],
                name="uq_emission_record_raw_scope"
            ),
            models.CheckConstraint(
                check=models.Q(period_end__gte=models.F("period_start")),
                name="chk_period_end_gte_start"
            ),
            models.CheckConstraint(
                check=models.Q(confidence_score__gte=0, confidence_score__lte=100),
                name="chk_confidence_score_range"
            ),
            models.CheckConstraint(
                check=models.Q(co2e_kg__gte=0),
                name="chk_co2e_non_negative"
            ),
        ]
        indexes = [
            BTreeIndex(fields=["organization", "reporting_year", "scope"]),
            BTreeIndex(fields=["organization", "review_status"]),
            BTreeIndex(fields=["organization", "source_type", "reporting_year"]),
            BTreeIndex(fields=["anomaly_flag"]),
            BTreeIndex(fields=["period_start", "period_end"]),
        ]

    def __str__(self):
        return f"{self.organization_id} | {self.scope} | {self.co2e_kg} kg CO2e"


# ─────────────────────────────────────────────
# 6. AuditLog  (field-level change history)
# ─────────────────────────────────────────────
class AuditLog(models.Model):
    """
    Append-only record of every meaningful change to an EmissionRecord.
    Uses JSONB for before/after to avoid coupling the log schema to the
    EmissionRecord schema — a schema migration on EmissionRecord does not
    require a matching migration here.

    The (object_type, object_id) pair is generic enough to log changes
    to other models (DataSource status changes, etc.) without a new table.
    Kept simple intentionally: no event sourcing, no replay capability.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="audit_logs"
    )
    # Generic reference — avoids tight FK coupling while still being queryable
    object_type  = models.CharField(max_length=100, help_text="e.g. 'EmissionRecord', 'DataSource'")
    object_id    = models.UUIDField(help_text="PK of the changed object")

    action       = models.CharField(
        max_length=50,
        help_text="e.g. 'STATUS_CHANGE', 'FIELD_EDIT', 'LOCK', 'REJECT', 'INGEST'"
    )
    changed_by   = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    changed_at   = models.DateTimeField(default=timezone.now, db_index=True)

    # Field-level delta
    field_name   = models.CharField(max_length=100, blank=True,
                                    help_text="Which field changed. Empty for multi-field actions.")
    before_value = models.JSONField(null=True, blank=True)
    after_value  = models.JSONField(null=True, blank=True)

    # Free-text context (analyst notes, pipeline messages)
    note         = models.TextField(blank=True)

    class Meta:
        db_table = "esg_audit_log"
        indexes  = [
            BTreeIndex(fields=["object_type", "object_id"]),
            BTreeIndex(fields=["organization", "changed_at"]),
            BTreeIndex(fields=["changed_by"]),
        ]
```

---

## 3. Relationships Explained

```
Organization ─┬─< User
              ├─< DataSource ─< RawRecord ─< EmissionRecord
              ├─< RawRecord                      │
              ├─< EmissionRecord                 │ (also FK'd directly)
              └─< AuditLog                       │
                                                 └── reviewed_by / locked_by → User
```

| Relationship | Cardinality | Note |
|---|---|---|
| Organization → User | 1:N | Users are org-scoped |
| Organization → DataSource | 1:N | Each ingestion event belongs to one org |
| DataSource → RawRecord | 1:N | One feed produces many raw rows |
| RawRecord → EmissionRecord | 1:N* | Usually 1:1, but a raw row can yield multiple scoped records |
| EmissionRecord → User (reviewed_by) | N:1 optional | Set on review action |
| EmissionRecord → User (locked_by) | N:1 optional | Set on audit lock |
| AuditLog → EmissionRecord | generic (object_id) | Loosely coupled, queryable |

> \* `UniqueConstraint(raw_record, scope)` prevents accidental duplication — one normalized record per scope per raw row.

---

## 4. Index Recommendations

| Index | Type | Rationale |
|---|---|---|
| `(org, reporting_year, scope)` on EmissionRecord | B-tree | Primary aggregation axis for dashboards |
| `(org, review_status)` on EmissionRecord | B-tree | Analyst review queue filter |
| `(org, source_type, reporting_year)` on EmissionRecord | B-tree | Source breakdown reports |
| `(anomaly_flag)` on EmissionRecord | B-tree | Fast anomaly queue retrieval |
| `(period_start, period_end)` on EmissionRecord | B-tree | Utility billing period range queries |
| `(data_source, checksum)` on RawRecord | Unique B-tree | Duplicate ingestion prevention |
| `(raw_payload)` on RawRecord | GIN | Ad-hoc JSONB key/value queries during debugging |
| `(object_type, object_id)` on AuditLog | B-tree | Fetch change history for any record |
| `(org, changed_at)` on AuditLog | B-tree | Chronological org-level audit trail |

**PostgreSQL-specific feature notes:**
- Use `GinIndex` from `django.contrib.postgres.indexes` for the JSONB field.
- Consider a **partial index** on `EmissionRecord` for the review queue:
  ```sql
  CREATE INDEX idx_needs_review
  ON esg_emission_record (organization_id, created_at)
  WHERE review_status = 'NEEDS_REVIEW';
  ```
- For large orgs, consider **table partitioning** on `EmissionRecord` by `reporting_year`.

---

## 5. Why RawRecord is Separated from EmissionRecord

This is the most important architectural decision in this schema.

**The core problem:** Source data is noisy, heterogeneous, and legally significant.

| Concern | RawRecord | EmissionRecord |
|---|---|---|
| Schema | JSONB (freeform) | Typed, strict columns |
| Mutability | **Never updated** | Updatable during review |
| Purpose | Legal & compliance anchor | Business logic & reporting |
| Owned by | Ingestion pipeline | Normalization pipeline + analysts |
| Audit exposure | Not directly reviewed | Reviewed, approved, locked |

**Practical consequences:**

1. **Re-normalization without data loss.** If your emission factors change (DEFRA updates annually), you can delete all `EmissionRecord` rows and re-derive them from `RawRecord` without re-ingestion. The source truth is never lost.

2. **Schema evolution.** SAP adds a new field next quarter. It lands in `raw_payload` (JSONB) immediately with zero schema migration. The normalization pipeline extracts it asynchronously.

3. **Legal defensibility.** In a GHG audit, regulators may ask "what exactly did your SAP system send?" `RawRecord` answers that unambiguously. `EmissionRecord` is your *interpretation* of that data.

4. **Anomaly investigation.** When `confidence_score < 50`, analysts can inspect `raw_record.raw_payload` directly to understand what the source sent, without inferring backward from normalized values.

---

## 6. Design Justifications

### JSONB for `raw_payload`
SAP exports differ from utility CSVs differ from travel management system APIs. A single typed schema cannot represent all three without nullable columns proliferating. JSONB stores each payload as-is and supports GIN indexing for ad-hoc queries.

### `co2e_kg` always in kilograms
Reports must aggregate across Scope 1, 2, and 3. Storing everything in a single unit (kg CO2e) avoids conversion bugs at query time. The `quantity_normalized` + `unit_normalized` fields preserve the intermediate unit for auditability.

### `period_start` / `period_end` on EmissionRecord (not RawRecord)
Utility bills cover billing cycles; travel bookings cover trip windows. These are *business* concepts, not raw data concepts. RawRecord holds whatever the source sent (which may be a billing date, a departure date, etc.). EmissionRecord interprets that into a canonical period.

### `confidence_score` as integer 0–100 (not enum)
An enum (HIGH/MEDIUM/LOW) discards precision. Pipelines can express nuance: a record with two of five fields missing might score 60, not just "MEDIUM". Thresholds for `AUTO_APPROVED` vs `NEEDS_REVIEW` can be tuned operationally without schema changes.

### Generic `(object_type, object_id)` on AuditLog
Avoids a separate audit table per model. Allows logging `DataSource` status changes, `User` role changes, etc. without proliferating tables. Trade-off: no FK enforcement — this must be enforced at the service layer.

### `on_delete=PROTECT` everywhere
Deleting an `Organization` or `DataSource` should be a deliberate, rare operation — not a cascade accident. `PROTECT` forces explicit cleanup, which is the correct default for compliance data.

---

## 7. Tradeoffs and Deliberate Simplifications

| What's simplified | Why | Production consideration |
|---|---|---|
| Single org per user | Avoids role/permission explosion | Extend with `UserOrganizationMembership` if auditors span orgs |
| AuditLog has no FK to EmissionRecord | Keeps it generic | Accept that orphan log entries are possible; clean up at the service layer |
| `emission_factor` stored per row | Denormalized for simplicity | Extract to an `EmissionFactor` lookup table if factors are versioned and shared |
| No `DataSourceSchema` versioning | Avoids complexity | Add if you need to track which pipeline version parsed which raw payload |
| `review_status` as a simple field | No state machine enforcement in DB | Enforce valid transitions in a Django service layer or use `django-fsm` |
| No soft-delete on EmissionRecord | Simplicity | Use `is_deleted` + partial unique indexes if records must be "retracted" without deletion |
| `reporting_year` is a plain integer | Avoids a reporting period model | Extend to a `ReportingPeriod` model if orgs use non-calendar fiscal years |
| No composite tenant key on every query | Relies on FK chain | Add `organization_id` to every model and enforce it at the ORM layer (custom Manager) |

---

## 8. Review Status State Machine

```
         ┌─────────────┐
         │ NEEDS_REVIEW │◄──────────────────────┐
         └──────┬───────┘                       │
                │ pipeline sets confidence ≥ 80  │ analyst resets
                ▼                               │
       ┌────────────────┐                       │
       │ AUTO_APPROVED  │                       │
       └──────┬─────────┘                       │
              │ analyst overrides               │
              ▼                                 │
         ┌──────────┐      ┌──────────┐         │
         │ APPROVED │      │ REJECTED │─────────┘
         └────┬─────┘      └──────────┘
              │ admin locks
              ▼
         ┌──────────┐
         │  LOCKED  │  ← terminal state, no further edits
         └──────────┘
```

**Enforcement note:** LOCKED must set `locked_at` and `locked_by`. Enforce this invariant in a Django model `save()` override or a dedicated service method — not at the DB level alone, since PostgreSQL cannot call Python. A `CheckConstraint` can validate `locked_at IS NOT NULL WHEN review_status = 'LOCKED'` using a generated column or trigger if needed.
