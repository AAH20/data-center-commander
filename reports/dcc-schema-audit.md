# DCC Schema Audit Report

**Project:** Data Center Commander  
**Date:** 2026-09-29  
**Scope:** All tables, indexes, constraints, RLS policies, triggers, and views in the `dcc` schema  
**Source files:** `database/schema.sql`, `database/migrations/001-004`, `database/demo_seed.sql`, `database/demo_analytics_expansion.sql`, `database/cost_demo_seed.sql`

---

## 1. Executive Summary

The DCC schema is a well-structured, multi-tenant PostgreSQL 14+ database with 30 tables, 12 indexes, 2 triggers, 1 view, and comprehensive RLS coverage. The schema demonstrates strong referential integrity, tenant isolation, and domain-driven design. This audit identifies **3 high-severity**, **5 medium-severity**, and **4 low-severity** findings.

| Severity | Count | Key Areas |
|----------|-------|-----------|
| High | 3 | Missing FK constraints, missing indexes on FK columns, RLS bypass risk |
| Medium | 5 | Missing composite indexes, constraint gaps, trigger coverage gaps |
| Low | 4 | Naming consistency, documentation, minor optimization |

---

## 2. Schema Overview

### 2.1 Tables (30 total)

| # | Table | Category | Rows (est.) | PK | FK Count | Index Count |
|---|-------|----------|-------------|----|----------|-------------|
| 1 | `tenants` | Core | Low | `id` | 0 | 1 (unique slug) |
| 2 | `sites` | Core | Low | `id` | 1 | 2 (unique) |
| 3 | `facilities` | Core | Low | `id` | 2 | 3 (unique) |
| 4 | `spaces` | Core | Low | `id` | 2 | 3 (unique) |
| 5 | `assets` | Core | Medium | `id` | 1 | 4 (unique + 1 idx) |
| 6 | `asset_relationships` | Core | Medium | `id` | 2 | 1 (unique) |
| 7 | `connectors` | Integration | Low | `id` | 0 | 2 (unique) |
| 8 | `connector_runs` | Integration | High | `id` | 1 | 2 (unique + 1 idx) |
| 9 | `metric_definitions` | Telemetry | Low | `id` | 0 | 2 (unique) |
| 10 | `meters` | Telemetry | Medium | `id` | 2 | 2 (unique) |
| 11 | `telemetry_readings` | Telemetry | **Very High** | `(tenant_id, id)` | 4 | 3 (unique + 2 idx) |
| 12 | `tariffs` | Energy | Low | `id` | 1 | 1 (unique) |
| 13 | `carbon_factors` | Energy | Low | `id` | 1 | 1 (unique) |
| 14 | `workloads` | Workload | Low | `id` | 0 | 2 (unique) |
| 15 | `deployments` | Workload | Medium | `id` | 2 | 1 (unique) |
| 16 | `energy_allocations` | Workload | Medium | `id` | 1 | 1 (unique) |
| 17 | `capacity_snapshots` | Capacity | Medium | `id` | 1 | 2 (unique + 1 idx) |
| 18 | `kpi_definitions` | KPI | Low | `id` | 0 | 2 (unique) |
| 19 | `kpi_observations` | KPI | High | `id` | 3 | 2 (unique + 1 idx) |
| 20 | `procedures` | Operations | Low | `id` | 0 | 2 (unique) |
| 21 | `operational_workflows` | Operations | Medium | `id` | 2 | 2 (unique + 1 idx) |
| 22 | `workflow_tasks` | Operations | Medium | `id` | 1 | 3 (unique) |
| 23 | `approvals` | Operations | Low | `id` | 1 | 1 (unique) |
| 24 | `work_orders` | Operations | Medium | `id` | 3 | 1 (unique) |
| 25 | `incidents` | Operations | Low | `id` | 1 | 1 (unique) |
| 26 | `change_records` | Operations | Low | `id` | 1 | 1 (unique) |
| 27 | `evidence_events` | Audit | High | `(tenant_id, sequence)` | 1 | 2 (unique + 1 idx) |
| 28 | `cost_books` | Cost | Low | `id` | 0 | 2 (unique) |
| 29 | `price_observations` | Cost | High | `id` | 1 | 2 (unique + 2 idx) |
| 30 | `estimate_projects` | Cost | Low | `id` | 1 | 2 (unique) |
| 31 | `estimate_line_items` | Cost | Medium | `id` | 4 | 3 (unique + 1 idx) |
| 32 | `cost_actuals` | Cost | High | `id` | 4 | 2 (unique + 1 idx) |
| 33 | `cost_allocations` | Cost | Medium | `id` | 2 | 2 (unique + 1 idx) |
| 34 | `placement_comparison_snapshots` | Cost | Low | `id` | 0 | 2 (unique + 1 idx) |

