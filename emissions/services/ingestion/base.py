import hashlib
import json
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
    Template method pattern for ingestion.
    Subclasses must implement: parse_rows(), extract_fields(), get_period()
    """
    source_type: str  # overridden by each subclass

    def __init__(self, organization, user, reporting_year: int):
        self.organization   = organization
        self.user           = user
        self.reporting_year = reporting_year

    # ── Public entry point ───────────────────────────────────────
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

        data_source.row_count       = success
        data_source.ingestion_status = (
            IngestionStatus.COMPLETED if not errors else IngestionStatus.FAILED
        )
        data_source.error_summary = errors or None
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

    # ── Step 1: Create DataSource ────────────────────────────────
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
            raise ValueError(f"Duplicate row at index {idx} (checksum: {checksum[:8]}...)")
        return raw

    # ── Steps 3-8: Full normalization + persistence ───────────────
    def _process_row(self, data_source: DataSource, raw_record: RawRecord, row: dict):
        fields       = self.extract_fields(row)
        period_start, period_end = self.get_period(row)

        norm_context = {
            "factor_found":     True,
            "unit_converted":   False,
            "missing_fields":   not all([fields.get("category"), fields.get("quantity"), fields.get("unit")]),
            "degenerate_period": period_start == period_end,
            "no_row_index":     raw_record.source_row_index is None,
        }

        try:
            norm = normalize_record(
                source_type=self.source_type,
                category=fields["category"],
                quantity_raw=Decimal(str(fields["quantity"])),
                unit_raw=fields["unit"],
            )
            if fields["unit"] != norm["unit_normalized"]:
                norm_context["unit_converted"] = True
        except (ValueError, KeyError):
            norm_context["factor_found"] = False
            norm = self._fallback_norm(fields)

        confidence, review_status = score_record(norm_context)

        anomaly_flag, anomaly_reason = check_anomaly(
            organization_id=self.organization.id,
            scope=norm["scope"],
            category=norm["category"],
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
        """Zero-emission fallback when no factor is found. Flags for analyst review."""
        from emissions.enums import EmissionScope
        return {
            "scope":                  EmissionScope.SCOPE_1,
            "category":               fields.get("category", "UNKNOWN"),
            "quantity_raw":           Decimal(str(fields.get("quantity", 0))),
            "unit_raw":               fields.get("unit", "unknown"),
            "quantity_normalized":    Decimal(str(fields.get("quantity", 0))),
            "unit_normalized":        "kg_CO2e",
            "emission_factor":        Decimal("0"),
            "emission_factor_source": "NOT_FOUND",
            "co2e_kg":                Decimal("0"),
        }

    # ── Subclass interface ────────────────────────────────────────
    def parse_rows(self, raw_input) -> list[dict]:
        raise NotImplementedError

    def extract_fields(self, row: dict) -> dict:
        """Must return dict with keys: category (str), quantity (Decimal), unit (str)"""
        raise NotImplementedError

    def get_period(self, row: dict) -> tuple:
        """Must return (period_start: date, period_end: date)"""
        raise NotImplementedError
