# DCC Performance Audit Report

**Date:** 2026-09-29  
**Scope:** Database query patterns, N+1 queries, missing indexes, slow query patterns, connection pool configuration  
**Files Analyzed:** `src/dcc/api.py`, `database/schema.sql`, `database/migrations/*.sql`, `database/demo_seed.sql`, `database/demo_analytics_expansion.sql`

---

## 1. Executive Summary

The Data Center Commander API layer exhibits several performance anti-patterns that will degrade under load. The most critical issues are **N+1 query patterns in the `/v1/analytics` and `/v1/costs` endpoints**, **missing indexes on time-range filtered tables**, and **a connection pool configuration that disables prepared statements**. The schema is well-normalized with appropriate foreign keys and RLS policies, but the query patterns in the API layer do not leverage the available indexes effectively.

---

## 2. N+1 Query Patterns

### 2.1 `/v1/analytics` Endpoint — 4 Sequential Queries (CRITICAL)

**Location:** `api.py:261-305`

The analytics endpoint fires **4 separate queries** within a single request, each acquiring a connection from the pool:

| Query | Purpose | Issue |
|-------|---------|-------|
| `series` | KPI time series | `date_trunc` + GROUP BY on large window |
| `quality` | KPI quality summary | LEFT JOIN with time filter |
| `telemetry` | Telemetry quality counts | Full scan on `telemetry_readings` |
| `queues` | Workflow health | GROUP BY on `operational_workflows` |

**Impact:** Each query acquires a connection from the pool sequentially. With `max_size=8` and concurrent users, this creates a **4x multiplier** on connection pool pressure. A single analytics request holds a connection for the duration of all 4 queries.

**Recommendation:** Combine into fewer queries using CTEs or fetch all data in a single query with JSON aggregation.

### 2.2 `/v1/costs` Endpoint — 3 Sequential Queries (HIGH)

**Location:** `api.py:346-387`

| Query | Purpose | Issue |
|-------|---------|-------|
| `estimates` | Estimate projects with rollup | Subquery on `estimate_cost_rollup` view |
| `prices` | Price observations | JOIN with `cost_books`, ORDER BY `observed_at DESC` |
| `actuals` | Cost actuals aggregation | GROUP BY on `cost_actuals` |

**Impact:** The `estimate_cost_rollup` view uses `CROSS JOIN LATERAL` with `generate_series`, which is **O(n × m)** where n = line items and m = horizon months. For a 240-month horizon with 100 line items, this generates 24,000 rows before aggregation.

### 2.3 `/v1/overview` Endpoint — 4 Sequential Queries (MEDIUM)

**Location:** `api.py:388-411`

| Query | Purpose |
|-------|---------|
| `facilities` | Count active facilities |
| `kpis` | Latest KPI observations |
| `open_work` | Count open workflows |
| `latest` | Max ingested_at from telemetry |

**Impact:** The `latest` query does a full aggregate scan on `telemetry_readings` with only a `tenant_id` filter — no index supports `max(ingested_at)` per tenant.

### 2.4 `/v1/topology` Endpoint — 2 Queries with JOINs (MEDIUM)

**Location:** `api.py:244-260`

The nodes query JOINs `assets → spaces → facilities` with `ORDER BY a.name LIMIT 500`. The edges query JOINs `asset_relationships → assets` twice with `ORDER BY r.valid_from DESC LIMIT 1000`.

---

## 3. Missing Indexes

### 3.1 Critical Missing Indexes

| Table | Missing Index | Query Pattern | Impact |
|-------|--------------|---------------|--------|
| `telemetry_readings` | `(tenant_id, observed_at DESC)` | Time-range filters in `/v1/analytics`, `/v1/overview` | Full table scan on telemetry |
| `kpi_observations` | `(tenant_id, window_end DESC)` | Time-range filters in `/v1/analytics` | Full table scan on KPI observations |
| `assets` | `(tenant_id, lifecycle_state, name)` | `/v1/assets` endpoint filters and sorts | Filesort on large asset tables |
| `connector_runs` | `(tenant_id, started_at DESC)` | Recent connector run queries | Full scan on connector_runs |
| `evidence_events` | `(tenant_id, sequence DESC)` | `/v1/evidence` endpoint | Full scan on evidence_events |
| `operational_workflows` | `(tenant_id, status, due_at)` | `/v1/workflows`, `/v1/analytics` queue queries | Full scan on workflows |
| `cost_actuals` | `(tenant_id, occurred_at DESC)` | Recent actuals queries | Full scan on cost_actuals |
| `price_observations` | `(tenant_id, observed_at DESC)` | `/v1/costs` prices query | Full scan on price_observations |

