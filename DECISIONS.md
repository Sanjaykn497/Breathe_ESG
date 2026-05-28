# DECISIONS.md — Resolved Ambiguities & Source Assumptions

This document lists every design ambiguity, selected resolutions, and assumptions made about the three source shapes.

## 1. Resolved Ambiguities

### A. Authentication & Scopes
* **Ambiguity**: How are analysts and admins authenticated, and how is session/CSRF handled for a decoupled React app?
* **Resolution**: Implemented `DevAuthenticationMiddleware` to handle mock login roles via `X-Mock-User` headers, and built `CsrfExemptSessionAuthentication` to bypass CSRF in development. This allows frictionless role-based testing in Vite.

### B. Unit & Category Mismatches
* **Ambiguity**: What should happen if a client uploads Diesel data measured in Megajoules (MJ) or Natural Gas in Liters (L)?
* **Resolution**: The conversion engine only handles conversions within identical physical properties (e.g. Volume-to-Volume or Energy-to-Energy). If an unrealistic category-unit pair is received, the calculation defaults to `0 CO2e` and drops the confidence score to `55` (Needs Review) to force professional analyst auditing.

---

## 2. Source Shape Assumptions & Scope

### A. SAP (Fuel and Procurement)
* **Real-World Reality**: SAP data typically lives in BAPIs, flat CSV IDocs, or OData services.
* **Our Scope**: We selected a flat CSV export format containing `plant_code`, `quantity`, `unit`, and `document_date`.
* **Justification**: Enterprise analysts typically export procurement logs to flat CSVs before uploading them to reporting tools. We used a plant code dictionary (`PLT001=DIESEL`, `PLT002=NATURAL_GAS`) to resolve categories.

### B. Utility Data (Electricity)
* **Real-World Reality**: Bills have overlapping billing cycles that do not align with neat calendar months.
* **Our Scope**: We selected a facilities portal CSV export containing `kwh_usage`, `period_start`, and `period_end`.
* **Justification**: Portal scrapes are the most common way energy managers download utility data before full API integrations are built.

### C. Corporate Travel
* **Real-World Reality**: Exposed as Concur or Navan webhooks and APIs.
* **Our Scope**: Handled a JSON API payload containing travel types (`FLIGHT`, `HOTEL`, `CAR`), distance, dates, or nights.
* **Justification**: Concur integrations are natively web-based JSON APIs.
