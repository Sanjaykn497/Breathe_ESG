export type ReviewStatus =
  | "AUTO_APPROVED"
  | "NEEDS_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "LOCKED";

export type Scope = "SCOPE_1" | "SCOPE_2" | "SCOPE_3";
export type SourceType = "SAP" | "UTILITY" | "TRAVEL";
export type UserRole = "ADMIN" | "ANALYST";
export type IngestionStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface EmissionRecord {
  id: string;
  source_type: SourceType;
  scope: Scope;
  category: string;
  quantity_raw: string;
  unit_raw: string;
  quantity_normalized: string;
  unit_normalized: string;
  emission_factor: string;
  emission_factor_source: string;
  co2e_kg: string;
  confidence_score: number;
  anomaly_flag: boolean;
  anomaly_reason: string;
  review_status: ReviewStatus;
  reviewed_by: string | null;
  reviewed_by_email?: string | null;
  reviewed_at: string | null;
  review_notes: string;
  locked_at: string | null;
  locked_by: string | null;
  locked_by_email?: string | null;
  period_start: string;
  period_end: string;
  reporting_year: number;
  raw_payload?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  id: string;
  object_type: string;
  object_id: string;
  action: string;
  changed_by_email: string | null;
  changed_at: string;
  field_name: string;
  before_value: string | null;
  after_value: string | null;
  note: string;
}

export interface DataSource {
  id: string;
  source_type: SourceType;
  name: string;
  ingestion_status: IngestionStatus;
  reporting_year: number;
  row_count: number;
  error_summary: Array<{ row: number; error: string }> | null;
  ingested_at: string;
}

export interface User {
  id: string;
  email: string;
  role: UserRole;
}

export interface RecordFilters {
  scope?: Scope | "";
  review_status?: ReviewStatus | "";
  reporting_year?: string;
  anomaly_flag?: boolean;
}

export interface EditRecordPayload {
  category?: string;
  quantity_raw?: string;
  unit_raw?: string;
  emission_factor?: string;
  co2e_kg?: string;
  scope?: Scope;
  review_notes?: string;
  anomaly_reason?: string;
}
