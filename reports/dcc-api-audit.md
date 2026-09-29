# Data Center Commander — API Audit Report

**Date:** 2026-09-29  
**Scope:** All HTTP endpoints, authentication, rate limiting, request/response formats  
**Source:** `src/dcc/api.py`, `src/dcc/azure_prices.py`, `src/dcc/google_prices.py`, `database/schema.sql`, `database/migrations/`

---

## 1. Endpoint Inventory

### 1.1 Health & Readiness

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/healthz` | None | Liveness probe. Returns service name and mode. |
| GET | `/readyz` | None | Readiness probe. Checks database schema and RLS enforcement. |

**Response — `/healthz` (200):**
```json
{
  "service": "data-center-commander",
  "mode": "read_only",
  "execution_permitted": false
}
```

**Response — `/readyz` (200 ready / 503 not ready):**
```json
{
  "service": "data-center-commander",
  "ready": true,
  "checks": {
    "database": "ok",
    "schema": "ok",
    "tenant_rls": "ok"
  },
  "execution_permitted": false
}
```

---

### 1.2 Core Data Endpoints (GET)

All core endpoints require `tenant_id` as a query parameter (UUID format). All return `read_only: true` and `execution_permitted: false`.

| Method | Path | Query Params | Description |
|--------|------|--------------|-------------|
| GET | `/v1/overview` | `tenant_id`, `window_days` (1–90, default 30), `demo` (`synthetic`) | Dashboard summary: facility count, latest KPIs, open workflows, telemetry status |
| GET | `/v1/topology` | `tenant_id` | Asset graph nodes and edges (LIMIT 500 nodes, 1000 edges) |
| GET | `/v1/facilities` | `tenant_id` | Facilities with site info (LIMIT 500) |
| GET | `/v1/assets` | `tenant_id` | Assets with facility/space names (LIMIT 1000) |
| GET | `/v1/workflows` | `tenant_id` | Operational workflows (LIMIT 500) |
| GET | `/v1/connectors` | `tenant_id` | Connector registry (LIMIT 500) |
| GET | `/v1/capacity` | `tenant_id` | Capacity snapshots, latest per facility/dimension/scenario (LIMIT 1000) |
| GET | `/v1/evidence` | `tenant_id` | Evidence events, most recent first (LIMIT 100) |
| GET | `/v1/costs` | `tenant_id`, `demo` (`synthetic`) | Cost estimates, price observations, actuals (LIMIT 100/500/500) |
| GET | `/v1/analytics` | `tenant_id`, `window_days` (1–90, default 30) | KPI series, quality, telemetry quality, workflow health (LIMIT 5000/500/500) |

**Common error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Invalid `tenant_id` or `window_days` | `{"error": "<message>"}` |
| 404 | Unknown route | `{"error": "route_not_found"}` |
| 503 | Database unavailable | `{"error": "database_unavailable_or_schema_missing", "read_only": true, "execution_permitted": false}` |

---

### 1.3 Pricing Endpoints (GET)

| Method | Path | Query Params | Description |
|--------|------|--------------|-------------|
| GET | `/v1/pricing/azure-retail` | `tenant_id`, `service_name` (default "Virtual Machines"), `region`, `sku`, `currency` (default "USD") | Azure Retail Prices catalog lookup (max 100 rows) |
| GET | `/v1/pricing/google-cloud-retail` | `tenant_id`, `service_name` (default "Compute Engine"), `region`, `sku_query`, `currency` (default "USD") | Google Cloud Billing Catalog lookup (max 100 rows) |

**Azure pricing response (200):**
```json
{
  "provider": "Microsoft Azure Retail Prices API",
  "api_version": "2023-01-01-preview",
  "retrieved_at": "2026-09-29T...",
  "source_url": "https://prices.azure.com/api/retail/prices",
  "query": {"service_name": "...", "region": "...", "sku": "...", "currency": "USD"},
  "prices": [{"serviceName": "...", "retailPrice": "0.096", ...}],
  "returned": 1,
  "truncated": false,
  "commercial_basis": "Public retail list rates only; ...",
  "persisted": false,
  "execution_permitted": false
}
```

**Google pricing response (200):**
```json
{
  "provider": "Google Cloud Billing Catalog API",
  "api_version": "v1",
  "retrieved_at": "2026-09-29T...",
  "source_url": "https://cloudbilling.googleapis.com/v1/services",
  "query": {"service_name": "...", "region": "...", "sku_query": "...", "currency": "USD"},
  "prices": [{"serviceName": "...", "skuId": "...", "retailPrice": "0.096", "tiered_rates": [...], ...}],
  "returned": 1,
  "truncated": false,
  "commercial_basis": "Public Google Cloud catalog list rates; ...",
  "persisted": false,
  "execution_permitted": false
}
```

**Pricing error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Invalid query params | `{"error": "<message>", "execution_permitted": false}` |
| 502 | Azure/Google API unreachable | `{"error": "<message>", "execution_permitted": false}` |
| 503 | Google API key not configured | `{"error": "GOOGLE_CLOUD_BILLING_API_KEY is not configured...", "execution_permitted": false}` |

---

### 1.4 Placement Scenarios

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/placement/scenarios?tenant_id=<uuid>` | List saved comparison snapshots (LIMIT 100) |
| POST | `/v1/placement/scenarios` | Save a new comparison snapshot |

