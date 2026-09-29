# Data Center Commander — Comprehensive Test Strategy

**Date:** 2026-09-29  
**Project:** data-center-commander  
**Python:** 3.11+  
**Test frameworks:** pytest 9.1.1, unittest, hypothesis, locust, playwright  
**Current coverage:** 50% (451 statements, 225 missed)  
**Existing tests:** 26 test files, ~20 test cases  

---

## 1. Executive Summary

This document defines a multi-layered test strategy for Data Center Commander (DCC), a read-only, PostgreSQL-backed data-center operations command view. The strategy addresses eight test dimensions: unit, integration, end-to-end, performance, security, fuzzing, property-based, and visual regression.

**Current state:** The project has 26 test files covering API contracts, Azure/Google pricing adapters, and schema validation. Coverage is 50% with critical gaps in the POST endpoint, most GET routes, and all forecasting/economics/quality modules.

**Target state:** ≥85% line coverage, ≥90% branch coverage, all critical paths exercised, security boundaries verified, performance baselines established.

---

## 2. Test Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Pyramid                              │
├─────────────────────────────────────────────────────────────┤
│  E2E (Playwright)     │ Full user journeys, UI + API + DB   │
│  ─────────────────────┼────────────────────────────────────  │
│  Integration (pytest) │ API routes + DB + adapters          │
│  ─────────────────────┼────────────────────────────────────  │
│  Unit (pytest/unittest)│ Pure functions, classes, modules   │
│  ─────────────────────┼────────────────────────────────────  │
│  Property (hypothesis) │ Invariants, round-trips, boundaries │
│  ─────────────────────┼────────────────────────────────────  │
│  Fuzz (hypothesis)    │ Malformed inputs, edge cases        │
│  ─────────────────────┼────────────────────────────────────  │
│  Security (pytest)    │ AuthN/AuthZ, injection, RLS        │
│  ─────────────────────┼────────────────────────────────────  │
│  Performance (locust) │ Load, stress, soak, benchmarks      │
│  ─────────────────────┼────────────────────────────────────  │
│  Visual (Playwright)  │ Screenshot diff, responsive layout  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Unit Tests

### 3.1 Economics Module (`src/dcc/economics/`)

#### 3.1.1 TCO Calculator (`tco.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `TCOAssumptions.__post_init__` | Valid assumptions; invalid currency (non-3-letter, lowercase, non-alpha); horizon 0/51/1.5; discount rate -0.1/1.1; escalation -1.1/1.1; contingency -0.1/1.1; tax rate -0.1/1.1; include_tax non-bool | HIGH |
| `TCOCostBreakdown.__post_init__` | All zero costs; negative cost values; refresh_interval 0/51/-1; non-numeric cost | HIGH |
| `TCOCostBreakdown` properties | `total_upfront` sums correctly; `total_annual_opex` sums correctly; `terminal_net` = decommission - residual; `total_capex` includes refresh | MEDIUM |
| `_discount_factor` | rate=0 → 1.0; rate=0.08, year=1 → 0.9259; year=0 → 1.0 | HIGH |
| `_escalation_factor` | rate=0 → 1.0; rate=0.03, year=1 → 1.03; negative rate | HIGH |
| `_compute_yearly_cash_flows` | Year 0 has only capex; years 1..N have opex; refresh at correct intervals; terminal only in final year; escalation applied correctly; discount factor applied | HIGH |
| `_equivalent_annual_cost` | rate=0 → pv/years; rate=0.08, years=10 → correct annuity; years=0 → ValueError | HIGH |
| `evaluate_tco` | Zero costs → all zeros; typical scenario → correct PV/EAC; after-tax with tax_rate>0; unit economics with capacity/rack/area/energy; yearly_cash_flows length = horizon+1 | HIGH |
| `compare_tco` | Single scenario → all deltas zero; multiple scenarios → correct deltas; baseline_index out of range → ValueError; empty list → ValueError | HIGH |
| `run_tco_sensitivity` | Each supported parameter; unsupported parameter → ValueError; empty values → ValueError; results monotonic where expected | MEDIUM |
| `TCOEngine` | add/remove/clear scenarios; evaluate by name; compare with baseline name; sensitivity by scenario name; to_dict serialization | MEDIUM |
| `quick_tco` | All defaults → zero result; typical inputs → correct result; with unit economics | MEDIUM |
| `tco_breakdown_by_category` | Correct category sums | LOW |
| `tco_cost_per_unit` | kw/rack/m2/kwh; unit_value ≤ 0 → None; unsupported unit_type → ValueError | LOW |

#### 3.1.2 Allocation (`allocation.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Allocation fraction validation | Fractions sum to 1.0; individual fraction bounds [0,1]; method-specific validation | HIGH |
| Direct meter allocation | 100% to metered workload; remainder unallocated | HIGH |
| Capacity share allocation | Proportional to capacity; zero capacity → equal share | HIGH |
| Allocation uncertainty | Lower ≤ upper bounds; coverage in [0,1] | MEDIUM |

#### 3.1.3 Scenarios (`scenarios.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Scenario construction | Valid scenario; missing required fields; invalid cost_behavior | HIGH |
| Scenario comparison | Side-by-side NPV/EAC; baseline selection; delta computation | HIGH |
| Sensitivity sweep | Parameter range; monotonicity; boundary values | MEDIUM |

#### 3.1.4 Estimates (`estimates.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Estimate rollup | Line item aggregation; phase grouping; currency consistency | HIGH |
| Price link validation | Sourced line requires price observation; unpriced line without basis → error | HIGH |
| Lifecycle PV | Discounted cash flow; escalation; horizon boundary | HIGH |

#### 3.1.5 Tariffs (`tariffs.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Tariff period validation | valid_from < valid_to; overlapping periods; open-ended | MEDIUM |
| Rate extraction | Tiered rates; time-of-use; demand charges | MEDIUM |

#### 3.1.6 Budget (`budget.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Budget vs actual | Variance computation; over/under detection | MEDIUM |
| Period aggregation | Monthly/quarterly/annual rollup | LOW |

#### 3.1.7 Reconciliation (`reconciliation.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Estimate-to-actual | Line-level reconciliation; variance thresholds | HIGH |
| Cost allocation | Workload allocation; unallocated remainder | MEDIUM |

