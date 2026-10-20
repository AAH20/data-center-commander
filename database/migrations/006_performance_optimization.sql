-- Migration 005: Performance optimization — indexes, partitioning, materialized views
-- Apply after migrations 001-004. Idempotent.

-- ---------------------------------------------------------------------------
-- 1. Composite indexes for tenant-scoped queries
-- ---------------------------------------------------------------------------

-- Assets: tenant + lifecycle_state + name (common filter)
CREATE INDEX IF NOT EXISTS assets_tenant_state_name_idx
    ON dcc.assets(tenant_id, lifecycle_state, name);

-- Workflows: tenant + status + priority + due_at (queue ordering)
CREATE INDEX IF NOT EXISTS workflows_tenant_status_priority_due_idx
    ON dcc.operational_workflows(tenant_id, status, priority, due_at);

-- KPI observations: tenant + facility + definition + window_end (analytics)
CREATE INDEX IF NOT EXISTS kpi_obs_tenant_facility_def_window_idx
    ON dcc.kpi_observations(tenant_id, facility_id, kpi_definition_id, window_end DESC);

-- Evidence events: tenant + sequence (hash chain verification)
CREATE INDEX IF NOT EXISTS evidence_tenant_sequence_idx
    ON dcc.evidence_events(tenant_id, sequence);

-- Cost actuals: tenant + accounting_period + cost_type (reconciliation)
CREATE INDEX IF NOT EXISTS cost_actuals_tenant_period_type_idx
    ON dcc.cost_actuals(tenant_id, accounting_period, cost_type);

-- Price observations: tenant + item_code + geography + valid_from (lookup)
-- Already exists as price_lookup_idx, but add quality_status filter
CREATE INDEX IF NOT EXISTS price_lookup_approved_idx
    ON dcc.price_observations(tenant_id, item_code, geography, valid_from DESC)
    WHERE quality_status = 'approved';

-- Capacity snapshots: tenant + facility + dimension + observed_at
CREATE INDEX IF NOT EXISTS capacity_tenant_facility_dim_observed_idx
    ON dcc.capacity_snapshots(tenant_id, facility_id, dimension, observed_at DESC);

-- Telemetry readings: tenant + metric_id + observed_at (time-series queries)
CREATE INDEX IF NOT EXISTS telemetry_tenant_metric_observed_idx
    ON dcc.telemetry_readings(tenant_id, metric_id, observed_at DESC);

-- ---------------------------------------------------------------------------
-- 2. Materialized views for common aggregations
-- ---------------------------------------------------------------------------

-- Daily KPI rollup (replaces expensive GROUP BY on the fly)
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_daily_kpi_rollup AS
SELECT
    o.tenant_id,
    d.metric_key,
    d.name,
    d.unit,
    date_trunc('day', o.window_end) AS bucket,
    avg(o.value_numeric) AS value,
    avg(o.coverage) AS coverage,
    avg(o.uncertainty) AS uncertainty,
    count(*)::int AS samples,
    bool_or(o.provenance->>'synthetic' = 'true') AS synthetic
FROM dcc.kpi_observations o
JOIN dcc.kpi_definitions d ON d.tenant_id = o.tenant_id AND d.id = o.kpi_definition_id
GROUP BY o.tenant_id, d.metric_key, d.name, d.unit, date_trunc('day', o.window_end);

CREATE UNIQUE INDEX IF NOT EXISTS mv_daily_kpi_rollup_pk
    ON dcc.mv_daily_kpi_rollup(tenant_id, metric_key, bucket);

-- Workflow health summary
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_workflow_health AS
SELECT
    tenant_id,
    workflow_type,
    status,
    priority,
    count(*)::int AS items,
    count(*) FILTER (WHERE due_at < now() AND status NOT IN ('closed', 'cancelled'))::int AS overdue,
    round(avg(extract(epoch FROM (now() - opened_at)) / 86400.0)::numeric, 1) AS mean_age_days
FROM dcc.operational_workflows
GROUP BY tenant_id, workflow_type, status, priority;

CREATE UNIQUE INDEX IF NOT EXISTS mv_workflow_health_pk
    ON dcc.mv_workflow_health(tenant_id, workflow_type, status, priority);

-- Telemetry quality distribution
CREATE MATERIALIZED VIEW IF NOT EXISTS dcc.mv_telemetry_quality AS
SELECT
    tenant_id,
    quality_status,
    count(*)::int AS samples,
    count(DISTINCT metric_id)::int AS metrics,
    count(DISTINCT asset_id)::int AS assets,
    max(observed_at) AS latest_observed_at