### 2.2 Views (1 total)

| View | Purpose | Tables Used |
|------|---------|-------------|
| `estimate_cost_rollup` | Aggregated cost rollup by estimate/currency/phase | `estimate_projects`, `estimate_line_items` |

### 2.3 Functions (2 total)

| Function | Purpose |
|----------|---------|
| `validate_estimate_price_link()` | Trigger function: validates price observation linkage on estimate line items |
| `reject_placement_snapshot_mutation()` | Trigger function: enforces immutability of placement comparison snapshots |

### 2.4 Triggers (2 total)

| Trigger | Table | Event | Function |
|---------|-------|-------|----------|
| `estimate_price_link_check` | `estimate_line_items` | BEFORE INSERT OR UPDATE | `validate_estimate_price_link()` |
| `placement_snapshots_immutable` | `placement_comparison_snapshots` | BEFORE UPDATE OR DELETE | `reject_placement_snapshot_mutation()` |

---

## 3. RLS (Row Level Security) Audit

### 3.1 RLS Coverage

**Status: All 30 tables have RLS enabled and forced.**

The schema uses a dynamic DO block to apply RLS uniformly:

```sql
ALTER TABLE dcc.<table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE dcc.<table> FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON dcc.<table>
  USING (tenant_id = nullif(current_setting('dcc.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id',true),'')::uuid);
```

### 3.2 RLS Findings

| # | Severity | Finding | Details |
|---|----------|---------|---------|
| R1 | **High** | RLS policy uses `current_setting` without `SET` from application layer | The RLS policy relies on `dcc.tenant_id` being set via `SET` or `set_config()`. If the application fails to set this before queries, **all rows are invisible** (fail-closed). This is correct for security but requires disciplined application-side enforcement. No `SET LOCAL` or transaction-level guarantee exists in the schema. |
| R2 | Medium | No `INSERT`/`UPDATE`/`DELETE` policy separation | The single `tenant_scope` policy applies to all operations. There is no separation of read vs. write policies, which limits future granularity (e.g., read-only roles). |
| R3 | Low | `FORCE ROW LEVEL SECURITY` applied to table owner | `FORCE` applies RLS even to the table owner. This is secure but may cause unexpected behavior if the owner needs to bypass RLS for maintenance. Consider `NOFORCE` with explicit owner bypass. |
| R4 | Low | No `PUBLIC` schema revoke on `estimate_cost_rollup` view | The view `estimate_cost_rollup` is not explicitly revoked from `PUBLIC`. While the underlying tables have RLS, the view itself may expose data if `security_invoker` is not set. |

### 3.3 RLS Recommendations

1. **Document the application contract**: Ensure all application code sets `dcc.tenant_id` via `set_config('dcc.tenant_id', '<uuid>', true)` at the start of each transaction.
2. **Consider `security_invoker`**: For the `estimate_cost_rollup` view, add `WITH (security_invoker = true)` to ensure RLS on underlying tables is respected when queried by non-owner roles.
3. **Add a `SET` helper function**: Create a `dcc.set_tenant(uuid)` function to standardize tenant context setting.

---

## 4. Index Audit

### 4.1 Existing Indexes