#### 3.1.8 Unit Economics (`unit.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Cost per kW-year | EAC / capacity; zero capacity → None | MEDIUM |
| Cost per rack-year | EAC / rack count | MEDIUM |
| Cost per m²-year | EAC / area | MEDIUM |
| Cost per kWh | PV / total energy | MEDIUM |

### 3.2 Forecasting Module (`src/dcc/forecasting/`)

#### 3.2.1 Capacity Forecast (`capacity.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `_validate_dimension` | Valid dimensions (all 10); invalid dimension → ValueError | HIGH |
| `_validate_horizon` | 1/365 valid; 0/365/366/non-int/bool → ValueError | HIGH |
| `_validate_data_points` | Empty list → ValueError; insufficient points for method; sufficient points | HIGH |
| `_compute_linear_trend` | Perfect linear fit → r²=1.0; flat line → slope=0; single point → slope=0; two points → exact fit | HIGH |
| `_compute_moving_average` | Window larger than data; window=1; normal case | MEDIUM |
| `_compute_exponential_smoothing` | Single point; two points; convergence; alpha=0/1 | MEDIUM |
| `_compute_volatility` | Zero variance → 0.0; constant values → 0.0; high variance | MEDIUM |
| `_assess_quality` | Fresh data → good; stale data → estimated; suspicious growth → suspect; high volatility → suspect; low coverage → estimated | HIGH |
| `_generate_forecast_points` | Correct number of points; non-negative predictions; uncertainty grows with horizon; confidence decreases with horizon | HIGH |
| `forecast_capacity` | End-to-end with valid data; provenance contains method/points/r²; execution_permitted=False | HIGH |
| `forecast_from_snapshots` | Dict input parsing; ISO datetime string; naive datetime → UTC; invalid dicts skipped | HIGH |
| `select_best_method` | <2 points → moving_average; 2 points → moving_average; good linear fit → linear; high volatility → exponential_smoothing; default → moving_average | MEDIUM |
| `compute_capacity_at_risk` | No dates above threshold → severity=none; 1-3 dates → low; 4-7 → medium; 8+ → high | MEDIUM |

#### 3.2.2 Load Forecast (`load.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Load prediction | Historical pattern; seasonality; trend | MEDIUM |
| Confidence intervals | Wider with less data; narrower with more data | MEDIUM |

#### 3.2.3 Price Forecast (`price.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Price trend | Linear extrapolation; confidence bounds | MEDIUM |
| Seasonal adjustment | Peak/off-peak detection | LOW |

#### 3.2.4 Failure Prediction (`failure.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Failure probability | Feature-based scoring; threshold classification | HIGH |
| Label requirement | No labels → no forecast (fail-closed) | HIGH |

#### 3.2.5 Calibration (`calibration.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Probability calibration | Reliability diagram; Brier score | MEDIUM |

#### 3.2.6 Drift Detection (`drift.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Data drift | Distribution shift detection; feature drift | MEDIUM |
| Model drift | Performance degradation detection | MEDIUM |

#### 3.2.7 Backtest (`backtest.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Time-series backtest | Walk-forward validation; no leakage | HIGH |
| Error metrics | MAE/RMSE/MAPE computation | MEDIUM |

#### 3.2.8 Features (`features.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Feature extraction | Rolling statistics; lag features; interaction terms | MEDIUM |
| Feature selection | Correlation filtering; importance ranking | LOW |

#### 3.2.9 Maintenance (`maintenance.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Maintenance scheduling | Interval-based; condition-based; predictive | MEDIUM |
| Work order prioritization | Criticality × age; SLA compliance | MEDIUM |

### 3.3 Quality Module (`src/dcc/quality/`)

#### 3.3.1 Quality Engine (`engine.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `completeness_score` | All fields present → 1.0; none present → 0.0; partial → proportional; empty records → 0.0; optional fields contribute 20% | HIGH |
| `freshness_score` | Fresh data → 1.0; data at max_age → 1.0; data at 7× max_age → 0.0; linear decay in between; empty timestamps → 0.0; naive datetime → UTC | HIGH |
| `consistency_score` | All pass → 1.0; none pass → 0.0; partial → proportional; empty records → 0.0; rule exception → False | HIGH |
| `accuracy_score` | All match → 1.0; none match → 0.0; partial → proportional; empty records → 0.0; tolerance boundary; non-numeric expected | HIGH |
| `QualityEngine.score_source` | All dimensions scored; overall = weighted sum; recommendations for <0.5 and <0.8; custom weights | HIGH |
| `QualityEngine._recommendations` | Score <0.5 → critical; 0.5-0.8 → needs improvement; ≥0.8 → no recommendation | MEDIUM |

#### 3.3.2 Anomaly Detection (`anomaly.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Z-score anomaly | Normal data → no anomaly; outlier → anomaly; threshold tuning | HIGH |
| IQR anomaly | Normal range; outside 1.5×IQR; outside 3×IQR | MEDIUM |
| Seasonal anomaly | Expected seasonal pattern; unexpected deviation | MEDIUM |

#### 3.3.3 Freshness (`freshness.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Source freshness | Last read time; stale threshold; never read | MEDIUM |
| Data lag | Expected lag; excessive lag detection | MEDIUM |

### 3.4 Validation Module (`src/dcc/validation/`)

#### 3.4.1 Consistency (`consistency.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Cross-source validation | Matching values → pass; mismatched → fail; missing → skip | HIGH |
| Severity classification | pass/warn/fail/skip correct assignment | HIGH |
| Finding serialization | to_dict produces correct structure | MEDIUM |

#### 3.4.2 Intervals (`intervals.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Interval alignment | Overlapping intervals; gap detection; boundary alignment | HIGH |
| Interval merging | Adjacent intervals merge; overlapping merge; disjoint stay separate | MEDIUM |

#### 3.4.3 Boundaries (`boundaries.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Meter boundary | Import/export/bidirectional; nested boundaries; boundary validation | HIGH |

#### 3.4.4 Schema (`schema.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Schema validation | Valid record; missing required field; wrong type; extra field | HIGH |

#### 3.4.5 Units (`units.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Unit conversion | kW→W; kWh→MWh; °C→°F; invalid conversion | HIGH |
| Unit validation | Valid unit; unknown unit; incompatible units | MEDIUM |

