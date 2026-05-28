from django.contrib import admin
from emissions.models import (
    Organization, User, DataSource,
    RawRecord, EmissionRecord, AuditLog,
)
from emissions.enums import ReviewStatus


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display  = ["name", "slug", "country", "industry", "is_active", "created_at"]
    search_fields = ["name", "slug"]
    list_filter   = ["is_active", "country"]


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display  = ["email", "organization", "role", "is_active", "is_staff"]
    search_fields = ["email"]
    list_filter   = ["role", "is_active", "organization"]


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display  = ["name", "organization", "source_type", "ingestion_status", "reporting_year", "row_count", "ingested_at"]
    list_filter   = ["source_type", "ingestion_status", "reporting_year"]
    search_fields = ["name", "external_ref"]
    readonly_fields = ["ingested_at", "row_count", "error_summary"]


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display  = ["id", "organization", "data_source", "source_row_index", "checksum", "received_at"]
    search_fields = ["checksum"]
    readonly_fields = ["id", "organization", "data_source", "raw_payload",
                       "source_row_index", "checksum", "received_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display  = [
        "id", "organization", "source_type", "scope", "category",
        "co2e_kg", "confidence_score", "review_status", "anomaly_flag",
        "period_start", "period_end",
    ]
    list_filter   = ["review_status", "scope", "source_type", "anomaly_flag", "reporting_year"]
    search_fields = ["category", "organization__name"]
    readonly_fields = [
        "id", "organization", "raw_record", "data_source",
        "created_at", "updated_at", "locked_at", "locked_by",
    ]

    def has_delete_permission(self, request, obj=None):
        if obj and obj.review_status == ReviewStatus.LOCKED:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ["action", "object_type", "object_id", "changed_by", "field_name", "changed_at"]
    list_filter   = ["action", "object_type"]
    search_fields = ["object_id", "changed_by__email"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