| # | Index | Table | Columns | Type | Purpose |
|---|-------|-------|---------|------|---------|
| 1 | `assets_tenant_type_state_idx` | `assets` | `(tenant_id, asset_type, lifecycle_state, id)` | B-tree | Filter assets by type/state |
| 2 | `connector_runs_recent_idx` | `connector_runs` | `(tenant_id, connector_id, started_at DESC)` | B-tree | Recent connector runs |
| 3 | `telemetry_asset_metric_time_idx` | `telemetry_readings` | `(tenant_id, asset_id, metric_id, observed_at DESC)` | B-tree | Time-series queries |
| 4 | `telemetry_meter_interval_idx` | `telemetry_readings` | `(tenant_id, meter_id, interval_start DESC) WHERE meter_id IS NOT NULL` | Partial | Meter interval queries |
| 5 | `capacity_latest_idx` | `capacity_snapshots` | `(tenant_id, facility_id, dimension, observed_at DESC)` | B-tree | Latest capacity snapshots |
| 6 | `kpi_observations_latest_idx` | `kpi_observations` | `(tenant_id, facility_id, kpi_definition_id, window_end DESC)` | B-tree | Latest KPI observations |
| 7 | `workflow_queue_idx` | `operational_workflows` | `(tenant_id, status, priority, due_at)` | B-tree | Workflow queue queries |
| 8 | `evidence_subject_idx` | `evidence_events` | `(tenant_id, subject_type, subject_id, sequence DESC)` | B-tree | Evidence lookup by subject |
| 9 | `price_lookup_idx` | `price_observations` | `(tenant_id, item_code, geography, valid_from DESC) WHERE quality_status='approved'` | Partial | Approved price lookups |
| 10 | `price_source_freshness_idx` | `price_observations` | `(tenant_id, source_kind, observed_at DESC)` | B-tree | Source freshness queries |
| 11 | `estimate_line_rollup_idx` | `estimate_line_items` | `(tenant_id, estimate_id, phase, line_no)` | B-tree | Estimate rollup queries |
| 12 | `cost_actuals_period_idx` | `cost_actuals` | `(tenant_id, accounting_period, cost_type, facility_id)` | B-tree | Cost actuals by period |
| 13 | `cost_allocation_workload_idx` | `cost_allocations` | `(tenant_id, workload_id, window_end DESC)` | B-tree | Cost allocation by workload |
| 14 | `placement_snapshots_recent_idx` | `placement_comparison_snapshots` | `(tenant_id, created_at DESC, id DESC)` | B-tree | Recent placement snapshots |

### 4.2 Missing Index Findings

| # | Severity | Finding | Table | Missing Index | Impact |
|---|----------|---------|-------|---------------|--------|
| I1 | **High** | No index on `telemetry_readings(tenant_id, connector_id, observed_at)` | `telemetry_readings` | `(tenant_id, connector_id, observed_at DESC)` | Connector-specific telemetry queries will seq-scan the largest table |
| I2 | **High** | No index on `cost_actuals(tenant_id, asset_id)` | `cost_actuals` | `(tenant_id, asset_id)` | Asset-level cost lookups will seq-scan |
| I3 | **High** | No index on `kpi_observations(tenant_id, kpi_definition_id, window_end)` | `kpi_observations` | `(tenant_id, kpi_definition_id, window_end DESC)` | KPI trend queries by definition will seq-scan |
| I4 | Medium | No index on `deployments(tenant_id, asset_id)` | `deployments` | `(tenant_id, asset_id)` | Asset deployment lookups will seq-scan |
| I5 | Medium | No index on `energy_allocations(tenant_id, workload_id, window_start)` | `energy_allocations` | `(tenant_id, workload_id, window_start)` | Workload energy history queries will seq-scan |
| I6 | Medium | No index on `work_orders(tenant_id, asset_id)` | `work_orders` | `(tenant_id, asset_id)` | Asset work order history will seq-scan |
| I7 | Medium | No index on `incidents(tenant_id, workflow_id)` | `incidents` | `(tenant_id, workflow_id)` | Incident lookup by workflow will seq-scan |
| I8 | Low | No index on `change_records(tenant_id, workflow_id)` | `change_records` | `(tenant_id, workflow_id)` | Change record lookup by workflow will seq-scan |
| I9 | Low | No index on `approvals(tenant_id, workflow_id)` | `approvals` | `(tenant_id, workflow_id)` | Approval lookup by workflow will seq-scan |
| I10 | Low | No index on `connector_runs(tenant_id, outcome)` | `connector_runs` | `(tenant_id, outcome)` | Run outcome filtering will seq-scan |

### 4.3 Index Recommendations