### 3.5 Provenance Module (`src/dcc/provenance/`)

#### 3.5.1 Tracker (`tracker.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `register_source` | Valid source; content hash computed; metadata stored | HIGH |
| `record_transformation` | Links inputs to output; hash chain; tenant isolation | HIGH |
| `create_record` | Complete provenance; record hash; lineage steps | HIGH |
| `get_lineage` | Upstream walk; downstream walk; max_depth; not found | HIGH |
| `verify_chain` | Valid chain → valid=True; tampered hash → valid=False; broken link → valid=False; empty chain → valid=True | HIGH |
| `get_tenant_summary` | Correct counts; chain_valid flag | MEDIUM |

### 3.6 Adapters Module (`src/dcc/adapters/`)

#### 3.6.1 Registry (`registry.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Adapter registration | Valid adapter; duplicate; missing required fields | HIGH |
| Adapter lookup | By ID; by name; not found | MEDIUM |

#### 3.6.2 Cloud (`cloud.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Azure adapter | Valid response; HTTP error; timeout; malformed JSON | HIGH |
| Google adapter | Valid response; missing API key; HTTP error; timeout | HIGH |

#### 3.6.3 BMS/EPMS/CMMS/Meter/Hypervisor/OEM/Utility/Weather

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| Each adapter | Valid response; error handling; timeout; malformed data; rate limiting | MEDIUM |

### 3.7 API Module (`src/dcc/api.py`)

#### 3.7.1 Core Functions

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `parse_tenant` | Valid UUID; invalid UUID; empty; multiple values; non-string | HIGH |
| `validate_placement_snapshot` | Valid payload; name too long/short; wrong schema_version; invalid currency; horizon 0/121; missing source fields; invalid date; payload >64KiB; NaN in JSON | HIGH |
| `connect_pool` | Valid DSN; missing DSN → RuntimeError; ImportError for psycopg | HIGH |
| `database_readiness` | Pool=None → not_configured; valid pool → ok; missing RLS → not_enforced; exception → unavailable | HIGH |
| `serve` | Loopback OK; non-loopback → ValueError | HIGH |

#### 3.7.2 GET Routes (all currently untested)

| Endpoint | Test Cases | Priority |
|----------|-----------|----------|
| `/v1/overview` | Valid tenant; synthetic data suppression; demo mode; no telemetry | HIGH |
| `/v1/facilities` | Valid tenant; empty result; tenant isolation | HIGH |
| `/v1/assets` | Valid tenant; empty result; tenant isolation | HIGH |
| `/v1/workflows` | Valid tenant; empty result; ordering | HIGH |
| `/v1/connectors` | Valid tenant; empty result | MEDIUM |
| `/v1/capacity` | Valid tenant; DISTINCT ON; empty result | MEDIUM |
| `/v1/evidence` | Valid tenant; empty result; LIMIT | MEDIUM |
| `/v1/costs` | Valid tenant; synthetic filtering; demo mode; estimates/prices/actuals | HIGH |
| `/v1/analytics` | Valid tenant; window_days validation; 4-query execution; model_policy | HIGH |
| `/v1/topology` | Valid tenant; nodes+edges; empty result | MEDIUM |
| `/v1/placement/scenarios` | Valid tenant; empty result; tenant isolation | MEDIUM |
| `/healthz` | Always 200; correct body | HIGH |
| `/readyz` | Ready; not ready; pool=None | HIGH |
| `/v1/pricing/azure-retail` | Valid params; invalid params; ConnectionError | HIGH |
| `/v1/pricing/google-cloud-retail` | Valid params; missing API key; ConnectionError | HIGH |
| `/assets/*.js` | Valid asset; invalid path → 404; cache headers | MEDIUM |
| `/` | HTML content; content-type | LOW |
| Unknown route | 404 response | MEDIUM |

#### 3.7.3 POST Route (currently untested — CRITICAL)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `do_POST /v1/placement/scenarios` | Valid body → 201; invalid Origin → 403; missing Content-Length → 400; body >70000 → 400; non-JSON content-type → 400; invalid JSON → 400; non-dict body → 400; invalid tenant → 400; invalid snapshot → 400; DB error → 503; correct INSERT with set_config | CRITICAL |

### 3.8 Azure/Google Price Modules

#### 3.8.1 Azure (`azure_prices.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `fetch_azure_retail_prices` | Valid response; HTTPError → ConnectionError; URLError → ConnectionError; TimeoutError → ConnectionError; JSONDecodeError → ConnectionError; invalid service_name → ValueError; invalid currency → ValueError; empty Items; missing retailPrice; negative price; non-dict item | HIGH |

#### 3.8.2 Google (`google_prices.py`)

| Test Area | Test Cases | Priority |
|-----------|-----------|----------|
| `fetch_google_cloud_prices` | Valid 2-step response; no API key → ConnectionError; HTTPError; invalid service; invalid SKU; region filtering; tiered rates; pagination; truncated flag | HIGH |

---

## 4. Integration Tests

### 4.1 API + Database Integration

**Setup:** Spin up a test PostgreSQL instance (or use `testing.postgresql`), apply `schema.sql` + migrations, seed with `demo_seed.sql`.

