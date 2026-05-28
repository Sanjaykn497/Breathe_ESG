# breathe_ESG — Project Memory

> **Purpose:** This file is the single source of truth for any agent, developer, or collaborator working on this project.
> It documents every architectural decision, every file, every API route, every design constraint, and the current build state.
> **Always update this file when adding new features, models, or services.**

---

## Project Overview

| Field | Value |
|---|---|
| **Project name** | breathe_ESG |
| **Type** | Django REST API — ESG data ingestion and analyst review platform |
| **Database** | PostgreSQL (psycopg2-binary) |
| **Framework** | Django 4.2.13 + Django REST Framework 3.15.2 |
| **Python** | 3.10.11 |
| **Root path** | `c:\Users\manju\breathe_ESG` |
| **Conversation ID** | `6cfab2f8-17d8-44e1-b8c2-4acb88432d0d` |
| **Build status** | ✅ `django check` passes (0 issues), `makemigrations` completed |

---

## What This Platform Does

An internal ESG data platform for enterprises that:

1. **Ingests** emissions data from three source types: SAP (fuel/procurement), Utility (electricity bills), Corporate Travel (flights/hotels/ground)
2. **Stores** raw data immutably as JSONB (compliance anchor)
3. **Normalizes** raw data into typed emission records with unit conversion and kg CO2e calculation
4. **Scores** records with a confidence score (0–100) and assigns initial review status
5. **Flags anomalies** when emissions exceed 200% of 3-period rolling average
6. **Routes records** through an analyst approval workflow (NEEDS_REVIEW → APPROVED → LOCKED)
7. **Tracks** every field-level change in an append-only AuditLog
8. **Locks** approved records permanently (LOCKED is terminal)

---

## Key Design Principles

| Principle | Implementation |
|---|---|
| Multi-tenancy | Every row has `organization_id` FK; all queries scoped by org |
| Immutable raw data | `RawRecord.save()` raises `PermissionDenied` if `pk` exists; no update/delete route exists |
| Audit lock | `EmissionRecord.save()` checks current DB status; raises if LOCKED |
| Thin views | Zero business logic in views; all logic in `services/` |
| State machine | `ALLOWED_TRANSITIONS` dict enforced in `services/review.py` before every status change |
| `on_delete=PROTECT` | All FKs use PROTECT — no accidental cascade deletes on compliance data |
| `co2e_kg` always kg | All emissions stored in kilograms CO2e for consistent cross-scope aggregation |

---

## Tech Stack & Dependencies

```
Django==4.2.13
djangorestframework==3.15.2
psycopg2-binary==2.9.9
django-environ==0.11.2
django-cors-headers==4.3.1
Pillow==10.3.0
```

- **`django-environ`** — 12-factor `.env` config (`DATABASE_URL`, `SECRET_KEY`, etc.)
- **`django.contrib.postgres`** — required for `GinIndex` (JSONB) and `BTreeIndex`
- **`django-cors-headers`** — CORS for frontend at `localhost:3000`
- **`Pillow`** — future image/attachment support

---

## Environment Configuration