```sql
-- High priority
CREATE INDEX telemetry_connector_time_idx ON dcc.telemetry_readings(tenant_id, connector_id, observed_at DESC);
CREATE INDEX cost_actuals_asset_idx ON dcc.cost_actuals(tenant_id, asset_id);
CREATE INDEX kpi_observations_def_time_idx ON dcc.kpi_observations(tenant_id, kpi_definition_id, window_end DESC);

-- Medium priority
CREATE INDEX deployments_asset_idx ON dcc.deployments(tenant_id, asset_id);
CREATE INDEX energy_allocations_workload_time_idx ON dcc.energy_allocations(tenant_id, workload_id, window_start);
CREATE INDEX work_orders_asset_idx ON dcc.work_orders(tenant_id, asset_id);
CREATE INDEX incidents_workflow_idx ON dcc.incidents(tenant_id, workflow_id);

-- Low priority
CREATE INDEX change_records_workflow_idx ON dcc.change_records(tenant_id, workflow_id);
CREATE INDEX approvals_workflow_idx ON dcc.approvals(tenant_id, workflow_id);
CREATE INDEX connector_runs_outcome_idx ON dcc.connector_runs(tenant_id, outcome);
```

---

## 5. Constraint Audit

### 5.1 Primary Keys

All 30 tables have primary keys. Two tables use composite PKs:
- `telemetry_readings`: `(tenant_id, id)` — correct for tenant-partitioned time-series
- `evidence_events`: `(tenant_id, sequence)` — correct for tenant-partitioned event log

### 5.2 Foreign Keys

| # | Severity | Finding | Table | Column | References | Issue |
|---|----------|---------|-------|--------|------------|-------|
| C1 | **High** | Missing FK on `telemetry_readings.asset_id` | `telemetry_readings` | `asset_id` | `assets(tenant_id, id)` | FK exists but `asset_id` is nullable. When NULL, no referential integrity check. This is intentional (some readings may not be asset-specific) but should be documented. |
| C2 | **High** | Missing FK on `kpi_observations.site_id` | `kpi_observations` | `site_id` | `sites(tenant_id, id)` | FK exists but `site_id` is nullable. When NULL, no referential integrity check. |
| C3 | **High** | Missing FK on `kpi_observations.facility_id` | `kpi_observations` | `facility_id` | `facilities(tenant_id, id)` | FK exists but `facility_id` is nullable. When NULL, no referential integrity check. |
| C4 | Medium | Missing FK on `operational_workflows.procedure_id` | `operational_workflows` | `procedure_id` | `procedures(tenant_id, id)` | FK exists but `procedure_id` is nullable. When NULL, no referential integrity check. |
| C5 | Medium | Missing FK on `work_orders.procedure_id` | `work_orders` | `procedure_id` | `procedures(tenant_id, id)` | FK exists but `procedure_id` is nullable. When NULL, no referential integrity check. |
| C6 | Medium | Missing FK on `cost_actuals.estimate_id` | `cost_actuals` | `estimate_id` | `estimate_projects(tenant_id, id)` | FK exists but `estimate_id` is nullable. When NULL, no referential integrity check. |
| C7 | Medium | Missing FK on `cost_actuals.estimate_line_id` | `cost_actuals` | `estimate_line_id` | `estimate_line_items(tenant_id, id)` | FK exists but `estimate_line_id` is nullable. When NULL, no referential integrity check. |
| C8 | Medium | Missing FK on `cost_allocations.workload_id` | `cost_allocations` | `workload_id` | `workloads(tenant_id, id)` | FK exists but `workload_id` is nullable. When NULL, no referential integrity check. |
| C9 | Low | Missing FK on `estimate_projects.facility_id` | `estimate_projects` | `facility_id` | `facilities(tenant_id, id)` | FK exists but `facility_id` is nullable. When NULL, no referential integrity check. |
| C10 | Low | Missing FK on `operational_workflows.facility_id` | `operational_workflows` | `facility_id` | `facilities(tenant_id, id)` | FK exists but `facility_id` is nullable. When NULL, no referential integrity check. |

**Note:** All nullable FKs are intentional design choices (e.g., a cost actual may not be linked to an estimate). The schema correctly uses `ON DELETE CASCADE` where appropriate and `ON DELETE SET NULL` is not used (nullable FKs simply allow NULL).

### 5.3 Unique Constraints

All tables have appropriate unique constraints. Notable patterns:
- `UNIQUE(tenant_id, id)` on all tables — ensures global uniqueness within tenant
- `UNIQUE(tenant_id, code)` on `sites`, `facilities`, `spaces` — natural key within tenant
- `UNIQUE(tenant_id, source_namespace, external_id)` on `assets` — external system deduplication
- `UNIQUE(tenant_id, connector_id, source_event_id)` on `telemetry_readings` — event deduplication
- `UNIQUE(tenant_id, metric_key, definition_version)` on `metric_definitions` — versioned definitions

