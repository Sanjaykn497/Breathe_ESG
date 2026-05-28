import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings

# Database-agnostic index fallback for SQLite/Postgres compatibility
use_postgres = False
try:
    engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    if "postgresql" in engine or "postgres" in engine:
        use_postgres = True
except Exception:
    pass

if use_postgres:
    from django.contrib.postgres.indexes import BTreeIndex, GinIndex
else:
    BTreeIndex = models.Index
    GinIndex = models.Index

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .enums import (
    UserRole, SourceType, EmissionScope,
    ReviewStatus, IngestionStatus, NormalizedUnit,
)


# ─────────────────────────────────────────────
# Organization (multi-tenant root)
# ─────────────────────────────────────────────
class Organization(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name     = models.CharField(max_length=255)
    slug     = models.SlugField(max_length=100, unique=True)
    country  = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    active_reporting_year = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        db_table = "org_organization"

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# User (role-based, org-scoped)
# ─────────────────────────────────────────────
class UserManager(BaseUserManager):
    def create_user(self, email, organization, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user  = self.model(email=email, organization=organization, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # For django admin — creates a placeholder org if needed
        org, _ = Organization.objects.get_or_create(
            slug="superuser-org",
            defaults={"name": "Superuser Org"},
        )
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, organization=org, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="users"
    )
    email     = models.EmailField(unique=True)
    role      = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.ANALYST)
    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "org_user"
        indexes  = [BTreeIndex(fields=["organization", "role"])]

    def __str__(self):
        return self.email


# ─────────────────────────────────────────────
# DataSource (single ingestion event)
# ─────────────────────────────────────────────
class DataSource(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="data_sources"
    )
    source_type      = models.CharField(max_length=20, choices=SourceType.choices)
    name             = models.CharField(max_length=255)
    external_ref     = models.CharField(max_length=255, blank=True)
    ingestion_status = models.CharField(
        max_length=20, choices=IngestionStatus.choices, default=IngestionStatus.PENDING
    )
    reporting_year = models.PositiveSmallIntegerField()
    ingested_by    = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="ingested_sources"
    )
    ingested_at  = models.DateTimeField(auto_now_add=True)
    row_count    = models.PositiveIntegerField(default=0)
    error_summary = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "esg_data_source"
        indexes  = [
            BTreeIndex(fields=["organization", "source_type", "reporting_year"]),
            BTreeIndex(fields=["ingestion_status"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.source_type}]"


# ─────────────────────────────────────────────
# RawRecord (immutable source-of-truth)
# ─────────────────────────────────────────────
class RawRecord(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="raw_records"
    )
    data_source      = models.ForeignKey(
        DataSource, on_delete=models.PROTECT, related_name="raw_records"
    )
    raw_payload      = models.JSONField()
    source_row_index = models.PositiveIntegerField(null=True, blank=True)
    checksum         = models.CharField(max_length=64)
    received_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "esg_raw_record"
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "checksum"],
                name="uq_raw_record_source_checksum",
            )
        ]
        indexes = [
            BTreeIndex(fields=["organization", "data_source"]),
            BTreeIndex(fields=["checksum"]),
            GinIndex(fields=["raw_payload"], name="gin_raw_payload"),
        ]

    def save(self, *args, **kwargs):
        # Since UUID PK default is pre-generated in memory, check DB presence to block updates
        if self.pk is not None and RawRecord.objects.filter(pk=self.pk).exists():
            raise PermissionDenied("RawRecord is immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("RawRecord cannot be deleted.")


# ─────────────────────────────────────────────
# EmissionRecord (normalized, reviewable)
# ─────────────────────────────────────────────
class EmissionRecord(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="emission_records"
    )
    raw_record  = models.ForeignKey(
        RawRecord, on_delete=models.PROTECT, related_name="emission_records"
    )
    data_source = models.ForeignKey(
        DataSource, on_delete=models.PROTECT, related_name="emission_records"
    )
    reporting_year = models.PositiveSmallIntegerField()

    # Temporal
    period_start = models.DateField()
    period_end   = models.DateField()

    # Classification
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    scope       = models.CharField(max_length=10, choices=EmissionScope.choices)
    category    = models.CharField(max_length=100, blank=True)

    # Raw quantity
    quantity_raw = models.DecimalField(max_digits=20, decimal_places=6)
    unit_raw     = models.CharField(max_length=50)

    # Normalized quantity
    quantity_normalized = models.DecimalField(max_digits=20, decimal_places=6)
    unit_normalized     = models.CharField(max_length=20, choices=NormalizedUnit.choices)

    # Emission calculation
    emission_factor        = models.DecimalField(max_digits=20, decimal_places=8)
    emission_factor_source = models.CharField(max_length=255, blank=True)
    co2e_kg                = models.DecimalField(max_digits=20, decimal_places=4)

    # Quality
    confidence_score = models.SmallIntegerField(default=100)
    anomaly_flag     = models.BooleanField(default=False)
    anomaly_reason   = models.TextField(blank=True)

    # Review workflow
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.NEEDS_REVIEW
    )
    reviewed_by  = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_records"
    )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Audit lock
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="locked_records"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "esg_emission_record"
        constraints = [
            models.UniqueConstraint(
                fields=["raw_record", "scope"],
                name="uq_emission_record_raw_scope",
            ),
            models.CheckConstraint(
                check=models.Q(period_end__gte=models.F("period_start")),
                name="chk_period_end_gte_start",
            ),
            models.CheckConstraint(
                check=models.Q(confidence_score__gte=0, confidence_score__lte=100),
                name="chk_confidence_score_range",
            ),
            models.CheckConstraint(
                check=models.Q(co2e_kg__gte=0),
                name="chk_co2e_non_negative",
            ),
        ]
        indexes = [
            BTreeIndex(fields=["organization", "reporting_year", "scope"]),
            BTreeIndex(fields=["organization", "review_status"]),
            BTreeIndex(fields=["organization", "source_type", "reporting_year"]),
            BTreeIndex(fields=["anomaly_flag"]),
            BTreeIndex(fields=["period_start", "period_end"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            current_status = (
                EmissionRecord.objects
                .filter(pk=self.pk)
                .values_list("review_status", flat=True)
                .first()
            )
            if current_status == ReviewStatus.LOCKED:
                raise PermissionDenied("Cannot modify a LOCKED EmissionRecord.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization} | {self.scope} | {self.co2e_kg} kg CO2e"


# ─────────────────────────────────────────────
# AuditLog (append-only field-level history)
# ─────────────────────────────────────────────
class AuditLog(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="audit_logs"
    )
    object_type = models.CharField(max_length=100)
    object_id   = models.UUIDField()
    action      = models.CharField(max_length=50)
    changed_by  = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    changed_at   = models.DateTimeField(default=timezone.now, db_index=True)
    field_name   = models.CharField(max_length=100, blank=True)
    before_value = models.JSONField(null=True, blank=True)
    after_value  = models.JSONField(null=True, blank=True)
    note         = models.TextField(blank=True)

    class Meta:
        db_table = "esg_audit_log"
        indexes  = [
            BTreeIndex(fields=["object_type", "object_id"]),
            BTreeIndex(fields=["organization", "changed_at"]),
            BTreeIndex(fields=["changed_by"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.object_type}:{self.object_id} by {self.changed_by}"
