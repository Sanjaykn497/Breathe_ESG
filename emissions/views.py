from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from emissions.models import EmissionRecord, AuditLog, DataSource
from emissions.serializers import (
    EmissionRecordListSerializer,
    EmissionRecordDetailSerializer,
    EmissionRecordEditSerializer,
    ReviewActionSerializer,
    AuditLogSerializer,
    DataSourceSerializer,
)
from emissions.services.review import (
    approve_record, reject_record, lock_record, edit_emission_record
)
from emissions.services.ingestion import (
    SAPIngestionService, UtilityIngestionService, TravelIngestionService
)


# ── Ingestion ──────────────────────────────────────────────────────
class IngestSAPView(APIView):
    def post(self, request):
        csv_text = request.data.get("csv_text", "")
        name     = request.data.get("name", "SAP Upload")
        ext_ref  = request.data.get("external_ref", "")
        year     = int(request.data.get("reporting_year", 2024))

        svc         = SAPIngestionService(request.user.organization, request.user, year)
        data_source = svc.ingest(name, ext_ref, csv_text)
        return Response(DataSourceSerializer(data_source).data, status=status.HTTP_201_CREATED)


class IngestUtilityView(APIView):
    def post(self, request):
        csv_text = request.data.get("csv_text", "")
        name     = request.data.get("name", "Utility Upload")
        ext_ref  = request.data.get("external_ref", "")
        year     = int(request.data.get("reporting_year", 2024))

        svc         = UtilityIngestionService(request.user.organization, request.user, year)
        data_source = svc.ingest(name, ext_ref, csv_text)
        return Response(DataSourceSerializer(data_source).data, status=status.HTTP_201_CREATED)


class IngestTravelView(APIView):
    def post(self, request):
        records = request.data.get("records", [])
        name    = request.data.get("name", "Travel API Upload")
        ext_ref = request.data.get("external_ref", "")
        year    = int(request.data.get("reporting_year", 2024))

        svc         = TravelIngestionService(request.user.organization, request.user, year)
        data_source = svc.ingest(name, ext_ref, records)
        return Response(DataSourceSerializer(data_source).data, status=status.HTTP_201_CREATED)


# ── EmissionRecord list ────────────────────────────────────────────
class EmissionRecordListView(APIView):
    def get(self, request):
        qs = (
            EmissionRecord.objects
            .filter(organization=request.user.organization)
            .select_related("raw_record", "reviewed_by", "locked_by")
            .order_by("-created_at")
        )

        # Optional filters
        scope         = request.query_params.get("scope")
        review_status = request.query_params.get("review_status")
        year          = request.query_params.get("reporting_year")
        anomaly       = request.query_params.get("anomaly_flag")

        if scope:
            qs = qs.filter(scope=scope)
        if review_status:
            qs = qs.filter(review_status=review_status)
        if year:
            qs = qs.filter(reporting_year=year)
        if anomaly is not None:
            qs = qs.filter(anomaly_flag=anomaly.lower() == "true")

        return Response(EmissionRecordListSerializer(qs, many=True).data)


# ── EmissionRecord detail + edit ───────────────────────────────────
class EmissionRecordDetailView(APIView):
    def _get_record(self, request, pk):
        return get_object_or_404(
            EmissionRecord.objects.select_related("raw_record", "reviewed_by", "locked_by"),
            pk=pk,
            organization=request.user.organization,
        )

    def get(self, request, pk):
        record = self._get_record(request, pk)
        return Response(EmissionRecordDetailSerializer(record).data)

    def patch(self, request, pk):
        record = self._get_record(request, pk)
        ser    = EmissionRecordEditSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = edit_emission_record(record, request.user, ser.validated_data)
        return Response(EmissionRecordDetailSerializer(updated).data)


# ── Review actions ─────────────────────────────────────────────────
class ApproveRecordView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(EmissionRecord, pk=pk, organization=request.user.organization)
        ser    = ReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = approve_record(record, request.user, notes=ser.validated_data["notes"])
        return Response({"detail": "Approved.", "review_status": updated.review_status})


class RejectRecordView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(EmissionRecord, pk=pk, organization=request.user.organization)
        ser    = ReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = reject_record(record, request.user, notes=ser.validated_data["notes"])
        return Response({"detail": "Rejected.", "review_status": updated.review_status})


class LockRecordView(APIView):
    def post(self, request, pk):
        record  = get_object_or_404(EmissionRecord, pk=pk, organization=request.user.organization)
        updated = lock_record(record, request.user)
        return Response({"detail": "Locked.", "review_status": updated.review_status})


# ── AuditLog ───────────────────────────────────────────────────────
class AuditLogView(APIView):
    def get(self, request, pk):
        """Retrieve full audit trail for a single EmissionRecord."""
        logs = (
            AuditLog.objects
            .filter(
                organization=request.user.organization,
                object_type="EmissionRecord",
                object_id=pk,
            )
            .select_related("changed_by")
            .order_by("changed_at")
        )
        return Response(AuditLogSerializer(logs, many=True).data)
