#!/usr/bin/env bash
set -euo pipefail
: "${DCC_DATABASE_URL:?Set DCC_DATABASE_URL to a disposable local demo database}"
: "${DCC_ALLOW_DEMO_RESET:?Explicit reset acknowledgement required}"
db="$(psql "$DCC_DATABASE_URL" -XAtqc 'select current_database()')"
local_db="$(psql "$DCC_DATABASE_URL" -XAtqc "select inet_server_addr() is null or inet_server_addr() in ('127.0.0.1','::1')")"
[[ "$db" == dcc_demo_* && "$local_db" == t && "$DCC_ALLOW_DEMO_RESET" == "RESET_$db" ]] || { echo "Refusing reset: use a local dcc_demo_* database and exact RESET_$db acknowledgement" >&2; exit 2; }
psql "$DCC_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "DELETE FROM dcc.tenants WHERE slug='dcc-demo-lab'"
echo "Removed only the seeded dcc-demo-lab tenant from $db."