### 3.2 Existing Indexes (Verified)

The schema already has these indexes:
- `assets_tenant_type_state_idx` on `assets(tenant_id, asset_type, lifecycle_state, id)`
- `connector_runs_recent_idx` on `connector_runs(tenant_id, connector_id, started_at DESC)`
- `telemetry_asset_metric_time_idx` on `telemetry_readings(tenant_id, asset_id, metric_id, observed_at DESC)`
- `telemetry_meter_interval_idx` on `telemetry_readings(tenant_id, meter_id, interval_start DESC) WHERE meter_id IS NOT NULL`
- `capacity_latest_idx` on `capacity_snapshots(tenant_id, facility_id, dimension, observed_at DESC)`
- `kpi_observations_latest_idx` on `kpi_observations(tenant_id, facility_id, kpi_definition_id, window_end DESC)`
- `workflow_queue_idx` on `operational_workflows(tenant_id, status, priority, due_at)`
- `evidence_subject_idx` on `evidence_events(tenant_id, subject_type, subject_id, sequence DESC)`
- `price_lookup_idx` on `price_observations(tenant_id, item_code, geography, valid_from DESC) WHERE quality_status='approved'`
- `price_source_freshness_idx` on `price_observations(tenant_id, source_kind, observed_at DESC)`
- `estimate_line_rollup_idx` on `estimate_line_items(tenant_id, estimate_id, phase, line_no)`
- `cost_actuals_period_idx` on `cost_actuals(tenant_id, accounting_period, cost_type, facility_id)`
- `cost_allocation_workload_idx` on `cost_allocations(tenant_id, workload_id, window_end DESC)`
- `placement_snapshots_recent_idx` on `placement_comparison_snapshots(tenant_id, created_at DESC, id DESC)`

### 3.3 Index Gaps

The existing indexes are **optimized for asset/meter-centric queries** but the API queries are **tenant-centric with time-range filters**. The key gap is:

- `telemetry_readings` has `(tenant_id, asset_id, metric_id, observed_at DESC)` but queries filter on `(tenant_id, observed_at)` without `asset_id` — the index cannot be used efficiently.
- `kpi_observations` has `(tenant_id, facility_id, kpi_definition_id, window_end DESC)` but queries filter on `(tenant_id, window_end)` without `facility_id`.

---

## 4. Slow Query Patterns

### 4.1 `estimate_cost_rollup` View — CROSS JOIN LATERAL (CRITICAL)

**Location:** `schema.sql:304-317`, `migrations/002_lifecycle_rollup_fix.sql`

```sql
CROSS JOIN LATERAL (SELECT month_no FROM generate_series(l.start_month, e.horizon_months,
  coalesce(l.recurrence_months, e.horizon_months+1)) AS periods(month_no)) period
```

**Problem:** For each line item, this generates a series of months. With 100 line items and a 240-month horizon, this produces **24,000 intermediate rows** before the GROUP BY aggregation. The view is queried in `/v1/costs` with a subquery that further aggregates.

**Recommendation:** 
- Materialize the rollup as a table refreshed on write, OR
- Add a composite index on `estimate_line_items(tenant_id, estimate_id, start_month, recurrence_months)` to at least speed up the lateral join, OR
- Pre-compute the rollup in a background job.

### 4.2 `date_trunc` with GROUP BY (HIGH)

**Location:** `api.py:262-271`

