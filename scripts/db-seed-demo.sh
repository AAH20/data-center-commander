#!/usr/bin/env bash
set -euo pipefail
: "${DCC_DATABASE_URL:?Set DCC_DATABASE_URL to a disposable local demo database}"
: "${DCC_ALLOW_SYNTHETIC_DATA:?Explicit synthetic-data acknowledgement required}"
[[ "$DCC_ALLOW_SYNTHETIC_DATA" == "YES_SYNTHETIC_dcc_demo_local" ]] || { echo "Refusing: acknowledgement must be YES_SYNTHETIC_dcc_demo_local" >&2; exit 2; }
db="$(psql "$DCC_DATABASE_URL" -XAtqc 'select current_database()')"
local_db="$(psql "$DCC_DATABASE_URL" -XAtqc "select inet_server_addr() is null or inet_server_addr() in ('127.0.0.1','::1')")"
[[ "$db" == dcc_demo_* && "$local_db" == t ]] || { echo "Refusing: database must be named dcc_demo_* and hosted locally" >&2; exit 2; }
psql "$DCC_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f "$(dirname "$0")/../database/demo_seed.sql"
echo "Synthetic fixture seeded into $db; all seeded records are explicitly labelled synthetic."