| Test | Description | Priority |
|------|-------------|----------|
| `test_overview_with_data` | Seed tenant + facilities + KPIs → `/v1/overview` returns correct counts | HIGH |
| `test_overview_synthetic_suppression` | Seed synthetic KPIs → `/v1/overview` without `demo=synthetic` returns zeros | HIGH |
| `test_overview_demo_mode` | Seed synthetic KPIs → `/v1/overview?demo=synthetic` returns data | HIGH |
| `test_analytics_window_days` | Seed KPI observations → `/v1/analytics?window_days=7` filters correctly | HIGH |
| `test_analytics_invalid_window` | `window_days=0` → 400; `window_days=91` → 400; `window_days=abc` → 400 | HIGH |
| `test_costs_synthetic_filtering` | Seed synthetic prices → `/v1/costs` without demo → empty; with demo → data | HIGH |
| `test_costs_estimate_rollup` | Seed estimate + line items → `/v1/costs` returns correct rollup | HIGH |
| `test_placement_snapshot_round_trip` | POST snapshot → GET snapshots → verify data matches | CRITICAL |
| `test_placement_snapshot_tenant_isolation` | POST to tenant A → GET from tenant B → empty | CRITICAL |
| `test_placement_snapshot_immutability` | Attempt UPDATE/DELETE → trigger rejects | HIGH |
| `test_topology_joins` | Seed assets + relationships → `/v1/topology` returns correct nodes/edges | MEDIUM |
| `test_tenant_isolation_all_endpoints` | For each endpoint: tenant A data not visible to tenant B | CRITICAL |
| `test_rls_enforcement` | Verify `set_config('dcc.tenant_id', ...)` is called; verify RLS policies exist on all tables | HIGH |
| `test_readonly_transaction` | Verify `SET TRANSACTION READ ONLY` is set on all GET queries | HIGH |
| `test_health_readiness` | `/healthz` always 200; `/readyz` reflects DB state | HIGH |
| `test_static_assets` | Each `/assets/*.js` returns 200 with correct content-type; invalid path → 404 | MEDIUM |
| `test_pricing_azure_integration` | Mock HTTP → verify correct URL, timeout, params, response parsing | HIGH |
| `test_pricing_google_integration` | Mock HTTP → verify 2-step flow, API key, response parsing | HIGH |

### 4.2 Database Schema Integration

| Test | Description | Priority |
|------|-------------|----------|
| `test_schema_creates_all_tables` | Apply schema → verify all 30+ tables exist | HIGH |
| `test_rls_policies_exist` | Verify RLS enabled + forced on all tenant tables | HIGH |
| `test_rls_fail_closed` | Query without `set_config` → no rows returned | CRITICAL |
| `test_foreign_key_cascade` | Delete tenant → all child rows cascade | HIGH |
| `test_estimate_price_link_trigger` | Insert sourced line without price → rejected; insert with wrong currency → rejected | HIGH |
| `test_placement_snapshot_immutable_trigger` | UPDATE/DELETE on snapshots → rejected | HIGH |
| `test_estimate_cost_rollup_view` | Seed data → view returns correct aggregation | MEDIUM |
| `test_migrations_idempotent` | Apply migrations twice → no error | MEDIUM |
| `test_demo_seed_idempotent` | Apply demo seed twice → no error | MEDIUM |

### 4.3 Adapter Integration

| Test | Description | Priority |
|------|-------------|----------|
| `test_azure_adapter_end_to_end` | Mock urllib → verify request construction, timeout, response parsing | HIGH |
| `test_google_adapter_end_to_end` | Mock urllib → verify 2-step flow, pagination, tiered rate handling | HIGH |
| `test_adapter_error_handling` | HTTP 429 → ConnectionError; HTTP 500 → ConnectionError; timeout → ConnectionError | HIGH |
| `test_adapter_input_validation` | SQL injection attempt in service_name → ValueError; XSS attempt → ValueError | HIGH |

---

## 5. End-to-End Tests (Playwright)

### 5.1 User Journeys

| Journey | Steps | Priority |
|---------|-------|----------|
| **First-time setup** | Open UI → enter tenant UUID → verify overview loads → verify KPIs display | HIGH |
| **Demo mode toggle** | Open UI → click "Open synthetic demo" → verify SYNTHETIC DEMO banner → verify data appears → click "Exit synthetic demo" → verify data hidden | HIGH |
| **Navigation** | Click through all 11 nav items → verify each view loads → verify breadcrumb updates | HIGH |
| **Analytics refresh** | Navigate to Analytics → change window to 7 days → verify data refreshes → change to 90 days → verify | HIGH |
| **Cost analysis** | Navigate to Sizing & Economics → verify estimate cards → verify price book → verify actual costs | HIGH |
| **Azure price lookup** | Navigate to Sizing & Economics → fill Azure form → submit → verify results table | MEDIUM |
| **Placement comparison** | Navigate to Placement → fill comparison form → save draft snapshot → verify snapshot appears in list | HIGH |
| **Workflow queue** | Navigate to Operations Queue → search workflows → filter by status → export CSV | MEDIUM |
| **Evidence audit** | Navigate to Evidence & Audit → verify event list → verify hash chain | MEDIUM |
| **Auto-refresh** | Set refresh rate to 30s → verify auto-refresh occurs → set to Off → verify stops | LOW |
| **Responsive layout** | Resize to 1120px → verify 2-column grid → resize to 760px → verify single column → resize to 480px → verify compact layout | MEDIUM |

### 5.2 API E2E

| Test | Description | Priority |
|------|-------------|----------|
| `test_full_api_flow` | Start server → health check → readiness → query all endpoints → verify responses | HIGH |
| `test_server_refuses_non_loopback` | Attempt to bind to 0.0.0.0 → ValueError | HIGH |
| `test_concurrent_requests` | 10 concurrent requests → all succeed (within pool limits) | MEDIUM |
| `test_graceful_shutdown` | SIGTERM → server stops → pool closed | LOW |

---

## 6. Performance Tests

### 6.1 Load Testing (Locust)

| Scenario | Users | Duration | Success Criteria |
|----------|-------|----------|-----------------|
| **Light load** | 5 | 5 min | p95 < 200ms, p99 < 500ms, 0 errors |
| **Moderate load** | 20 | 10 min | p95 < 500ms, p99 < 1s, <0.1% errors |
| **Heavy load** | 50 | 15 min | p95 < 1s, p99 < 2s, <1% errors |
| **Spike test** | 5→50→5 | 5 min | Recovery < 30s, no cascading failures |
| **Soak test** | 10 | 4 hours | No memory leaks, no connection pool exhaustion, stable latency |

### 6.2 Endpoint-Specific Benchmarks

| Endpoint | Target p95 | Target p99 | Notes |
|----------|-----------|-----------|-------|
| `/healthz` | <10ms | <20ms | No DB |
| `/readyz` | <50ms | <100ms | 2 DB queries |
| `/v1/overview` | <100ms | <200ms | 4 DB queries |
| `/v1/analytics` | <500ms | <1s | 4 DB queries, date_trunc |
| `/v1/costs` | <500ms | <1s | 3 DB queries, CROSS JOIN LATERAL |
| `/v1/topology` | <200ms | <500ms | 2 DB queries, JOINs |
| `/v1/assets` | <100ms | <200ms | 1 DB query, LEFT JOINs |
| `/v1/placement/scenarios` (POST) | <200ms | <500ms | 1 DB query, INSERT |

