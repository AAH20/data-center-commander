"""Backup run recording and verification endpoints.

WHY EXECUTION IS NOT IN THIS MODULE
-----------------------------------
``dcc.operations.backup`` contains a real ``BackupEngine`` that shells out to
``pg_dump``, and it is reachable from nothing. The obvious fix -- a ``POST
/v2/backup/runs`` that calls ``create_backup()`` -- is the wrong one, for three
reasons that are worth writing down because the route looks harmless:

1. A dump is a long blocking operation. It runs for minutes on a real database.
   Holding an HTTP request open for it means the caller times out, retries, and
   starts a second dump while the first is still writing, so the endpoint's own
   failure mode is concurrent dumps of the same database.
2. It is an arbitrary-write primitive triggered by a remote request. The engine
   writes files under a backup root and invokes a binary with a database DSN. Any
   bug in the request body becomes a file written where the process can write, or
   a command constructed from user input. That is a much larger attack surface
   than "record what happened".
3. The transaction that would record the run is the same transaction the dump
   reads from, so a dump that fails halfway leaves the record and the filesystem
   disagreeing, with no way to tell which is authoritative.

So this router does the part that belongs in a request: it records what a backup
run was, and it reports whether a recorded run's checksum still matches. Execution
stays with the worker/scheduler that owns it, which writes its results into the
same table with ``source='scheduler'`` or ``source='engine'``.

WHAT "VERIFY" MEANS HERE
------------------------
Recomputing a checksum requires reading the backup file, which lives on the backup
volume, not in Postgres. This endpoint therefore compares the checksum the engine
recorded against ``checksum_observed``, the value written by an out-of-band
verification pass (``operations.backup.verify_backup``). When no verification has
been recorded, ``checksum_match`` is ``null`` -- NOT ``true``. A check that did not
happen is not a check that passed, and reporting it as one is the exact false
assurance this repository has had to remove from other verifiers.

TENANCY
-------
Every query is tenant scoped the same way as the rest of the API: open the pool,
``SET TRANSACTION READ ONLY`` for reads, bind ``dcc.tenant_id`` for the session,
then filter by ``tenant_id``. Both are necessary -- the explicit predicate is the
query's own guarantee and the session setting is what the ``tenant_scope`` RLS
policy on ``dcc.backup_runs`` checks.

No side effects at import: nothing touches the network, the database or the
filesystem until a request arrives. ``_get_pool`` imports ``api_async`` lazily
because ``api_async`` imports this module to mount the router.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(tags=["backup"])

# Set explicitly on every successful body. The parent application's middleware
# injects these for /v2 paths, but a router must be correct on its own: it is
# imported and tested in isolation, and the guarantee should not depend on being
# mounted.
ADVISORY: dict = {"read_only": True, "execution_permitted": False}

# Pinned to dcc.operations.backup's enums by tests/unit/test_backup_api.py. They are
# copied rather than imported so that importing this module does not pull in the
# backup engine (and its subprocess handling) just to serve a list request.
BACKUP_TYPES = ("full", "incremental", "differential")
BACKUP_STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "verified",
    "expired",
    "deleted",
)
COMPRESSION_TYPES = ("none", "gzip")
SOURCES = ("api", "scheduler", "engine")

# Statuses that describe a run that finished. A row in one of these states without
# completed_at is internally inconsistent and is reported as such by verify.
FINISHED_STATUSES = ("completed", "failed", "verified", "expired", "deleted")

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

_RUN_COLUMNS = (
    "run_id::text AS run_id, backup_id::text AS backup_id, backup_type, status, "
    "compression, source, size_bytes, checksum, checksum_observed, verified_at, "
    "wal_start, wal_end, point_in_time, error_message, tags, metadata, "
    "started_at, completed_at, created_at, updated_at"
)


# ---------------------------------------------------------------------------
# Pagination -- same envelope and cursor encoding as api_async
# ---------------------------------------------------------------------------


def encode_cursor(offset: int) -> str:
    return base64.b64encode(json.dumps({"offset": offset}).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        data = json.loads(base64.b64decode(cursor.encode()))
        return int(data.get("offset", 0))
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


def _page(items: list, limit: int, offset: int, has_more: bool) -> dict:
    return {
        "items": items,
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "next_cursor": encode_cursor(offset + limit) if has_more else None,
        **ADVISORY,
    }


# ---------------------------------------------------------------------------
# Pool access
# ---------------------------------------------------------------------------


async def _get_pool():
    """Return the application's shared pool.

    Imported here rather than at module scope: api_async imports this router to
    mount it, so a top-level import would be circular. Function-level import also
    keeps this module importable in a unit test with no database.
    """
    from .api_async import get_pool

    return await get_pool()


def _bad_request(code: str, detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"error": code, "detail": detail})


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def _require_enum(value: Any, allowed: tuple, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _bad_request("invalid_" + field, f"{field} must be one of {list(allowed)}")
    return value


def _require_uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise _bad_request("invalid_" + field, f"{field} must be a UUID string")
    try:
        from uuid import UUID

        UUID(value)
    except ValueError:
        raise _bad_request("invalid_" + field, f"{field} must be a valid UUID") from None
    return value


def _optional_uuid(value: Any, field: str):
    if value is None:
        return None
    return _require_uuid(value, field)


def _optional_timestamp(value: Any, field: str):
    """Return the value unchanged for Postgres to cast, after checking it parses.

    Values are bound as text and cast with ::timestamptz server-side, so a malformed
    timestamp is a 400 here instead of a 500 from the driver.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise _bad_request("invalid_" + field, f"{field} must be an ISO-8601 string")
    from datetime import datetime

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _bad_request("invalid_" + field, f"{field} must be an ISO-8601 string") from None
    return value


