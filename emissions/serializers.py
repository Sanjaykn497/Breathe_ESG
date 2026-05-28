from rest_framework import serializers
from emissions.models import DataSource, EmissionRecord, AuditLog
from emissions.enums import ReviewStatus


# ── DataSource ────────────────────────────────────────────────
class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DataSource
        fields = [
            "id", "source_type", "name", "external_ref",
            "ingestion_status", "reporting_year",
            "ingested_by", "ingested_at", "row_count", "error_summary",
        ]
        read_only_fields = [
            "id", "ingestion_status", "ingested_by",
            "ingested_at", "row_count", "error_summary",
        ]


# ── EmissionRecord — list view (lightweight) ──────────────────
class EmissionRecordListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EmissionRecord
        fields = [
            "id", "source_type", "scope", "category",
            "quantity_raw", "unit_raw",
            "co2e_kg", "confidence_score", "review_status",
            "anomaly_flag", "period_start", "period_end", "reporting_year",
        ]


# ── EmissionRecord — detail view (full, includes raw payload) ─
class EmissionRecordDetailSerializer(serializers.ModelSerializer):
    raw_payload      = serializers.SerializerMethodField()
    reviewed_by_email = serializers.SerializerMethodField()
    locked_by_email   = serializers.SerializerMethodField()

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

    def get_reviewed_by_email(self, obj):
        return obj.reviewed_by.email if obj.reviewed_by else None

    def get_locked_by_email(self, obj):
        return obj.locked_by.email if obj.locked_by else None


# ── EmissionRecord — analyst edit (restricted fields only) ────
class EmissionRecordEditSerializer(serializers.Serializer):
    category            = serializers.CharField(required=False)
    quantity_raw        = serializers.DecimalField(max_digits=20, decimal_places=6, required=False)
    unit_raw            = serializers.CharField(required=False)
    emission_factor     = serializers.DecimalField(max_digits=20, decimal_places=8, required=False)
    co2e_kg             = serializers.DecimalField(max_digits=20, decimal_places=4, required=False)
    scope               = serializers.ChoiceField(
        choices=["SCOPE_1", "SCOPE_2", "SCOPE_3"], required=False
    )
    review_notes        = serializers.CharField(required=False, allow_blank=True)
    anomaly_reason      = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data


# ── Review action (approve / reject) ─────────────────────────
class ReviewActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


# ── AuditLog ──────────────────────────────────────────────────
class AuditLogSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source="changed_by.email", read_only=True, default=None)

    class Meta:
        model  = AuditLog
        fields = [
            "id", "object_type", "object_id", "action",
            "changed_by_email", "changed_at",
            "field_name", "before_value", "after_value", "note",
        ]
