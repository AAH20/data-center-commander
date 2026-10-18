-- Migration 005: Performance Indexes and Materialized Views
-- Addresses: B2 (unbounded queries), B4 (missing indexes), B7 (no materialized views)

-- ---------------------------------------------------------------------------
-- Missing Composite Indexes (B4)
-- These indexes support RLS policy: tenant_id = current_setting('dcc.tenant_id')
-- ---------------------------------------------------------------------------

-- Telemetry readings: time-series queries by tenant + time
CREATE INDEX IF NOT EXISTS telemetry_tenant_observed_idx
    ON dcc.telemetry_readings (tenant_id, observed_at DESC);

-- KPI observations: analytics queries by tenant + window
CREATE INDEX IF NOT EXISTS kpi_obs_tenant_window_idx
    ON dcc.kpi_observations (tenant_id, window_end DESC);

-- Cost actuals: reconciliation queries by tenant + period
CREATE INDEX IF NOT EXISTS cost_actuals_tenant_period_idx
    ON dcc.cost_actuals (tenant_id, accounting_period DESC);

-- Evidence events: hash chain verification by tenant + sequence
CREATE INDEX IF NOT EXISTS evidence_tenant_sequence_idx
    ON dcc.evidence_events (tenant_id, sequence DESC);

-- Connector runs: health check queries by tenant + time
CREATE INDEX IF NOT EXISTS connector_runs_tenant_started_idx
    ON dcc.connector_runs (tenant_id, started_at DESC);

-- Asset relationships: topology queries by tenant
CREATE INDEX IF NOT EXISTS asset_rel_tenant_source_idx
    ON dcc.asset_relationships (tenant_id, source_asset_id);
CREATE INDEX IF NOT EXISTS asset_rel_tenant_target_idx
    ON dcc.asset_relationships (tenant_id, target_asset_id);

-- Energy allocations: workload energy queries
CREATE INDEX IF NOT EXISTS energy_alloc_tenant_workload_idx
    ON dcc.energy_allocations (tenant_id, workload_id, window_end DESC);

-- Capacity snapshots: latest snapshot queries
CREATE INDEX IF NOT EXISTS capacity_tenant_facility_dim_idx
    ON dcc.capacity_snapshots (tenant_id, facility_id, dimension, observed_at DESC);

-- Estimate line items: rollup queries
CREATE INDEX IF NOT EXISTS estimate_line_tenant_estimate_idx
    ON dcc.estimate_line_items (tenant_id, estimate_id, line_no);

-- Price observations: freshness queries
CREATE INDEX IF NOT EXISTS price_obs_tenant_item_idx
    ON dcc.price_observations (tenant_id, item_code, valid_from DESC);

-- Operational workflows: queue queries
CREATE INDEX IF NOT EXISTS workflow_tenant_status_idx
    ON dcc.operational_workflows (tenant_id, status, priority, due_at);

-- ---------------------------------------------------------------------------
-- Materialized Views (B7)
-- Pre-aggregated analytics for fast dashboard queries
-- ---------------------------------------------------------------------------

-- Daily KPI rollup: replaces the expensive GROUP BY in /v1/analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_daily_kpi AS
SELECT
    o.tenant_id,
    d.metric_key,
    d.name AS metric_name,
    d.unit,
    date_trunc('day', o.window_end) AS bucket,
    avg(o.value_numeric) AS avg_value,
    min(o.value_numeric) AS min_value,
    max(o.value_numeric) AS max_value,
    avg(o.coverage) AS avg_coverage,
    avg(o.uncertainty) AS avg_uncertainty,
    count(*)::int AS sample_count,
    bool_or(o.provenance->>'synthetic' = 'true') AS has_synthetic
FROM dcc.kpi_observations o
JOIN dcc.kpi_definitions d ON d.tenant_id = o.tenant_id AND d.id = o.kpi_definition_id
WHERE o.quality_status IN ('good', 'estimated')
GROUP BY o.tenant_id, d.metric_key, d.name, d.unit, date_trunc('day', o.window_end);

CREATE UNIQUE INDEX IF NOT EXISTS mv_daily_kpi_pk
    ON dcc.mv_daily_kpi (tenant_id, metric_key, bucket);
CREATE INDEX IF NOT EXISTS mv_daily_kpi_tenant_bucket_idx
    ON dcc.mv_daily_kpi (tenant_id, bucket DESC);

-- Daily telemetry quality rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_daily_telemetry_quality AS
SELECT
    tenant_id,
    quality_status,
    date_trunc('day', observed_at) AS bucket,
    count(*)::int AS sample_count,
    count(DISTINCT metric_id)::int AS metric_count,
    count(DISTINCT asset_id)::int AS asset_count,
    max(observed_at) AS latest_observed_at