### 6.3 Database Performance

| Test | Description | Priority |
|------|-------------|----------|
| `test_query_plan_analytics` | EXPLAIN ANALYZE `/v1/analytics` query → verify index usage | HIGH |
| `test_query_plan_costs` | EXPLAIN ANALYZE `/v1/costs` query → verify index usage | HIGH |
| `test_query_plan_overview` | EXPLAIN ANALYZE `/v1/overview` queries → verify index usage | HIGH |
| `test_connection_pool_exhaustion` | 8 concurrent analytics requests → verify pool behavior | HIGH |
| `test_n_plus_1_detection` | Verify no N+1 patterns in API routes | MEDIUM |
| `test_index_usage_on_large_tables` | Seed 100K rows → verify queries use indexes | MEDIUM |

### 6.4 Scalability Tests

| Test | Description | Priority |
|------|-------------|----------|
| `test_large_tenant_dataset` | 1M telemetry readings → query performance | MEDIUM |
| `test_many_tenants` | 100 tenants → RLS overhead | MEDIUM |
| `test_concurrent_tenants` | 10 tenants querying simultaneously → isolation + performance | MEDIUM |

---

## 7. Security Tests

### 7.1 Authentication & Authorization

| Test | Description | Priority |
|------|-------------|----------|
| `test_no_auth_required` | Verify all endpoints accessible without auth (documents current state) | HIGH |
| `test_tenant_id_enumeration` | Sequential UUIDs → verify trivial enumeration | HIGH |
| `test_tenant_isolation_rls` | Tenant A cannot read tenant B data via any endpoint | CRITICAL |
| `test_rls_fail_closed` | Missing `dcc.tenant_id` setting → no rows returned | CRITICAL |
| `test_rls_all_tables` | Verify RLS on all 30+ tenant tables (not just assets/evidence) | HIGH |
| `test_no_write_endpoints` | Verify only POST is `/v1/placement/scenarios`; all others read-only | HIGH |
| `test_readonly_transaction` | Verify `SET TRANSACTION READ ONLY` on all GET queries | HIGH |

### 7.2 Injection Tests

| Test | Description | Priority |
|------|-------------|----------|
| `test_sql_injection_tenant_id` | `tenant_id=' OR '1'='1` → ValueError | CRITICAL |
| `test_sql_injection_placement_name` | `name='; DROP TABLE assets;--` → safe handling | CRITICAL |
| `test_sql_injection_azure_filter` | `service_name=' or name eq 'x` → ValueError | HIGH |
| `test_xss_in_tenant_id` | `tenant_id=<script>alert(1)</script>` → ValueError | HIGH |
| `test_xss_in_placement_name` | `name=<img src=x onerror=alert(1)>` → safe handling | HIGH |
| `test_xss_in_api_response` | API returns data → UI escapes correctly | HIGH |
| `test_path_traversal_asset` | `/assets/../../../etc/passwd` → 404 | HIGH |
| `test_path_traversal_normalized` | `/assets/%2e%2e/%2e%2e/etc/passwd` → 404 | HIGH |

### 7.3 Input Validation

| Test | Description | Priority |
|------|-------------|----------|
| `test_placement_snapshot_size_limit` | Body >70000 bytes → 400 | HIGH |
| `test_placement_snapshot_64k_payload` | Payload >64KiB → ValueError | HIGH |
| `test_placement_snapshot_nan_json` | `NaN` in JSON → ValueError (allow_nan=False) | HIGH |
| `test_placement_snapshot_schema_version` | Wrong schema_version → ValueError | HIGH |
| `test_placement_snapshot_currency` | Invalid currency → ValueError | HIGH |
| `test_placement_snapshot_horizon` | 0/121/non-int → ValueError | HIGH |
| `test_placement_snapshot_dates` | Invalid date format → ValueError | HIGH |
| `test_content_type_enforcement` | POST without `application/json` → 400 | HIGH |
| `test_origin_check` | POST with wrong Origin → 403 | HIGH |

### 7.4 Secret Management

| Test | Description | Priority |
|------|-------------|----------|
| `test_no_seeds_in_source` | Grep for API keys, passwords in source code | HIGH |
| `test_no_seeds_in_demo_data` | Grep for credentials in seed SQL | HIGH |
| `test_api_key_not_logged` | Verify Google API key never appears in logs/responses | HIGH |
| `test_dsn_not_logged` | Verify DSN never appears in logs | HIGH |

### 7.5 Headers & Transport

| Test | Description | Priority |
|------|-------------|----------|
| `test_cache_control_no_store` | API responses have `Cache-Control: no-store` | MEDIUM |
| `test_no_cors_on_get` | GET responses have no `Access-Control-Allow-Origin` | MEDIUM |
| `test_loopback_only_bind` | Server refuses non-loopback bind | HIGH |
| `test_no_sensitive_headers` | No `X-Powered-By`, no server version leak | LOW |

### 7.6 CSRF

| Test | Description | Priority |
|------|-------------|----------|
| `test_post_requires_origin` | POST without Origin header → 403 | HIGH |
| `test_post_wrong_origin` | POST with `http://evil.com` Origin → 403 | HIGH |
| `test_post_correct_origin` | POST with `http://127.0.0.1:8790` Origin → proceeds | HIGH |

---

## 8. Fuzzing Tests

### 8.1 API Input Fuzzing (hypothesis)

| Target | Strategy | Invariants |
|--------|----------|------------|
| `parse_tenant` | Random strings, UUIDs, empty, very long | Either valid UUID or ValueError |
| `validate_placement_snapshot` | Random dicts, nested structures, unicode | Either valid result or ValueError |
| `window_days` | Random ints, strings, floats, None | Either valid 1-90 or ValueError |
| `service_name` (Azure) | Random strings, SQL metachars, unicode | Either valid or ValueError |
| `sku` (Azure) | Random strings, special chars | Either valid or ValueError |
| `region` (Azure) | Random strings | Either valid or ValueError |
| `currency` | Random strings, 3-letter, non-3-letter | Either valid 3-letter or ValueError |

### 8.2 HTTP Request Fuzzing