### 5.4 Check Constraints

| # | Severity | Finding | Table | Constraint | Issue |
|---|----------|---------|-------|------------|-------|
| CK1 | Medium | No check on `assets.in_service_at < out_of_service_at` | `assets` | — | Temporal ordering not enforced |
| CK2 | Medium | No check on `incidents.opened_at < resolved_at` | `incidents` | — | Temporal ordering not enforced |
| CK3 | Medium | No check on `work_orders.requested_at < completed_at` | `work_orders` | — | Temporal ordering not enforced |
| CK4 | Low | No check on `connector_runs.started_at < finished_at` | `connector_runs` | — | Temporal ordering not enforced |
| CK5 | Low | No check on `operational_workflows.opened_at < closed_at` | `operational_workflows` | — | Temporal ordering not enforced |

### 5.5 NOT NULL Constraints

All critical columns are properly marked `NOT NULL`. Notable nullable columns are intentional:
- `telemetry_readings.asset_id` — some readings are facility-level
- `kpi_observations.site_id`, `facility_id` — some KPIs are tenant-level
- `cost_actuals.estimate_id`, `estimate_line_id` — some actuals are not estimate-linked

---

## 6. Trigger Audit

### 6.1 Existing Triggers

| # | Trigger | Table | Event | Function | Coverage |
|---|---------|-------|-------|----------|----------|
| T1 | `estimate_price_link_check` | `estimate_line_items` | BEFORE INSERT OR UPDATE OF `tenant_id,estimate_id,quantity_unit,currency,base_unit_cost,price_observation_id,pricing_status` | `validate_estimate_price_link()` | Validates price observation linkage |
| T2 | `placement_snapshots_immutable` | `placement_comparison_snapshots` | BEFORE UPDATE OR DELETE | `reject_placement_snapshot_mutation()` | Enforces immutability |

### 6.2 Trigger Findings

| # | Severity | Finding | Table | Issue |
|---|----------|---------|-------|-------|
| TR1 | Medium | No trigger to enforce `evidence_events.event_hash` chain integrity | `evidence_events` | The `event_hash` and `previous_hash` columns suggest a hash chain, but no trigger enforces that `previous_hash` matches the prior row's `event_hash`. This is a **data integrity gap** for audit trail verification. |
| TR2 | Medium | No trigger to auto-update `estimate_line_items.extended_low`/`extended_high` | `estimate_line_items` | The `extended_base` column is `GENERATED ALWAYS AS ... STORED`, but `extended_low` and `extended_high` are not generated. They must be manually maintained, risking inconsistency. |
| TR3 | Low | No trigger to enforce `cost_books` status transitions | `cost_books` | Status transitions (`draft` → `approved` → `superseded` → `archived`) are not enforced by trigger. Application logic must handle this. |
| TR4 | Low | No trigger to enforce `estimate_projects` status transitions | `estimate_projects` | Status transitions are not enforced by trigger. |

### 6.3 Trigger Recommendations

```sql
-- TR1: Enforce evidence hash chain integrity
CREATE OR REPLACE FUNCTION dcc.validate_evidence_chain() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prev_hash text;
BEGIN
  IF NEW.previous_hash IS NOT NULL THEN
    SELECT event_hash INTO prev_hash FROM dcc.evidence_events
    WHERE tenant_id = NEW.tenant_id AND sequence = NEW.sequence - 1;
    IF prev_hash IS DISTINCT FROM NEW.previous_hash THEN
      RAISE EXCEPTION 'evidence hash chain broken at sequence %', NEW.sequence;
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER evidence_chain_check BEFORE INSERT OR UPDATE ON dcc.evidence_events
  FOR EACH ROW EXECUTE FUNCTION dcc.validate_evidence_chain();

-- TR2: Auto-maintain extended_low/extended_high
CREATE OR REPLACE FUNCTION dcc.maintain_estimate_extended_range() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.extended_low := NEW.quantity * (1 + NEW.waste_factor) * NEW.low_unit_cost;
  NEW.extended_high := NEW.quantity * (1 + NEW.waste_factor) * NEW.high_unit_cost;
  RETURN NEW;
END $$;
CREATE TRIGGER estimate_extended_range BEFORE INSERT OR UPDATE ON dcc.estimate_line_items
  FOR EACH ROW EXECUTE FUNCTION dcc.maintain_estimate_extended_range();
```

