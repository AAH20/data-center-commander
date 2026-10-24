#!/usr/bin/env bash
# verify_rls_isolation.sh -- provision a role that CANNOT bypass row-level security.
#
# Why this exists
# ---------------
# Every table in this project is created with ENABLE + FORCE ROW LEVEL SECURITY and a
# `tenant_scope` policy:
#
#     CREATE POLICY tenant_scope ON dcc.<table>
#       USING      (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
#       WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);
#
# Every test that exercised that policy connected as the database owner, which on a
# local Homebrew Postgres is a SUPERUSER. A superuser (or any role with BYPASSRLS)
# ignores row-level security completely -- even FORCE does not apply to it, because
# FORCE only removes the table owner's exemption. So those tests pass whether the
# policy is correct, wrong, or missing.
#
# This script creates `dcc_rls_probe`: NOSUPERUSER NOCREATEDB NOCREATEROLE
# NOBYPASSRLS LOGIN. Nothing about that role can skip the policy, so
# tests/security/test_rls_non_superuser.py measures the real thing.
#
# Idempotent: the role is dropped and recreated on every run, then re-granted.
# It never revokes a privilege from anybody else and it owns nothing.
#
# Usage:
#   scripts/verify_rls_isolation.sh                  # create/refresh the role
#   scripts/verify_rls_isolation.sh --read-only      # same, but no INSERT grant
#   scripts/verify_rls_isolation.sh --drop           # remove the role
#
# Environment:
#   DCC_DATABASE_URL          owner DSN (default postgresql://localhost:5432/dcc_demo_local)
#   DCC_RLS_PROBE_ROLE        role name (default dcc_rls_probe)
#   DCC_RLS_PROBE_PASSWORD    password (default dcc_rls_probe_local_dev_only)
#   DCC_ALLOW_NON_DEMO_DB=1   permit running against a database not named dcc_demo_*
set -euo pipefail

ROLE="${DCC_RLS_PROBE_ROLE:-dcc_rls_probe}"
PASSWORD="${DCC_RLS_PROBE_PASSWORD:-dcc_rls_probe_local_dev_only}"
DSN="${DCC_DATABASE_URL:-postgresql://localhost:5432/dcc_demo_local}"
READ_ONLY=0
DROP_ONLY=0

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dsn)       DSN="${2:?--dsn needs a value}"; shift 2 ;;
    --read-only) READ_ONLY=1; shift ;;
    --drop)      DROP_ONLY=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# The role name is interpolated into SQL identifiers, so constrain it hard.
