# DCC Test Coverage Audit

**Date:** 2026-09-29  
**Project:** data-center-commander  
**Python:** 3.11.15  
**Test framework:** pytest 9.1.1 + pytest-cov 7.1.0

---

## Summary

| Metric | Value |
|--------|-------|
| Total statements | 451 |
| Missed statements | 225 |
| **Overall coverage** | **50%** |
| Test files | 2 |
| Test cases | 20 (+ 4 subtests) |
| All tests passing | ✅ Yes |

---

## Module Coverage

| Module | Statements | Missed | Coverage |
|--------|-----------|--------|----------|
| `src/dcc/api.py` | 289 | 188 | **35%** |
| `src/dcc/azure_prices.py` | 65 | 14 | **78%** |
| `src/dcc/google_prices.py` | 97 | 23 | **76%** |

---

## Top 20 Untested Code Paths by Risk

Ranked by risk (security impact × complexity × blast radius).

### 1. `api.py` — `do_POST /v1/placement/scenarios` (lines 420–457)
**Risk: CRITICAL** — Write path with tenant isolation, origin validation, JSON parsing, DB insert. No test exercises the POST handler end-to-end. Origin check, content-length validation, tenant scoping, and the INSERT with `set_config` are all untested.

### 2. `api.py` — `do_GET /v1/costs` (lines 346–387)
**Risk: HIGH** — Complex 3-query route (estimates, prices, actuals) with synthetic-data filtering logic. The `synthetic_prices` / `show_synthetic` branching and the `demo=synthetic` query parameter path are completely untested.

### 3. `api.py` — `do_GET /v1/analytics` (lines 261–305)
**Risk: HIGH** — 4-query route (series, quality, telemetry, workflow health) with window_days parameter. The `window_days` validation, SQL parameterization, and model_policy response are untested.

### 4. `api.py` — `do_GET /v1/topology` (lines 244–260)
**Risk: HIGH** — 2-query route (nodes + edges) with 3-table JOINs. Tenant scoping on asset_relationships and the LEFT JOIN chain are untested.

### 5. `api.py` — `do_GET /v1/overview` (lines 388–411)
**Risk: HIGH** — 4-query route with synthetic-data suppression logic. The `synthetic` / `show_synthetic` branching that zeros out facility_count, kpis, and open_workflows is untested.

### 6. `api.py` — `connect_pool()` (lines 62–74)
**Risk: HIGH** — Database connection pool creation with psycopg. The `DCC_DATABASE_URL` env var check, ImportError handling for missing postgres extra, and pool configuration are untested.

### 7. `api.py` — `validate_placement_snapshot` error paths (lines 28–57)
**Risk: HIGH** — Input validation for placement snapshots. Only the happy path and one invalid date are tested. Missing: name length checks, schema_version validation, currency format, horizon range, source field validation, 64 KiB size limit, and the `allow_nan=False` JSON encoding path.

### 8. `api.py` — `do_GET /v1/placement/scenarios` (lines 127–145)
**Risk: MEDIUM** — Read path for placement snapshots with tenant scoping. The `set_config` call, SELECT query, and error handling (ValueError → 400, Exception → 503) are untested.

### 9. `api.py` — `do_GET` asset serving (lines 147–159)
**Risk: MEDIUM** — Static JS asset serving with 5 allowed paths. The path allowlist, file reading, 404 handling, and cache headers are untested.

### 10. `api.py` — `do_GET /v1/facilities` (lines 306–312)
**Risk: MEDIUM** — 2-table JOIN query with tenant scoping. Untested.

### 11. `api.py` — `do_GET /v1/assets` (lines 313–320)
**Risk: MEDIUM** — 3-table LEFT JOIN query with tenant scoping. Untested.

### 12. `api.py` — `do_GET /v1/workflows` (lines 321–327)
**Risk: MEDIUM** — Query with CASE-based ordering and tenant scoping. Untested.

### 13. `api.py` — `do_GET /v1/connectors` (lines 328–333)
**Risk: MEDIUM** — Simple SELECT with tenant scoping. Untested.

### 14. `api.py` — `do_GET /v1/capacity` (lines 334–339)
**Risk: MEDIUM** — DISTINCT ON query with tenant scoping. Untested.

### 15. `api.py` — `do_GET /v1/evidence` (lines 340–345)
**Risk: MEDIUM** — SELECT with tenant scoping and LIMIT. Untested.

### 16. `api.py` — `database_readiness` error paths (lines 97, 103–104)
**Risk: MEDIUM** — The `except Exception` fallback returning `database: unavailable` and the incomplete-schema path returning `schema: incomplete` are untested.

### 17. `api.py` — `serve()` (lines 460–476)
**Risk: MEDIUM** — Server startup, pool initialization, graceful shutdown. Only the loopback validation is tested.

### 18. `azure_prices.py` — HTTP error handling (lines 66–75)
**Risk: MEDIUM** — HTTPError → ConnectionError, URLError/TimeoutError/OSError → ConnectionError, JSONDecodeError → ConnectionError, and response contract validation paths are untested.

### 19. `azure_prices.py` — Row filtering edge cases (lines 80–86)
**Risk: LOW** — Invalid/missing retailPrice, non-finite/negative price filtering, and non-dict item skipping are untested.

### 20. `google_prices.py` — Service/SKU matching edge cases (lines 76–100)
**Risk: LOW** — No-match service error, invalid SKU response contract, region filtering, and tiered rate parsing edge cases are untested.

---

## Recommendations

1. **Prioritize `api.py` POST path** — the only write endpoint has zero coverage. Add integration tests with a mocked pool to verify origin validation, tenant scoping, and INSERT behavior.

2. **Add route-level tests for all GET endpoints** — use a fake pool/connection pattern (like the existing `database_readiness` tests) to exercise each route's SQL, tenant scoping, and error handling.

3. **Test `validate_placement_snapshot` error branches** — parameterized tests for each validation rule (name length, schema version, currency, horizon, source fields, size limit).

4. **Mock external API error paths** — add tests for HTTPError, URLError, JSON decode errors, and response contract violations in both `azure_prices.py` and `google_prices.py`.

5. **Test `connect_pool()`** — mock psycopg imports to verify env var handling, ImportError fallback, and pool configuration.

---

## Test Files

| File | Tests | Focus |
|------|-------|-------|
| `tests/test_azure_prices.py` | 6 | Azure/Google pricing fetch, HTTP route delegation, input validation |
| `tests/test_contracts.py` | 14 | Schema/UI contract assertions, readiness, tenant validation, placement snapshot validation |