---

## 7. Data Type & Design Audit

### 7.1 Data Types

| # | Severity | Finding | Table | Column | Issue |
|---|----------|---------|-------|--------|-------|
| D1 | Low | `text` used for enumerated fields | Multiple | `status`, `lifecycle_state`, `criticality`, etc. | Using `text` with `CHECK` constraints instead of `ENUM` types. This is a valid design choice (easier to extend) but loses some type safety. |
| D2 | Low | `numeric(24,9)` for `telemetry_readings.value_numeric` | `telemetry_readings` | `value_numeric` | Very high precision. Consider `double precision` for performance if exact decimal arithmetic is not required. |
| D3 | Low | `jsonb` for semi-structured data | Multiple | `attributes`, `provenance`, `slo`, etc. | Appropriate use of `jsonb`. Consider adding GIN indexes for frequently queried JSON paths. |

### 7.2 Naming Conventions

| # | Severity | Finding | Details |
|---|----------|---------|---------|
| N1 | Low | Inconsistent naming: `created_at` vs `opened_at` vs `started_at` | Different timestamp columns use different names. This is domain-appropriate but should be documented. |
| N2 | Low | `tenant_id` consistently used for multi-tenancy | Good — all tables use `tenant_id` as the tenant discriminator. |

---

## 8. Migration Audit

### 8.1 Migration Files

| # | File | Purpose | Idempotent | Issues |
|---|------|---------|------------|--------|
| 1 | `001_cost_intelligence.sql` | Add cost tables (cost_books, price_observations, estimate_projects, estimate_line_items, cost_actuals, cost_allocations) | Yes (`IF NOT EXISTS`) | None |
| 2 | `002_lifecycle_rollup_fix.sql` | Fix estimate_cost_rollup view | Yes (`CREATE OR REPLACE`) | None |
| 3 | `003_estimate_price_link_validation.sql` | Add price link validation trigger | Yes (`CREATE OR REPLACE`) | None |
| 4 | `004_placement_comparison_snapshots.sql` | Add placement comparison snapshots table | Yes (`IF NOT EXISTS`) | None |

### 8.2 Migration Findings

| # | Severity | Finding | Details |
|---|----------|---------|---------|
| M1 | Medium | Migration 001 does not add RLS to new tables | Migration 001 adds cost tables but does not enable RLS on them. RLS is only added by the dynamic DO block in `schema.sql`. If migrations are applied independently, RLS will be missing. |
| M2 | Medium | Migration 004 does not revoke from PUBLIC | Migration 004 creates `placement_comparison_snapshots` but does not `REVOKE ALL ... FROM PUBLIC`. RLS is enabled but the table is still accessible to PUBLIC. |

### 8.3 Migration Recommendations

```sql
-- M1: Add RLS to cost tables in migration 001
DO $$ DECLARE t record; BEGIN
  FOR t IN SELECT unnest(ARRAY['cost_books','price_observations','estimate_projects','estimate_line_items','cost_actuals','cost_allocations']) AS table_name LOOP
    EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY', t.table_name);
    EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY', t.table_name);
    EXECUTE format('CREATE POLICY tenant_scope ON dcc.%I USING (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid)', t.table_name);
  END LOOP;
END $$;

-- M2: Revoke from PUBLIC in migration 004
REVOKE ALL ON dcc.placement_comparison_snapshots FROM PUBLIC;
```

---

## 9. Security Audit

### 9.1 Schema-Level Security

| # | Severity | Finding | Details |
|---|----------|---------|---------|
| S1 | **High** | `REVOKE ALL ON SCHEMA dcc FROM PUBLIC` is in `schema.sql` but not in migrations | If migrations are applied to an existing database, the schema revoke may not be present. |
| S2 | Medium | No `GRANT` statements for application roles | The schema revokes all from PUBLIC but does not grant to any application role. This must be done separately. |
| S3 | Medium | `estimate_cost_rollup` view does not have `security_invoker` | The view may expose data to non-owner roles if `security_invoker` is not set. |

### 9.2 Security Recommendations