[[ "$ROLE" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || {
  echo "Refusing: DCC_RLS_PROBE_ROLE must match ^[a-z_][a-z0-9_]{0,62}\$ (got '$ROLE')" >&2; exit 2; }
# Single quotes are the only way out of a SQL string literal; forbid them.
[[ "$PASSWORD" != *"'"* && "$PASSWORD" != *'\'* ]] || {
  echo "Refusing: DCC_RLS_PROBE_PASSWORD must not contain quotes or backslashes" >&2; exit 2; }

psql_owner() { psql "$DSN" -X -v ON_ERROR_STOP=1 "$@"; }

# --- preconditions -----------------------------------------------------------
db="$(psql_owner -Atqc 'select current_database()')"
if [[ "$db" != dcc_demo_* && "${DCC_ALLOW_NON_DEMO_DB:-0}" != 1 ]]; then
  echo "Refusing: database '$db' is not named dcc_demo_*; set DCC_ALLOW_NON_DEMO_DB=1 to override" >&2
  exit 2
fi
# host() strips the /128 prefix that inet::text carries (e.g. '::1/128').
is_local="$(psql_owner -Atqc "select coalesce(host(inet_server_addr()),'') in ('','127.0.0.1','::1')")"
[[ "$is_local" == t ]] || { echo "Refusing: '$db' is not a local server" >&2; exit 2; }
[[ "$(psql_owner -Atqc "select to_regnamespace('dcc') is not null")" == t ]] || {
  echo "Refusing: schema dcc does not exist in '$db' -- apply database/schema.sql first" >&2; exit 2; }

owner_user="$(psql_owner -Atqc 'select current_user')"
owner_super="$(psql_owner -Atqc "select usesuper from pg_user where usename = current_user")"
echo "Target      : $db (owner: $owner_user, usesuper=$owner_super)"
echo "Probe role  : $ROLE"
echo

# --- drop path (also used as the first half of a re-create) ------------------
if [[ "$(psql_owner -Atqc "select 1 from pg_roles where rolname = '$ROLE'")" == 1 ]]; then
  # DROP OWNED BY silently drops objects the role owns, so refuse if it owns any.
  owned="$(psql_owner -Atqc "
    select (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
             where n.nspname not in ('pg_catalog','information_schema')
               and pg_get_userbyid(c.relowner) = '$ROLE')
         + (select count(*) from pg_namespace where pg_get_userbyid(nspowner) = '$ROLE')
         + (select count(*) from pg_proc where pg_get_userbyid(proowner) = '$ROLE')")"
  if [[ "$owned" != 0 ]]; then
    echo "Refusing: role '$ROLE' owns $owned object(s); this script will not drop them." >&2
    echo "           Inspect with:  select ... from pg_class where pg_get_userbyid(relowner)='$ROLE';" >&2
    exit 3
  fi
  psql_owner -q -c "DROP OWNED BY \"$ROLE\";"   # revokes its grants; it owns nothing (checked above)
  psql_owner -q -c "DROP ROLE \"$ROLE\";"
  echo "Dropped previous '$ROLE'."
fi

if [[ "$DROP_ONLY" == 1 ]]; then
  echo "Role '$ROLE' removed. Nothing else changed."
  exit 0
fi

# --- create the genuinely unprivileged role ---------------------------------
# Every capability that would let a role skip a policy is explicitly off:
#   NOSUPERUSER  -> cannot ignore RLS the way the owner does
#   NOBYPASSRLS  -> cannot set BYPASSRLS later
#   NOCREATEDB / NOCREATEROLE -> cannot escalate on its own
psql_owner -q -c "CREATE ROLE \"$ROLE\" NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS LOGIN PASSWORD '$PASSWORD';"

# --- minimum grants ---------------------------------------------------------
# `REVOKE ALL ON SCHEMA dcc FROM PUBLIC` is in schema.sql, so USAGE must be given
# back explicitly. SELECT on dcc.assets is what the isolation asserts read.
# INSERT on dcc.assets exists ONLY so a test can prove a cross-tenant write is
# rejected by the policy's WITH CHECK clause -- without INSERT the rejection would
# be indistinguishable from "permission denied". --read-only drops it again.
psql_owner -q <<SQL
GRANT USAGE ON SCHEMA dcc TO "$ROLE";
GRANT SELECT ON dcc.assets TO "$ROLE";
$( [[ "$READ_ONLY" == 1 ]] && echo "-- write grant suppressed by --read-only" || echo "GRANT INSERT ON dcc.assets TO \"$ROLE\";" )
SQL

# --- print what the operator must see ---------------------------------------
echo "=== role flags (pg_authid-derived) ==="
psql_owner -P pager=off -c "
select rolname,
       rolsuper        as usesuper,
       rolbypassrls,
       rolcanlogin,
       rolcreatedb,
       rolcreaterole
from pg_roles where rolname = '$ROLE';"

echo "=== cross-check against pg_user.usesuper ==="
psql_owner -P pager=off -c "
select usename, usesuper, usecreatedb, userepl, usebypassrls
from pg_user where usename = '$ROLE';"

echo "=== direct grants held by $ROLE ==="
psql_owner -P pager=off -c "
select table_schema, table_name, privilege_type
from information_schema.role_table_grants
where grantee = '$ROLE' order by table_name, privilege_type;"
# Schema USAGE is not exposed by information_schema.role_usage_grants, so read the
# ACL directly. USAGE ('U') on dcc is required because schema.sql revokes it from PUBLIC.
psql_owner -P pager=off -c "
select nspname,
       coalesce(nspacl::text, '(default)')                as schema_acl,
       has_schema_privilege('$ROLE', nspname, 'USAGE')     as has_usage
from pg_namespace where nspname = 'dcc';"

# --- live proof as the role, not as the owner -------------------------------
# A real login (not SET ROLE) is what a deployment actually does, so use it when the
# server's pg_hba allows it, and say plainly when it does not.
echo "=== live proof: logged in AS $ROLE ==="
PROBE_LOGIN=0
if PGPASSWORD="$PASSWORD" psql "$DSN" -X -U "$ROLE" -Atqc 'select 1' >/dev/null 2>&1; then
  PROBE_LOGIN=1
  echo "(direct login as $ROLE succeeded)"
else
  echo "(direct login refused by pg_hba; falling back to SET ROLE -- the pytest module always uses a real login)"
fi

run_as_probe() {
  if [[ "$PROBE_LOGIN" == 1 ]]; then
    PGPASSWORD="$PASSWORD" psql "$DSN" -X -U "$ROLE" "$@" 2>&1 || true
  else
    psql_owner -c "SET ROLE \"$ROLE\";" "$@" 2>&1 || true
  fi
}

run_as_probe -P pager=off -c "
select current_user                                              as current_user,
       (select usesuper from pg_user where usename = current_user)     as usesuper,
       (select rolbypassrls from pg_roles where rolname = current_user) as rolbypassrls;"

echo "--- tenant_scope with dcc.tenant_id unset (must be 0 rows, not all rows) ---"
run_as_probe -Atqc "select coalesce(current_setting('dcc.tenant_id', true), '<unset>') as setting,
                           (select count(*) from dcc.assets) as rows_visible;"

echo "--- same role against a table it was NOT granted (must be permission denied) ---"
run_as_probe -Atqc "select count(*) from dcc.sites;" | sed 's/^/    /'

echo "--- policy that applies to $ROLE (FORCE, so no owner exemption) ---"
psql_owner -P pager=off -c "
select tablename, policyname, cmd, qual, with_check
from pg_policies where schemaname = 'dcc' and tablename = 'assets';"

echo
echo "Done. '$ROLE' exists with: USAGE on schema dcc, SELECT on dcc.assets$( [[ "$READ_ONLY" == 1 ]] || echo ", INSERT on dcc.assets (test-only)" )."
echo "It is NOSUPERUSER NOBYPASSRLS, so every policy applies to it."
echo "Now run:  .venv/bin/python -m pytest tests/security/test_rls_non_superuser.py -v -s"