**GET response (200):**
```json
{
  "tenant_id": "dcc00000-0000-4000-8000-000000000001",
  "scenarios": [
    {
      "id": "uuid",
      "name": "Lab comparison",
      "schema_version": "placement-tco-comparison.v1",
      "payload": {...},
      "payload_sha256": "abc123...",
      "created_by": null,
      "created_at": "2026-09-29T..."
    }
  ],
  "status": "draft_snapshots",
  "execution_permitted": false
}
```

**POST request body:**
```json
{
  "tenant_id": "dcc00000-0000-4000-8000-000000000001",
  "name": "Lab comparison",
  "payload": {
    "schema_version": "placement-tco-comparison.v1",
    "assumptions": {
      "currency": "USD",
      "horizon_months": 36
    },
    "sources": {
      "onprem": {"type": "Vendor quote / contract", "reference": "Q-123", "observed_on": "2026-09-25"},
      "cloud": {"type": "Vendor quote / contract", "reference": "Q-456", "observed_on": "2026-09-25"}
    },
    "results": {
      "onprem": {"npv": 1.0},
      "cloud": {"npv": 1.0}
    }
  }
}
```

**POST response (201):**
```json
{
  "tenant_id": "dcc00000-0000-4000-8000-000000000001",
  "scenario": {
    "id": "uuid",
    "name": "Lab comparison",
    "schema_version": "placement-tco-comparison.v1",
    "payload": {...},
    "payload_sha256": "abc123...",
    "created_at": "2026-09-29T..."
  },
  "status": "draft_snapshot",
  "execution_permitted": false
}
```

**POST error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Invalid body/validation | `{"error": "<message>", "execution_permitted": false}` |
| 403 | Origin not localhost | `{"error": "same_origin_required", "execution_permitted": false}` |
| 404 | Not a POST route | `{"error": "route_not_found", "execution_permitted": false}` |
| 503 | Database unavailable | `{"error": "placement_snapshot_database_unavailable", "execution_permitted": false}` |

---

### 1.5 Static Assets

| Method | Path | Content-Type | Description |
|--------|------|--------------|-------------|
| GET | `/` | `text/html; charset=utf-8` | Main UI (index.html) |
| GET | `/assets/onboarding.js` | `text/javascript; charset=utf-8` | Onboarding module |
| GET | `/assets/topology.js` | `text/javascript; charset=utf-8` | Topology graph module |
| GET | `/assets/azure-prices.js` | `text/javascript; charset=utf-8` | Azure prices module |
| GET | `/assets/placement-comparison.js` | `text/javascript; charset=utf-8` | Placement comparison module |
| GET | `/assets/placement-scenarios.js` | `text/javascript; charset=utf-8` | Placement scenarios module |

---

## 2. Authentication & Authorization Gaps

### 2.1 No Authentication Mechanism

**Severity: CRITICAL**

The API has **no authentication whatsoever**. Any process that can reach the loopback port can call every endpoint. The server relies solely on:

- Loopback binding (`127.0.0.1`, `::1`, `localhost` only)
- PostgreSQL Row-Level Security (RLS) for tenant isolation

**Missing:**
- No API key, bearer token, or session cookie verification
- No user identity — `created_by` is always `NULL` in placement snapshots
- No authorization layer beyond RLS (no role checks, no permission model)
- No audit trail of who accessed what

### 2.2 Tenant ID is Client-Supplied

**Severity: HIGH**

The `tenant_id` is passed as a query parameter by the client. While RLS will correctly scope data to that tenant, there is no verification that the caller is authorized to access that tenant. Any local process can pass any valid tenant UUID and read that tenant's data.

### 2.3 No CSRF Protection

**Severity: MEDIUM**

The POST endpoint checks `Origin` but does not use CSRF tokens. The Origin check is a weak defense (only verifies the request came from localhost). A malicious local page could still trigger POST requests if it can determine the port.

### 2.4 No CORS Headers

**Severity: LOW**

No `Access-Control-Allow-Origin` or related CORS headers are returned. This is acceptable for a loopback-only server but would need to be addressed if the server is ever exposed beyond localhost.

### 2.5 No Request Signing

**Severity: MEDIUM**

Requests are not signed or verified for integrity. A local MITM (e.g., compromised proxy) could modify request bodies or query parameters.

---

## 3. Rate Limiting Needs

### 3.1 No Rate Limiting

**Severity: HIGH**

There is **no rate limiting** on any endpoint. This exposes the server to:

- **Database exhaustion:** Each request acquires a connection from the pool (max 8). A flood of requests will exhaust the pool and cause 503s for all tenants.
- **External API abuse:** The pricing endpoints call Azure/Google APIs. Without rate limiting, a local process could hammer those external APIs, potentially triggering provider-side throttling or blocking.
- **Resource exhaustion:** Large result sets (e.g., `/v1/analytics` with 5000 rows) could be requested repeatedly.

### 3.2 Recommended Rate Limits

| Endpoint Class | Suggested Limit | Rationale |
|----------------|-----------------|-----------|
| Health/Readiness | 60 req/min | Monitoring probes |
| Core data (GET) | 120 req/min per tenant | Normal UI usage |
| Pricing (GET) | 30 req/min per tenant | External API cost control |
| Placement POST | 10 req/min per tenant | Write operation |
| Static assets | 300 req/min | Browser loading |

### 3.3 Concurrency Controls

The database pool has `max_size=8` and `timeout=3`. This is a global limit, not per-tenant. A single tenant could consume all 8 connections. Consider:
- Per-tenant connection limits
- Request queuing with timeouts
- Circuit breaker for external API calls

---

## 4. Request/Response Format Details

### 4.1 Content Negotiation

- **Request:** POST requires `Content-Type: application/json`
- **Response:** All JSON responses use `application/json; charset=utf-8`
- **Static assets:** Served with appropriate `text/javascript` or `text/html` content types

### 4.2 Response Headers

All responses include:
- `Content-Type`
- `Content-Length`
- `Cache-Control: no-store` (JSON) or `no-cache` (static assets)

**Missing headers:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (if ever exposed over HTTPS)
- `Content-Security-Policy`

### 4.3 Error Format

Errors return a consistent JSON structure:
```json
{"error": "<machine_readable_code_or_message>"}
```

Some errors include additional context:
```json
{"error": "database_unavailable_or_schema_missing", "read_only": true, "execution_permitted": false}
```

### 4.4 Pagination

**Not implemented.** All endpoints return fixed-size result sets with `LIMIT` clauses. There is no cursor-based or offset-based pagination. Clients cannot request additional pages.

### 4.5 Filtering

Minimal filtering capability:
- `window_days` on `/v1/overview` and `/v1/analytics` (1–90 days)
- `demo=synthetic` on `/v1/overview` and `/v1/costs` to show synthetic data
- Pricing endpoints support `region`, `sku`/`sku_query`, `currency`

No filtering on core data endpoints (e.g., filter assets by type, facilities by status).

### 4.6 Sorting

Not configurable. All endpoints use hardcoded `ORDER BY` clauses (typically `created_at DESC` or `name ASC`).

---

## 5. Security Strengths

| Control | Implementation |
|---------|---------------|
| SQL Injection prevention | Parameterized queries throughout |
| Input validation | UUID format check, regex validation on pricing params, length limits |
| RLS enforcement | `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on all tables |
| Tenant isolation | `dcc.tenant_id` set per transaction, RLS policy scopes all queries |
| External API bounds | Response size limits (1–2 MB), no redirect following, timeout=8s |
| Request body limits | POST body limited to 70,000 bytes |
| Loopback-only binding | `serve()` rejects non-loopback hosts |
| No secrets in responses | API keys never returned; `credential_ref` is a reference only |
| Immutable snapshots | Placement snapshots have `BEFORE UPDATE OR DELETE` trigger rejecting mutations |
| Synthetic data quarantine | Synthetic data excluded unless `demo=synthetic` is explicitly set |

---

## 6. Summary of Findings

### Critical (must fix before any non-local exposure)

1. **No authentication** — any local process can access all endpoints
2. **No rate limiting** — vulnerable to resource exhaustion and external API abuse

### High (should fix before production)

3. **Client-supplied tenant_id** — no authorization verification
4. **No request signing** — integrity not guaranteed
5. **No pagination** — large result sets could impact performance

### Medium (should address)

6. **No CSRF tokens** — Origin check is weak
7. **No security headers** — missing standard HTTP security headers
8. **No per-tenant concurrency limits** — single tenant can exhaust connection pool

### Low (nice to have)

9. **No CORS headers** — acceptable for loopback-only
10. **No filtering/sorting options** — limited query flexibility
11. **No audit logging** — `log_message` is suppressed; no request audit trail

---

## 7. Recommendations

1. **Add authentication layer** — even for local use, implement a simple token-based auth (e.g., a local API key stored in a file or environment variable) to prevent unauthorized local access.
2. **Implement rate limiting** — use a token-bucket or sliding-window algorithm per tenant and per endpoint class.
3. **Add security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`.
4. **Implement pagination** — cursor-based pagination for endpoints that can return large result sets.
5. **Add audit logging** — log all requests with timestamp, tenant, endpoint, and outcome (without sensitive data).
6. **Add CSRF tokens** — for the POST endpoint, require a CSRF token in addition to Origin check.
7. **Add request signing** — HMAC-based request signing for integrity verification.
8. **Document the API** — generate OpenAPI/Swagger documentation from the endpoint definitions.