```sql
SELECT d.metric_key, d.name, d.unit, date_trunc('day', o.window_end) AS bucket,
       avg(o.value_numeric) AS value, ...
FROM dcc.kpi_observations o JOIN dcc.kpi_definitions d ...
WHERE o.tenant_id=%s::uuid AND o.window_end>=now()-(%s*interval '1 day')
GROUP BY d.metric_key, d.name, d.unit, date_trunc('day', o.window_end)
ORDER BY d.metric_key, bucket LIMIT 5000
```

**Problem:** `date_trunc` is not sargable — it prevents index usage on `window_end`. The query must scan all rows matching the tenant filter, then sort.

**Recommendation:** Add a functional index on `(tenant_id, date_trunc('day', window_end))` or pre-compute the bucket in a materialized view.

### 4.3 JSONB Operator Queries (MEDIUM)

**Location:** `api.py:265, 277, 378-380`

```sql
bool_or(o.provenance->>'synthetic'='true')
```

**Problem:** The `->>` operator on JSONB prevents index usage. While there are no GIN indexes on `provenance`, the query pattern is inherently non-sargable.

**Recommendation:** Add a GIN index on `kpi_observations(provenance)` if JSONB filtering becomes a bottleneck, or extract `synthetic` to a boolean column.

### 4.4 `DISTINCT ON` with ORDER BY (MEDIUM)

**Location:** `api.py:336-338`

```sql
SELECT DISTINCT ON (facility_id, dimension, scenario) facility_id::text, ...
FROM dcc.capacity_snapshots WHERE tenant_id=%s::uuid
ORDER BY facility_id, dimension, scenario, observed_at DESC LIMIT 1000
```

**Problem:** `DISTINCT ON` requires a sort of all matching rows before deduplication. With many snapshots per facility, this can be slow.

**Recommendation:** The existing `capacity_latest_idx` on `(tenant_id, facility_id, dimension, observed_at DESC)` helps, but the `scenario` column is not in the index. Consider adding it.

### 4.5 `validate_estimate_price_link` Trigger (MEDIUM)

**Location:** `schema.sql:260-283`

**Problem:** This trigger runs 3 additional queries (`price_observations`, `cost_books`, `estimate_projects`) on every INSERT/UPDATE to `estimate_line_items`. For bulk imports, this creates an N+1 pattern at the database level.

**Recommendation:** For bulk operations, consider deferring validation or using a batch validation approach.

---

## 5. Connection Pool Issues

### 5.1 Configuration (HIGH)

**Location:** `api.py:71-74`

```python
pool = ConnectionPool(conninfo=dsn, min_size=1, max_size=8, timeout=3,
                      kwargs={"row_factory": dict_row, "prepare_threshold": None})
```

| Setting | Value | Issue |
|---------|-------|-------|
| `min_size` | 1 | Too low — cold start latency on first request |
| `max_size` | 8 | Reasonable for moderate load |
| `timeout` | 3s | Aggressive — may cause 503s under load |
| `prepare_threshold` | None | **Disables prepared statements** — every query is parsed and planned from scratch |

### 5.2 No Connection Retry Logic (MEDIUM)

If a connection fails or times out, the API returns a 503 immediately. There is no retry with exponential backoff for transient failures.

### 5.3 No Connection Health Checks (LOW)

The pool does not configure `pool_lifespan` or `pool_recycle`, meaning connections may become stale without detection.

### 5.4 Pool Exhaustion Risk (HIGH)

With `max_size=8` and the N+1 query patterns identified above, a single concurrent user can consume 4 connections (analytics endpoint). **Just 2 concurrent analytics requests can exhaust the pool.**

**Recommendation:**
- Increase `min_size` to 4 to reduce cold start
- Set `prepare_threshold` to 5 (default) to enable prepared statements for repeated queries
- Increase `timeout` to 10s for resilience
- Consider `max_size=16` if the database can handle it
- Add `pool_recycle=3600` to recycle stale connections

---

## 6. RLS Overhead

### 6.1 Redundant RLS Filtering (MEDIUM)

**Location:** `schema.sql:342-350`