File: [`.env`](file:///c:/Users/manju/breathe_ESG/.env) (copy from `.env.example`)

```env
SECRET_KEY=django-insecure-change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://breathe_user:breathe_pass@localhost:5432/breathe_esg
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

> ⚠️ Update `DATABASE_URL` with real PostgreSQL credentials before running migrations.

---

## Full File Tree

```
breathe_ESG/
├── .env                          ← local secrets (not committed)
├── .env.example                  ← template for .env
├── .gitignore
├── manage.py
├── requirements.txt
│
├── config/
│   ├── __init__.py
│   ├── settings.py               ← Django settings (django-environ, custom auth user)
│   ├── urls.py                   ← root URL: admin/ + api/
│   └── wsgi.py
│
└── emissions/                    ← single Django app (all ESG logic lives here)
    ├── __init__.py
    ├── apps.py                   ← EmissionsConfig
    ├── enums.py                  ← all TextChoices enums
    ├── models.py                 ← 6 models
    ├── serializers.py            ← DRF serializers
    ├── views.py                  ← thin API views
    ├── urls.py                   ← 9 API routes
    ├── admin.py                  ← Django admin (RawRecord + AuditLog read-only)
    ├── utils.py                  ← custom DRF exception handler
    ├── migrations/
    │   └── 0001_initial.py       ← generated, all models + indexes + constraints
    └── services/
        ├── __init__.py
        ├── emission_factors.py   ← factor registry + unit conversion table
        ├── normalization.py      ← unit convert + kg CO2e calculation
        ├── confidence.py         ← 0–100 scoring logic
        ├── anomaly.py            ← YoY spike detection
        ├── audit.py              ← AuditLog writer utility
        ├── review.py             ← state machine: approve/reject/lock/edit
        └── ingestion/
            ├── __init__.py       ← exports all 3 services
            ├── base.py           ← BaseIngestionService (template method)
            ├── sap.py            ← SAPIngestionService
            ├── utility.py        ← UtilityIngestionService
            └── travel.py         ← TravelIngestionService
```

---

## Data Models

### `AUTH_USER_MODEL = "emissions.User"`

All 6 models live in `emissions/models.py`. PKs are UUIDs everywhere.

---

### 1. Organization (db_table: `org_organization`)

The multi-tenant root. Every other model has an `organization` FK.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | CharField(255) | |
| `slug` | SlugField(100) unique | URL-safe identifier |
| `country` | CharField(100) optional | |
| `industry` | CharField(100) optional | |
| `active_reporting_year` | PositiveSmallInteger optional | |
| `created_at` | DateTimeField auto | |
| `is_active` | Boolean | |

---

### 2. User (db_table: `org_user`)

Custom user model. One user = one organization.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `organization` | FK → Organization PROTECT | |
| `email` | EmailField unique | USERNAME_FIELD |
| `role` | CharField choices | `ADMIN` or `ANALYST` |
| `is_active` | Boolean | |
| `is_staff` | Boolean | Django admin access |
| `created_at` | DateTimeField auto | |

**Index:** `(organization, role)` BTree

**Manager:** `UserManager` — `create_user(email, organization, password)`, `create_superuser` auto-creates a placeholder org.

---

### 3. DataSource (db_table: `esg_data_source`)

One ingestion event. Provenance anchor for all RawRecords.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `organization` | FK PROTECT | |
| `source_type` | CharField choices | SAP / UTILITY / TRAVEL |
| `name` | CharField(255) | Human label |
| `external_ref` | CharField(255) optional | Filename / S3 key / API batch ID |
| `ingestion_status` | CharField choices | PENDING / PROCESSING / COMPLETED / FAILED |
| `reporting_year` | PositiveSmallInteger | |
| `ingested_by` | FK → User SET_NULL | |
| `ingested_at` | DateTimeField auto | |
| `row_count` | PositiveInteger | Set after ingestion |
| `error_summary` | JSONField optional | Per-row errors from pipeline |

**Indexes:** `(organization, source_type, reporting_year)`, `(ingestion_status)`

---

### 4. RawRecord (db_table: `esg_raw_record`)

**IMMUTABLE.** Stores data exactly as received. Legal/compliance anchor.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `organization` | FK PROTECT | |
| `data_source` | FK PROTECT | |
| `raw_payload` | JSONField | Unmodified source data |
| `source_row_index` | PositiveInteger optional | Original file line number |
| `checksum` | CharField(64) | SHA-256 of raw_payload |
| `received_at` | DateTimeField | |

**Constraints:** `UniqueConstraint(data_source, checksum)` — prevents duplicate ingestion

**Indexes:** `(organization, data_source)`, `(checksum)`, `GIN(raw_payload)`

**Immutability enforcement:**
- `save()` raises `PermissionDenied` if `pk` is set (no updates)
- `delete()` raises `PermissionDenied` always
- No PATCH/PUT/DELETE API route exists
- Django admin: `has_change_permission → False`, `has_delete_permission → False`

---

### 5. EmissionRecord (db_table: `esg_emission_record`)

The business-facing normalized record. What analysts review.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `organization` | FK PROTECT | |
| `raw_record` | FK PROTECT | Traceability to source |
| `data_source` | FK PROTECT | |
| `reporting_year` | PositiveSmallInteger | |
| `period_start` | DateField | Start of coverage window |
| `period_end` | DateField | End of coverage window |
| `source_type` | CharField choices | SAP / UTILITY / TRAVEL |
| `scope` | CharField choices | SCOPE_1 / SCOPE_2 / SCOPE_3 |
| `category` | CharField(100) | e.g. DIESEL, ELECTRICITY, FLIGHT_SHORT_HAUL |
| `quantity_raw` | Decimal(20,6) | As received |
| `unit_raw` | CharField(50) | As received, e.g. gallons |
| `quantity_normalized` | Decimal(20,6) | After unit conversion |
| `unit_normalized` | CharField choices | kg_CO2e / kWh / MJ / L / km / night |
| `emission_factor` | Decimal(20,8) | kg CO2e per unit |
| `emission_factor_source` | CharField(255) | e.g. DEFRA 2024 |
| `co2e_kg` | Decimal(20,4) | Final impact, always kg |
| `confidence_score` | SmallInteger | 0–100 |
| `anomaly_flag` | Boolean | |
| `anomaly_reason` | TextField | |
| `review_status` | CharField choices | AUTO_APPROVED / NEEDS_REVIEW / APPROVED / REJECTED / LOCKED |
| `reviewed_by` | FK → User SET_NULL optional | |
| `reviewed_at` | DateTimeField optional | |
| `review_notes` | TextField | |
| `locked_at` | DateTimeField optional | Set on LOCKED |
| `locked_by` | FK → User SET_NULL optional | Set on LOCKED |
| `created_at` / `updated_at` | DateTimeField auto | |

**Constraints:**
- `UniqueConstraint(raw_record, scope)` — one normalized record per scope per raw row
- `CheckConstraint(period_end >= period_start)`
- `CheckConstraint(0 <= confidence_score <= 100)`
- `CheckConstraint(co2e_kg >= 0)`

**Indexes:** `(org, reporting_year, scope)`, `(org, review_status)`, `(org, source_type, reporting_year)`, `(anomaly_flag)`, `(period_start, period_end)`

**Lock enforcement:** `save()` queries current DB status; raises `PermissionDenied` if LOCKED.

---

### 6. AuditLog (db_table: `esg_audit_log`)

**APPEND-ONLY.** Field-level change history for any model.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `organization` | FK PROTECT | |
| `object_type` | CharField(100) | e.g. `EmissionRecord`, `DataSource` |
| `object_id` | UUIDField | Generic PK reference |
| `action` | CharField(50) | INGEST / STATUS_CHANGE / FIELD_EDIT / LOCK / REJECT |
| `changed_by` | FK → User SET_NULL | |
| `changed_at` | DateTimeField | db_index=True |
| `field_name` | CharField(100) | Which field changed |
| `before_value` | JSONField optional | |
| `after_value` | JSONField optional | |
| `note` | TextField | Analyst notes / pipeline messages |

**Indexes:** `(object_type, object_id)`, `(organization, changed_at)`, `(changed_by)`

**Admin:** Fully read-only. `has_add_permission → False`, `has_change_permission → False`, `has_delete_permission → False`.

---

## Enums (emissions/enums.py)

```
UserRole:        ADMIN | ANALYST
SourceType:      SAP | UTILITY | TRAVEL
EmissionScope:   SCOPE_1 | SCOPE_2 | SCOPE_3
ReviewStatus:    AUTO_APPROVED | NEEDS_REVIEW | APPROVED | REJECTED | LOCKED
IngestionStatus: PENDING | PROCESSING | COMPLETED | FAILED
NormalizedUnit:  kg_CO2e | tCO2e | kWh | MJ | L | km | night
```

---

## API Routes

Base prefix: `/api/`

| Method | URL | View | Description |
|---|---|---|---|
| POST | `/api/ingest/sap/` | `IngestSAPView` | Ingest SAP CSV |
| POST | `/api/ingest/utility/` | `IngestUtilityView` | Ingest Utility CSV |
| POST | `/api/ingest/travel/` | `IngestTravelView` | Ingest Travel API payload |
| GET | `/api/records/` | `EmissionRecordListView` | List records (filterable) |
| GET | `/api/records/<uuid>/` | `EmissionRecordDetailView` | Full record + raw payload |
| PATCH | `/api/records/<uuid>/` | `EmissionRecordDetailView` | Analyst edit (restricted fields) |
| POST | `/api/records/<uuid>/approve/` | `ApproveRecordView` | Approve record |
| POST | `/api/records/<uuid>/reject/` | `RejectRecordView` | Reject record |
| POST | `/api/records/<uuid>/lock/` | `LockRecordView` | Lock record (ADMIN only) |
| GET | `/api/records/<uuid>/audit/` | `AuditLogView` | Full audit trail |

### Query params on GET `/api/records/`

| Param | Example | Description |
|---|---|---|
| `scope` | `SCOPE_1` | Filter by GHG scope |
| `review_status` | `NEEDS_REVIEW` | Filter by workflow status |
| `reporting_year` | `2024` | Filter by year |
| `anomaly_flag` | `true` | Filter flagged records only |

---

## Ingestion Pipeline

### How it works

```
POST /api/ingest/<source>/
        │
        ▼
BaseIngestionService.ingest()
  ├─ 1. Create DataSource (status=PROCESSING)
  ├─ 2. parse_rows()          ← subclass: parse CSV or API payload
  ├─ For each row:
  │   ├─ 3. _store_raw()      ← SHA-256 checksum, get_or_create RawRecord
  │   ├─ 4. extract_fields()  ← subclass: extract category, quantity, unit
  │   ├─ 5. normalize_record() ← convert units, lookup factor, calc co2e_kg
  │   ├─ 6. score_record()    ← 0–100 confidence + AUTO_APPROVED/NEEDS_REVIEW
  │   ├─ 7. check_anomaly()   ← >200% YoY spike detection
  │   └─ 8. EmissionRecord.objects.create()
  └─ Update DataSource status + row_count + error_summary
  └─ Write INGEST AuditLog entry
```

### Source parsers

| Parser | Input | Key logic |
|---|---|---|
| `SAPIngestionService` | CSV string | Plant code → fuel category map (`PLT001=DIESEL`, etc.) |
| `UtilityIngestionService` | CSV string | Reads `kwh_usage`, `period_start`, `period_end` |
| `TravelIngestionService` | List of dicts | Classifies FLIGHT by distance (≤3700km = short haul) |

### Expected CSV format — SAP

```csv
plant_code,quantity,unit,document_date
PLT001,500,L,2024-01-15
PLT002,1200,MJ,2024-01-15
```

### Expected CSV format — Utility

```csv
kwh_usage,period_start,period_end
12500,2024-01-01,2024-01-31
```

### Expected JSON format — Travel

```json
{
  "records": [
    {"travel_type": "FLIGHT", "distance_km": 850, "travel_date": "2024-03-10"},
    {"travel_type": "HOTEL",  "nights": 2,        "travel_date": "2024-03-10"},
    {"travel_type": "CAR",    "distance_km": 45,  "travel_date": "2024-03-12"}
  ]
}
```

---

## Emission Factor Registry (emission_factors.py)

| Key (source_type, category, unit) | Factor (kg CO2e/unit) | Source |
|---|---|---|
| SAP, DIESEL, L | 2.6840 | DEFRA 2024 |
| SAP, NATURAL_GAS, MJ | 0.0561 | DEFRA 2024 |
| SAP, PETROL, L | 2.3100 | DEFRA 2024 |
| UTILITY, ELECTRICITY, kWh | 0.2330 | EPA eGRID 2023 |
| TRAVEL, FLIGHT_SHORT_HAUL, km | 0.2550 | DEFRA 2024 |
| TRAVEL, FLIGHT_LONG_HAUL, km | 0.1950 | DEFRA 2024 |
| TRAVEL, HOTEL_NIGHT, night | 20.600 | DEFRA 2024 |
| TRAVEL, CAR_RENTAL, km | 0.1710 | DEFRA 2024 |

### Unit Conversion Table

| Raw unit | Normalized to | Multiplier |
|---|---|---|
| gallons | L | 3.78541 |
| kBTU | MJ | 1.05506 |
| BTU | MJ | 0.00105506 |
| MWh | kWh | 1000 |
| miles | km | 1.60934 |

---

## Confidence Scoring (confidence.py)

Starts at 100 and deducts:

| Condition | Deduction |
|---|---|
| Emission factor not found | −30 |
| Unit required conversion | −20 |
| Missing required field (category/quantity/unit) | −20 |
| period_start == period_end (suspicious for utility) | −15 |
| source_row_index is None | −10 |

**Score bands:**
- `≥ 80` → `AUTO_APPROVED`
- `< 80` → `NEEDS_REVIEW`
- Floor: `0`

---

## Anomaly Detection (anomaly.py)

Compares incoming `co2e_kg` against rolling 3-period average for `(org, scope, category)`.

- Threshold: **> 200% above baseline**
- Sets `anomaly_flag = True` and writes a human-readable `anomaly_reason`
- Does NOT change `review_status` — analyst sees both independently
- No history → no flag (safe first-ingestion behaviour)

---

## Review Workflow State Machine (review.py)

```
NEEDS_REVIEW ─┬──► APPROVED ──► LOCKED (terminal)
               └──► REJECTED ──► NEEDS_REVIEW (re-open)

AUTO_APPROVED ─┬──► APPROVED ──► LOCKED (terminal)
               └──► REJECTED ──► NEEDS_REVIEW (re-open)
```

| Function | Who can call | Guard |
|---|---|---|
| `approve_record(record, analyst, notes)` | ANALYST | `_guard_not_locked` + `_guard_transition` |
| `reject_record(record, analyst, notes)` | ANALYST | `_guard_not_locked` + `_guard_transition` |
| `lock_record(record, admin_user)` | ADMIN only | Role check + `_guard_not_locked` + `_guard_transition` |
| `edit_emission_record(record, analyst, data)` | ANALYST | `_guard_not_locked` + field whitelist |

**Edit rules:**
- Only `EDITABLE_FIELDS` are allowed: `{category, quantity_raw, unit_raw, quantity_normalized, unit_normalized, emission_factor, co2e_kg, scope, review_notes, anomaly_reason}`
- Any edit on `AUTO_APPROVED` resets it to `NEEDS_REVIEW`
- Every edit writes per-field `AuditLog` entries

---

## Audit Logging (audit.py)

Two functions, always called from service layer (never from views):

```python
log_change(organization_id, object_type, object_id, action, changed_by, field_name, before_value, after_value, note)
log_field_changes(organization_id, record, old_data, new_data, changed_by)  # diffs and writes per-field
```

**Actions used:**
- `INGEST` — DataSource created, ingestion completed
- `STATUS_CHANGE` — review_status transitioned
- `FIELD_EDIT` — per-field edit by analyst
- `LOCK` — record locked by admin

---

## Serializers (serializers.py)

| Serializer | Used in | Purpose |
|---|---|---|
| `DataSourceSerializer` | Ingestion response | POST /ingest/* response |
| `EmissionRecordListSerializer` | GET /records/ | Lightweight list |
| `EmissionRecordDetailSerializer` | GET /records/<id>/ | Full detail + `raw_payload` from RawRecord |
| `EmissionRecordEditSerializer` | PATCH /records/<id>/ | Write-only, restricted fields only |
| `ReviewActionSerializer` | POST approve/reject | `notes` field |
| `AuditLogSerializer` | GET /records/<id>/audit/ | Full audit trail |

---

## Exception Handling (utils.py)

Custom DRF exception handler registered in `REST_FRAMEWORK` settings:

| Exception | HTTP Response |
|---|---|
| `django.core.exceptions.PermissionDenied` | 403 |
| `django.core.exceptions.ValidationError` | 400 |
| DRF native exceptions | handled by DRF default |
| Unhandled | Django 500 |

---

## Django Admin (admin.py)

| Model | Add | Change | Delete |
|---|---|---|---|
| Organization | ✅ | ✅ | ✅ |
| User | ✅ | ✅ | ✅ |
| DataSource | ✅ | Status only | ✅ |
| RawRecord | ❌ | ❌ | ❌ (fully read-only) |
| EmissionRecord | ✅ | ✅ | ❌ if LOCKED |
| AuditLog | ❌ | ❌ | ❌ (fully read-only) |

---

## Migrations

| File | Status |
|---|---|
| `emissions/migrations/0001_initial.py` | ✅ Generated |

Includes all 6 models, all B-tree and GIN indexes, all check constraints, all unique constraints.

**To apply migrations (requires PostgreSQL running):**
```bash
# Create DB first
psql -U postgres -c "CREATE DATABASE breathe_esg;"
psql -U postgres -c "CREATE USER breathe_user WITH PASSWORD 'breathe_pass';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE breathe_esg TO breathe_user;"

# Apply
.venv\Scripts\python manage.py migrate

# Create superuser
.venv\Scripts\python manage.py createsuperuser

# Run dev server
.venv\Scripts\python manage.py runserver
```

---

## What Is Deliberately Simplified (and Why)

| Simplification | Production recommendation |
|---|---|
| Synchronous ingestion in request cycle | Move to Celery/RQ task queue triggered by file upload |
| Hardcoded emission factors in `emission_factors.py` | Extract to `EmissionFactor` versioned DB table (org + year + region scoped) |
| Single anomaly rule (>200% YoY) | Rule engine: configurable thresholds per org per category |
| No PDF parsing for utility bills | Add `pdfplumber` in `UtilityIngestionService.parse_rows()` |
| Plant code → category is a static dict | DB-backed `PlantCodeMapping` table, org-scoped |
| No pagination on record list | Add `django-filters` + DRF `PageNumberPagination` |
| State machine in pure Python | Add `django-fsm` for declarative transitions + signal hooks |
| No per-field DB-level lock enforcement | PostgreSQL trigger on LOCKED rows (belt-and-suspenders) |
| One org per user | Add `UserOrganizationMembership` for auditors who span orgs |
| `reporting_year` as plain integer | Extend to a `ReportingPeriod` model for non-calendar fiscal years |
| No soft-delete on EmissionRecord | Add `is_deleted` + partial unique indexes for record retraction |

---

## Artifacts (Design Documents)

Both files exist at the project root and in the agent artifact directory.

| File | Contents |
|---|---|
| [`esg_data_model.md`](file:///c:/Users/manju/breathe_ESG/esg_data_model.md) | Full data model design: model code, enums, relationships, index rationale, RawRecord separation justification, state machine diagram |
| [`esg_service_layer.md`](file:///c:/Users/manju/breathe_ESG/esg_service_layer.md) | Full service layer design: pipeline architecture, all service code outlines, anomaly rules, confidence scoring, approval workflow, serializer strategy, error handling, tradeoffs |

---

## What Is NOT Yet Built

The following are planned next steps (not yet implemented):

- [ ] Unit tests (`emissions/tests/`)
- [ ] Pagination + filtering (`django-filters`)
- [ ] Bulk ingestion endpoint (zip upload with multiple CSVs)
- [ ] Reporting aggregation endpoint (total CO2e by scope/year/org)
- [ ] User authentication (JWT or session login endpoints)
- [ ] Permission classes (DRF `IsAuthenticated` is currently the only guard)
- [ ] Frontend / dashboard UI
- [ ] PDF parsing for utility bills
- [ ] Celery background task queue for async ingestion
- [ ] Versioned emission factor table
- [ ] Org-scoped plant code mapping table
- [ ] Docker / docker-compose setup

---

## Frontend — React + TypeScript + shadcn/ui

### Status
✅ **Production build passes** — `tsc -b && vite build` clean, 0 errors, 412 KB bundle.

### Tech Stack
| Layer | Choice |
|---|---|
| Framework | React 18 + TypeScript (Vite scaffold) |
| UI Library | **shadcn/ui** (mandatory — all components from `@/components/ui/`) |
| Styling | Tailwind CSS v3 (via shadcn) + CSS variable tokens |
| Icons | lucide-react |
| Routing | React Router v6 |
| HTTP | Native `fetch` with session cookie auth |
| State | `useState` / `useCallback` — no Redux |

### Frontend Root
`c:\Users\manju\breathe_ESG\frontend\`

### Folder Structure
```
frontend/
├── src/
│   ├── api/
│   │   └── api.ts                  ← ALL API calls in one file
│   ├── types/
│   │   └── index.ts                ← All TypeScript interfaces
│   ├── lib/
│   │   └── utils.ts                ← shadcn cn() + formatDate/formatDateTime
│   ├── context/
│   │   └── AuthContext.tsx         ← user + isAdmin React context
│   ├── components/
│   │   ├── ui/                     ← shadcn components (DO NOT EDIT)
│   │   │   ├── badge.tsx
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── label.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── select.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── switch.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   └── textarea.tsx
│   │   ├── StatusBadge.tsx         ← Review status colored Badge
│   │   ├── AnomalyIcon.tsx         ← Red AlertTriangle with tooltip
│   │   ├── RecordTable.tsx         ← shadcn Table + skeleton loading
│   │   ├── RecordDrawer.tsx        ← shadcn Sheet (right drawer) + Dialog confirms
│   │   ├── RawPayloadViewer.tsx    ← Collapsible JSON via ScrollArea
│   │   ├── AuditTimeline.tsx       ← Timeline with Separator + colored dots
│   │   └── EditRecordForm.tsx      ← Restricted field form (Input/Select/Textarea)
│   ├── pages/
│   │   ├── LoginPage.tsx           ← shadcn Card login, mock users
│   │   ├── DashboardPage.tsx       ← Tabs + Select filters + Switch + RecordTable
│   │   └── IngestionPage.tsx       ← 3x shadcn Card upload forms
│   ├── App.tsx                     ← BrowserRouter + ProtectedRoute
│   ├── main.tsx                    ← Entry point
│   └── index.css                   ← Tailwind directives + shadcn CSS variables
├── tailwind.config.js              ← CSS variable token mapping
├── vite.config.ts                  ← /api proxy → localhost:8000
├── components.json                 ← shadcn config (Radix/Nova preset)
└── tsconfig.app.json               ← @/ alias, noUnusedLocals off
```

### Pages

| Page | Route | Description |
|---|---|---|
| LoginPage | `/` | Card login form. Mock: analyst@breathe.io or admin@breathe.io / password |
| DashboardPage | `/dashboard` | Tabs (Needs Review/All/Approved/Locked), Select filters, Switch anomaly toggle, RecordTable |
| IngestionPage | `/ingest` | 3 Card upload forms for SAP CSV, Utility CSV, Travel JSON |

### Key Components

| Component | shadcn used | Purpose |
|---|---|---|
| `StatusBadge` | `Badge` | Color-coded review status |
| `RecordTable` | `Table` | Clickable rows, skeleton loading, confidence bar |
| `RecordDrawer` | `Sheet`, `ScrollArea`, `Dialog`, `Button`, `Badge`, `Separator` | Full record detail + approve/reject/lock/edit + confirm dialog |
| `EditRecordForm` | `Input`, `Textarea`, `Select`, `Label`, `Button`, `Separator` | Restricted field edit (resets AUTO_APPROVED → NEEDS_REVIEW) |
| `RawPayloadViewer` | `ScrollArea`, `Button` | Collapsible dark JSON viewer |
| `AuditTimeline` | `Separator` | Color-coded action dots with before/after diffs |

### Status Badge Colors
| Status | Color |
|---|---|
| AUTO_APPROVED | Blue outline |
| NEEDS_REVIEW | Yellow outline |
| APPROVED | Green outline |
| REJECTED | Red outline |
| LOCKED | Neutral/gray outline |

### LOCKED Enforcement (UI)
```tsx
const isLocked = record.review_status === "LOCKED";
<Button disabled={isLocked}>Approve</Button>   // disabled
<Button disabled={isLocked}>Reject</Button>    // disabled
<Button disabled={isLocked}>Edit</Button>      // disabled
// Lock button only for ADMIN, only when status === "APPROVED"
{isAdmin && <Button disabled={record.review_status !== "APPROVED"}>Lock</Button>}
```

### API Proxy (vite.config.ts)
```
/api/* → http://localhost:8000   (Django backend)
```
No CORS issues in dev. All `fetch("/api/...")` calls auto-proxied.

### Auth (Mock)
Login page switches between two hardcoded users:
- `analyst@breathe.io` / `password` → role: ANALYST
- `admin@breathe.io` / `password` → role: ADMIN (sees Lock button)

Replace with real Django session login when ready.

### Run Commands

**Backend (Django):**
```bash
# Terminal 1
cd c:\Users\manju\breathe_ESG
.venv\Scripts\python manage.py runserver
# → http://localhost:8000
```

**Frontend (Vite):**
```bash
# Terminal 2
cd c:\Users\manju\breathe_ESG\frontend
npm run dev
# → http://localhost:5173
```

**Prerequisites & Database Architecture:**
1. **Self-Healing Connection**: The database engine in `settings.py` is configured to dynamically check if the PostgreSQL service (`postgresql-x64-15` or similar) is listening on port `5432`.
   - **PostgreSQL Online**: Connects to the local PostgreSQL database matching the `.env` credentials.
   - **PostgreSQL Offline**: Gracefully falls back to a zero-configuration local SQLite database (`db.sqlite3`), ensuring the environment never crashes due to database connection errors!
2. **Database-Agnostic Setup**: Standard indexes (`models.Index`) replace PostgreSQL-specific index classes (`BTreeIndex`, `GinIndex`) in `models.py` when running on SQLite, making migrations (`0001_initial.py`) 100% database-agnostic.
3. **Sessionless Dev-Login & CSRF Exemption**:
   - `DevAuthenticationMiddleware` in [middleware.py](file:///c:/Users/manju/breathe_ESG/emissions/middleware.py) intercepts incoming `X-Mock-User` headers, auto-creating and logging in the mock React users (`analyst@breathe.io` or `admin@breathe.io`) with strict multitenancy scoping.
   - `CsrfExemptSessionAuthentication` bypasses standard CSRF token checks in development so the React client can perform unsafe actions (`POST`, `PATCH`) seamlessly.
4. **Pristine Demo Data Population**:
   - Run the population script in your terminal to instantly wipe tables and ingest a realistic batch of records displaying successful conversions, YoY anomalies, and status locks:
     ```bash
     .venv\Scripts\python populate_demo_data.py
     ```

### Build Verification
```
✓ tsc -b                     → 0 TypeScript errors
✓ vite build                 → 412.43 kB JS, 26.26 kB CSS
✓ django system check        → 0 errors
✓ db migration (Postgres)    → Successful, all 6 tables generated
```

---

## For Agents: Key Rules to Always Follow

1. **Never update or delete a `RawRecord`** — `save()` and `delete()` are hardcoded to raise.
2. **Never allow edits to a LOCKED `EmissionRecord`** — always call `_guard_not_locked(record)` first.
3. **All records must be scoped to an org** — always filter with `organization=request.user.organization`.
4. **All business logic goes in `services/`** — views must remain thin.
5. **All AuditLog writes go through `audit.py`** — never call `AuditLog.objects.create()` directly outside that file.
6. **State transitions must use `_guard_transition()`** — never change `review_status` directly.
7. **Emission calculations always in `kg` CO2e** — use `co2e_kg` for aggregation, never mix units.
8. **`on_delete=PROTECT` for all FKs** — never switch to CASCADE on compliance data models.