| Target | Strategy | Invariants |
|--------|----------|------------|
| Random paths | Fuzz URL paths | 404 or valid route, never 500 |
| Random query params | Fuzz query string | 400 or valid response |
| Random headers | Fuzz header values | No crash, no info leak |
| Random body (POST) | Fuzz JSON body | 400 or valid response, never 500 |
| Random HTTP methods | PUT/DELETE/PATCH | 404 or 405 |

### 8.3 Database Input Fuzzing

| Target | Strategy | Invariants |
|--------|----------|------------|
| Tenant UUID | Random UUIDs, invalid UUIDs | Either valid result or empty |
| Placement snapshot payload | Deeply nested JSON, circular refs, huge strings | Either valid or ValueError |
| Estimate line items | Random quantities, costs, dates | Either valid or constraint violation |

---

## 9. Property-Based Tests (hypothesis)

### 9.1 TCO Properties

| Property | Description | Priority |
|----------|-------------|----------|
| `test_tco_pv_monotonic_in_horizon` | Longer horizon → higher PV (for positive costs) | HIGH |
| `test_tco_pv_monotonic_in_discount_rate` | Higher discount rate → lower PV | HIGH |
| `test_tco_eac_positive` | EAC > 0 for any positive cost | HIGH |
| `test_tco_zero_costs_zero_pv` | All zero costs → PV = 0 | HIGH |
| `test_tco_contingency_increases_pv` | Higher contingency → higher PV | MEDIUM |
| `test_tco_escalation_increases_pv` | Higher escalation → higher PV | MEDIUM |
| `test_tco_after_tax_less_than_pretax` | After-tax PV ≤ pre-tax PV (when tax_rate > 0) | MEDIUM |
| `test_tco_comparison_deltas_consistent` | Delta = scenario - baseline for each metric | MEDIUM |
| `test_tco_sensitivity_monotonic` | PV monotonic in discount_rate, energy_escalation | MEDIUM |
| `test_tco_yearly_flows_length` | len(yearly_cash_flows) == horizon + 1 | HIGH |
| `test_tco_year_zero_no_opex` | Year 0 has opex = 0 | HIGH |
| `test_tco_terminal_only_final_year` | Terminal cost only in final year | HIGH |

### 9.2 Quality Score Properties

| Property | Description | Priority |
|----------|-------------|----------|
| `test_comteness_bounds` | 0.0 ≤ score ≤ 1.0 for any input | HIGH |
| `test_freshness_bounds` | 0.0 ≤ score ≤ 1.0 for any input | HIGH |
| `test_consistency_bounds` | 0.0 ≤ score ≤ 1.0 for any input | HIGH |
| `test_accuracy_bounds` | 0.0 ≤ score ≤ 1.0 for any input | HIGH |
| `test_overall_weighted_sum` | overall == sum(score × weight) | HIGH |
| `test_freshness_monotonic` | Newer data → higher or equal freshness score | MEDIUM |
| `test_completeness_stricter` | More required fields missing → lower or equal score | MEDIUM |

### 9.3 Forecast Properties

| Property | Description | Priority |
|----------|-------------|----------|
| `test_forecast_non_negative` | All predicted values ≥ 0 | HIGH |
| `test_forecast_lower_le_upper` | lower_bound ≤ upper_bound for all points | HIGH |
| `test_forecast_confidence_bounds` | 0.0 ≤ confidence ≤ 1.0 | HIGH |
| `test_forecast_count` | len(forecast_points) == horizon_days | HIGH |
| `test_forecast_uncertainty_grows` | Later points have wider intervals | MEDIUM |
| `test_forecast_confidence_decreases` | Later points have lower confidence | MEDIUM |
| `test_linear_trend_perfect_fit` | Perfect linear data → r² = 1.0 | HIGH |
| `test_moving_average_constant` | Constant data → moving average = constant | MEDIUM |
| `test_exponential_smoothing_bounded` | Smoothed value within [min, max] of inputs | MEDIUM |

### 9.4 Provenance Properties

| Property | Description | Priority |
|----------|-------------|----------|
| `test_chain_tamper_detection` | Modify any step → verify_chain detects | HIGH |
| `test_chain_order_matters` | Reorder steps → verify_chain detects | HIGH |
| `test_tenant_isolation` | Steps from tenant A not in tenant B chain | HIGH |
| `test_hash_deterministic` | Same input → same hash | MEDIUM |
| `test_hash_changes_with_input` | Different input → different hash | MEDIUM |

### 9.5 Validation Properties

| Property | Description | Priority |
|----------|-------------|----------|
| `test_unit_conversion_roundtrip` | kW→W→kW = identity | HIGH |
| `test_unit_conversion_linear` | kW→W = ×1000 | HIGH |
| `test_interval_merge_idempotent` | merge(merge(x)) == merge(x) | MEDIUM |
| `test_interval_merge_commutative` | merge(a,b) == merge(b,a) | MEDIUM |

### 9.6 API Properties

| Property | Description | Priority |
|----------|-------------|----------|
| `test_tenant_isolation_property` | For all endpoints: tenant A data ∉ tenant B response | CRITICAL |
| `test_readonly_property` | GET requests never modify database state | HIGH |
| `test_response_shape_property` | All responses have expected keys | MEDIUM |
| `test_error_response_property` | All error responses have `error` key | MEDIUM |

---

## 10. Visual Regression Tests (Playwright)

### 10.1 Screenshot Tests

| View | Viewport | Priority |
|------|----------|----------|
| Overview (Command picture) | 1440×900 | HIGH |
| Energy & carbon | 1440×900 | HIGH |
| Data science & BI | 1440×900 | HIGH |
| Sizing & economics | 1440×900 | HIGH |
| Capacity & resilience | 1440×900 | MEDIUM |
| Estate & lifecycle | 1440×900 | MEDIUM |
| Reliability | 1440×900 | MEDIUM |
| Operations queue | 1440×900 | MEDIUM |
| Integrations | 1440×900 | LOW |
| Evidence & audit | 1440×900 | LOW |
| Overview (demo mode) | 1440×900 | HIGH |
| Overview (no tenant) | 1440×900 | MEDIUM |
| Overview (no data) | 1440×900 | MEDIUM |

### 10.2 Responsive Tests

