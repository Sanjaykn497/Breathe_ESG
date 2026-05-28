from django.urls import path
from emissions.views import (
    IngestSAPView, IngestUtilityView, IngestTravelView,
    EmissionRecordListView, EmissionRecordDetailView,
    ApproveRecordView, RejectRecordView, LockRecordView,
    AuditLogView,
)

urlpatterns = [
    # ── Ingestion ──────────────────────────────────────────────
    path("ingest/sap/",     IngestSAPView.as_view(),     name="ingest-sap"),
    path("ingest/utility/", IngestUtilityView.as_view(), name="ingest-utility"),
    path("ingest/travel/",  IngestTravelView.as_view(),  name="ingest-travel"),

    # ── EmissionRecord ─────────────────────────────────────────
    path("records/",         EmissionRecordListView.as_view(),   name="record-list"),
    path("records/<uuid:pk>/", EmissionRecordDetailView.as_view(), name="record-detail"),

    # ── Review actions ─────────────────────────────────────────
    path("records/<uuid:pk>/approve/", ApproveRecordView.as_view(), name="record-approve"),
    path("records/<uuid:pk>/reject/",  RejectRecordView.as_view(),  name="record-reject"),
    path("records/<uuid:pk>/lock/",    LockRecordView.as_view(),    name="record-lock"),

    # ── Audit trail ────────────────────────────────────────────
    path("records/<uuid:pk>/audit/",   AuditLogView.as_view(),     name="record-audit"),
]