def _optional_count(value: Any, field: str) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _bad_request("invalid_" + field, f"{field} must be a non-negative integer")
    return value


def _optional_object(value: Any, field: str) -> str:
    """Serialise a JSON object for a jsonb column.

    Dumped to text and cast with ::jsonb: psycopg3 does not adapt a bare dict to
    jsonb, and wrapping it with psycopg's Json adapter would make this module
    import the driver it is otherwise happy not to touch.
    """
    if value is None:
        return "{}"
    if not isinstance(value, dict):
        raise _bad_request("invalid_" + field, f"{field} must be an object")
    return json.dumps(value)


# ---------------------------------------------------------------------------
# GET /v2/backup/runs
# ---------------------------------------------------------------------------


@router.get("/v2/backup/runs")
async def list_backup_runs(
    tenant_id: str = Query(..., pattern=r"^[0-9a-fA-F-]{36}$"),
    limit: int = Query(50, ge=1, le=500),
    cursor: Optional[str] = None,
    status: Optional[str] = None,
):
    """Recent backup runs for one tenant, newest first.

    Paged like the other list endpoints: fetch limit+1 rows to learn whether
    another page exists, then hand back a cursor holding the next offset. The
    ordering tiebreaks on run_id so that two runs created in the same transaction
    cannot swap places between pages and cause a row to be skipped.
    """
    try:
        offset = decode_cursor(cursor) if cursor else 0
    except ValueError as exc:
        # A cursor is caller-supplied opaque state. A bad one is a bad request, not a
        # server error: reporting 500 would send operators hunting for a database
        # problem that does not exist.
        raise _bad_request("invalid_cursor", str(exc)) from exc
    if status is not None:
        _require_enum(status, BACKUP_STATUSES, "status")

    pool = await _get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT " + _RUN_COLUMNS + " FROM dcc.backup_runs "
            "WHERE tenant_id=$1::uuid AND ($2::text IS NULL OR status=$2::text) "
            "ORDER BY created_at DESC, run_id DESC LIMIT $3 OFFSET $4",
            tenant_id,
            status,
            limit + 1,
            offset,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    return _page(items, limit, offset, has_more)


