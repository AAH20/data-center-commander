"""Tests for the backup run API.

The router is exercised against a fake pool, on purpose. The unit job in CI has no
database, so a test that needed one would either be skipped there or be run only by
whoever remembers to start Postgres -- and a route nobody tests in CI is a route
that breaks quietly. Everything asserted below is observable without a server: the
route table, the tenant-scoping calls, the paging envelope, and the rule that an
unverified backup reports ``checksum_match: null`` rather than ``true``.

What this file cannot prove, and does not pretend to: that the SQL is valid and
that RLS actually isolates tenants. Those need the migration applied, and are
covered by the integration job against a real Postgres.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dcc.api_backup as api_backup
from dcc.api_backup import router

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "22222222-2222-2222-2222-222222222222"
RUN_ID = "33333333-3333-3333-3333-333333333333"
BACKUP_ID = "44444444-4444-4444-4444-444444444444"
CHECKSUM = hashlib.sha256(b"backup bytes").hexdigest()


# ---------------------------------------------------------------------------
# Fake pool
# ---------------------------------------------------------------------------


class _FakeTransaction:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> "_FakeTransaction":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        self.committed = True
        return False


class _FakeConnection:
    """Records every statement so the test can assert on the tenant binding."""

    def __init__(self, fetch_rows: Optional[list] = None, fetchrow_queue: Optional[list] = None):
        self.calls: list[tuple[str, tuple]] = []
        self._fetch_rows = fetch_rows if fetch_rows is not None else []
        self._fetchrow_queue = list(fetchrow_queue or [])

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, sql: str, *params: Any) -> int:
        self.calls.append((sql, params))
        return 0

    async def fetch(self, sql: str, *params: Any) -> list:
        self.calls.append((sql, params))
        return self._fetch_rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if not self._fetchrow_queue:
            return None
        return self._fetchrow_queue.pop(0)

    # --- assertions -----------------------------------------------------
    def statements(self) -> list[str]:
        return [sql for sql, _ in self.calls]

    def statements_like(self, needle: str) -> list[tuple[str, tuple]]:
        return [(sql, params) for sql, params in self.calls if needle in sql]

    def tenant_binding(self) -> list[tuple]:
        return [params for sql, params in self.calls if "set_config('dcc.tenant_id'" in sql]


class _FakeConnectionCtx:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakePool:
    def __init__(self, conn: _FakeConnection) -> None:
        self.conn = conn

    def connection(self) -> _FakeConnectionCtx:
        return _FakeConnectionCtx(self.conn)


class _UnreachablePool:
    """Fails loudly if a validation error still reached the database."""

    def connection(self):
        raise AssertionError("validation should reject before opening a connection")


def _client(monkeypatch, pool) -> TestClient:
    async def _fake_get_pool():
        return pool

    monkeypatch.setattr(api_backup, "_get_pool", _fake_get_pool)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _row(**overrides: Any) -> dict:
    row = {
        "run_id": RUN_ID,
        "backup_id": BACKUP_ID,
        "backup_type": "full",
        "status": "completed",
        "compression": "gzip",
        "source": "engine",
        "size_bytes": 4096,
        "checksum": CHECKSUM,
        "checksum_observed": None,
        "verified_at": None,
        "wal_start": None,
        "wal_end": None,
        "point_in_time": None,
        "error_message": "",
        "tags": {},
        "metadata": {},
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:05:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:05:00+00:00",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Route surface
# ---------------------------------------------------------------------------


class TestRouteSurface:
    def _routes(self) -> dict:
        return {
            (sorted(getattr(route, "methods", ()))[0], getattr(route, "path", "")): route
            for route in router.routes
            if getattr(route, "methods", None)
        }

    def test_the_three_routes_exist(self):
        routes = self._routes()
        assert ("GET", "/v2/backup/runs") in routes
        assert ("POST", "/v2/backup/runs") in routes
        assert ("GET", "/v2/backup/verify/{run_id}") in routes

    def test_router_has_no_app_side_effects(self):
        """The router is mounted by another module, so it must not build an app."""
        from fastapi import APIRouter

        assert isinstance(router, APIRouter)
        assert not hasattr(api_backup, "app")

    def test_enums_match_the_backup_engine(self):
        """The constants are copied, not imported. Pin them to the real enums."""
        from dcc.operations.backup import BackupStatus, BackupType, CompressionType

        assert tuple(m.value for m in BackupType) == api_backup.BACKUP_TYPES
        assert tuple(m.value for m in BackupStatus) == api_backup.BACKUP_STATUSES
        assert tuple(m.value for m in CompressionType) == api_backup.COMPRESSION_TYPES

    def test_module_cannot_execute_a_backup(self):
        """No shelling out, no import of the engine: execution is a worker's job.

        Checked on the parsed AST rather than on text, because the module's docstring
        discusses pg_dump and create_backup() at length to explain why neither is
        here -- a substring search would fail on the explanation, not the code.
        """
        import ast

        tree = ast.parse(inspect.getsource(api_backup))

        imported: set = set()
        called: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name:
                    called.add(name)

        assert "subprocess" not in imported
        assert not any("operations.backup" in name for name in imported)
        assert "create_backup" not in called
        assert "verify_backup" not in called
        assert "run_in_threadpool" not in called


# ---------------------------------------------------------------------------
# GET /v2/backup/runs
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_paging_envelope_has_the_expected_keys(self, monkeypatch):
        conn = _FakeConnection(fetch_rows=[_row()])
        client = _client(monkeypatch, _FakePool(conn))

        response = client.get("/v2/backup/runs", params={"tenant_id": TENANT, "limit": 1})

        assert response.status_code == 200
        body = response.json()
        for key in ("items", "next_cursor", "total", "limit", "offset", "has_more"):
            assert key in body
        assert len(body["items"]) == 1
        assert body["has_more"] is False
        assert body["next_cursor"] is None

    def test_a_full_page_yields_a_cursor_for_the_next_offset(self, monkeypatch):
        conn = _FakeConnection(fetch_rows=[_row(), _row(run_id=BACKUP_ID)])
        client = _client(monkeypatch, _FakePool(conn))

        body = client.get("/v2/backup/runs", params={"tenant_id": TENANT, "limit": 1}).json()

        assert body["has_more"] is True
        assert len(body["items"]) == 1
        decoded = json.loads(base64.b64decode(body["next_cursor"].encode()))
        assert decoded == {"offset": 1}

    def test_the_cursor_is_accepted_and_applied(self, monkeypatch):
        conn = _FakeConnection(fetch_rows=[])
        client = _client(monkeypatch, _FakePool(conn))
        cursor = base64.b64encode(json.dumps({"offset": 40}).encode()).decode()

        body = client.get(
            "/v2/backup/runs",
            params={"tenant_id": TENANT, "cursor": cursor, "limit": 10},
        ).json()

        assert body["offset"] == 40
        select = conn.statements_like("FROM dcc.backup_runs")[0]
        assert select[1][0] == TENANT
        assert select[1][2] == 11  # limit + 1, to detect another page
        assert select[1][3] == 40  # decoded offset

    def test_the_read_is_tenant_scoped(self, monkeypatch):
        conn = _FakeConnection(fetch_rows=[])
        client = _client(monkeypatch, _FakePool(conn))

        client.get("/v2/backup/runs", params={"tenant_id": TENANT})

        assert "SET TRANSACTION READ ONLY" in conn.statements()
        assert conn.tenant_binding() == [(TENANT,)]
        select = conn.statements_like("FROM dcc.backup_runs")[0]
        assert "tenant_id=$1::uuid" in select[0]
        assert select[1][0] == TENANT

    def test_newest_first_ordering(self, monkeypatch):
        conn = _FakeConnection(fetch_rows=[])
        client = _client(monkeypatch, _FakePool(conn))

        client.get("/v2/backup/runs", params={"tenant_id": TENANT})

        select = conn.statements_like("FROM dcc.backup_runs")[0][0]
        assert "ORDER BY created_at DESC" in select

    def test_status_filter_is_bound_not_interpolated(self, monkeypatch):
        """A value in the SQL string is an injection; a placeholder is not."""
        conn = _FakeConnection(fetch_rows=[])
        client = _client(monkeypatch, _FakePool(conn))

        client.get("/v2/backup/runs", params={"tenant_id": TENANT, "status": "failed"})

        sql, params = conn.statements_like("FROM dcc.backup_runs")[0]
        assert "failed" not in sql
        assert "$2::text" in sql
        assert params[1] == "failed"

    def test_unknown_status_is_rejected_before_the_database(self, monkeypatch):
        client = _client(monkeypatch, _UnreachablePool())

        response = client.get(
            "/v2/backup/runs", params={"tenant_id": TENANT, "status": "not_a_status"}
        )

        assert response.status_code == 400

    def test_a_malformed_tenant_never_reaches_the_database(self, monkeypatch):
        client = _client(monkeypatch, _UnreachablePool())

        response = client.get("/v2/backup/runs", params={"tenant_id": "not-a-uuid"})

        assert response.status_code == 422

    def test_a_corrupt_cursor_is_a_bad_request_not_a_server_error(self, monkeypatch):
        client = _client(monkeypatch, _UnreachablePool())

        response = client.get(
            "/v2/backup/runs", params={"tenant_id": TENANT, "cursor": "not-base64!!"}
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_cursor"

    def test_advisory_contract_on_the_listing(self, monkeypatch):
        conn = _FakeConnection(fetch_rows=[_row()])
        client = _client(monkeypatch, _FakePool(conn))

        body = client.get("/v2/backup/runs", params={"tenant_id": TENANT}).json()

        assert body["read_only"] is True
        assert body["execution_permitted"] is False


# ---------------------------------------------------------------------------
# POST /v2/backup/runs
# ---------------------------------------------------------------------------


class TestRecordRun:
    def _post(self, monkeypatch, body: dict, conn=None):
        conn = conn or _FakeConnection(fetchrow_queue=[None, _row()])
        client = _client(monkeypatch, _FakePool(conn))
        response = client.post("/v2/backup/runs", params={"tenant_id": TENANT}, json=body)
        return response, conn

    def test_a_run_is_recorded_and_the_response_says_so(self, monkeypatch):
        response, conn = self._post(
            monkeypatch,
            {"backup_id": BACKUP_ID, "backup_type": "full", "size_bytes": 4096, "checksum": CHECKSUM},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["backup_id"] == BACKUP_ID
        assert body["created"] is True
        assert body["executed"] is False
        assert body["execution_permitted"] is False
        assert body["read_only"] is True

    def test_it_writes_a_row_and_never_runs_a_dump(self, monkeypatch):
        _, conn = self._post(monkeypatch, {"backup_id": BACKUP_ID})

        inserts = conn.statements_like("INSERT INTO dcc.backup_runs")
        assert len(inserts) == 1
        assert "'api'" in inserts[0][0]  # source is the recorder, not the engine
        joined = " ".join(conn.statements())
        assert "pg_dump" not in joined
        assert "pg_restore" not in joined

    def test_the_write_binds_the_tenant_for_rls(self, monkeypatch):
        """FORCE RLS applies to INSERT too: without the setting the row is rejected."""
        _, conn = self._post(monkeypatch, {"backup_id": BACKUP_ID})

        assert conn.tenant_binding() == [(TENANT,)]
        assert "SET TRANSACTION READ ONLY" not in conn.statements()

    def test_jsonb_is_dumped_and_cast_not_passed_as_a_dict(self, monkeypatch):
        """psycopg3 cannot adapt a dict to jsonb; a bare dict here is a 500 at runtime."""
        _, conn = self._post(
            monkeypatch, {"backup_id": BACKUP_ID, "tags": {"reason": "pre-upgrade"}}
        )

        sql, params = conn.statements_like("INSERT INTO dcc.backup_runs")[0]
        assert "$15::jsonb" in sql
        assert isinstance(params[14], str)
        assert json.loads(params[14]) == {"reason": "pre-upgrade"}

    def test_reposting_the_same_backup_updates_rather_than_duplicating(self, monkeypatch):
        conn = _FakeConnection(fetchrow_queue=[{"run_id": RUN_ID}, _row()])
        client = _client(monkeypatch, _FakePool(conn))

        body = client.post(
            "/v2/backup/runs", params={"tenant_id": TENANT}, json={"backup_id": BACKUP_ID}
        ).json()

        assert body["created"] is False
        assert "ON CONFLICT (tenant_id, backup_id) DO UPDATE" in conn.statements_like(
            "INSERT INTO dcc.backup_runs"
        )[0][0]

    def test_verified_status_without_an_observed_checksum_is_refused(self, monkeypatch):
        """The API must not be able to record a verification it never performed."""
        response, _ = self._post(
            monkeypatch, {"backup_id": BACKUP_ID, "status": "verified"}, conn=_FakeConnection()
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_status"

    def test_an_observed_checksum_needs_a_timestamp(self, monkeypatch):
        response, _ = self._post(
            monkeypatch,
            {"backup_id": BACKUP_ID, "checksum_observed": CHECKSUM},
            conn=_FakeConnection(),
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_verified_at"

    def test_a_non_sha256_checksum_is_refused(self, monkeypatch):
        response, _ = self._post(
            monkeypatch, {"backup_id": BACKUP_ID, "checksum": "deadbeef"}, conn=_FakeConnection()
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_checksum"

    def test_a_non_uuid_backup_id_is_refused(self, monkeypatch):
        response, _ = self._post(monkeypatch, {"backup_id": "bkp_abc"}, conn=_FakeConnection())

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_backup_id"

    def test_a_non_object_body_is_refused(self, monkeypatch):
        client = _client(monkeypatch, _UnreachablePool())

        response = client.post("/v2/backup/runs", params={"tenant_id": TENANT}, json=[1, 2, 3])

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v2/backup/verify/{run_id}
# ---------------------------------------------------------------------------


class TestVerifyRun:
    def _get(self, monkeypatch, row):
        conn = _FakeConnection(fetchrow_queue=[row])
        client = _client(monkeypatch, _FakePool(conn))
        return client.get(
            "/v2/backup/verify/{0}".format(RUN_ID), params={"tenant_id": TENANT}
        ), conn

    def test_an_unverified_run_reports_null_not_true(self, monkeypatch):
        response, _ = self._get(monkeypatch, _row(checksum_observed=None))

        body = response.json()
        assert response.status_code == 200
        assert body["checksum_match"] is None
        assert body["verified"] is False
        assert body["verification_source"] == "none"
        assert body["valid"] is False
        assert any("not the same as a match" in w for w in body["warnings"])

    def test_a_matching_observed_checksum_is_a_match(self, monkeypatch):
        response, _ = self._get(
            monkeypatch,
            _row(checksum_observed=CHECKSUM, verified_at="2026-01-02T00:00:00+00:00", status="verified"),
        )

        body = response.json()
        assert body["checksum_match"] is True
        assert body["valid"] is True
        assert body["metadata_valid"] is True
        assert body["errors"] == []

    def test_a_differing_observed_checksum_is_not_a_match(self, monkeypatch):
        response, _ = self._get(
            monkeypatch,
            _row(checksum_observed="0" * 64, verified_at="2026-01-02T00:00:00+00:00"),
        )

        body = response.json()
        assert body["checksum_match"] is False
        assert body["valid"] is False
        assert any("does not match" in e for e in body["errors"])

    def test_a_completed_run_with_no_size_is_an_inconsistent_record(self, monkeypatch):
        response, _ = self._get(
            monkeypatch,
            _row(size_bytes=0, checksum_observed=CHECKSUM, verified_at="2026-01-02T00:00:00+00:00"),
        )

        body = response.json()
        assert body["checksum_match"] is True
        assert body["metadata_valid"] is False
        assert body["valid"] is False

    def test_the_verify_read_is_tenant_scoped(self, monkeypatch):
        _, conn = self._get(monkeypatch, _row())

        assert "SET TRANSACTION READ ONLY" in conn.statements()
        assert conn.tenant_binding() == [(TENANT,)]
        sql, params = conn.statements_like("FROM dcc.backup_runs")[0]
        assert "tenant_id=$1::uuid AND run_id=$2::uuid" in sql
        assert params == (TENANT, RUN_ID)

    def test_a_run_outside_the_tenant_is_a_404(self, monkeypatch):
        """RLS makes this indistinguishable from a missing row, which is the point."""
        response, _ = self._get(monkeypatch, None)

        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "backup_run_not_found"

    def test_a_non_uuid_run_id_never_reaches_the_database(self, monkeypatch):
        client = _client(monkeypatch, _UnreachablePool())

        response = client.get("/v2/backup/verify/not-a-uuid", params={"tenant_id": TENANT})

        assert response.status_code == 400

    def test_advisory_contract_on_the_verification(self, monkeypatch):
        response, _ = self._get(monkeypatch, _row())

        body = response.json()
        assert body["read_only"] is True
        assert body["execution_permitted"] is False
