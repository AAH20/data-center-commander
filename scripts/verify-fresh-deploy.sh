#!/usr/bin/env bash
# Verify that a completely empty database can be brought up from this repository.
#
# Why this exists: the Integration workflow applied schema.sql and every migration
# with `psql -f` and no ON_ERROR_STOP, so psql ignored failing statements and exited 0.
# Three migrations aborted on a fresh database and a materialized view kept the wrong
# column names, and CI reported the migration step as passing throughout. A gate that
# cannot fail is indistinguishable from one that does not run.
#
# This script fails on the first error and then proves the result is usable, not just
# that the SQL parsed: it asserts the expected table count and, when the application is
# importable, exercises every GET /v2 route against the fresh database.
#
# Usage:
#   scripts/verify-fresh-deploy.sh                 # uses a scratch database on localhost
#   DCC_VERIFY_DSN=postgresql://... scripts/...    # uses an existing empty database
#
# Requires: psql on PATH, and a server the current user can create databases on.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCRATCH_DB="dcc_fresh_deploy_check"
CREATED_DB=0

cleanup() {
  if [ "$CREATED_DB" -eq 1 ]; then
    dropdb --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [ -n "${DCC_VERIFY_DSN:-}" ]; then
  DSN="$DCC_VERIFY_DSN"
  echo "==> using supplied database"
else
  echo "==> creating scratch database $SCRATCH_DB"
  dropdb --if-exists "$SCRATCH_DB"
  createdb "$SCRATCH_DB"
  CREATED_DB=1
  DSN="postgresql:///${SCRATCH_DB}"
fi

# ON_ERROR_STOP is the whole point. Without it psql prints ERROR and exits 0.
PSQL=(psql "$DSN" -v ON_ERROR_STOP=1 -q)

echo "==> schema.sql"
"${PSQL[@]}" -f database/schema.sql

echo "==> migrations"
for f in database/migrations/*.sql; do
  printf '    %-46s' "$(basename "$f")"
  "${PSQL[@]}" -f "$f"
  echo "ok"
done

TABLES=$("${PSQL[@]}" -tA -c \
  "select count(*) from information_schema.tables where table_schema='dcc';")
echo "==> dcc tables: $TABLES"

if [ "$TABLES" -lt 40 ]; then
  echo "FATAL: expected at least 40 tables in schema dcc, found $TABLES" >&2
  exit 1
fi

# Derived objects that earlier revisions silently left in the wrong shape. Each of
# these was broken on a fresh database while CI reported success.
echo "==> required objects"
MISSING=$("${PSQL[@]}" -tA -c "
  SELECT string_agg(o, ', ') FROM (VALUES
    ('dcc.mv_workflow_health'),('dcc.mv_telemetry_quality'),
    ('dcc.backup_policies'),('dcc.dr_test_plans'),('dcc.dr_metric_measurements'),
    ('dcc.procedures'),('dcc.evidence_events')
  ) AS v(o) WHERE to_regclass(o) IS NULL;")
if [ -n "${MISSING:-}" ]; then
  echo "FATAL: missing object(s): $MISSING" >&2
  exit 1
fi
echo "    all present"

# The workflow view's column names are the contract /v2/analytics selects on.
echo "==> mv_workflow_health exposes items/overdue"
COLS=$("${PSQL[@]}" -tA -c \
  "select count(*) from pg_attribute where attrelid='dcc.mv_workflow_health'::regclass
     and attname in ('items','overdue','mean_age_days') and not attisdropped;")
if [ "$COLS" -ne 3 ]; then
  echo "FATAL: mv_workflow_health is missing expected columns (found $COLS of 3)" >&2
  echo "       005 and 006 both define this view; 006 must replace it, not no-op." >&2
  exit 1
fi
echo "    ok"

echo "==> RLS enabled and forced on tenant tables"
UNPROTECTED=$("${PSQL[@]}" -tA -c \
  "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='dcc' and c.relkind='r'
      and c.relname in ('backup_policies','dr_test_plans','dr_test_executions',
                        'dr_metric_measurements')
      and not (c.relrowsecurity and c.relforcerowsecurity);")
if [ "$UNPROTECTED" -ne 0 ]; then
  echo "FATAL: $UNPROTECTED table(s) lack ENABLE + FORCE row level security" >&2
  exit 1
fi
echo "    ok"

echo "==> application smoke test"
if python -c "import dcc.api_async" >/dev/null 2>&1; then
  DCC_DATABASE_URL="$DSN" python scripts/verify_fresh_deploy_routes.py
else
  echo "    skipped: dcc.api_async not importable (run from the project venv)"
fi

echo
echo "PASS: fresh deploy builds and serves"
