import type {
  EmissionRecord,
  AuditLogEntry,
  DataSource,
  RecordFilters,
  EditRecordPayload,
} from "../types";

const BASE = "/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const savedUser = localStorage.getItem("breathe_user");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (savedUser) {
    try {
      const user = JSON.parse(savedUser);
      headers["X-Mock-User"] = JSON.stringify(user);
    } catch {}
  }

  const res = await fetch(`${BASE}${path}`, {
    headers: { ...headers, ...options?.headers },
    credentials: "include", // send Django session cookie
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `HTTP ${res.status}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

// ── Records ────────────────────────────────────────────────────
function buildParams(filters: RecordFilters): string {
  const p = new URLSearchParams();
  if (filters.scope) p.set("scope", filters.scope);
  if (filters.review_status) p.set("review_status", filters.review_status);
  if (filters.reporting_year) p.set("reporting_year", filters.reporting_year);
  if (filters.anomaly_flag) p.set("anomaly_flag", "true");
  const q = p.toString();
  return q ? `?${q}` : "";
}

export const api = {
  records: {
    list: (filters: RecordFilters = {}) =>
      request<EmissionRecord[]>(`/records/${buildParams(filters)}`),

    get: (id: string) =>
      request<EmissionRecord>(`/records/${id}/`),

    patch: (id: string, data: EditRecordPayload) =>
      request<EmissionRecord>(`/records/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),

    approve: (id: string, notes = "") =>
      request<{ detail: string; review_status: string }>(`/records/${id}/approve/`, {
        method: "POST",
        body: JSON.stringify({ notes }),
      }),

    reject: (id: string, notes = "") =>
      request<{ detail: string; review_status: string }>(`/records/${id}/reject/`, {
        method: "POST",
        body: JSON.stringify({ notes }),
      }),

    lock: (id: string) =>
      request<{ detail: string; review_status: string }>(`/records/${id}/lock/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),

    audit: (id: string) =>
      request<AuditLogEntry[]>(`/records/${id}/audit/`),
  },

  ingest: {
    sap: (payload: {
      csv_text: string;
      name: string;
      external_ref?: string;
      reporting_year: number;
    }) =>
      request<DataSource>("/ingest/sap/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    utility: (payload: {
      csv_text: string;
      name: string;
      external_ref?: string;
      reporting_year: number;
    }) =>
      request<DataSource>("/ingest/utility/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    travel: (payload: {
      records: Record<string, unknown>[];
      name: string;
      external_ref?: string;
      reporting_year: number;
    }) =>
      request<DataSource>("/ingest/travel/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
};

export { ApiError };