Every table has RLS with `tenant_id = nullif(current_setting('dcc.tenant_id',true),'')::uuid`. The API already filters by `tenant_id` explicitly in every query. This means:

1. The query planner must apply the RLS policy filter **in addition to** the explicit `WHERE tenant_id = ...` clause.
2. For queries that don't use `set_config('dcc.tenant_id', ...)`, the RLS policy returns no rows (fail-closed).

**Impact:** The RLS policy adds a `Filter` step to every query plan. While not catastrophic, it prevents certain index optimizations and adds CPU overhead.

**Recommendation:** This is a security feature and should be kept. However, ensure `set_config` is always called before queries (it already is in the API). The overhead is acceptable for the security benefit.

---

## 7. Query Pattern Summary by Endpoint

| Endpoint | Queries | Est. Rows Scanned | Index Usage | Severity |
|----------|---------|------------------|-------------|----------|
| `/v1/analytics` | 4 | High (telemetry + KPI full scans) | Poor | CRITICAL |
| `/v1/costs` | 3 | High (rollup view expansion) | Poor | HIGH |
| `/v1/overview` | 4 | Medium (4 aggregate queries) | Poor | MEDIUM |
| `/v1/topology` | 2 | Medium (JOINs with LIMIT) | Fair | MEDIUM |
| `/v1/assets` | 1 | Medium (LEFT JOIN + ORDER BY) | Fair | LOW |
| `/v1/facilities` | 1 | Low (JOIN + LIMIT) | Good | LOW |
| `/v1/workflows` | 1 | Low (ORDER BY + LIMIT) | Good | LOW |
| `/v1/connectors` | 1 | Low (ORDER BY + LIMIT) | Good | LOW |
| `/v1/capacity` | 1 | Medium (DISTINCT ON) | Fair | MEDIUM |
| `/v1/evidence` | 1 | Low (ORDER BY + LIMIT) | Good | LOW |
| `/v1/placement/scenarios` | 1 | Low (ORDER BY + LIMIT) | Good | LOW |

---

## 8. Recommendations (Prioritized)

### P0 — Immediate (Critical)

1. **Add time-range indexes** on `telemetry_readings(tenant_id, observed_at DESC)` and `kpi_observations(tenant_id, window_end DESC)`
2. **Enable prepared statements** by removing `prepare_threshold=None`
3. **Increase pool `min_size`** to 4 and `timeout` to 10

### P1 — Short-term (High)

4. **Combine analytics queries** into a single CTE-based query to reduce connection pool pressure
5. **Materialize `estimate_cost_rollup`** as a table or add supporting indexes
6. **Add missing indexes** for `assets(tenant_id, lifecycle_state, name)`, `cost_actuals(tenant_id, occurred_at DESC)`, `price_observations(tenant_id, observed_at DESC)`

### P2 — Medium-term (Medium)

7. **Add connection retry logic** with exponential backoff for transient failures
8. **Add `pool_recycle=3600`** to prevent stale connections
9. **Consider GIN indexes** on JSONB columns if JSONB filtering becomes a bottleneck
10. **Add `scenario` to `capacity_latest_idx`** for the DISTINCT ON query

### P3 — Long-term (Low)

11. **Implement query result caching** for frequently accessed endpoints (e.g., `/v1/overview`)
12. **Add database-level query timeout** to prevent runaway queries
13. **Consider read replicas** for analytics queries to offload the primary

---

## 9. Appendix: Query Count per Request

```
/v1/analytics     → 4 queries  → 4 connection acquisitions
/v1/costs         → 3 queries  → 3 connection acquisitions
/v1/overview      → 4 queries  → 4 connection acquisitions
/v1/topology      → 2 queries  → 2 connection acquisitions
/v1/assets        → 1 query
/v1/facilities    → 1 query
/v1/workflows     → 1 query
/v1/connectors    → 1 query
/v1/capacity      → 1 query
/v1/evidence      → 1 query
/v1/placement/*   → 1 query
```

**Worst case:** A single `/v1/analytics` request holds a connection for 4 sequential queries. With `max_size=8`, only **2 concurrent analytics requests** can be served before pool exhaustion.