# ---------------------------------------------------------------------------
# POST /v2/backup/runs
# ---------------------------------------------------------------------------


@router.post("/v2/backup/runs")
async def record_backup_run(
    request: Request,
    tenant_id: str = Query(..., pattern=r"^[0-9a-fA-F-]{36}$"),
):
    """Record a backup run. Does NOT run pg_dump.

    See the module docstring for why execution stays out of the request path: a
    dump is a minutes-long blocking operation, an arbitrary-write primitive when
    driven by a remote body, and it cannot share a transaction with its own audit
    record.

    The body carries the facts about a run that has already happened (or is
    expected to happen):

        backup_id          uuid, required -- the engine's id for the run
        backup_type        full | incremental | differential (default full)
        status             pending..deleted (default completed)
        compression        none | gzip (default none)
        size_bytes         non-negative integer (default 0)
        checksum           SHA-256 recorded by the engine for the written backup
        checksum_observed  SHA-256 from an out-of-band verification pass, if one ran
        verified_at        when that pass ran; required with checksum_observed
        parent_backup_id   uuid of the parent run, for incremental/differential
        wal_start/wal_end  WAL range covered, as text
        point_in_time      ISO-8601 recovery target
        started_at/completed_at  ISO-8601
        error_message      failure detail, for status=failed
        tags/metadata      free-form JSON objects

    Re-posting the same (tenant, backup_id) updates that run instead of failing, so
    a worker that retries a report does not have to know whether its first attempt
    landed. ``created`` in the response says which happened.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise _bad_request("invalid_json", str(exc)) from exc
    if not isinstance(body, dict):
        raise _bad_request("expected_object", "request body must be a JSON object")

    backup_id = _require_uuid(body.get("backup_id"), "backup_id")
    backup_type = _require_enum(body.get("backup_type", "full"), BACKUP_TYPES, "backup_type")
    status = _require_enum(body.get("status", "completed"), BACKUP_STATUSES, "status")
    compression = _require_enum(
        body.get("compression", "none"), COMPRESSION_TYPES, "compression"
    )
    size_bytes = _optional_count(body.get("size_bytes"), "size_bytes")

    checksum = body.get("checksum") or ""
    if not isinstance(checksum, str):
        raise _bad_request("invalid_checksum", "checksum must be a string")
    checksum = checksum.strip().lower()
    if checksum and not _SHA256_HEX.match(checksum):
        raise _bad_request("invalid_checksum", "checksum must be a 64-character hex SHA-256")

    observed = body.get("checksum_observed")
    if observed is not None:
        if not isinstance(observed, str):
            raise _bad_request("invalid_checksum_observed", "checksum_observed must be a string")
        observed = observed.strip().lower()
        if not _SHA256_HEX.match(observed):
            raise _bad_request(
                "invalid_checksum_observed",
                "checksum_observed must be a 64-character hex SHA-256",
            )
    verified_at = _optional_timestamp(body.get("verified_at"), "verified_at")
    if observed and not verified_at:
        raise _bad_request(
            "invalid_verified_at",
            "verified_at is required when checksum_observed is given: a checksum with no "
            "timestamp is an unverifiable claim",
        )
    if verified_at and not observed:
        raise _bad_request(
            "invalid_checksum_observed",
            "checksum_observed is required when verified_at is given",
        )
    if status == "verified" and not observed:
        raise _bad_request(
            "invalid_status",
            "status 'verified' requires checksum_observed; recording a verification that "
            "did not happen is not permitted",
        )

    parent_backup_id = _optional_uuid(body.get("parent_backup_id"), "parent_backup_id")
    point_in_time = _optional_timestamp(body.get("point_in_time"), "point_in_time")
    started_at = _optional_timestamp(body.get("started_at"), "started_at")
    completed_at = _optional_timestamp(body.get("completed_at"), "completed_at")
    wal_start = body.get("wal_start")
    wal_end = body.get("wal_end")
    for name, value in (("wal_start", wal_start), ("wal_end", wal_end)):
        if value is not None and not isinstance(value, str):
            raise _bad_request("invalid_" + name, f"{name} must be a string")
    error_message = body.get("error_message") or ""
    if not isinstance(error_message, str):
        raise _bad_request("invalid_error_message", "error_message must be a string")
    tags = _optional_object(body.get("tags"), "tags")
    metadata = _optional_object(body.get("metadata"), "metadata")

    pool = await _get_pool()
    async with pool.connection() as conn, conn.transaction():
        # A write transaction: no SET TRANSACTION READ ONLY. The tenant setting is
        # still required, because dcc.backup_runs is FORCE ROW LEVEL SECURITY and
        # the tenant_scope policy checks it on INSERT as well as SELECT.
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        existing = await conn.fetchrow(
            "SELECT run_id::text AS run_id FROM dcc.backup_runs "
            "WHERE tenant_id=$1::uuid AND backup_id=$2::uuid",
            tenant_id,
            backup_id,
        )

        row = await conn.fetchrow(
            "INSERT INTO dcc.backup_runs ("
            "tenant_id, backup_id, backup_type, status, compression, source, size_bytes, "
            "checksum, checksum_observed, verified_at, parent_backup_id, wal_start, wal_end, "
            "point_in_time, error_message, tags, metadata, started_at, completed_at"
            ") VALUES ("
            "$1::uuid, $2::uuid, $3, $4, $5, 'api', $6, $7, $8, $9::timestamptz, "
            "$10::uuid, $11, $12, $13::timestamptz, $14, $15::jsonb, $16::jsonb, "
            "$17::timestamptz, $18::timestamptz"
            ") ON CONFLICT (tenant_id, backup_id) DO UPDATE SET "
            "backup_type=EXCLUDED.backup_type, status=EXCLUDED.status, "
            "compression=EXCLUDED.compression, size_bytes=EXCLUDED.size_bytes, "
            "checksum=EXCLUDED.checksum, checksum_observed=EXCLUDED.checksum_observed, "
            "verified_at=EXCLUDED.verified_at, parent_backup_id=EXCLUDED.parent_backup_id, "
            "wal_start=EXCLUDED.wal_start, wal_end=EXCLUDED.wal_end, "
            "point_in_time=EXCLUDED.point_in_time, error_message=EXCLUDED.error_message, "
            "tags=EXCLUDED.tags, metadata=EXCLUDED.metadata, "
            "started_at=EXCLUDED.started_at, completed_at=EXCLUDED.completed_at, "
            "updated_at=now() "
            "RETURNING " + _RUN_COLUMNS,
            tenant_id,
            backup_id,
            backup_type,
            status,
            compression,
            size_bytes,
            checksum,
            observed,
            verified_at,
            parent_backup_id,
            wal_start,
            wal_end,
            point_in_time,
            error_message,
            tags,
            metadata,
            started_at,
            completed_at,
        )

    payload = dict(row) if row else {}
    return {
        **payload,
        "tenant_id": tenant_id,
        "created": existing is None,
        # Execution is not merely disabled here: this endpoint has no code path that
        # could invoke the engine, which is why it can state it plainly.
        "executed": False,
        **ADVISORY,
    }


# ---------------------------------------------------------------------------
# GET /v2/backup/verify/{run_id}
# ---------------------------------------------------------------------------


@router.get("/v2/backup/verify/{run_id}")
async def verify_backup_run(
    run_id: str,
    tenant_id: str = Query(..., pattern=r"^[0-9a-fA-F-]{36}$"),
):
    """Report whether a recorded run's checksum matches.

    Three separate questions, kept separate because collapsing them hides which one
    failed:

    * ``checksum_match`` -- recorded checksum vs the observed one. ``null`` when no
      verification has been recorded; never ``true`` in that case.
    * ``metadata_valid`` -- the row is internally consistent: a finished run has a
      completion time, a completed run has non-zero size and a checksum, a failed
      run says why.
    * ``valid`` -- true only when both the checksum matches and the record is
      consistent. A matching checksum on an inconsistent record, or a consistent
      record with no verification, is not a valid backup.

    Reading a backup file to recompute its checksum is out of scope here: the file
    is on the backup volume, not in Postgres. ``operations.backup.verify_backup``
    does that and writes ``checksum_observed``; this endpoint reports the result.
    """
    _require_uuid(run_id, "run_id")

    pool = await _get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        row = await conn.fetchrow(
            "SELECT " + _RUN_COLUMNS + " FROM dcc.backup_runs "
            "WHERE tenant_id=$1::uuid AND run_id=$2::uuid",
            tenant_id,
            run_id,
        )

    if row is None:
        # Same answer whether the run is missing or belongs to another tenant: the
        # caller must not be able to probe for ids outside its own scope.
        raise HTTPException(status_code=404, detail={"error": "backup_run_not_found"})

    record = dict(row)
    errors: list = []
    warnings: list = []

    recorded = (record.get("checksum") or "").strip().lower()
    observed = (record.get("checksum_observed") or "").strip().lower() or None
    checksum_present = bool(recorded)

    if recorded and not _SHA256_HEX.match(recorded):
        errors.append("recorded checksum is not a 64-character hex SHA-256")
    if observed and not _SHA256_HEX.match(observed):
        errors.append("observed checksum is not a 64-character hex SHA-256")

    checksum_match = None
    if observed is None:
        warnings.append(
            "no verification has been recorded for this run; checksum_match is null, "
            "which is not the same as a match"
        )
    elif not checksum_present:
        errors.append("run has no recorded checksum to compare against")
        checksum_match = False
    else:
        checksum_match = recorded == observed
        if not checksum_match:
            errors.append("recorded checksum does not match the observed checksum")

    status = record.get("status")
    metadata_ok = True
    if not record.get("backup_id"):
        metadata_ok = False
        errors.append("run has no backup_id")
    if status in FINISHED_STATUSES:
        if record.get("completed_at") is None:
            metadata_ok = False
            errors.append(f"status is {status!r} but completed_at is unset")
        if record.get("started_at") and record.get("completed_at"):
            try:
                if record["completed_at"] < record["started_at"]:
                    metadata_ok = False
                    errors.append("completed_at precedes started_at")
            except TypeError:
                # Mixed naive/aware timestamps: reported, not raised, so one odd row
                # cannot turn a verification into a 500.
                metadata_ok = False
                errors.append("started_at and completed_at are not comparable")
    if status == "completed" or status == "verified":
        if not record.get("size_bytes"):
            metadata_ok = False
            errors.append("a completed backup must have a non-zero size")
        if not checksum_present:
            metadata_ok = False
            errors.append("a completed backup must have a checksum")
    if status == "failed" and not (record.get("error_message") or "").strip():
        warnings.append("run failed but records no error_message")
    if status == "verified" and observed is None:
        # The table's CHECK constraint forbids this. If it is ever seen, the row was
        # written by something that bypassed the constraint, and saying so matters.
        metadata_ok = False
        errors.append("status is 'verified' but no observed checksum was recorded")

    valid = bool(metadata_ok and checksum_match is True)

    return {
        "run_id": record.get("run_id"),
        "tenant_id": tenant_id,
        "backup_id": record.get("backup_id"),
        "status": status,
        "checksum_match": checksum_match,
        "checksum_present": checksum_present,
        "recorded_checksum": recorded or None,
        "observed_checksum": observed,
        "verified_at": record.get("verified_at"),
        "metadata_valid": metadata_ok,
        "valid": valid,
        "verification_source": "recorded_vs_observed" if observed else "none",
        "verified": observed is not None,
        "errors": errors,
        "warnings": warnings,
        **ADVISORY,
    }