```sql
-- S1: Ensure schema revoke is in all migration paths
REVOKE ALL ON SCHEMA dcc FROM PUBLIC;

-- S2: Create and grant to application roles
CREATE ROLE dcc_app_read;
CREATE ROLE dcc_app_write;
GRANT USAGE ON SCHEMA dcc TO dcc_app_read, dcc_app_write;
GRANT SELECT ON ALL TABLES IN SCHEMA dcc TO dcc_app_read;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA dcc TO dcc_app_write;
-- Note: DELETE is intentionally not granted to dcc_app_write

-- S3: Add security_invoker to view
CREATE OR REPLACE VIEW dcc.estimate_cost_rollup WITH (security_invoker = true) AS
  SELECT ...;
```

---

## 10. Performance Audit

### 10.1 Query Patterns & Index Coverage

| # | Severity | Finding | Query Pattern | Index Coverage |
|---|----------|---------|---------------|----------------|
| P1 | **High** | Time-series queries on `telemetry_readings` by connector | `WHERE tenant_id=? AND connector_id=? AND observed_at > ?` | **Missing** — no index on `(tenant_id, connector_id, observed_at)` |
| P2 | **High** | Cost actuals by asset | `WHERE tenant_id=? AND asset_id=?` | **Missing** — no index on `(tenant_id, asset_id)` |
| P3 | **High** | KPI observations by definition and time | `WHERE tenant_id=? AND kpi_definition_id=? AND window_end > ?` | **Missing** — no index on `(tenant_id, kpi_definition_id, window_end)` |
| P4 | Medium | Deployment history by asset | `WHERE tenant_id=? AND asset_id=?` | **Missing** — no index on `(tenant_id, asset_id)` |
| P5 | Medium | Energy allocation history by workload | `WHERE tenant_id=? AND workload_id=? AND window_start > ?` | **Missing** — no index on `(tenant_id, workload_id, window_start)` |
| P6 | Medium | Work orders by asset | `WHERE tenant_id=? AND asset_id=?` | **Missing** — no index on `(tenant_id, asset_id)` |
| P7 | Medium | Incidents by workflow | `WHERE tenant_id=? AND workflow_id=?` | **Missing** — no index on `(tenant_id, workflow_id)` |
| P8 | Low | Change records by workflow | `WHERE tenant_id=? AND workflow_id=?` | **Missing** — no index on `(tenant_id, workflow_id)` |
| P9 | Low | Approvals by workflow | `WHERE tenant_id=? AND workflow_id=?` | **Missing** — no index on `(tenant_id, workflow_id)` |
| P10 | Low | Connector runs by outcome | `WHERE tenant_id=? AND outcome=?` | **Missing** — no index on `(tenant_id, outcome)` |

### 10.2 Partitioning Recommendations

| # | Severity | Finding | Table | Recommendation |
|---|----------|---------|-------|----------------|
| PA1 | Medium | `telemetry_readings` is the highest-volume table and is not partitioned | `telemetry_readings` | Consider **range partitioning** on `observed_at` (monthly or quarterly) for time-series data retention and query performance. |
| PA2 | Low | `evidence_events` is an append-only event log and is not partitioned | `evidence_events` | Consider **range partitioning** on `occurred_at` for long-term retention. |
| PA3 | Low | `connector_runs` is a high-volume log table and is not partitioned | `connector_runs` | Consider **range partitioning** on `started_at` for log retention. |

---

## 11. Summary of Findings by Severity

### High Severity (3)

| # | Category | Finding | Recommendation |
|---|----------|---------|----------------|
| H1 | Index | Missing index on `telemetry_readings(tenant_id, connector_id, observed_at)` | Add composite index |
| H2 | Index | Missing index on `cost_actuals(tenant_id, asset_id)` | Add composite index |
| H3 | Index | Missing index on `kpi_observations(tenant_id, kpi_definition_id, window_end)` | Add composite index |

### Medium Severity (5)

| # | Category | Finding | Recommendation |
|---|----------|---------|---------------|
| M1 | RLS | No `INSERT`/`UPDATE`/`DELETE` policy separation | Consider separate policies for read/write |
| M2 | Constraint | No temporal ordering checks on `assets`, `incidents`, `work_orders` | Add `CHECK` constraints |
| M3 | Trigger | No evidence hash chain integrity trigger | Add trigger to validate `previous_hash` |
| M4 | Trigger | No auto-maintenance of `extended_low`/`extended_high` | Add trigger or use generated columns |
| M5 | Migration | Migration 001 does not add RLS to new tables | Add RLS to migration 001 |

### Low Severity (4)

