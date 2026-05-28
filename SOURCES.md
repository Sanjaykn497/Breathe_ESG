# SOURCES.md — Real-World Data Scopes & Formats

This document lists the real-world research behind our three data source shapes and explains our test data.

## 1. SAP (Fuel and Procurement)
* **Real-World Shape**: IDoc (Intermediate Document) flat files or OData exports from SAP ERP.
* **What We Learned**: Columns are often cryptic (e.g. `WERKS` for plant, `MENGE` for quantity, `MEINS` for unit) and plant codes (e.g. `PLT001`) mean nothing without lookup registries.
* **Our Sample Data**:
  ```csv
  plant_code,quantity,unit,document_date
  PLT001,500,L,2024-01-15
  PLT002,1000,kBTU,2024-04-15
  ```
* **What would break in production**: If a new plant code is added to SAP without updating our backend's `PLANT_CODE_MAP` registry, the category resolves to `UNKNOWN`.

## 2. Utility Electricity Portal Exports
* **Real-World Shape**: Interval data exports (Green Button XML/CSV) or portal scrapes.
* **What We Learned**: Billing intervals frequently span across calendar months (e.g. Jan 15 to Feb 14) and often include trailing tariff parameters.
* **Our Sample Data**:
  ```csv
  kwh_usage,period_start,period_end
  8000,2024-01-01,2024-01-31
  ```
* **What would break in production**: Overlapping date bounds for the same meter or organization must be blocked via strict checking in the ingestion service.

## 3. Corporate Travel (Concur/Navan)
* **Real-World Shape**: JSON webhooks and payloads.
* **What We Learned**: Distance bounds dictate scope factors (e.g., short-haul flights have higher carbon multipliers per km than long-haul flights).
* **Our Sample Data**:
  ```json
  {"travel_type": "FLIGHT", "distance_km": 850, "travel_date": "2024-03-10"}
  ```
* **What would break in production**: Airport code data (e.g., `JFK` to `LAX`) requires integrating an external distance routing API (Great Circle distance).
