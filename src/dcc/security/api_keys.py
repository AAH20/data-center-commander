"""API key generation, hashing, and verification.

API keys are opaque bearer tokens. The raw key is shown once at creation; only a
SHA-256 hash is stored. Verification compares with ``hmac.compare_digest``.

Format: ``dcc_<random>`` -- the prefix makes keys identifiable in logs without
revealing the secret portion.

DURABILITY
----------
``ApiKeyStore`` has two backends, chosen from its ``dsn`` argument (defaulting to
``DCC_DATABASE_URL``).

**postgres** -- any DSN configured. This is the real one. Keys live in
``dcc.api_keys``, so they survive a restart and every uvicorn worker sees the same
set. It fixes the defect that made enforced authentication unusable in a multi-worker
deployment: an in-memory dict meant a key minted on worker 1 was unknown to worker 2,
so one request in N returned 401 for no visible reason, and every restart destroyed
every key. The table also carries the audit trail (``created_by``, ``created_at``,
``revoked_at``, ``last_used_at``) that a governance product owes its customers.

**memory** -- no DSN. Kept for tests, ``keys_cli`` and single-process tools that
construct a store directly. It is process-local by definition; do not serve traffic
from it.

The postgres lookup runs **before a tenant is known** (the key is what tells you the
tenant), so it goes through the SECURITY DEFINER function ``dcc.lookup_api_key``
rather than a plain SELECT. ``dcc.api_keys`` keeps ENABLE + FORCE row level security
and the standard ``tenant_scope`` policy, and under FORCE a plain SELECT with no
``dcc.tenant_id`` set returns zero rows -- for the table owner too, and therefore for
a definer function owned by the table owner. Migration 011 explains the escape (a
NOLOGIN BYPASSRLS role owns only the lookup functions) and the fallback for
deployments where such a role cannot be created.

The memory path is not a cache in front of the database: with a DSN a durable row is
always consulted, because a cache would delay revocation. Process-local records exist
only for what the table cannot represent (a non-UUID tenant id, or a startup
registration that could not be persisted), and they never shadow a durable row.

THREADING
---------
``api_async`` calls ``verify()`` synchronously from an async middleware, so the
postgres backend uses a thread-safe synchronous psycopg pool and issues one indexed
single-row read. ``averify()`` wraps the same path in ``asyncio.to_thread`` for call
sites that can await, and is what new code should use.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

__all__ = [
    "ApiKey",
    "ApiKeyError",
    "ApiKeyStore",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
]

log = logging.getLogger("dcc.security.api_keys")


class ApiKeyError(Exception):
    """Base exception for API key operations."""


class ApiKeyInvalidError(ApiKeyError):
    """Raised when an API key is malformed or has a bad hash."""


class ApiKeyExpiredError(ApiKeyError):
    """Raised when an API key has expired."""


class ApiKeyRevokedError(ApiKeyError):
    """Raised when an API key has been revoked."""


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

_KEY_PREFIX = "dcc"
_KEY_ENTROPY_BYTES = 32  # 256 bits


def generate_api_key() -> str:
    """Generate a new API key.

    Returns
    -------
    str
        A key in the format ``dcc_<64 hex chars>``.
    """
    random_part = secrets.token_hex(_KEY_ENTROPY_BYTES)
    return f"{_KEY_PREFIX}_{random_part}"


# ---------------------------------------------------------------------------
# Key hashing
# ---------------------------------------------------------------------------


def hash_api_key(key: str) -> str:
    """Compute the SHA-256 hash of an API key for storage.

    Parameters
    ----------
    key:
        The raw API key string.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Key verification