FROM dcc.telemetry_readings
GROUP BY tenant_id, quality_status, date_trunc('day', observed_at);

CREATE UNIQUE INDEX IF NOT EXISTS mv_daily_telemetry_pk
    ON dcc.mv_daily_telemetry_quality (tenant_id, quality_status, bucket);

-- Workflow health rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_workflow_health AS
SELECT
    tenant_id,
    workflow_type,
    status,
    priority,
    count(*)::int AS item_count,
    count(*) FILTER (WHERE due_at < now() AND status NOT IN ('closed', 'cancelled'))::int AS overdue_count,
    round(avg(extract(epoch FROM (now() - opened_at)) / 86400.0)::numeric, 1) AS mean_age_days
FROM dcc.operational_workflows
GROUP BY tenant_id, workflow_type, status, priority;

CREATE UNIQUE INDEX IF NOT EXISTS mv_workflow_health_pk
    ON dcc.mv_workflow_health (tenant_id, workflow_type, status, priority);

-- Estimate cost rollup (replaces the expensive CROSS JOIN LATERAL view)
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_estimate_cost_rollup AS
SELECT
    e.tenant_id,
    e.id AS estimate_id,
    e.currency,
    l.phase,
    count(DISTINCT l.id) AS line_count,
    sum(l.extended_base) FILTER (WHERE l.start_month = 0) AS first_period_cost,
    sum(
        l.extended_base
        * power(1 + l.escalation_pct, (period.month_no - l.start_month)::numeric / 12)
        / power(1 + e.discount_rate, period.month_no::numeric / 12)
    ) AS present_value_base,
    sum(
        coalesce(l.extended_low, l.extended_base)
        * power(1 + l.escalation_pct, (period.month_no - l.start_month)::numeric / 12)
        / power(1 + e.discount_rate, period.month_no::numeric / 12)
    ) AS present_value_low,
    sum(
        coalesce(l.extended_high, l.extended_base)
        * power(1 + l.escalation_pct, (period.month_no - l.start_month)::numeric / 12)
        / power(1 + e.discount_rate, period.month_no::numeric / 12)
    ) AS present_value_high,
    count(DISTINCT l.id) FILTER (WHERE l.pricing_status = 'unpriced') AS unpriced_lines,
    count(DISTINCT l.id) FILTER (WHERE l.pricing_status = 'synthetic') AS synthetic_lines
FROM dcc.estimate_projects e
JOIN dcc.estimate_line_items l ON l.tenant_id = e.tenant_id AND l.estimate_id = e.id
CROSS JOIN LATERAL (
    SELECT month_no FROM generate_series(
        l.start_month,
        e.horizon_months,
        coalesce(l.recurrence_months, e.horizon_months + 1)
    ) AS periods(month_no)
) period
GROUP BY e.tenant_id, e.id, e.currency, l.phase;

CREATE UNIQUE INDEX IF NOT EXISTS mv_estimate_cost_rollup_pk
    ON dcc.mv_estimate_cost_rollup (tenant_id, estimate_id, phase);

-- ---------------------------------------------------------------------------
-- Refresh function for materialized views
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION dcc.refresh_materialized_views()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_daily_kpi;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_daily_telemetry_quality;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_workflow_health;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_estimate_cost_rollup;
END;
$$;

-- ---------------------------------------------------------------------------
-- Evidence hash chain verification function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION dcc.verify_evidence_chain(p_tenant_id uuid)
RETURNS TABLE (
    sequence bigint,
    event_id uuid,
    is_valid bool,
    expected_hash text,
    actual_hash text
)
LANGUAGE plpgsql
AS $$
DECLARE
    prev_hash text := '';
    rec record;
    computed text;
BEGIN
    FOR rec IN
        SELECT e.sequence, e.id, e.event_hash, e.payload, e.occurred_at, e.actor_ref, e.previous_hash
        FROM dcc.evidence_events e
        WHERE e.tenant_id = p_tenant_id
        ORDER BY e.sequence
    LOOP
        computed := encode(
            digest(
                coalesce(rec.previous_hash, '') || rec.payload::text || rec.occurred_at::text || coalesce(rec.actor_ref, ''),
                'sha256'
            ),
            'hex'
        );
        sequence := rec.sequence;
        event_id := rec.id;
        is_valid := (computed = rec.event_hash);
        expected_hash := computed;
        actual_hash := rec.event_hash;
        RETURN NEXT;
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- Pagination helper function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION dcc.paginate(
    p_limit int DEFAULT 100,
    p_offset int DEFAULT 0
)
RETURNS TABLE (page_limit int, page_offset int)
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT
        CASE WHEN p_limit BETWEEN 1 AND 1000 THEN p_limit ELSE 100 END,
        CASE WHEN p_offset >= 0 THEN p_offset ELSE 0 END
$$;
