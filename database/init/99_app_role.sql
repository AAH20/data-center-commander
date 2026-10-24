-- 99_app_role.sql
--
-- Create the role the application actually connects as.
--
-- The postgres image's POSTGRES_USER is the cluster's initdb superuser. A superuser
-- bypasses row-level security unconditionally -- FORCE does not apply to it -- so an
-- application connected as POSTGRES_USER silently reads and writes across every tenant
-- while all 40 tenant_scope policies sit there looking enforced. That is the same defect
-- class as testing RLS as the owner: a control that is present but cannot act.
--
-- This role is NOSUPERUSER, NOBYPASSRLS, and owns nothing, so the policies apply to it.
-- It runs after the schema and every migration (name sorts last in /docker-entrypoint-
-- initdb.d) because the grants need the tables to exist.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcc_app') THEN
        CREATE ROLE dcc_app
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOBYPASSRLS
            PASSWORD 'dcc_app_dev_password';
    END IF;
END $$;

-- current_database(), not a literal: this script must work against whatever database
-- name the deployment uses. A hardcoded name fails silently on a renamed database and
-- leaves the app unable to connect at all.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO dcc_app', current_database());
END $$;
GRANT USAGE ON SCHEMA dcc TO dcc_app;

-- DML only. No DDL, no ownership: the app must not be able to disable the policies that
-- constrain it, which is exactly what table ownership would allow.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dcc TO dcc_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dcc TO dcc_app;

-- Tables and partitions created later by a migration inherit nothing automatically.
ALTER DEFAULT PRIVILEGES IN SCHEMA dcc
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dcc_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA dcc
    GRANT USAGE, SELECT ON SEQUENCES TO dcc_app;

-- Prove the outcome rather than assuming it: a role that can bypass RLS makes every
-- policy in this schema decorative.
DO $$
DECLARE
    v_super boolean;
    v_bypass boolean;
BEGIN
    SELECT rolsuper, rolbypassrls INTO v_super, v_bypass FROM pg_roles WHERE rolname = 'dcc_app';
    IF v_super OR v_bypass THEN
        RAISE EXCEPTION 'dcc_app can bypass row-level security (super=%, bypassrls=%)', v_super, v_bypass;
    END IF;
    RAISE NOTICE 'dcc_app created: super=false bypassrls=false, policies apply';
END $$;