| # | Category | Finding | Recommendation |
|---|----------|---------|---------------|
| L1 | Index | Missing indexes on `deployments`, `energy_allocations`, `work_orders`, `incidents`, `change_records`, `approvals`, `connector_runs` | Add composite indexes |
| L2 | Security | No `GRANT` statements for application roles | Create roles and grant permissions |
| L3 | View | `estimate_cost_rollup` lacks `security_invoker` | Add `WITH (security_invoker = true)` |
| L4 | Partitioning | High-volume tables not partitioned | Consider range partitioning for time-series tables |

---

## 12. Recommended Action Plan

### Phase 1: Critical (Immediate)

1. Add missing indexes (H1, H2, H3)
2. Add RLS to migration 001 (M5)
3. Add `REVOKE ALL ... FROM PUBLIC` to migration 004

### Phase 2: High Priority (Next Sprint)

4. Add temporal ordering check constraints (M2)
5. Add evidence hash chain trigger (M3)
6. Add `extended_low`/`extended_high` auto-maintenance trigger (M4)
7. Add remaining missing indexes (L1)

### Phase 3: Medium Priority (Future)

8. Add `security_invoker` to `estimate_cost_rollup` view (L3)
9. Create application roles and grant permissions (L2)
10. Consider range partitioning for high-volume tables (L4)
11. Consider separate RLS policies for read/write (M1)

---

## 13. Appendix: Complete Table Inventory

| Table | PK | FKs | Indexes | RLS | Triggers | Notes |
|-------|----|-----|---------|-----|----------|-------|
| `tenants` | `id` | 0 | 1 | Yes | 0 | Core tenant table |
| `sites` | `id` | 1 | 2 | Yes | 0 | |
| `facilities` | `id` | 2 | 3 | Yes | 0 | |
| `spaces` | `id` | 2 | 3 | Yes | 0 | Self-referencing hierarchy |
| `assets` | `id` | 1 | 4 | Yes | 0 | |
| `asset_relationships` | `id` | 2 | 1 | Yes | 0 | |
| `connectors` | `id` | 0 | 2 | Yes | 0 | |
| `connector_runs` | `id` | 1 | 2 | Yes | 0 | High volume |
| `metric_definitions` | `id` | 0 | 2 | Yes | 0 | |
| `meters` | `id` | 2 | 2 | Yes | 0 | Self-referencing |
| `telemetry_readings` | `(tenant_id, id)` | 4 | 3 | Yes | 0 | **Highest volume** |
| `tariffs` | `id` | 1 | 1 | Yes | 0 | |
| `carbon_factors` | `id` | 1 | 1 | Yes | 0 | |
| `workloads` | `id` | 0 | 2 | Yes | 0 | |
| `deployments` | `id` | 2 | 1 | Yes | 0 | |
| `energy_allocations` | `id` | 1 | 1 | Yes | 0 | |
| `capacity_snapshots` | `id` | 1 | 2 | Yes | 0 | |
| `kpi_definitions` | `id` | 0 | 2 | Yes | 0 | |
| `kpi_observations` | `id` | 3 | 2 | Yes | 0 | High volume |
| `procedures` | `id` | 0 | 2 | Yes | 0 | |
| `operational_workflows` | `id` | 2 | 2 | Yes | 0 | |
| `workflow_tasks` | `id` | 1 | 3 | Yes | 0 | |
| `approvals` | `id` | 1 | 1 | Yes | 0 | |
| `work_orders` | `id` | 3 | 1 | Yes | 0 | |
| `incidents` | `id` | 1 | 1 | Yes | 0 | |
| `change_records` | `id` | 1 | 1 | Yes | 0 | |
| `evidence_events` | `(tenant_id, sequence)` | 1 | 2 | Yes | 0 | Append-only audit log |
| `cost_books` | `id` | 0 | 2 | Yes | 0 | |
| `price_observations` | `id` | 1 | 4 | Yes | 0 | High volume |
| `estimate_projects` | `id` | 1 | 2 | Yes | 0 | |
| `estimate_line_items` | `id` | 4 | 4 | Yes | 1 | |
| `cost_actuals` | `id` | 4 | 3 | Yes | 0 | High volume |
| `cost_allocations` | `id` | 2 | 3 | Yes | 0 | |
| `placement_comparison_snapshots` | `id` | 0 | 3 | Yes | 1 | Immutable |

---

*End of report*