FROM dcc.telemetry_readings
WHERE observed_at >= now() - interval '30 days'
GROUP BY tenant_id, quality_status;

CREATE UNIQUE INDEX IF NOT EXISTS mv_telemetry_quality_pk
    ON dcc.mv_telemetry_quality(tenant_id, quality_status);

-- ---------------------------------------------------------------------------
-- 3. Refresh function for materialized views
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION dcc.refresh_materialized_views()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_daily_kpi_rollup;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_workflow_health;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dcc.mv_telemetry_quality;
END;
$$;

-- ---------------------------------------------------------------------------
-- 4. Evidence chain verification function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION dcc.verify_evidence_chain(p_tenant_id uuid)
RETURNS TABLE (
    sequence bigint,
    event_id uuid,
    event_type text,
    occurred_at timestamptz,
    is_valid bool,
    expected_hash text,
    actual_hash text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_record record;
    v_previous_hash text := '';
    v_computed_hash text;
    v_payload_text text;
BEGIN
    FOR v_record IN
        SELECT e.sequence, e.id, e.event_type, e.occurred_at, e.payload,
               e.previous_hash, e.event_hash, e.actor_ref
        FROM dcc.evidence_events e
        WHERE e.tenant_id = p_tenant_id
        ORDER BY e.sequence
    LOOP
        v_payload_text := v_record.payload::text;
        v_computed_hash := encode(
            digest(
                v_previous_hash || v_payload_text || v_record.occurred_at::text || coalesce(v_record.actor_ref, ''),
                'sha256'
            ),
            'hex'
        );

        sequence := v_record.sequence;
        event_id := v_record.id;
        event_type := v_record.event_type;
        occurred_at := v_record.occurred_at;
        is_valid := (v_computed_hash = v_record.event_hash);
        expected_hash := v_computed_hash;
        actual_hash := v_record.event_hash;

        RETURN NEXT;

        v_previous_hash := v_record.event_hash;
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- 5. Partitioned telemetry table (for new deployments)
-- ---------------------------------------------------------------------------

-- Note: This creates a partitioned version of telemetry_readings.
-- Existing deployments should use pg_partman or manual partition creation.

CREATE TABLE IF NOT EXISTS dcc.telemetry_readings_partitioned (
    id bigint GENERATED ALWAYS AS IDENTITY,
    tenant_id uuid NOT NULL,
    connector_id uuid NOT NULL,
    source_event_id text NOT NULL,
    asset_id uuid,
    meter_id uuid,
    metric_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    interval_start timestamptz,
    interval_end timestamptz,
    value_numeric numeric(24,9),
    value_text text,
    reported_unit text NOT NULL,
    quality_status text NOT NULL,
    source_timezone text,
    clock_offset_ms integer,
    source_cursor text,
    provenance jsonb NOT NULL DEFAULT '{}',
    raw_payload_digest text,
    PRIMARY KEY (tenant_id, id, observed_at)
) PARTITION BY RANGE (observed_at);

-- Create monthly partitions for the next 12 months
-- In production, use pg_partman for automatic partition management
DO $$
DECLARE
    v_start date;
    v_end date;
    v_partition_name text;
BEGIN
    FOR i IN 0..11 LOOP
        v_start := date_trunc('month', now()) + (i || ' months')::interval;
        v_end := v_start + interval '1 month';
        v_partition_name := 'telemetry_readings_' || to_char(v_start, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS dcc.%I PARTITION OF dcc.telemetry_readings_partitioned
             FOR VALUES FROM (%L) TO (%L)',
            v_partition_name, v_start, v_end
        );
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 6. Automated retention policy enforcement
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION dcc.enforce_retention_policy()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant record;
    v_retention_days integer;
BEGIN
    FOR v_tenant IN SELECT id, retention_policy FROM dcc.tenants LOOP
        v_retention_days := (v_tenant.retention_policy->>'telemetry_days')::integer;
        IF v_retention_days IS NOT NULL AND v_retention_days > 0 THEN
            -- Delete old telemetry readings
            DELETE FROM dcc.telemetry_readings
            WHERE tenant_id = v_tenant.id
              AND observed_at < now() - (v_retention_days || ' days')::interval;

            -- Delete old connector runs
            DELETE FROM dcc.connector_runs
            WHERE tenant_id = v_tenant.id
              AND started_at < now() - (v_retention_days || ' days')::interval;
        END IF;
    END LOOP;
END;
$$;