| Breakpoint | Viewport | Priority |
|------------|----------|----------|
| Desktop | 1440×900 | HIGH |
| Tablet | 768×1024 | MEDIUM |
| Mobile | 375×812 | MEDIUM |
| Small mobile | 320×568 | LOW |

### 10.3 Interaction Tests

| Test | Description | Priority |
|------|-------------|----------|
| `test_navigation_highlight` | Click nav item → verify active class | MEDIUM |
| `test_demo_toggle_ribbon` | Toggle demo → verify ribbon appears/disappears | HIGH |
| `test_tenant_input_validation` | Enter invalid UUID → verify validation message | MEDIUM |
| `test_refresh_button` | Click refresh → verify loading state → verify data updates | MEDIUM |
| `test_auto_refresh` | Set interval → verify auto-refresh occurs | LOW |
| `test_table_sort` | Click column header → verify sort order | LOW |
| `test_search_filter` | Type in search → verify filtered results | MEDIUM |
| `test_csv_export` | Click export → verify file download | LOW |

---

## 11. Test Infrastructure

### 11.1 Test Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
markers =
    unit: Unit tests (fast, no I/O)
    integration: Integration tests (DB required)
    e2e: End-to-end tests (Playwright)
    performance: Performance tests (locust)
    security: Security tests
    fuzz: Fuzzing tests
    property: Property-based tests
    visual: Visual regression tests
    slow: Slow tests
```

### 11.2 Test Fixtures

```python
# conftest.py
import pytest
import testing.postgresql

@pytest.fixture(scope="session")
def test_db():
    """Spin up a test PostgreSQL instance."""
    with testing.postgresql.Postgresql() as postgresql:
        yield postgresql

@pytest.fixture
def db_connection(test_db):
    """Create a fresh database connection."""
    import psycopg
    conn = psycopg.connect(test_db.url())
    yield conn
    conn.close()

@pytest.fixture
def seeded_db(db_connection):
    """Apply schema and seed data."""
    with open("database/schema.sql") as f:
        db_connection.execute(f.read())
    with open("database/demo_seed.sql") as f:
        db_connection.execute(f.read())
    yield db_connection

@pytest.fixture
def api_client(seeded_db):
    """Create an API test client."""
    # Implementation depends on test approach
    pass
```

### 11.3 CI/CD Integration

```yaml
# .github/workflows/ci.yml (expanded)
name: data-center-commander-ci
on:
  pull_request:
  push:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run unit tests
        run: |
          pip install pytest pytest-cov hypothesis
          pytest tests/ -m unit --cov=src/dcc --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: <_REDACTED>
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run integration tests
        env:
          DCC_DATABASE_URL: postgresql://postgres:postgres@localhost/postgres
        run: |
          pip install pytest psycopg[binary,pool]
          pytest tests/ -m integration

  security-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run security tests
        run: |
          pip install pytest
          pytest tests/ -m security

  property-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run property-based tests
        run: |
          pip install hypothesis pytest
          pytest tests/ -m property

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run E2E tests
        run: |
          pip install playwright pytest-playwright
          playwright install chromium
          pytest tests/ -m e2e

  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run performance tests
        run: |
          pip install locust
          locust -f tests/performance/locustfile.py --headless -u 10 -r 2 -t 5m

  visual-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run visual regression tests
        run: |
          pip install playwright pytest-playwright
          playwright install chromium
          pytest tests/ -m visual