# ---------------------------------------------------------------------------


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its stored hash using constant-time comparison.

    Parameters
    ----------
    key:
        The raw API key to verify.
    key_hash:
        The stored SHA-256 hash.

    Returns
    -------
    bool
        True if the key matches the hash.
    """
    computed = hash_api_key(key)
    return hmac.compare_digest(computed, key_hash)


# ---------------------------------------------------------------------------
# ApiKey dataclass
# ---------------------------------------------------------------------------


# ``slots=True`` was dropped deliberately: it is 3.10+, and this module has to import
# on 3.9. Attribute access is the only thing anything does with an ApiKey.
@dataclass
class ApiKey:
    """Metadata for a stored API key.

    The raw key is never stored -- only its hash.

    The audit columns are not decoration. "Who issued this key, when, and is it still
    live" is a question a governance product has to answer, and an in-memory dict with
    no timestamps could not answer any of it.
    """

    id: str
    name: str
    key_hash: str
    tenant_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    last_used_at: Optional[float] = None
    scopes: List[str] = field(default_factory=list)
    revoked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    #: Who issued the key (operator, CLI, env bootstrap). Audit column; not a secret.
    created_by: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired

    def to_dict(self, *, include_hash: bool = False) -> Dict[str, Any]:
        """Serialize to dict. Never includes the raw key."""
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "scopes": list(self.scopes),
            "revoked": self.revoked,
            "metadata": dict(self.metadata),
        }
        if include_hash:
            result["key_hash"] = self.key_hash
        return result


# ---------------------------------------------------------------------------
# Postgres backend
# ---------------------------------------------------------------------------

_KEY_COLUMNS = (
    "id, tenant_id, key_hash, label, scopes, created_at, created_by, "
    "expires_at, revoked_at, last_used_at"
)


def _epoch(value: Any) -> Optional[float]:
    """timestamptz -> epoch seconds. ``None`` stays ``None``, never ``0.0``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    return float(value)


def _as_uuid(value: Any) -> Optional[str]:
    """Canonical UUID string, or None if the value cannot be a tenant id.

    ``None`` is meaningful: a non-UUID tenant cannot exist in ``dcc.tenants``, so the
    durable table cannot represent it and the caller degrades to a process-local key.
    """
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


