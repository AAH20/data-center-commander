-- ---------------------------------------------------------------------------
-- Disaster recovery persistence.
--
-- dcc/dr/ is ~3,950 lines of backup policy, DR test plan, failover and RTO/RPO
-- compliance machinery, and it is referenced by no route and backed by no table.
-- Everything it produces lives in process memory, so it is lost on restart and
-- differs between uvicorn workers -- the same defect that made the API-key store
-- unusable in any real deployment.
--
-- These four tables back the parts of the model that describe state an operator
-- must be able to see next week: what backup policies exist, what DR tests are
-- planned and what happened when they ran, and the RTO/RPO measurements those runs
-- produced. Failover procedures and executions are deliberately NOT modelled here:
-- they drive live automation and have no handler, so persisting them would create
-- rows nothing can act on.
--
-- RLS matches the convention used by every other tenant table in this schema:
-- ENABLE + FORCE, with a tenant_scope policy reading dcc.tenant_id. FORCE matters:
-- without it the table owner bypasses the policy and a bug in tenant binding shows
-- up only in production.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dcc.backup_policies (
    policy_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    name             text NOT NULL,
    policy_type      text NOT NULL DEFAULT 'scheduled'
                     CHECK (policy_type IN ('scheduled','continuous','on_demand','snapshot')),
    schedule         text,
    custom_cron      text,
    retention_days   integer NOT NULL DEFAULT 30 CHECK (retention_days > 0),
    tables           text[] NOT NULL DEFAULT '{}',
    compression      text NOT NULL DEFAULT 'none'
                     CHECK (compression IN ('none','gzip','zstd','lz4')),
    verify_after     boolean NOT NULL DEFAULT true,
    enabled          boolean NOT NULL DEFAULT true,
    status           text NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','running','succeeded','failed','disabled')),
    tags             jsonb NOT NULL DEFAULT '[]',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    last_run_at      timestamptz,
    next_run_at      timestamptz,
    UNIQUE (tenant_id, name)
);

-- "Which policies are due" is the question the scheduler asks on every tick, and
-- it is the only query that scans without a tenant filter already selected.
CREATE INDEX IF NOT EXISTS backup_policies_due_idx
    ON dcc.backup_policies (next_run_at)
    WHERE enabled AND next_run_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS backup_policies_tenant_idx
    ON dcc.backup_policies (tenant_id, name);


CREATE TABLE IF NOT EXISTS dcc.dr_test_plans (
    plan_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    name               text NOT NULL,
    description        text NOT NULL DEFAULT '',
    test_type          text NOT NULL DEFAULT 'failover'
                       CHECK (test_type IN ('failover','restore','tabletop','partial','full')),
    frequency          text NOT NULL DEFAULT 'monthly'
                       CHECK (frequency IN ('daily','weekly','monthly','quarterly','annual','ad_hoc')),
    steps              jsonb NOT NULL DEFAULT '[]',
    rto_target_seconds integer CHECK (rto_target_seconds IS NULL OR rto_target_seconds > 0),
    rpo_target_seconds integer CHECK (rpo_target_seconds IS NULL OR rpo_target_seconds > 0),
    enabled            boolean NOT NULL DEFAULT true,
    tags               jsonb NOT NULL DEFAULT '[]',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    last_run_at        timestamptz,
    next_run_at        timestamptz,
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS dr_test_plans_due_idx
    ON dcc.dr_test_plans (next_run_at)
    WHERE enabled AND next_run_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS dr_test_plans_tenant_idx
    ON dcc.dr_test_plans (tenant_id, name);


CREATE TABLE IF NOT EXISTS dcc.dr_test_executions (
    execution_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id            uuid REFERENCES dcc.dr_test_plans(plan_id) ON DELETE SET NULL,
    tenant_id          uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    test_type          text NOT NULL
                       CHECK (test_type IN ('failover','restore','tabletop','partial','full')),
    status             text NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','running','succeeded','failed','aborted')),
    steps              jsonb NOT NULL DEFAULT '[]',
    -- Actuals are nullable on purpose. A test that did not measure RTO must not
    -- record 0 seconds, which would read as an excellent result and silently
    -- improve the compliance rate.
    rto_actual_seconds integer CHECK (rto_actual_seconds IS NULL OR rto_actual_seconds >= 0),
    rpo_actual_seconds integer CHECK (rpo_actual_seconds IS NULL OR rpo_actual_seconds >= 0),
    result             text,
    error              text,
    evidence           jsonb NOT NULL DEFAULT '{}',
    metadata           jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    started_at         timestamptz,
    completed_at       timestamptz,
    duration_seconds   integer CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

CREATE INDEX IF NOT EXISTS dr_test_executions_tenant_idx
    ON dcc.dr_test_executions (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS dr_test_executions_plan_idx
    ON dcc.dr_test_executions (plan_id, created_at DESC);


CREATE TABLE IF NOT EXISTS dcc.dr_metric_measurements (
    measurement_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    metric_type     text NOT NULL CHECK (metric_type IN ('rto','rpo')),
    value_seconds   numeric(12,2) NOT NULL CHECK (value_seconds >= 0),
    target_seconds  numeric(12,2) CHECK (target_seconds IS NULL OR target_seconds > 0),
    status          text NOT NULL DEFAULT 'compliant'
                    CHECK (status IN ('compliant','warning','breach','unknown')),
    source          text NOT NULL DEFAULT 'dr_test',
    execution_id    uuid REFERENCES dcc.dr_test_executions(execution_id) ON DELETE SET NULL,
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    metadata        jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS dr_metric_measurements_tenant_time_idx
    ON dcc.dr_metric_measurements (tenant_id, metric_type, occurred_at DESC);


-- --- row level security -----------------------------------------------------
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'dcc'
          AND c.relname IN ('backup_policies','dr_test_plans','dr_test_executions','dr_metric_measurements')
    LOOP
        EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY', t.table_name);
        EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY', t.table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_scope ON dcc.%I', t.table_name);
        EXECUTE format(
            'CREATE POLICY tenant_scope ON dcc.%I USING (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid)',
            t.table_name
        );
    END LOOP;
END $$;

COMMENT ON TABLE dcc.backup_policies IS
    'Backup schedules per tenant. next_run_at drives the scheduler tick.';
COMMENT ON TABLE dcc.dr_test_plans IS
    'Planned disaster-recovery tests with RTO/RPO targets.';
COMMENT ON TABLE dcc.dr_test_executions IS
    'Runs of a DR test plan. Actual RTO/RPO are nullable: an unmeasured result must '
    'not be recorded as zero, which would inflate the compliance rate.';
COMMENT ON TABLE dcc.dr_metric_measurements IS
    'Observed RTO/RPO samples with the target in force at the time of measurement.';
