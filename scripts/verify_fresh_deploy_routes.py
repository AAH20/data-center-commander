"""Exercise every GET /v2 route against a freshly built database.

Companion to scripts/verify-fresh-deploy.sh. The SQL check proves the schema loads;
this proves the application can actually read it. Both were broken while CI was green:
migrations aborted silently under psql without ON_ERROR_STOP, and /v2/analytics
selected columns a materialized view did not have on a new database.

A route is considered verified only if it returns 200. Requiring a tenant that the
fresh database does not contain, and a key minted at run time, means this exercises the
authentication and RLS path as well -- the same path a real deployment takes.
"""

from __future__ import annotations

import os
import sys
import uuid

TENANT = "11111111-1111-4111-8111-111111111111"
SLUG = "fresh-deploy-check"


def _seed_tenant(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO dcc.tenants (id, slug, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (slug) DO NOTHING",
            (TENANT, SLUG, "Fresh Deploy Check"),
        )


def main() -> int:
    dsn = os.environ.get("DCC_DATABASE_URL", "")
    if not dsn:
        print("    FATAL: DCC_DATABASE_URL is not set", file=sys.stderr)
        return 1

    _seed_tenant(dsn)

    # Mint the key before importing the app: DCC_API_KEYS is read at import time, so a
    # key registered afterwards would authenticate nothing.
    from dcc.security.api_keys import generate_api_key, hash_api_key

    raw_key = generate_api_key()
    os.environ["DCC_API_KEYS"] = f"{TENANT}:{hash_api_key(raw_key)}"
    os.environ.pop("DCC_ALLOW_ANONYMOUS", None)

    from fastapi.testclient import TestClient

    from dcc.api_async import _iter_routes, app

    client = TestClient(app)
    headers = {"X-API-Key": raw_key}

    # _iter_routes, not app.routes: include_router wraps a sub-router in an
    # _IncludedRouter that has no .path, so iterating app.routes directly silently
    # skips every included route -- the backup endpoints were never exercised here
    # even after they were mounted.
    paths = sorted(
        {
            route.path
            for route in _iter_routes(app.routes)
            if getattr(route, "path", "").startswith("/v2")
            and "GET" in (getattr(route, "methods", None) or [])
            and "{" not in getattr(route, "path", "")
        }
    )

    failures: list[str] = []
    for path in paths:
        separator = "&" if "?" in path else "?"
        response = client.get(f"{path}{separator}tenant_id={TENANT}", headers=headers)
        status = "ok  " if response.status_code == 200 else "FAIL"
        print(f"    {status} {response.status_code:<4} {path}")
        if response.status_code != 200:
            body = response.text[:160].replace("\n", " ")
            failures.append(f"{path} -> {response.status_code} {body}")

    if failures:
        print(f"\n    {len(failures)} route(s) failed against a fresh database:", file=sys.stderr)
        for line in failures:
            print(f"      {line}", file=sys.stderr)
        return 1

    print(f"    {len(paths)} GET routes verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