class _PostgresBackend:
    """All SQL for the durable store.

    Tenant-scoped access sets ``dcc.tenant_id`` transaction-locally and then relies on
    the ordinary ``tenant_scope`` policy: the database authorises the statement, the
    store does not carry its own copy of the tenant rule. Only the pre-tenant lookup
    path goes through a SECURITY DEFINER function, because at that moment there is no
    tenant to scope by.
    """

    def __init__(self, dsn: str, *, pool_size: int = 4, timeout: float = 5.0) -> None:
        self._dsn = dsn
        self._pool_size = pool_size
        self._timeout = timeout
        self._pool: Any = None
        self._pool_lock = threading.Lock()

    # -- pool ---------------------------------------------------------------

    def _get_pool(self) -> Any:
        """Lazily open the pool. Never connects at import time."""
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
            if self._pool is not None:
                return self._pool
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            pool = ConnectionPool(
                conninfo=self._dsn,
                min_size=1,
                max_size=self._pool_size,
                timeout=self._timeout,
                open=False,
                kwargs={"row_factory": dict_row, "prepare_threshold": None},
            )
            try:
                pool.open(wait=False)
                pool.wait(timeout=self._timeout)
            except Exception:
                try:
                    pool.close()
                except Exception:  # noqa: BLE001 - never mask the real failure
                    pass
                raise
            self._pool = pool
            return pool

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            try:
                pool.close()
            except Exception:  # noqa: BLE001
                log.debug("error closing API key pool", exc_info=True)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        pool = self._get_pool()
        with pool.connection() as conn:
            yield conn

    @staticmethod
    def _bind_tenant(conn: Any, tenant_id: str) -> None:
        # set_config(..., is_local => true) is transaction-scoped, so it cannot leak to
        # the next request that checks this pooled connection out. SET LOCAL would be
        # equivalent but cannot take a parameter.
        conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (tenant_id,))

    # -- authentication path ------------------------------------------------

    def lookup(self, key_hash: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM dcc.lookup_api_key(%s)", (key_hash,)
            ).fetchone()

    def touch(self, key_hash: str) -> None:
        with self.connection() as conn:
            conn.execute("SELECT dcc.touch_api_key(%s)", (key_hash,))

    def count(self) -> int:
        with self.connection() as conn:
            row = conn.execute("SELECT dcc.api_key_count() AS n").fetchone()
        return int((row or {}).get("n") or 0)

    def list_visible(self) -> List[Dict[str, Any]]:
        """Rows this role may see with no tenant bound. Usually none, by design."""
        with self.connection() as conn:
            return list(
                conn.execute(
                    "SELECT " + _KEY_COLUMNS + " FROM dcc.api_keys "
                    "ORDER BY created_at DESC"
                ).fetchall()
            )

    # -- tenant-scoped administration --------------------------------------

    def insert(
        self,
        *,
        tenant_id: str,
        key_hash: str,
        label: str,
        scopes: List[str],
        expires_at: Optional[float],
        created_by: Optional[str],
    ) -> Dict[str, Any]:
        expires = (
            datetime.fromtimestamp(expires_at, tz=timezone.utc)
            if expires_at is not None
            else None
        )
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant_id)
                return conn.execute(
                    "INSERT INTO dcc.api_keys "
                    "(tenant_id, key_hash, label, scopes, expires_at, created_by) "
                    "VALUES (%s::uuid, %s, %s, %s, %s, %s) "
                    "RETURNING " + _KEY_COLUMNS,
                    (tenant_id, key_hash, label, list(scopes), expires, created_by),
                ).fetchone()

    def insert_if_absent(
        self,
        *,
        tenant_id: str,
        key_hash: str,
        label: str,
        scopes: List[str],
        expires_at: Optional[float],
        created_by: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Insert unless the digest already exists; return the row now in force.

        Registration is replayed on every process start, so it must be idempotent --
        and it must never revive a revoked key. A conflict therefore keeps the stored
        row (including ``revoked_at``) instead of overwriting it.
        """
        expires = (
            datetime.fromtimestamp(expires_at, tz=timezone.utc)
            if expires_at is not None
            else None
        )
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant_id)
                row = conn.execute(
                    "INSERT INTO dcc.api_keys "
                    "(tenant_id, key_hash, label, scopes, expires_at, created_by) "
                    "VALUES (%s::uuid, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (key_hash) DO NOTHING "
                    "RETURNING " + _KEY_COLUMNS,
                    (tenant_id, key_hash, label, list(scopes), expires, created_by),
                ).fetchone()
                if row is not None:
                    return row
                # Conflicted: return the stored row only if it belongs to this tenant.
                # A digest registered to a different tenant is a configuration error,
                # and adopting another tenant's row silently would be worse.
                return conn.execute(
                    "SELECT " + _KEY_COLUMNS + " FROM dcc.api_keys "
                    "WHERE key_hash = %s AND tenant_id = %s::uuid",
                    (key_hash, tenant_id),
                ).fetchone()

    def list_for_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant_id)
                return list(
                    conn.execute(
                        "SELECT " + _KEY_COLUMNS + " FROM dcc.api_keys "
                        "WHERE tenant_id = %s::uuid ORDER BY created_at DESC",
                        (tenant_id,),
                    ).fetchall()
                )

    def tenant_of(self, key_id: str) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT dcc.api_key_tenant(%s::uuid) AS tenant_id", (key_id,)
            ).fetchone()
        tenant = (row or {}).get("tenant_id")
        return str(tenant) if tenant else None

    def get(self, key_id: str, tenant_id: Optional[str]) -> Optional[Dict[str, Any]]:
        tenant = tenant_id or self.tenant_of(key_id)
        if tenant is None:
            return None
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant)
                return conn.execute(
                    "SELECT " + _KEY_COLUMNS + " FROM dcc.api_keys WHERE id = %s::uuid",
                    (key_id,),
                ).fetchone()

    def revoke(self, key_id: str, tenant_id: Optional[str]) -> bool:
        tenant = tenant_id or self.tenant_of(key_id)
        if tenant is None:
            return False
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant)
                # COALESCE keeps the first revocation time: revoking twice must not
                # rewrite the audit trail.
                cur = conn.execute(
                    "UPDATE dcc.api_keys SET revoked_at = COALESCE(revoked_at, now()) "
                    "WHERE id = %s::uuid",
                    (key_id,),
                )
                return cur.rowcount > 0

    def delete(self, key_id: str, tenant_id: Optional[str]) -> bool:
        tenant = tenant_id or self.tenant_of(key_id)
        if tenant is None:
            return False
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant)
                cur = conn.execute(
                    "DELETE FROM dcc.api_keys WHERE id = %s::uuid", (key_id,)
                )
                return cur.rowcount > 0

    def delete_expired(self, tenant_id: str) -> int:
        with self.connection() as conn:
            with conn.transaction():
                self._bind_tenant(conn, tenant_id)
                cur = conn.execute(
                    "DELETE FROM dcc.api_keys WHERE tenant_id = %s::uuid "
                    "AND expires_at IS NOT NULL AND expires_at < now()",
                    (tenant_id,),
                )
                return cur.rowcount


def _record_from_row(row: Dict[str, Any]) -> ApiKey:
    """Row -> ApiKey. There is no direction in which a raw key appears here."""
    return ApiKey(
        id=str(row["id"]),
        name=row.get("label") or "",
        key_hash=row["key_hash"],
        tenant_id=str(row["tenant_id"]),
        created_at=_epoch(row.get("created_at")) or time.time(),
        expires_at=_epoch(row.get("expires_at")),
        last_used_at=_epoch(row.get("last_used_at")),
        scopes=list(row.get("scopes") or []),
        revoked=row.get("revoked_at") is not None,
        created_by=row.get("created_by"),
    )


# ---------------------------------------------------------------------------
# API key store
# ---------------------------------------------------------------------------


class ApiKeyStore:
    """API key store: PostgreSQL when a DSN is available, in-memory otherwise.

    Parameters
    ----------
    dsn:
        Connection string. Defaults to ``DCC_DATABASE_URL``; with neither, the store
        is process-local and appropriate only for tests and single-process tools.
    touch_interval:
        Minimum seconds between ``last_used_at`` writes per key per process. The SQL
        applies its own 5-second guard, so the effective floor is the larger of the
        two. This is what keeps the audit update off the write path of every request.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        *,
        touch_interval: float = 30.0,
        pool_size: int = 4,
        timeout: float = 5.0,
    ) -> None:
        if dsn is None:
            dsn = os.getenv("DCC_DATABASE_URL", "")
        dsn = (dsn or "").strip()

        # Process-local records. With no DSN this IS the store. With a DSN it holds
        # only what the table cannot represent -- never a copy of a durable row, since
        # a copy would delay revocation and re-create the bug this class fixes.
        self._keys: Dict[str, ApiKey] = {}  # id -> ApiKey
        self._hash_to_id: Dict[str, str] = {}  # key_hash -> id
        self._lock = threading.RLock()

        self._dsn = dsn
        self._backend: Optional[_PostgresBackend] = (
            _PostgresBackend(dsn, pool_size=pool_size, timeout=timeout) if dsn else None
        )

        self._touch_interval = max(0.0, float(touch_interval))
        self._touch_lock = threading.Lock()
        self._touched: Dict[str, float] = {}
        self._executor: Any = None
        self._metadata_warned = False

    # -- introspection ------------------------------------------------------

    @property
    def backend(self) -> str:
        """``"postgres"`` when keys are durable and shared; ``"memory"`` otherwise."""
        return "postgres" if self._backend is not None else "memory"

    def reset(self) -> None:
        """Clear process-local state. Durable rows are untouched.

        Exists for test isolation. With a DSN this deliberately does not delete keys:
        a test helper must not be able to wipe a deployment's credentials.
        """
        with self._lock:
            self._keys.clear()
            self._hash_to_id.clear()
        with self._touch_lock:
            self._touched.clear()

    def close(self) -> None:
        backend, self._backend = self._backend, None
        if backend is not None:
            backend.close()
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            try:
                executor.shutdown(wait=False)
            except Exception:  # noqa: BLE001 - shutdown must not raise at teardown
                log.debug("error shutting down the API key touch executor", exc_info=True)

    # -- process-local records ---------------------------------------------

    def _local_put(self, record: ApiKey) -> ApiKey:
        with self._lock:
            existing_id = self._hash_to_id.get(record.key_hash)
            if existing_id is not None:
                return self._keys[existing_id]
            self._keys[record.id] = record
            self._hash_to_id[record.key_hash] = record.id
            return record

    def _local_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        with self._lock:
            key_id = self._hash_to_id.get(key_hash)
            if key_id is None:
                return None
            return self._keys.get(key_id)

    # -- creation -----------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        tenant_id: str,
        scopes: Optional[List[str]] = None,
        expires_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> Tuple[str, ApiKey]:
        """Create a new API key.

        Returns
        -------
        tuple[str, ApiKey]
            The raw key (show once) and the stored metadata.

        On the durable path a failed write raises. A key reported as created but
        absent from the database is worse than an error: the operator would hand out
        a credential that works nowhere.
        """
        scopes = list(scopes or [])
        metadata = dict(metadata or {})
        tenant_uuid = _as_uuid(tenant_id)

        if self._backend is not None and tenant_uuid is not None:
            if metadata and not self._metadata_warned:
                self._metadata_warned = True
                log.warning(
                    "ApiKeyStore metadata is not persisted: dcc.api_keys carries the "
                    "audit columns (created_by/created_at/revoked_at) but no free-form "
                    "metadata column, so the value is returned on the record only."
                )
            raw_key = generate_api_key()
            row = self._backend.insert(
                tenant_id=tenant_uuid,
                key_hash=hash_api_key(raw_key),
                label=name,
                scopes=scopes,
                expires_at=expires_at,
                created_by=created_by,
            )
            return raw_key, _record_from_row(row)

        if self._backend is not None:
            log.warning(
                "tenant_id %r is not a UUID, so it cannot exist in dcc.tenants and "
                "cannot be stored durably; issuing a process-local key instead (only "
                "tests and local fixtures do this)",
                tenant_id,
            )
        raw_key = generate_api_key()
        record = ApiKey(
            id=str(uuid.uuid4()),
            name=name,
            key_hash=hash_api_key(raw_key),
            tenant_id=tenant_id,
            expires_at=expires_at,
            scopes=scopes,
            metadata=metadata,
            created_by=created_by,
        )
        self._local_put(record)
        return raw_key, record

    # -- registration -------------------------------------------------------

    def register_hash(
        self,
        *,
        tenant_id: str,
        key_hash: str,
        name: str = "env-bootstrap",
        scopes: Optional[List[str]] = None,
        expires_at: Optional[float] = None,
        created_by: Optional[str] = "env:DCC_API_KEYS",
    ) -> ApiKey:
        """Register an already-hashed key.

        Loads keys from configuration at process start and backs the minting CLI. The
        plaintext key is never supplied here; the caller hashes it beforehand.

        This is the one write that must not raise, because it runs at import time: a
        database that is briefly unreachable, or a tenant that does not exist yet, must
        not stop the process from starting. On failure the key is kept process-local
        and a warning states the consequence -- it works in this process only, which
        is precisely the limitation this class exists to remove.
        """
        if not key_hash or len(key_hash) < 32:
            raise ValueError("key_hash must be a hex digest")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        scopes = list(scopes or [])

        existing = self._local_by_hash(key_hash)
        if existing is not None:
            return existing

        tenant_uuid = _as_uuid(tenant_id)
        if self._backend is not None and tenant_uuid is not None:
            try:
                row = self._backend.insert_if_absent(
                    tenant_id=tenant_uuid,
                    key_hash=key_hash,
                    label=name,
                    scopes=scopes,
                    expires_at=expires_at,
                    created_by=created_by,
                )
            except Exception as exc:  # noqa: BLE001 - startup must survive the database
                log.warning(
                    "could not persist API key %s... for tenant %s (%s): it will "
                    "authenticate in THIS process only and will not survive a restart "
                    "or reach a sibling worker. Fix the database or DCC_DATABASE_URL.",
                    key_hash[:8],
                    tenant_id,
                    exc,
                )
                row = None
            if row is not None:
                return _record_from_row(row)

        if self._backend is not None and tenant_uuid is None:
            log.warning(
                "tenant_id %r is not a UUID; registering its API key process-locally "
                "(such a tenant cannot exist in dcc.tenants)",
                tenant_id,
            )
        return self._local_put(
            ApiKey(
                id=str(uuid.uuid4()),
                name=name,
                key_hash=key_hash,
                tenant_id=tenant_id,
                expires_at=expires_at,
                scopes=scopes,
                created_by=created_by,
            )
        )

    # -- verification -------------------------------------------------------

    def verify(self, raw_key: str) -> ApiKey:
        """Verify a raw API key and return its metadata.

        Raises
        ------
        ApiKeyInvalidError
            If the key is not found, the hash doesn't match, or the key store is
            unreachable. An unreachable store authenticates nobody except keys it holds
            in this process (a bootstrap registration that never reached the database):
            failing open would turn a database outage into an authentication bypass.
        ApiKeyExpiredError
            If the key has expired.
        ApiKeyRevokedError
            If the key has been revoked.
        """
        if not isinstance(raw_key, str) or not raw_key:
            raise ApiKeyInvalidError("unknown API key")
        digest = hash_api_key(raw_key)
        if self._backend is None:
            return self._verify_local(raw_key, digest)
        return self._verify_durable(raw_key, digest)

    async def averify(self, raw_key: str) -> ApiKey:
        """``verify`` off the event loop. Preferred by async callers."""
        return await asyncio.to_thread(self.verify, raw_key)

    def _verify_durable(self, raw_key: str, digest: str) -> ApiKey:
        try:
            row = self._backend.lookup(digest)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - any failure means "cannot authenticate"
            # The store is unreachable. A key that this process holds locally -- a
            # bootstrap registration that never reached the database, or a fixture
            # tenant that cannot exist in dcc.tenants -- is still checked, because it
            # never depended on the database. Everything else is refused: failing open
            # would turn a database outage into an authentication bypass.
            local = self._local_by_hash(digest)
            if local is not None:
                log.warning(
                    "API key store unreachable (%s); authenticating from this "
                    "process's local registrations only",
                    exc,
                )
                return self._verify_local(raw_key, digest)
            log.critical(
                "API key store unreachable, rejecting the request (fail closed): %s",
                exc,
            )
            raise ApiKeyInvalidError("API key store unavailable") from exc

        if row is None:
            # Not durable: an unknown key, or a DCC_API_KEYS entry that could not be
            # persisted at startup. The process-local map is the only place such a key
            # can be found, and it never shadows a durable row.
            return self._verify_local(raw_key, digest)

        # Re-assert the match in constant time against the digest the function
        # returned, rather than trusting that the function filtered on p_hash.
        if not hmac.compare_digest(str(row.get("key_hash") or ""), digest):
            raise ApiKeyInvalidError("API key hash mismatch")

        if row.get("revoked_at") is not None:
            raise ApiKeyRevokedError("API key has been revoked")

        expires_at = _epoch(row.get("expires_at"))
        if expires_at is not None and time.time() >= expires_at:
            raise ApiKeyExpiredError("API key has expired")

        now = time.time()
        record = ApiKey(
            id=str(row.get("key_id")),
            name=row.get("label") or "",
            key_hash=digest,
            tenant_id=str(row.get("tenant_id")),
            created_at=_epoch(row.get("created_at")) or now,
            expires_at=expires_at,
            last_used_at=now,
            scopes=list(row.get("scopes") or []),
        )
        self._schedule_touch(digest)
        return record

    def _verify_local(self, raw_key: str, digest: str) -> ApiKey:
        api_key = self._local_by_hash(digest)
        if api_key is None:
            raise ApiKeyInvalidError("unknown API key")
        # Constant time, and a real comparison rather than a dict-hit trust: the dict
        # key is the digest, so this only proves the stored record agrees with it.
        if not hmac.compare_digest(api_key.key_hash, digest):
            raise ApiKeyInvalidError("API key hash mismatch")
        if api_key.revoked:
            raise ApiKeyRevokedError("API key has been revoked")
        if api_key.is_expired:
            raise ApiKeyExpiredError("API key has expired")
        api_key.last_used_at = time.time()
        return api_key

    # -- last_used_at: best effort, never on the failure path ---------------

    def _schedule_touch(self, digest: str) -> None:
        """Record usage without making every request a row write.

        Throttled per key per process, run on a one-thread executor, and every failure
        is swallowed: the audit trail is worth having, never worth failing an
        authenticated request over.
        """
        now = time.time()
        with self._touch_lock:
            last = self._touched.get(digest)
            if last is not None and (now - last) < self._touch_interval:
                return
            if len(self._touched) > 4096:
                # Bounded memory in a long-lived process with many keys.
                self._touched.clear()
            self._touched[digest] = now

        try:
            self._executor_or_create().submit(self._touch_now, digest)
        except Exception:  # noqa: BLE001 - a missed audit write is not an auth failure
            log.debug("could not schedule last_used_at update", exc_info=True)

    def _executor_or_create(self) -> Any:
        executor = self._executor
        if executor is not None:
            return executor
        with self._touch_lock:
            if self._executor is None:
                from concurrent.futures import ThreadPoolExecutor

                self._executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="dcc-api-key-touch"
                )
            return self._executor

    def _touch_now(self, digest: str) -> None:
        try:
            self._backend.touch(digest)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            log.debug(
                "last_used_at update failed for key %s...", digest[:8], exc_info=True
            )

    # -- reads --------------------------------------------------------------

    def get(self, key_id: str, tenant_id: Optional[str] = None) -> Optional[ApiKey]:
        """Look up an API key by id."""
        with self._lock:
            local = self._keys.get(key_id)
        if local is not None:
            return local
        if self._backend is None:
            return None
        row = self._backend.get(key_id, tenant_id)
        return _record_from_row(row) if row is not None else None

    def count(self) -> int:
        """How many keys exist, across all tenants.

        One number is all a startup lockout check needs, and it is answerable without
        a tenant context -- ``list_keys()`` is not, because under FORCE RLS a listing
        with no ``dcc.tenant_id`` is correctly empty for every non-bypassing role.
        """
        with self._lock:
            local = len(self._keys)
        if self._backend is None:
            return local
        return self._backend.count() + local

    def list_keys(self, tenant_id: Optional[str] = None) -> List[ApiKey]:
        """List API keys, optionally filtered by tenant.

        With a DSN this returns what the role is permitted to see. A listing with no
        tenant is empty under row level security unless the role bypasses it -- that
        is the policy working, not a bug. Pass ``tenant_id`` for a real listing, and
        use ``count()`` to ask "is the store empty".
        """
        with self._lock:
            local = list(self._keys.values())
        if tenant_id is not None:
            local = [k for k in local if k.tenant_id == tenant_id]

        if self._backend is None:
            return local

        durable: List[ApiKey] = []
        if tenant_id is not None:
            tenant_uuid = _as_uuid(tenant_id)
            if tenant_uuid is not None:
                durable = [
                    _record_from_row(r)
                    for r in self._backend.list_for_tenant(tenant_uuid)
                ]
        else:
            try:
                durable = [_record_from_row(r) for r in self._backend.list_visible()]
            except Exception:  # noqa: BLE001
                log.debug("listing API keys without a tenant failed", exc_info=True)
                durable = []
            if not durable:
                try:
                    total = self._backend.count()
                except Exception:  # noqa: BLE001
                    total = 0
                if total:
                    # Without this, the caller reads "no keys" off a healthy store and
                    # concludes the deployment is unconfigured.
                    log.warning(
                        "list_keys() without a tenant sees 0 of %d key(s): row level "
                        "security scopes dcc.api_keys by dcc.tenant_id, so a listing "
                        "needs a tenant. Use count() to ask whether the store is empty.",
                        total,
                    )

        seen = {k.key_hash for k in durable}
        merged = durable + [k for k in local if k.key_hash not in seen]
        merged.sort(key=lambda k: k.created_at, reverse=True)
        return merged

    # -- mutation -----------------------------------------------------------

    def revoke(self, key_id: str, tenant_id: Optional[str] = None) -> bool:
        """Revoke an API key. Returns True if it existed."""
        with self._lock:
            local = self._keys.get(key_id)
            if local is not None:
                local.revoked = True
        if self._backend is None:
            return local is not None
        if self._backend.revoke(key_id, tenant_id):
            return True
        return local is not None

    def delete(self, key_id: str, tenant_id: Optional[str] = None) -> bool:
        """Permanently delete an API key. Returns True if it existed."""
        with self._lock:
            local = self._keys.pop(key_id, None)
            if local is not None:
                self._hash_to_id.pop(local.key_hash, None)
        if self._backend is None:
            return local is not None
        if self._backend.delete(key_id, tenant_id):
            return True
        return local is not None

    def cleanup_expired(self, tenant_id: Optional[str] = None) -> int:
        """Delete expired keys. Returns the count removed.

        Under row level security the delete has to name a tenant; without one this
        removes only process-local entries and returns that count, rather than
        deleting across tenants.
        """
        with self._lock:
            expired = [kid for kid, k in self._keys.items() if k.is_expired]
            for kid in expired:
                key = self._keys.pop(kid)
                self._hash_to_id.pop(key.key_hash, None)
            removed = len(expired)

        if self._backend is None:
            return removed

        tenant_uuid = _as_uuid(tenant_id) if tenant_id is not None else None
        if tenant_uuid is None:
            if not removed:
                log.debug(
                    "cleanup_expired() without a tenant is a no-op on the durable store"
                )
            return removed
        return removed + self._backend.delete_expired(tenant_uuid)
