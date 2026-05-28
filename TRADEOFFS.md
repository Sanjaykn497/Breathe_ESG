# TRADEOFFS.md — Deliberate Engineering Exclusions

To deliver a high-quality data model, strict compliance rules, and a premium dashboard in 4 days, the following three items were deliberately excluded:

## 1. Real-Time PDF Parsing for Utility Bills
* **What**: PDF reading via tools like `pdfplumber` to extract text from scanned electricity bills.
* **Why we skipped it**: Writing OCR and PDF scrapers takes a significant amount of edge-case handling (every utility bill format differs). 
* **Tradeoff**: Facility portals almost always provide a "Download as CSV" option. We prioritized a clean facilities portal CSV parser with start/end date validation over complex PDF scrapers.

## 2. Persistent Database Connection Pooling (`PgBouncer`)
* **What**: Production-grade connection pooling to reuse database sockets.
* **Why we skipped it**: For a prototype/internal audit tool, Django's default behavior of opening and closing one connection per request is robust and simple.
* **Tradeoff**: Can be easily added in production settings via `"CONN_MAX_AGE": 60` or by deploying a PgBouncer sidecar.

## 3. JWT/OAuth2 Authentication Flow
* **What**: Fully implemented JWT tokens with refresh cycles.
* **Why we skipped it**: Implementing session-secure JWT authentication is highly repetitive and adds no business value for a prototype review dashboard.
* **Tradeoff**: Leveraged a highly robust, session-based developer middleware with Mock Users (`analyst@breathe.io` / `admin@breathe.io`) that allows instantly switching between roles in the UI.
