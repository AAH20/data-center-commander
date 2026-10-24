-- 010_telemetry_partition_rls.sql
--
-- Close a row-level-security gap on the partitioned telemetry table.
--
-- 006 created dcc.telemetry_readings_partitioned and twelve monthly partitions but
-- never enabled RLS on any of them, so 13 tenant-scoped relations carried no tenant
-- policy at all while the other 39 did. The leak is latent rather than active today
-- (the partitions hold zero rows; the plain dcc.telemetry_readings table holds the data
-- and is protected), which is what makes it worth fixing now: the moment a writer is
-- pointed at the partitioned parent, every role with SELECT reads every tenant.
--
-- RLS is enabled on the parent AND on each partition. The parent's policy covers access
-- routed through the parent, but Postgres does not apply a parent's policy to a direct
-- partition reference, so a partition needs its own. New partitions created later must
-- inherit this, so the creation helper below enables protection as it creates each one.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Protect the partitioned parent
-- ---------------------------------------------------------------------------

ALTER TABLE dcc.telemetry_readings_partitioned ENABLE ROW LEVEL SECURITY;
ALTER TABLE dcc.telemetry_readings_partitioned FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_scope ON dcc.telemetry_readings_partitioned;
CREATE POLICY tenant_scope ON dcc.telemetry_readings_partitioned
    USING (tenant_id = (NULLIF(current_setting('dcc.tenant_id', true), ''))::uuid)
    WITH CHECK (tenant_id = (NULLIF(current_setting('dcc.tenant_id', true), ''))::uuid);

-- ---------------------------------------------------------------------------
-- 2. Protect every existing partition
-- ---------------------------------------------------------------------------
-- Enumerated from pg_inherits rather than hardcoded, so this migration protects
-- whatever actually exists rather than the twelve names that happened to be in 006.

DO $$
DECLARE
    v_partition text;
BEGIN
    FOR v_partition IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'dcc'
          AND p.relname = 'telemetry_readings_partitioned'
        ORDER BY c.relname
    LOOP
        EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY', v_partition);
        EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY', v_partition);
        EXECUTE format('DROP POLICY IF EXISTS tenant_scope ON dcc.%I', v_partition);
        EXECUTE format(
            'CREATE POLICY tenant_scope ON dcc.%I '
            'USING (tenant_id = (NULLIF(current_setting(''dcc.tenant_id'', true), ''''))::uuid) '
            'WITH CHECK (tenant_id = (NULLIF(current_setting(''dcc.tenant_id'', true), ''''))::uuid)',
            v_partition
        );
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Make future partitions inherit the protection
-- ---------------------------------------------------------------------------
-- A partition created without RLS is a tenant leak that no test would notice until
-- someone wrote to it. Creating it through this function means the protection is not
-- something a future migration has to remember.

CREATE OR REPLACE FUNCTION dcc.ensure_telemetry_partitions(p_months integer DEFAULT 12)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    v_start date;
    v_end date;
    v_partition text;
    v_created integer := 0;
BEGIN
    FOR i IN 0..(p_months - 1) LOOP
        v_start := date_trunc('month', now()) + (i || ' months')::interval;
        v_end := v_start + interval '1 month';
        v_partition := 'telemetry_readings_' || to_char(v_start, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS dcc.%I PARTITION OF dcc.telemetry_readings_partitioned '
            'FOR VALUES FROM (%L) TO (%L)',
            v_partition, v_start, v_end
        );
        v_created := v_created + 1;

        -- Idempotent: enable|force RLS and recreate the policy on every pass, so a
        -- partition created by an older version of this function is repaired too.
        EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY', v_partition);
        EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY', v_partition);
        EXECUTE format('DROP POLICY IF EXISTS tenant_scope ON dcc.%I', v_partition);
        EXECUTE format(
            'CREATE POLICY tenant_scope ON dcc.%I '
            'USING (tenant_id = (NULLIF(current_setting(''dcc.tenant_id'', true), ''''))::uuid) '
            'WITH CHECK (tenant_id = (NULLIF(current_setting(''dcc.tenant_id'', true), ''''))::uuid)',
            v_partition
        );
    END LOOP;

    RETURN v_created;
END $$;

COMMENT ON FUNCTION dcc.ensure_telemetry_partitions(integer) IS
    'Create monthly telemetry partitions and enable FORCE row-level security on each. '
    'Partitions created outside this function will not be protected.';

COMMIT;