```

---

## 12. Coverage Targets

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| `api.py` | 35% | 90% | CRITICAL |
| `azure_prices.py` | 78% | 95% | HIGH |
| `google_prices.py` | 76% | 95% | HIGH |
| `economics/tco.py` | 0% | 90% | HIGH |
| `economics/allocation.py` | 0% | 85% | HIGH |
| `economics/scenarios.py` | 0% | 85% | MEDIUM |
| `economics/estimates.py` | 0% | 85% | HIGH |
| `economics/tariffs.py` | 0% | 80% | MEDIUM |
| `economics/budget.py` | 0% | 80% | MEDIUM |
| `economics/reconciliation.py` | 0% | 85% | HIGH |
| `economics/unit.py` | 0% | 85% | MEDIUM |
| `forecasting/capacity.py` | 0% | 85% | HIGH |
| `forecasting/load.py` | 0% | 80% | MEDIUM |
| `forecasting/price.py` | 0% | 80% | MEDIUM |
| `forecasting/failure.py` | 0% | 85% | HIGH |
| `forecasting/calibration.py` | 0% | 80% | MEDIUM |
| `forecasting/drift.py` | 0% | 80% | MEDIUM |
| `forecasting/backtest.py` | 0% | 85% | HIGH |
| `forecasting/features.py` | 0% | 80% | MEDIUM |
| `forecasting/maintenance.py` | 0% | 80% | MEDIUM |
| `quality/engine.py` | 0% | 90% | HIGH |
| `quality/anomaly.py` | 0% | 85% | HIGH |
| `quality/freshness.py` | 0% | 85% | MEDIUM |
| `validation/consistency.py` | 0% | 85% | HIGH |
| `validation/intervals.py` | 0% | 85% | HIGH |
| `validation/boundaries.py` | 0% | 85% | HIGH |
| `validation/schema.py` | 0% | 85% | HIGH |
| `validation/units.py` | 0% | 85% | HIGH |
| `provenance/tracker.py` | 0% | 85% | HIGH |
| `adapters/*.py` | 0% | 80% | MEDIUM |
| **Overall** | **50%** | **85%** | — |

---

## 13. Test Execution Plan

### Phase 1: Critical Gaps (Week 1)

1. Add unit tests for `api.py` POST endpoint (CRITICAL — zero coverage)
2. Add integration tests for all GET routes (CRITICAL — zero coverage)
3. Add security tests for tenant isolation (CRITICAL)
4. Add unit tests for `validate_placement_snapshot` error paths (HIGH)

### Phase 2: Core Modules (Week 2)

5. Add unit tests for `economics/tco.py` (HIGH)
6. Add unit tests for `quality/engine.py` (HIGH)
7. Add unit tests for `forecasting/capacity.py` (HIGH)
8. Add unit tests for `provenance/tracker.py` (HIGH)
9. Add integration tests for DB schema (HIGH)

### Phase 3: Remaining Modules (Week 3)

10. Add unit tests for remaining economics modules
11. Add unit tests for remaining forecasting modules
12. Add unit tests for validation modules
13. Add unit tests for adapters

### Phase 4: Advanced Testing (Week 4)

14. Add property-based tests (hypothesis)
15. Add fuzzing tests
16. Add E2E tests (Playwright)
17. Add performance tests (locust)
18. Add visual regression tests

### Phase 5: Hardening (Week 5)

19. Achieve 85%+ coverage
20. Add CI/CD pipeline
21. Add coverage reporting
22. Add test documentation

---

## 14. Risk-Based Test Prioritization

| Risk | Test Type | Mitigation |
|------|-----------|------------|
| Tenant data leak | Security + Property | RLS tests, tenant isolation property tests |
| SQL injection | Security + Fuzz | Parameterized query tests, fuzz tenant_id |
| XSS via API data | Security | UI escaping tests, API response validation |
| POST endpoint abuse | Security + Integration | Origin validation, size limits, rate limiting |
| DB constraint violation | Integration | Trigger tests, constraint validation |
| Forecast accuracy | Unit + Property | Backtest tests, calibration tests |
| TCO calculation errors | Unit + Property | Property tests, boundary tests |
| Connection pool exhaustion | Performance | Load tests, concurrency tests |
| Memory leaks | Performance | Soak tests, profiling |
| Visual regression | Visual | Screenshot diff tests |

---

## 15. Test Data Strategy

### 5.1 Synthetic Data

- Use `database/demo_seed.sql` for integration tests
- Use `database/demo_analytics_expansion.sql` for time-series tests
- Generate additional synthetic data with `hypothesis` for property tests
- Use `factory_boy` or similar for complex object generation

### 5.2 Test Isolation

- Each test runs in a transaction that is rolled back
- Use `pytest.fixture` for setup/teardown
- Never depend on test execution order
- Use unique tenant IDs per test

### 5.3 Performance Test Data

- Generate 1M+ telemetry readings for scale tests
- Use `generate_series` for time-series data
- Seed 100+ tenants for multi-tenant tests

---

## 16. Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Line coverage | ≥85% | pytest-cov |
| Branch coverage | ≥80% | pytest-cov |
| Test pass rate | 100% | CI pipeline |
| Critical path coverage | 100% | Manual review |
| Security test pass rate | 100% | CI pipeline |
| Performance p95 | <500ms | Locust |
| Performance p99 | <1s | Locust |
| Zero critical bugs | 0 | Security review |
| Visual regression | 0 unexpected diffs | Playwright |

---

## 17. Appendix: Test File Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/
│   ├── test_api_unit.py           # parse_tenant, validate_placement_snapshot, etc.
│   ├── test_tco.py                # TCO calculator
│   ├── test_allocation.py         # Cost allocation
│   ├── test_scenarios.py          # Scenario comparison
│   ├── test_estimates.py          # Estimate rollup
│   ├── test_tariffs.py            # Tariff validation
│   ├── test_budget.py             # Budget vs actual
│   ├── test_reconciliation.py     # Estimate-to-actual
│   ├── test_unit_economics.py     # Unit economics
│   ├── test_capacity_forecast.py  # Capacity forecasting
│   ├── test_load_forecast.py      # Load forecasting
│   ├── test_price_forecast.py     # Price forecasting
│   ├── test_failure_prediction.py # Failure prediction
│   ├── test_calibration.py        # Probability calibration
│   ├── test_drift.py              # Drift detection
│   ├── test_backtest.py           # Time-series backtest
│   ├── test_features.py           # Feature extraction
│   ├── test_maintenance.py        # Maintenance scheduling
│   ├── test_quality_engine.py     # Quality scoring
│   ├── test_anomaly.py            # Anomaly detection
│   ├── test_freshness.py         # Freshness checks
│   ├── test_consistency.py        # Cross-source consistency
│   ├── test_intervals.py          # Interval alignment
│   ├── test_boundaries.py         # Meter boundaries
│   ├── test_schema.py             # Schema validation
│   ├── test_units.py              # Unit conversion
│   ├── test_provenance.py         # Lineage tracking
│   ├── test_adapters.py           # Adapter tests
│   ├── test_azure_prices.py       # Azure pricing (expand existing)
│   └── test_google_prices.py      # Google pricing (expand existing)
├── integration/
│   ├── test_api_routes.py         # All GET/POST routes
│   ├── test_db_schema.py          # Schema + migrations
│   ├── test_rls.py                # RLS enforcement
│   ├── test_tenant_isolation.py   # Cross-tenant isolation
│   ├── test_placement_round_trip.py # POST → GET flow
│   └── test_adapters_integration.py # Adapter end-to-end
├── security/
│   ├── test_auth.py               # AuthN/AuthZ (current state)
│   ├── test_injection.py          # SQL/XSS/path traversal
│   ├── test_input_validation.py   # Input bounds
│   ├── test_secrets.py            # Secret management
│   ├── test_headers.py            # Security headers
│   └── test_csrf.py               # CSRF protection
├── property/
│   ├── test_tco_properties.py     # TCO invariants
│   ├── test_quality_properties.py # Quality score invariants
│   ├── test_forecast_properties.py # Forecast invariants
│   ├── test_provenance_properties.py # Chain invariants
│   ├── test_validation_properties.py # Validation invariants
│   └── test_api_properties.py     # API invariants
├── fuzz/
│   ├── test_api_fuzz.py           # API input fuzzing
│   ├── test_http_fuzz.py          # HTTP request fuzzing
│   └── test_db_fuzz.py            # DB input fuzzing
├── e2e/
│   ├── test_user_journeys.py      # Full user flows
│   ├── test_api_e2e.py            # API end-to-end
│   └── test_server_lifecycle.py   # Startup/shutdown
├── performance/
│   ├── locustfile.py              # Locust load tests
│   ├── test_endpoint_benchmarks.py # Per-endpoint benchmarks
│   ├── test_db_performance.py     # Query plan tests
│   └── test_scalability.py        # Scale tests
└── visual/
    ├── test_screenshots.py        # Screenshot diff
    ├── test_responsive.py         # Responsive layout
    └── test_interactions.py       # UI interaction tests
```

---

*End of test strategy document.*
