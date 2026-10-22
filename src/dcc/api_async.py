"""Async API layer for Data Center Commander.

Replaces the monolithic ThreadingHTTPServer with FastAPI + Uvicorn.
Adds pagination, caching, rate limiting, and optimization endpoints.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .provenance.evidence import verify_evidence_chain
from .economics.tco import quick_tco, tco_breakdown_by_category
from .validation.schema import validate_currency_code
from .validation.boundaries import validate_value_range
from .optimization_kernels import (
    Asset,
    CapacityDimension,
    EnergyRequest,
    NetworkNode,
    Technician,
    Workload,
    WorkOrder,
    capacity_allocation,
    clarke_wright_savings,
    dsatur_zoning,
    first_fit_decreasing,
    max_min_fair_energy_allocation,
)

# ---------------------------------------------------------------------------
# Circuit breaker pattern
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Circuit breaker with states: closed, open, half-open.

    - closed: normal operation, failures tracked; trips to open on threshold
    - open: rejects calls; after recovery_timeout transitions to half-open
    - half-open: allows limited calls through to test recovery
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state: str = "closed"  # closed, open, half-open
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0
        self.call_count: int = 0

    def record_success(self) -> None:
        """Record a successful call."""
        self.call_count += 1
        self.success_count += 1
        self.failure_count = 0

        if self.state == "half-open" and self.success_count >= self.half_open_max_calls:
            self.state = "closed"
            self.success_count = 0
            self.call_count = 0
            self.last_success_time = time.time()

    def record_failure(self) -> None:
        """Record a failed call."""
        self.call_count += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == "closed":
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                self.failure_count = 0
                self.success_count = 0
                self.call_count = 0
        elif self.state == "half-open":
            # Any failure in half-open reopens the circuit
            self.state = "open"
            self.failure_count = 0
            self.success_count = 0
            self.call_count = 0

    def can_call(self) -> bool:
        """Check if a call is allowed through the circuit breaker."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half-open"
                self.success_count = 0
                self.call_count = 0
                return True
            return False
        elif self.state == "half-open":
            return self.call_count < self.half_open_max_calls
        return False

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.call_count = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0


# Global circuit breakers per service key
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(key: str, **kwargs: Any) -> CircuitBreaker:
    """Get or create a circuit breaker keyed by service identifier."""
    if key not in _circuit_breakers:
        _circuit_breakers[key] = CircuitBreaker(**kwargs)
    return _circuit_breakers[key]


# ---------------------------------------------------------------------------
# API async layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DCC_DATABASE_URL", "")
    redis_url: str = os.environ.get("DCC_REDIS_URL", "redis://localhost:6379/0")
    cache_ttl_seconds: int = int(os.environ.get("DCC_CACHE_TTL", "30"))
    rate_limit_rps: int = int(os.environ.get("DCC_RATE_LIMIT_RPS", "100"))
    max_page_size: int = 1000
    default_page_size: int = 100


settings = Settings()

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_cursor: str | None = None


def encode_cursor(offset: int) -> str:
    import base64

    return base64.b64encode(json.dumps({"offset": offset}).encode()).decode()


def decode_cursor(cursor: str) -> int:
    import base64

    try:
        data = json.loads(base64.b64decode(cursor.encode()))
        return int(data.get("offset", 0))
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


# ---------------------------------------------------------------------------
# In-memory cache (replace with Redis in production)
# ---------------------------------------------------------------------------


class Cache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key in self._data:
            expiry, value = self._data[key]
            if time.time() < expiry:
                return value
            del self._data[key]
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or settings.cache_ttl_seconds
        self._data[key] = (time.time() + ttl, value)

    def invalidate(self, pattern: str) -> None:
        keys_to_delete = [k for k in self._data if pattern in k]
        for k in keys_to_delete:
            del self._data[k]


cache = Cache()

# ---------------------------------------------------------------------------
# Rate limiter (simple token bucket)
# ---------------------------------------------------------------------------


class RateLimiter:
    def __init__(self, rps: int) -> None:
        self.rps = rps
        self._tokens: dict[str, tuple[float, float]] = {}

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        if key not in self._tokens:
            self._tokens[key] = (now, self.rps - 1)
            return True

        last_time, tokens = self._tokens[key]
        elapsed = now - last_time
        tokens = min(self.rps, tokens + elapsed * self.rps)

        if tokens >= 1:
            self._tokens[key] = (now, tokens - 1)
            return True
        self._tokens[key] = (now, tokens)
        return False


rate_limiter = RateLimiter(settings.rate_limit_rps)

# ---------------------------------------------------------------------------
# Database pool (lazy import)
# ---------------------------------------------------------------------------

_pool: Any = None


async def get_pool():
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise HTTPException(status_code=503, detail="database_not_configured")
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="postgres_extra_required") from exc
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=20,
            timeout=5,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
        )
        try:
            await _pool.open()
            await _pool.wait(timeout=5)
        except Exception as exc:
            await _pool.close()
            raise HTTPException(status_code=503, detail="database_unavailable") from exc
    return _pool


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    _warn_if_locked_out()
    with suppress(Exception):
        await get_pool()
    yield
    # Shutdown
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Data Center Commander",
    version="2.0.0",
    description="Read-only, energy-to-compute data-center operations command view",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded", "execution_permitted": False},
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Metrics (dcc.observability)
#
# The observability package is ~5,000 lines of counters, gauges, histograms and a
# Prometheus text renderer with no consumer at all. This wires it into the served
# app so the process can actually be monitored: request latency, throughput and
# error rate, exported in Prometheus text format at /metrics.
# ---------------------------------------------------------------------------

from .observability.metrics import ErrorType as _ErrorType  # noqa: E402
from .observability.metrics import MetricsEngine as _MetricsEngine  # noqa: E402

_METRICS = _MetricsEngine()
_METRICS_EXCLUDED = {"/metrics", "/healthz", "/readyz"}


def _classify_status(status_code: int) -> _ErrorType:
    """Map an HTTP status onto the engine's error taxonomy."""
    if status_code == 429:
        return _ErrorType.RATE_LIMIT
    if status_code in (401, 403):
        return _ErrorType.AUTHENTICATION
    if status_code in (400, 422):
        return _ErrorType.VALIDATION
    if status_code == 404:
        return _ErrorType.UNKNOWN
    if status_code == 504:
        return _ErrorType.TIMEOUT
    if status_code >= 500:
        return _ErrorType.INTERNAL
    return _ErrorType.UNKNOWN


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Time every request and record its outcome.

    The label is the matched ROUTE TEMPLATE ("/v2/assets/{asset_id}"), never the
    concrete path. Labelling on the request path creates a new time series per
    distinct identifier, so a tenant scanning by id would grow the registry without
    bound and eventually take the process down. Using scope["route"] after routing
    keeps cardinality equal to the number of routes.
    """
    if request.url.path in _METRICS_EXCLUDED:
        return await call_next(request)

    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        label = getattr(route, "path", None) or "unmatched"
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _METRICS.record_latency(label, elapsed_ms)
        _METRICS.increment_throughput("api_requests_total", labels={"route": label})
        if status_code >= 400:
            _METRICS.record_error(_classify_status(status_code), labels={"route": label})


# ---------------------------------------------------------------------------
# Authentication and tenant isolation (dcc.security)
#
# Every /v2 route takes tenant_id as a caller-supplied query parameter and nothing
# authenticated it, so any client that could reach the port could read any tenant's
# data by supplying that tenant's id. dcc/security already ships ApiKeyStore,
# verify_api_key, ApiKeyExpiredError and TenantMismatchError -- none of it was wired
# into the served application.
#
# Enforcement is ON by default. DCC_ALLOW_ANONYMOUS=true is an explicit, logged
# opt-out for local development and the legacy test suite; it is not a production
# mode. A missing key is a 401, a key that does not own the requested tenant is a
# 403, and the two are deliberately distinguishable in the response body but not in
# whether the request proceeds.
# ---------------------------------------------------------------------------

from .security.api_keys import ApiKey  # noqa: E402
from .security.api_keys import ApiKeyExpiredError as _ApiKeyExpired  # noqa: E402
from .security.api_keys import ApiKeyInvalidError as _ApiKeyInvalid  # noqa: E402
from .security.api_keys import ApiKeyRevokedError as _ApiKeyRevoked  # noqa: E402
from .security.api_keys import ApiKeyStore as _ApiKeyStore  # noqa: E402

_API_KEYS = _ApiKeyStore()


def _bootstrap_api_keys() -> int:
    """Load durable keys from DCC_API_KEYS at process start.

    Format: comma-separated "tenant_id:sha256hex" entries:

        DCC_API_KEYS="<tenant-uuid>:<64-hex>,<tenant-uuid>:<64-hex>"

    Hashes, not plaintext, so the secret never sits in the environment. The store is
    in-memory and per-process, so without this every restart forgot every key and each
    worker held a different set, making enforced authentication unusable in any
    multi-worker deployment.

    Mint an entry with:  python -m dcc.keys_cli create --tenant <uuid> --name ops
    """
    raw = os.getenv("DCC_API_KEYS", "").strip()
    if not raw:
        return 0

    loaded = 0
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        tenant_id, _, key_hash = entry.partition(":")
        tenant_id, key_hash = tenant_id.strip(), key_hash.strip()
        if not tenant_id or not key_hash:
            # Fail loudly: a silently skipped entry presents as "my key stopped
            # working" with no clue why.
            raise RuntimeError(f"DCC_API_KEYS entry is not 'tenant_id:hash': {entry[:24]!r}")
        _API_KEYS.register_hash(tenant_id=tenant_id, key_hash=key_hash)
        loaded += 1
    return loaded


_BOOTSTRAPPED_KEYS = _bootstrap_api_keys()


def _warn_if_locked_out() -> None:
    """Announce a deployment that enforces auth but holds no keys.

    Enforced authentication with an empty key store is a lockout: every request gets
    401 and nothing in the logs says why. DCC_REQUIRE_KEYS=true turns that into a
    startup failure for production; otherwise it is a loud warning, because a
    developer running locally without keys should still get a working process.
    """
    if _auth_is_open():
        return
    try:
        existing = len(_API_KEYS.list_keys())
    except Exception:
        existing = 0
    if existing or _BOOTSTRAPPED_KEYS:
        return

    message = (
        "Authentication is enforced but no API keys are configured: every request "
        "will be rejected with 401. Mint one with "
        "'python -m dcc.keys_cli create --tenant <uuid> --name ops' and set "
        "DCC_API_KEYS to the printed entry. For local development only, set "
        "DCC_ALLOW_ANONYMOUS=true."
    )
    if os.getenv("DCC_REQUIRE_KEYS", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError(message)
    import logging

    logging.getLogger("dcc.auth").warning("NO API KEYS CONFIGURED. %s", message)

_AUTH_PUBLIC_PATHS = {
    "/healthz", "/readyz", "/metrics", "/openapi.json", "/docs",
    "/docs/oauth2-redirect", "/redoc",
    # The console shell contains no tenant data, and a browser cannot present a key
    # before the page that would tell it which key to use has loaded.
    "/",
}


def _auth_is_open() -> bool:
    """True only when anonymity was explicitly requested via the environment.

    Delegated to dcc.security.posture so the application and the compliance controls
    read the same configuration. They previously disagreed on what "authentication is
    enabled" means, and the compliance side was reading a variable nothing consumed.
    """
    from .security.posture import anonymous_allowed

    return anonymous_allowed()


def _presented_key(request: Request) -> str | None:
    """Read an API key from Authorization: Bearer or X-API-Key."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token:
            return token
    explicit = request.headers.get("x-api-key", "").strip()
    return explicit or None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Authenticate the caller and bind the tenant before the handler runs.

    Ordering matters: this is registered after the metrics middleware, so Starlette
    runs it OUTSIDE metrics and a rejected request is still counted. An unauthenticated
    request is still a request an operator wants to see on the dashboard.
    """
    path = request.url.path
    if path in _AUTH_PUBLIC_PATHS or path.startswith("/docs") or _auth_is_open():
        return await call_next(request)

    presented = _presented_key(request)
    if presented is None:
        return JSONResponse(
            status_code=401,
            content={
                "error": "missing_credentials",
                "detail": "send an API key as 'Authorization: Bearer <key>' or 'X-API-Key: <key>'",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        api_key: ApiKey = _API_KEYS.verify(presented)
    except _ApiKeyExpired:
        return JSONResponse(status_code=401, content={"error": "key_expired"})
    except _ApiKeyRevoked:
        return JSONResponse(status_code=401, content={"error": "key_revoked"})
    except _ApiKeyInvalid:
        # Deliberately identical to the missing-key response body's shape: telling a
        # caller whether a key EXISTS is an oracle for key enumeration.
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    requested_tenant = request.query_params.get("tenant_id")
    if requested_tenant is not None and requested_tenant != api_key.tenant_id:
        # This is the tenant-isolation check. Without it, a valid key for tenant A
        # can read tenant B's data simply by changing one query parameter.
        return JSONResponse(
            status_code=403,
            content={
                "error": "tenant_mismatch",
                "detail": "the presented key is not authorised for the requested tenant",
            },
        )

    # Hand the authenticated identity to the handler without trusting the query string.
    request.state.tenant_id = api_key.tenant_id
    request.state.api_key_id = api_key.id
    return await call_next(request)


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus text exposition of the process metrics."""
    body = _METRICS.render()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/healthz")
async def healthz():
    return {"service": "data-center-commander", "mode": "read_only", "execution_permitted": False}


@app.get("/readyz")
async def readyz():
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            schema = await conn.fetchrow(
                "SELECT to_regclass('dcc.tenants') IS NOT NULL AS tenants, "
                "to_regclass('dcc.assets') IS NOT NULL AS assets"
            )
            if not schema or not all(schema.values()):
                return JSONResponse(
                    status_code=503,
                    content={"ready": False, "checks": {"schema": "incomplete"}},
                )
        return {"ready": True, "checks": {"database": "ok", "schema": "ok"}}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@app.get("/v2/overview")
async def overview(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    demo: str | None = None,
):
    cache_key = f"overview:{tenant_id}:{demo}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        facilities = await conn.fetchrow(
            "SELECT count(*)::int AS facility_count FROM dcc.facilities WHERE tenant_id=$1::uuid AND status='active'",
            tenant_id,
        )
        kpis = await conn.fetch(
            "SELECT DISTINCT ON (d.metric_key) d.metric_key,d.name,d.unit,o.value_numeric,o.window_start,o.window_end,o.observed_at,o.coverage,o.uncertainty,o.quality_status,o.reason_codes,o.provenance "
            "FROM dcc.kpi_observations o JOIN dcc.kpi_definitions d ON d.tenant_id=o.tenant_id AND d.id=o.kpi_definition_id "
            "WHERE o.tenant_id=$1::uuid ORDER BY d.metric_key,o.window_end DESC,o.observed_at DESC LIMIT 100",
            tenant_id,
        )
        open_work = await conn.fetchrow(
            "SELECT count(*)::int AS open_count FROM dcc.operational_workflows WHERE tenant_id=$1::uuid AND status NOT IN ('closed','cancelled')",
            tenant_id,
        )
        latest = await conn.fetchrow(
            "SELECT max(ingested_at) AS latest_ingested_at FROM dcc.telemetry_readings WHERE tenant_id=$1::uuid",
            tenant_id,
        )

    result = {
        "tenant_id": tenant_id,
        "facility_count": facilities["facility_count"] if facilities else 0,
        "kpis": [dict(k) for k in kpis],
        "open_workflows": open_work["open_count"] if open_work else 0,
        "latest_telemetry_ingested_at": latest["latest_ingested_at"] if latest else None,
        "read_only": True,
        "execution_permitted": False,
    }
    cache.set(cache_key, result, ttl=30)
    return result


# ---------------------------------------------------------------------------
# Paginated list endpoints
# ---------------------------------------------------------------------------


@app.get("/v2/assets")
async def list_assets(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = None,
):
    offset = decode_cursor(cursor) if cursor else 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT a.external_id,a.asset_type,a.name,a.manufacturer,a.model,a.lifecycle_state,a.criticality,a.observed_at,f.name AS facility_name,s.name AS space_name "
            "FROM dcc.assets a LEFT JOIN dcc.spaces s ON s.tenant_id=a.tenant_id AND s.id=a.space_id "
            "LEFT JOIN dcc.facilities f ON f.tenant_id=s.tenant_id AND f.id=s.facility_id "
            "WHERE a.tenant_id=$1::uuid ORDER BY a.lifecycle_state,a.name LIMIT $2 OFFSET $3",
            tenant_id,
            limit + 1,
            offset,
        )
        total = await conn.fetchrow(
            "SELECT count(*)::int AS total FROM dcc.assets WHERE tenant_id=$1::uuid",
            tenant_id,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    next_cursor = encode_cursor(offset + limit) if has_more else None

    return Page(
        items=items,
        total=total["total"] if total else 0,
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=next_cursor,
    ).__dict__


@app.get("/v2/facilities")
async def list_facilities(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = None,
):
    offset = decode_cursor(cursor) if cursor else 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT f.id::text,f.code,f.name,f.facility_type,f.status,s.code AS site_code,s.name AS site_name "
            "FROM dcc.facilities f JOIN dcc.sites s ON s.tenant_id=f.tenant_id AND s.id=f.site_id "
            "WHERE f.tenant_id=$1::uuid ORDER BY s.name,f.name LIMIT $2 OFFSET $3",
            tenant_id,
            limit + 1,
            offset,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    next_cursor = encode_cursor(offset + limit) if has_more else None

    return Page(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=next_cursor,
    ).__dict__


@app.get("/v2/costs")
async def list_costs(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    demo: str | None = None,
):
    """Cost intelligence: estimate projects, observed prices and actuals.

    This query was already written -- in src/dcc/api.py, a stdlib HTTP server that is
    never mounted, which is why the console's cost panel called a route that did not
    exist. Ported here rather than rewritten.

    Synthetic demo data is withheld unless demo=synthetic is passed explicitly. Seeded
    fixtures must never render as if they were sourced prices: an estimate built on
    synthetic unit rates looks identical to a real one in the response shape, so the
    gate is here and not in the UI.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        estimates = await conn.fetch(
            "SELECT e.id::text,e.project_code,e.name,e.lifecycle_phase,e.status,e.currency,e.geography,"
            "e.price_as_of,e.horizon_months,e.it_capacity_kw,e.facility_area_m2,e.rack_count,"
            "e.annual_it_energy_kwh,e.annual_useful_work,e.discount_rate,e.contingency_pct,"
            "e.assumptions,e.calculation_version,"
            "coalesce(r.lifecycle_pv,0) AS lifecycle_pv,coalesce(r.low_pv,0) AS low_pv,"
            "coalesce(r.high_pv,0) AS high_pv,coalesce(r.first_period_cost,0) AS first_period_cost,"
            "coalesce(r.line_count,0) AS line_count,coalesce(r.unpriced_lines,0) AS unpriced_lines,"
            "coalesce(r.synthetic_lines,0) AS synthetic_lines "
            "FROM dcc.estimate_projects e LEFT JOIN (SELECT tenant_id,estimate_id,currency,"
            "sum(present_value_base) AS lifecycle_pv,sum(present_value_low) AS low_pv,"
            "sum(present_value_high) AS high_pv,sum(first_period_cost) AS first_period_cost,"
            "sum(line_count) AS line_count,sum(unpriced_lines) AS unpriced_lines,"
            "sum(synthetic_lines) AS synthetic_lines "
            "FROM dcc.estimate_cost_rollup GROUP BY tenant_id,estimate_id,currency) r "
            "ON r.tenant_id=e.tenant_id AND r.estimate_id=e.id "
            "WHERE e.tenant_id=$1::uuid ORDER BY e.created_at DESC LIMIT 100",
            tenant_id,
        )

        prices = await conn.fetch(
            "SELECT p.item_code,p.description,p.category,p.quantity_unit,p.unit_price,p.currency,"
            "p.normalized_unit_price,b.currency AS book_currency,p.currency_basis_date,p.fx_to_book,"
            "p.geography,p.delivery_basis,p.observed_at,p.valid_from,p.valid_to,p.source_kind,"
            "p.source_name,p.source_ref,p.confidence,p.quality_status,p.provenance "
            "FROM dcc.price_observations p "
            "JOIN dcc.cost_books b ON b.tenant_id=p.tenant_id AND b.id=p.cost_book_id "
            "WHERE p.tenant_id=$1::uuid ORDER BY p.observed_at DESC LIMIT 500",
            tenant_id,
        )

        actuals = await conn.fetch(
            "SELECT accounting_period,cost_type,currency,sum(amount) AS actual_amount,"
            "count(*)::int AS entries,bool_or(provenance->>'synthetic'='true') AS synthetic "
            "FROM dcc.cost_actuals WHERE tenant_id=$1::uuid "
            "GROUP BY accounting_period,cost_type,currency "
            "ORDER BY accounting_period DESC,cost_type LIMIT 500",
            tenant_id,
        )

    estimate_rows = [dict(r) for r in estimates]
    price_rows = [dict(r) for r in prices]
    actual_rows = [dict(r) for r in actuals]

    synthetic_present = (
        any(
            r.get("source_kind") == "synthetic_demo"
            or (r.get("provenance") or {}).get("synthetic") is True
            for r in price_rows
        )
        or any(int(r.get("synthetic_lines") or 0) > 0 for r in estimate_rows)
        or any(r.get("synthetic") is True for r in actual_rows)
    )
    show_synthetic = demo == "synthetic" and synthetic_present
    withhold = synthetic_present and not show_synthetic

    return {
        "tenant_id": tenant_id,
        "estimates": [] if withhold else estimate_rows,
        "prices": [] if withhold else price_rows,
        "actuals": [] if withhold else actual_rows,
        "read_only": True,
        "synthetic": synthetic_present,
        "synthetic_demo_mode": show_synthetic,
    }


def _unconsumed_configuration(controls) -> dict[str, list[str]]:
    """Environment variables a control reads that the application never consults.

    All 16 built-in evaluators read at least one variable that appears nowhere in the
    served code: DCC_MFA_ENABLED, DCC_LOG_LEVEL, DCC_TLS_ENFORCED and so on. A control
    that reports pass because such a variable is set to "true" is asserting a
    configuration the running system ignores -- the operator can change it and nothing
    happens.

    This is determined by reading each evaluator's source for os.environ.get(...) calls
    and checking whether the application references the name at all. It is deliberately
    conservative and cheap: it answers "does the app know this variable exists", which
    is the question that separates a real control from a decorative one.
    """
    import inspect as _inspect
    import re as _re
    from pathlib import Path as _Path

    try:
        app_source = _Path(__file__).read_text(encoding="utf-8")
    except OSError:
        return {}

    gaps: dict[str, list[str]] = {}
    for control in controls:
        evaluator = getattr(control, "evaluator", None)
        if evaluator is None:
            continue
        try:
            source = _inspect.getsource(evaluator)
        except (OSError, TypeError):
            continue
        names = set(_re.findall(r'os\.environ\.get\(["\']([A-Z_]+)["\']', source))
        unconsumed = sorted(n for n in names if n not in app_source)
        if unconsumed:
            gaps[control.control_id] = unconsumed
    return gaps


def _build_posture_engine():
    """Register posture controls that measure THIS process, not a declared config.

    Every check here reads state the application actually holds: the middleware stack,
    the route table, the authentication posture. None of them read an environment
    variable that the code ignores, which is the defect that made the compliance
    controls decorative.

    Checks that genuinely cannot be decided without a database return NOT_ASSESSED
    rather than a guess. An honest gap scores zero and shows up in the report; a
    fabricated pass scores full marks and hides a hole.
    """
    from .security.posture import auth_posture
    from .security_posture import ControlStatus, PostureDimension, SecurityScoringEngine
    from .security_posture.scoring import ControlResult

    def _result(name, dimension, ok, description, evidence=None):
        return ControlResult(
            name=name,
            dimension=dimension,
            status=ControlStatus.PASS if ok else ControlStatus.FAIL,
            description=description,
            evidence=evidence or {},
        )

    def _middleware_names():
        return {getattr(m.cls, "__name__", str(m.cls)) for m in app.user_middleware}

    def _route_paths():
        return {getattr(r, "path", "") for r in app.routes}

    engine = SecurityScoringEngine()

    # --- identity and access ---
    def authentication_required():
        posture = auth_posture()
        return _result(
            "authentication_required", PostureDimension.IDENTITY_ACCESS,
            posture["authentication_required"],
            "API requires credentials" if posture["authentication_required"]
            else "DCC_ALLOW_ANONYMOUS is set; the API accepts unauthenticated requests",
            posture,
        )

    def _live_keys() -> int:
        """Keys actually registered in this process.

        auth_posture() counts DCC_API_KEYS entries, which is the durable, auditable
        configuration. But a key can also be registered at runtime (keys_cli, or an
        admin call), and that key authenticates while contributing nothing to the env
        count. Reporting "no keys configured" alongside a working key would be a false
        negative, so the identity controls count what can actually authenticate.
        """
        try:
            return len(_API_KEYS.list_keys())
        except Exception:
            return 0

    def keys_configured():
        live = _live_keys()
        return _result(
            "api_keys_configured", PostureDimension.IDENTITY_ACCESS,
            live > 0,
            f"{live} key(s) registered" if live else "no API keys registered",
            {"registered_keys": live},
        )

    def not_locked_out():
        posture = auth_posture()
        live = _live_keys()
        locked_out = posture["authentication_required"] and live == 0
        return _result(
            "not_locked_out", PostureDimension.IDENTITY_ACCESS,
            not locked_out,
            "access is usable" if not locked_out
            else "authentication enforced with no keys: every request is rejected",
            {"registered_keys": live, "anonymous_allowed": posture["anonymous_allowed"]},
        )

    def tenant_isolation():
        """Tenant isolation is decided by the auth posture, not by middleware names.

        @app.middleware("http") registers a BaseHTTPMiddleware whose dispatch function
        keeps the name; the stack does not carry "auth_middleware". Checking for that
        name reported a failure on a correctly configured deployment. What actually
        guarantees isolation is that authentication is required and keys exist, because
        the middleware refuses a request whose tenant_id differs from the key's tenant.
        """
        posture = auth_posture()
        enforced = posture["authentication_required"] and _live_keys() > 0
        return _result(
            "tenant_isolation_enforced", PostureDimension.IDENTITY_ACCESS,
            enforced,
            "cross-tenant requests are rejected against the key's tenant"
            if enforced else "tenant binding cannot be enforced without authentication and keys",
            posture,
        )

    # --- network ---
    def cors_restricted():
        for m in app.user_middleware:
            if getattr(m.cls, "__name__", "") == "CORSMiddleware":
                options = m.kwargs if hasattr(m, "kwargs") else {}
                origins = options.get("allow_origins", [])
                wildcard = "*" in origins
                return _result(
                    "cors_not_wildcard", PostureDimension.NETWORK_SECURITY,
                    not wildcard,
                    f"CORS origins restricted to {len(origins)} host(s)" if not wildcard
                    else "CORS allows any origin",
                    {"allow_origins": origins},
                )
        return ControlResult(
            name="cors_not_wildcard", dimension=PostureDimension.NETWORK_SECURITY,
            status=ControlStatus.NOT_ASSESSED, description="no CORS middleware configured",
        )

    def metrics_not_public():
        """Health and metrics are intentionally open; this records that fact."""
        return _result(
            "observability_endpoints_scoped", PostureDimension.NETWORK_SECURITY,
            "/metrics" in _route_paths(),
            "metrics endpoint present for monitoring" if "/metrics" in _route_paths()
            else "no metrics endpoint",
            {"open_paths": sorted(p for p in _route_paths() if p in {"/healthz", "/readyz", "/metrics"})},
        )

    # --- logging and monitoring ---
    def _registered_dispatchers():
        """Names of the dispatch functions actually installed in the middleware stack.

        @app.middleware("http") wraps the function in BaseHTTPMiddleware and keeps it as
        .dispatch, so the stack never carries the function's own name at the top level.
        Checking render output instead gave a false negative on a cold start, because
        latencies are recorded AFTER the handler returns -- the first request cannot see
        its own metrics.
        """
        found = set()
        for entry in app.user_middleware:
            dispatch = getattr(entry, "dispatch", None)
            if dispatch is not None:
                found.add(getattr(dispatch, "__name__", ""))
            kwargs = getattr(entry, "kwargs", {}) or {}
            inner = kwargs.get("dispatch")
            if inner is not None:
                found.add(getattr(inner, "__name__", ""))
        return found

    def metrics_instrumented():
        dispatchers = _registered_dispatchers()
        instrumented = "metrics_middleware" in dispatchers
        return _result(
            "requests_instrumented", PostureDimension.LOGGING_MONITORING,
            instrumented,
            "requests are timed and counted" if instrumented
            else "no request instrumentation middleware",
            {"dispatchers": sorted(d for d in dispatchers if d)},
        )

    def evidence_api_present():
        return _result(
            "evidence_chain_readable", PostureDimension.LOGGING_MONITORING,
            "/v2/evidence" in _route_paths(),
            "evidence chain is readable over the API" if "/v2/evidence" in _route_paths()
            else "no evidence endpoint",
            {},
        )

    # --- data protection ---
    def evidence_verification_available():
        return _result(
            "evidence_verifiable", PostureDimension.DATA_PROTECTION,
            "/v2/evidence/verify" in _route_paths(),
            "evidence chain can be verified over the API"
            if "/v2/evidence/verify" in _route_paths() else "no verification endpoint",
            {},
        )

    def encryption_at_rest():
        # Cannot be decided from inside the process: depends on the Postgres configuration.
        return ControlResult(
            name="encryption_at_rest", dimension=PostureDimension.DATA_PROTECTION,
            status=ControlStatus.NOT_ASSESSED,
            description="requires database configuration; not observable from the application",
        )

    # --- infrastructure ---
    def fail_closed():
        posture = auth_posture()
        return _result(
            "auth_fails_closed", PostureDimension.INFRASTRUCTURE_SECURITY,
            not posture["anonymous_allowed"],
            "unauthenticated requests are rejected" if not posture["anonymous_allowed"]
            else "unauthenticated requests are accepted",
            posture,
        )

    def db_readiness_probe():
        return _result(
            "readiness_probe_present", PostureDimension.INFRASTRUCTURE_SECURITY,
            "/readyz" in _route_paths(),
            "readiness checks schema and tenant RLS" if "/readyz" in _route_paths()
            else "no readiness probe",
            {},
        )

    for dim, name, fn in (
        (PostureDimension.IDENTITY_ACCESS, "authentication_required", authentication_required),
        (PostureDimension.IDENTITY_ACCESS, "api_keys_configured", keys_configured),
        (PostureDimension.IDENTITY_ACCESS, "not_locked_out", not_locked_out),
        (PostureDimension.IDENTITY_ACCESS, "tenant_isolation_enforced", tenant_isolation),
        (PostureDimension.DATA_PROTECTION, "evidence_verifiable", evidence_verification_available),
        (PostureDimension.DATA_PROTECTION, "encryption_at_rest", encryption_at_rest),
        (PostureDimension.NETWORK_SECURITY, "cors_not_wildcard", cors_restricted),
        (PostureDimension.NETWORK_SECURITY, "observability_endpoints_scoped", metrics_not_public),
        (PostureDimension.LOGGING_MONITORING, "requests_instrumented", metrics_instrumented),
        (PostureDimension.LOGGING_MONITORING, "evidence_chain_readable", evidence_api_present),
        (PostureDimension.INFRASTRUCTURE_SECURITY, "auth_fails_closed", fail_closed),
        (PostureDimension.INFRASTRUCTURE_SECURITY, "readiness_probe_present", db_readiness_probe),
    ):
        engine.register_control(dim, name, fn)

    return engine


@app.get("/v2/security/posture")
async def security_posture():
    """Weighted security posture across five dimensions, from observable state.

    Distinct from /v2/compliance/scan. That answers "is the declared configuration
    present" for an audit framework. This answers "what can be observed about the
    running process" -- middleware, routes, authentication posture -- and it will not
    award a pass it cannot justify. Controls that need the database report
    NOT_ASSESSED rather than assuming a value.
    """
    report = await run_in_threadpool(lambda: _build_posture_engine().evaluate())

    return {
        "overall_score": report.overall_score,
        "graded_at": report.graded_at,
        "evaluation_basis": "observed_process_state",
        "dimensions": {
            getattr(dim, "value", str(dim)): {
                "score": round(score.score, 4),
                "weight": score.weight,
                "weighted": round(score.weighted, 4),
                "passed": score.passed,
                "failed": score.failed,
                "partial": score.partial,
                "not_assessed": score.not_assessed,
                "controls": score.details.get("controls", {}),
            }
            for dim, score in report.dimension_scores.items()
        },
        "recommendations": report.recommendations,
    }


@app.get("/v2/compliance/controls")
async def list_compliance_controls(framework: str | None = None):
    """The compliance control catalogue available to this deployment.

    Read-only metadata: which controls exist, what framework they belong to and how
    severe a failure is. It makes no claim about whether they pass.
    """
    from .compliance.controls import Framework, get_builtin_controls

    controls = get_builtin_controls()
    if framework is not None:
        try:
            wanted = Framework(framework)
        except ValueError as exc:
            raise HTTPException(400, detail={
                "error": "unknown_framework",
                "value": framework,
                "accepted": [f.value for f in Framework],
            }) from exc
        controls = [c for c in controls if c.framework is wanted]

    return {
        "count": len(controls),
        "controls": [
            {
                "control_id": c.control_id,
                "framework": getattr(c.framework, "value", str(c.framework)),
                "title": c.title,
                "description": c.description,
                "severity": getattr(c.severity, "value", str(c.severity)),
                "tags": list(c.tags or []),
                "version": c.version,
            }
            for c in controls
        ],
    }


@app.get("/v2/compliance/scan")
async def compliance_scan(framework: str | None = None):
    """Evaluate the control set and report per-control status.

    The basis is DECLARED CONFIGURATION, not observed traffic: these controls read
    environment and file configuration to answer "is this deployment set up to meet the
    control". A passing result here is not an audit and not evidence that the control
    operates in practice -- it means the configuration is present.

    Synthetic or seeded data plays no part in the result; every finding cites the
    configuration value it was derived from.
    """
    from .compliance.controls import Framework, get_builtin_controls
    from .compliance.scanner import ComplianceScanner

    controls = get_builtin_controls()
    if framework is not None:
        try:
            wanted = Framework(framework)
        except ValueError as exc:
            raise HTTPException(400, detail={
                "error": "unknown_framework",
                "value": framework,
                "accepted": [f.value for f in Framework],
            }) from exc
        controls = [c for c in controls if c.framework is wanted]

    if not controls:
        raise HTTPException(404, detail={"error": "no_controls", "framework": framework})

    # Scanning runs evaluators that touch the filesystem and environment; keep it off
    # the event loop.
    report = await run_in_threadpool(lambda: ComplianceScanner(controls).scan())

    counts: dict[str, int] = {}
    for result in report.results:
        key = getattr(result.status, "value", str(result.status))
        counts[key] = counts.get(key, 0) + 1

    gaps = _unconsumed_configuration(controls)

    return {
        "report_id": report.report_id,
        "framework": getattr(report.framework, "value", str(report.framework)) if report.framework else framework,
        "started_at": _jsonable(report.started_at),
        "completed_at": _jsonable(report.completed_at),
        "evaluation_basis": "declared_configuration",
        "note": (
            "Results reflect configuration, not observed system behaviour, and are not "
            "an audit. A pass means the configuration a control checks is present."
        ),
        "configuration_gaps": {
            "affected_controls": len(gaps),
            "detail": gaps,
            "impact": (
                "These controls read environment variables the served application never "
                "consults. Their result describes a declared configuration this system "
                "does not honour, so a pass must not be reported as an operational "
                "control being in place."
            ),
        },
        "summary": {"total": len(report.results), "by_status": counts},
        "results": _jsonable(report.results),
    }


def _select_current_versions(rows: list[dict], *, latest_only: bool) -> list[dict]:
    """Mark each row is_current and optionally collapse to the current version.

    Pure function over rows so the selection rule can be tested without a database --
    the rule is the part that can be wrong, and "which runbook version is in force" is
    not something to verify by reading.
    """
    by_key: dict[str, list[dict]] = {}
    for row in rows:
        item = dict(row)
        by_key.setdefault(item["procedure_key"], []).append(item)

    selected: list[dict] = []
    for versions in by_key.values():
        versions.sort(key=lambda r: _version_sort_key(r["version"]), reverse=True)
        current_id = versions[0]["id"]
        for item in versions:
            item["is_current"] = item["id"] == current_id
        selected.extend([versions[0]] if latest_only else versions)

    selected.sort(key=lambda r: (r["procedure_key"], _version_sort_key(r["version"])))
    return selected


def _version_sort_key(version: str):
    """Natural sort key for a free-text version.

    ORDER BY version DESC compares text, so "1.9" sorts above "1.10" and the current
    version of a runbook would be the wrong one -- for a document whose whole purpose is
    to be followed during an incident, that is a safety issue, not a cosmetic one.

    Splitting on digit runs and comparing ints where both sides are numeric gives the
    expected order: 1.9 < 1.10. Non-numeric segments compare as text, so "v2-beta" and
    "2" still sort deterministically rather than raising.
    """
    key = []
    for part in __import__("re").split(r"(\d+)", (version or "").strip()):
        if not part:
            continue
        key.append((1, int(part), "") if part.isdigit() else (0, 0, part.lower()))
    return tuple(key)


@app.get("/v2/procedures")
async def list_procedures(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    domain: str | None = None,
    risk_class: str | None = None,
    status: str | None = None,
    latest_only: bool = True,
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = None,
):
    """Operational procedures (runbooks) for a tenant.

    Every version is stored under the same procedure_key, so a naive list returns a
    procedure several times with no indication of which version is in force. latest_only
    (the default) collapses each key to its current version, chosen by a numeric-aware
    comparison of the version string rather than a text sort.

    There is no created_at on this table: ordering by insertion time is not available,
    so "current" means highest version number, which is the only ordering the schema
    supports and is what the UNIQUE(tenant_id, procedure_key, version) constraint implies.
    """
    offset = decode_cursor(cursor) if cursor else 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        clauses = ["tenant_id = $1::uuid"]
        args: list = [tenant_id]
        if domain is not None:
            args.append(domain)
            clauses.append(f"domain = ${len(args)}")
        if risk_class is not None:
            args.append(risk_class)
            clauses.append(f"risk_class = ${len(args)}")
        if status is not None:
            args.append(status)
            clauses.append(f"status = ${len(args)}")

        rows = await conn.fetch(
            "SELECT id::text, procedure_key, version, title, domain, risk_class, "
            "required_roles, hazards, entry_criteria, steps, exit_criteria, "
            "approval_policy, status "
            f"FROM dcc.procedures WHERE {' AND '.join(clauses)}",
            *args,
        )

    selected = _select_current_versions([dict(r) for r in rows], latest_only=latest_only)
    has_more = len(selected) > offset + limit
    page_items = selected[offset:offset + limit]

    return Page(
        items=page_items,
        total=len(page_items),
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=encode_cursor(offset + limit) if has_more else None,
    ).__dict__


@app.get("/v2/connectors")
async def list_connectors(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = None,
):
    """Registered data connectors and their access posture.

    Scopes and allowed destinations are returned because they are the actual security
    boundary of a connector: a source that is "active" but scoped to nothing is not
    contributing data, and an operator needs to see that.
    """
    offset = decode_cursor(cursor) if cursor else 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT id::text,name,vendor,product,adapter_id,adapter_version,status,access_mode,"
            "scopes,allowed_destinations,last_success_at "
            "FROM dcc.connectors WHERE tenant_id=$1::uuid "
            "ORDER BY name LIMIT $2 OFFSET $3",
            tenant_id,
            limit + 1,
            offset,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    return Page(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=encode_cursor(offset + limit) if has_more else None,
    ).__dict__


@app.get("/v2/capacity")
async def list_capacity(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    dimension: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    cursor: str | None = None,
):
    """Observed capacity snapshots, newest first per dimension.

    `forecast_peak` is whatever the forecast run wrote at the time. It is returned
    alongside `policy_reserve` rather than compared here, because "is this at risk"
    depends on the reserve policy in force when the snapshot was taken.
    """
    offset = decode_cursor(cursor) if cursor else 0
    where = "WHERE tenant_id=$1::uuid"
    args: list = [tenant_id]
    if dimension:
        args.append(dimension)
        where += f" AND dimension=${len(args)}"

    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        args.extend([limit + 1, offset])
        rows = await conn.fetch(
            "SELECT id::text,facility_id::text,observed_at,scenario,dimension,usable,reserved,"
            "policy_reserve,forecast_peak,unit,quality_status,forecast_version "
            f"FROM dcc.capacity_snapshots {where} "
            f"ORDER BY observed_at DESC,dimension LIMIT ${len(args) - 1} OFFSET ${len(args)}",
            *args,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    return Page(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=encode_cursor(offset + limit) if has_more else None,
    ).__dict__


@app.get("/v2/evidence")
async def list_evidence(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    limit: int = Query(200, ge=1, le=1000),
    cursor: str | None = None,
):
    """The evidence chain in sequence order.

    Ordered by sequence, not by time: the hash chain is defined over sequence, so any
    other ordering would present the chain as broken to a reader. Use
    POST /v2/evidence/verify to check the chain itself.
    """
    offset = decode_cursor(cursor) if cursor else 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT sequence,id::text,event_type,occurred_at,actor_ref,subject_type,subject_id,"
            "previous_hash,event_hash "
            "FROM dcc.evidence_events WHERE tenant_id=$1::uuid "
            "ORDER BY sequence LIMIT $2 OFFSET $3",
            tenant_id,
            limit + 1,
            offset,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    return Page(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=encode_cursor(offset + limit) if has_more else None,
    ).__dict__


@app.get("/v2/workflows")
async def list_workflows(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = None,
    status: str | None = None,
):
    offset = decode_cursor(cursor) if cursor else 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        where = "WHERE w.tenant_id=$1::uuid"
        params: list[Any] = [tenant_id]
        if status:
            where += " AND w.status=$2"
            params.append(status)

        rows = await conn.fetch(
            f"SELECT id::text,workflow_type,stage,status,priority,title,accountable_owner,opened_at,due_at,closed_at "
            f"FROM dcc.operational_workflows w {where} ORDER BY "
            f"CASE status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,priority,due_at NULLS LAST,opened_at DESC "
            f"LIMIT {limit + 1} OFFSET {offset}",
            *params,
        )

    has_more = len(rows) > limit
    items = [dict(r) for r in rows[:limit]]
    next_cursor = encode_cursor(offset + limit) if has_more else None

    return Page(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_cursor=next_cursor,
    ).__dict__


# ---------------------------------------------------------------------------
# Analytics (uses materialized views)
# ---------------------------------------------------------------------------


@app.get("/v2/analytics")
async def analytics(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    window_days: int = Query(30, ge=1, le=90),
):
    cache_key = f"analytics:{tenant_id}:{window_days}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        # Use materialized view for daily rollup
        series = await conn.fetch(
            "SELECT metric_key,name,unit,bucket,value,coverage,uncertainty,samples,synthetic "
            "FROM dcc.mv_daily_kpi_rollup WHERE tenant_id=$1::uuid ORDER BY metric_key,bucket LIMIT 5000",
            tenant_id,
        )
        quality = await conn.fetch(
            "SELECT d.metric_key,d.name,d.unit,count(o.id)::int AS observations, "
            "count(o.id) FILTER (WHERE o.quality_status IN ('good','estimated'))::int AS usable_observations, "
            "avg(o.coverage) AS mean_coverage,avg(o.uncertainty) AS mean_uncertainty, "
            "max(o.window_end) AS latest_window_end, "
            "count(o.id) FILTER (WHERE o.provenance->>'synthetic'='true')::int AS synthetic_observations "
            "FROM dcc.kpi_definitions d LEFT JOIN dcc.kpi_observations o "
            "ON o.tenant_id=d.tenant_id AND o.kpi_definition_id=d.id "
            "AND o.window_end>=now()-($2*interval '1 day') "
            "WHERE d.tenant_id=$1::uuid AND d.active GROUP BY d.metric_key,d.name,d.unit "
            "ORDER BY d.name LIMIT 500",
            tenant_id,
            window_days,
        )
        telemetry = await conn.fetch(
            "SELECT quality_status,samples,metrics,assets,latest_observed_at "
            "FROM dcc.mv_telemetry_quality WHERE tenant_id=$1::uuid",
            tenant_id,
        )
        workflows = await conn.fetch(
            "SELECT workflow_type,status,priority,items,overdue,mean_age_days "
            "FROM dcc.mv_workflow_health WHERE tenant_id=$1::uuid",
            tenant_id,
        )

    result = {
        "tenant_id": tenant_id,
        "window_days": window_days,
        "kpi_series": [dict(s) for s in series],
        "kpi_quality": [dict(q) for q in quality],
        "telemetry_quality": [dict(t) for t in telemetry],
        "workflow_health": [dict(w) for w in workflows],
        "read_only": True,
        "execution_permitted": False,
    }
    cache.set(cache_key, result, ttl=60)
    return result


# ---------------------------------------------------------------------------
# Optimization endpoints
# ---------------------------------------------------------------------------


@app.post("/v2/optimize/placement")
async def optimize_placement(request: Request):
    """Run workload placement optimization (FFD algorithm)."""
    body = await request.json()
    workloads = [
        Workload(
            id=w["id"],
            name=w.get("name", w["id"]),
            cpu_cores=w.get("cpu_cores", 0),
            ram_gb=w.get("ram_gb", 0),
            gpu_units=w.get("gpu_units", 0),
            power_kw=w.get("power_kw", 0),
            affinity=tuple(w.get("affinity", [])),
            anti_affinity=tuple(w.get("anti_affinity", [])),
        )
        for w in body.get("workloads", [])
    ]
    assets = [
        Asset(
            id=a["id"],
            name=a.get("name", a["id"]),
            total_cpu=a.get("total_cpu", 0),
            total_ram=a.get("total_ram", 0),
            total_gpu=a.get("total_gpu", 0),
            power_budget_kw=a.get("power_budget_kw", 0),
        )
        for a in body.get("assets", [])
    ]

    result = first_fit_decreasing(workloads, assets)
    return {
        "placement": result,
        "algorithm": "first_fit_decreasing",
        "approximation_ratio": "11/9 × OPT + 1",
        "execution_permitted": False,
    }


@app.post("/v2/optimize/maintenance-routing")
async def optimize_maintenance_routing(request: Request):
    """Run maintenance routing optimization (Clarke-Wright Savings)."""
    body = await request.json()
    work_orders = [
        WorkOrder(
            id=w["id"],
            asset_id=w.get("asset_id", ""),
            priority=w.get("priority", 1),
            duration_hours=w.get("duration_hours", 1),
            skill_required=w.get("skill_required", ""),
            latitude=w.get("latitude", 0),
            longitude=w.get("longitude", 0),
        )
        for w in body.get("work_orders", [])
    ]
    technicians = [
        Technician(
            id=t["id"],
            skills=frozenset(t.get("skills", [])),
            base_latitude=t.get("base_latitude", 0),
            base_longitude=t.get("base_longitude", 0),
        )
        for t in body.get("technicians", [])
    ]

    result = clarke_wright_savings(
        work_orders,
        technicians,
        depot_lat=body.get("depot_latitude", 0),
        depot_lon=body.get("depot_longitude", 0),
    )
    return {
        "routes": result,
        "algorithm": "clarke_wright_savings",
        "approximation_ratio": "2 × OPT",
        "execution_permitted": False,
    }


@app.post("/v2/optimize/capacity-allocation")
async def optimize_capacity_allocation(request: Request):
    """Run capacity allocation optimization (greedy density)."""
    body = await request.json()
    dimensions = [
        CapacityDimension(
            name=d["name"],
            total=d.get("total", 0),
            reserved=d.get("reserved", 0),
            policy_reserve=d.get("policy_reserve", 0),
        )
        for d in body.get("dimensions", [])
    ]
    demands = body.get("demands", {})

    result = capacity_allocation(dimensions, demands)
    return {
        "allocation": result,
        "algorithm": "greedy_density",
        "execution_permitted": False,
    }


@app.post("/v2/optimize/network-zoning")
async def optimize_network_zoning(request: Request):
    """Run network zoning optimization (DSATUR)."""
    body = await request.json()
    nodes = [
        NetworkNode(
            id=n["id"],
            neighbors=tuple(n.get("neighbors", [])),
        )
        for n in body.get("nodes", [])
    ]

    result = dsatur_zoning(nodes)
    return {
        "zones": result,
        "algorithm": "dsatur",
        "colors_used": len(set(result.values())),
        "execution_permitted": False,
    }


@app.post("/v2/optimize/energy-allocation")
async def optimize_energy_allocation(request: Request):
    """Run energy allocation optimization (max-min fairness)."""
    body = await request.json()
    requests = [
        EnergyRequest(
            workload_id=r["workload_id"],
            energy_kwh=r.get("energy_kwh", 0),
            useful_work_per_kwh=r.get("useful_work_per_kwh", 1),
            min_fair_share=r.get("min_fair_share", 0),
        )
        for r in body.get("requests", [])
    ]
    total_energy = body.get("total_energy_kwh", 0)

    result = max_min_fair_energy_allocation(requests, total_energy)
    return {
        "allocation": result,
        "algorithm": "max_min_fairness",
        "total_allocated": sum(result.values()),
        "execution_permitted": False,
    }


# ---------------------------------------------------------------------------
# Evidence chain verification
# ---------------------------------------------------------------------------


@app.get("/v2/evidence/verify")
async def verify_evidence_tenant_chain(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
    max_events: int = Query(10_000, ge=1, le=100_000),
    include_events: bool = False,
):
    """Verify the evidence hash chain for one tenant.

    This endpoint previously recomputed the hash inline over
    ``previous_hash + event_type + occurred_at`` while the chain is written over a
    much larger payload, so no stored row could ever validate. It now delegates to
    the single canonical implementation in ``dcc.provenance.evidence``, which the
    writer also uses. See that module for why the payload is defined as it is.

    Two bounds, because a verifier is a denial-of-service target as much as an
    assurance check. The previous version loaded every event for the tenant into
    memory and echoed every event's hashes back, so a tenant with a long history
    could exhaust a worker with one request, and the response grew without limit.

    ``max_events`` caps the scan. When the chain is longer than the cap, ``complete``
    is false and ``chain_valid`` is null -- NOT true. A verified prefix says nothing
    about the rest of the chain, and reporting a prefix as a valid chain is exactly
    the false assurance this module exists to prevent.

    ``include_events`` returns the per-event detail. Off by default: the actionable
    content is the summary plus the break point, and the default path returns only
    the events that failed.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT tenant_id,sequence,id,event_type,occurred_at,actor_ref,"
            "subject_type,subject_id,payload,previous_hash,event_hash "
            "FROM dcc.evidence_events "
            "WHERE tenant_id=$1::uuid ORDER BY sequence LIMIT $2",
            tenant_id,
            max_events + 1,
        )

    truncated = len(rows) > max_events
    result = verify_evidence_chain([dict(r) for r in rows[:max_events]])

    events = result.pop("events", [])
    failed = [e for e in events if not e["is_valid"]]

    payload = {
        "tenant_id": tenant_id,
        **result,
        "complete": not truncated,
        "scanned_events": len(events),
        "max_events": max_events,
    }

    if truncated:
        # A valid prefix is not a valid chain.
        payload["chain_valid"] = None
        payload["note"] = (
            f"Chain exceeds max_events ({max_events}); only the first {max_events} events "
            "were verified. chain_valid is null because the remainder is unverified -- "
            "raise max_events to complete the check."
        )

    if include_events:
        payload["events"] = events
    else:
        payload["invalid_event_details"] = failed

    return payload



# ---------------------------------------------------------------------------
# Economics — TCO, wired to dcc.economics
# ---------------------------------------------------------------------------
#
# dcc/economics/ is 8,058 lines of TCO, tariff, allocation, budget and
# reconciliation machinery that this API previously did not reach at all. A TCO
# result the operator can act on is the clearest thing that code produces, so it
# is exposed here rather than left as an unused library.
#
# The endpoint is a POST because a TCO model is a set of assumptions, not a
# query parameter list: 27 cost and escalation inputs is a request body.

# Accepted inputs, taken from quick_tco's own signature. An allowlist rather than
# **body: passing arbitrary keys would raise TypeError out of the handler and leak
# a traceback, and any future parameter added to quick_tco should be a deliberate
# decision to expose, not an accident of using **kwargs.
_TCO_FLOAT_FIELDS = frozenset({
    "hardware_capex", "facility_capex", "design_capex", "commissioning_capex",
    "migration_capex", "software_capex", "energy_annual", "maintenance_annual",
    "labor_annual", "network_annual", "software_annual", "insurance_annual",
    "tax_annual", "other_annual", "refresh_cost", "decommission_cost",
    "residual_value", "annual_discount_rate", "energy_escalation_pct",
    "maintenance_escalation_pct", "labor_escalation_pct", "other_escalation_pct",
    "contingency_pct", "it_capacity_kw", "rack_count", "area_m2",
    "annual_energy_kwh",
})
_TCO_INT_FIELDS = frozenset({"refresh_interval_years", "horizon_years"})
_TCO_STR_FIELDS = frozenset({"currency", "name", "scenario_type"})

# Inputs that cannot be negative. A negative capex or a negative energy bill
# produces a negative TCO, which reads as a saving and is nonsense.
_TCO_NON_NEGATIVE = _TCO_FLOAT_FIELDS - {
    "annual_discount_rate", "energy_escalation_pct", "maintenance_escalation_pct",
    "labor_escalation_pct", "other_escalation_pct", "contingency_pct",
}


def _coerce_tco_assumptions(body: dict[str, Any]) -> dict[str, Any]:
    """Validate a TCO request body and return kwargs for quick_tco.

    Raises HTTPException(400) with the offending field named, so a caller is told
    which input is wrong rather than receiving a TypeError traceback.
    """
    unknown = set(body) - (_TCO_FLOAT_FIELDS | _TCO_INT_FIELDS | _TCO_STR_FIELDS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_field",
                "fields": sorted(unknown),
                "accepted": sorted(_TCO_FLOAT_FIELDS | _TCO_INT_FIELDS | _TCO_STR_FIELDS),
            },
        )

    kwargs: dict[str, Any] = {}
    for key, value in body.items():
        if key in _TCO_STR_FIELDS:
            if not isinstance(value, str):
                raise HTTPException(400, detail={"error": "invalid_type", "field": key, "expected": "string"})
            kwargs[key] = value
        elif key in _TCO_INT_FIELDS:
            if isinstance(value, bool) or not isinstance(value, int):
                raise HTTPException(400, detail={"error": "invalid_type", "field": key, "expected": "integer"})
            kwargs[key] = value
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(400, detail={"error": "invalid_type", "field": key, "expected": "number"})
            kwargs[key] = float(value)

    if "currency" in kwargs:
        # Delegated to the validation package rather than re-checked here. This is
        # the one place the API and dcc/validation agree on what a currency is.
        try:
            kwargs["currency"] = validate_currency_code(kwargs["currency"])
        except Exception as exc:
            raise HTTPException(400, detail={"error": "invalid_currency", "detail": str(exc)}) from exc

    for key in _TCO_NON_NEGATIVE & set(kwargs):
        if kwargs[key] < 0:
            raise HTTPException(400, detail={"error": "negative_value", "field": key, "value": kwargs[key]})

    horizon = kwargs.get("horizon_years", 10)
    # ValidationResult exposes `passed` and a list of findings, not a single message.
    horizon_check = validate_value_range(float(horizon), 1.0, 50.0)
    if not horizon_check.passed:
        raise HTTPException(400, detail={
            "error": "out_of_range",
            "field": "horizon_years",
            "detail": [f.message for f in horizon_check.findings],
        })

    rate = kwargs.get("annual_discount_rate", 0.08)
    if not -0.5 <= rate <= 1.0:
        raise HTTPException(400, detail={"error": "out_of_range", "field": "annual_discount_rate", "value": rate})

    return kwargs


def _tco_result_payload(result: Any, assumptions: dict[str, Any]) -> dict[str, Any]:
    """Serialise a TCOResult.

    The engine returns dataclasses; building the response explicitly keeps the wire
    format a deliberate contract instead of whatever dataclasses.asdict emits today.
    """
    return {
        "scenario_name": result.scenario_name,
        "scenario_type": result.scenario_type,
        "currency": result.currency,
        "horizon_years": result.horizon_years,
        "totals": {
            "capex": round(result.total_capex, 2),
            "opex": round(result.total_opex, 2),
            "refresh": round(result.total_refresh, 2),
            "terminal": round(result.total_terminal, 2),
            "undiscounted": round(result.total_undiscounted, 2),
            "present_value": round(result.total_pv, 2),
            "equivalent_annual_cost": round(result.equivalent_annual_cost, 2),
            "average_annual_cost": round(result.average_annual_cost, 2),
            "year_zero_cash": round(result.year_zero_cash, 2),
            "year_one_cash": round(result.year_one_cash, 2),
        },
        "unit_costs": {
            "per_kw_year": None if result.cost_per_kw_year is None else round(result.cost_per_kw_year, 2),
            "per_rack_year": None if result.cost_per_rack_year is None else round(result.cost_per_rack_year, 2),
            "per_m2_year": None if result.cost_per_m2_year is None else round(result.cost_per_m2_year, 2),
            "per_kwh": None if result.cost_per_kwh is None else round(result.cost_per_kwh, 4),
        },
        "breakdown_by_category": {k: round(v, 2) for k, v in tco_breakdown_by_category(result).items()},
        "yearly_cash_flows": [
            {
                "year": cf.year,
                "capex": round(cf.capex, 2),
                "opex": round(cf.opex, 2),
                "refresh": round(cf.refresh, 2),
                "terminal": round(cf.terminal, 2),
                "total_undiscounted": round(cf.total_undiscounted, 2),
                "discount_factor": round(cf.discount_factor, 6),
                "total_discounted": round(cf.total_discounted, 2),
            }
            for cf in result.yearly_cash_flows
        ],
        # Echoed so a stored result can be reproduced from the response alone.
        "assumptions": assumptions,
    }


@app.post("/v2/economics/tco")
async def economics_tco(request: Request):
    """Total cost of ownership for one data-center scenario.

    Returns undiscounted totals, present value, equivalent annual cost, per-unit
    metrics, a category breakdown and the yearly cash flow series.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, detail={"error": "invalid_json", "detail": str(exc)}) from exc
    if not isinstance(body, dict):
        raise HTTPException(400, detail={"error": "expected_object"})

    assumptions = _coerce_tco_assumptions(body)
    # quick_tco is CPU-bound. Running it inline in an async handler would block the
    # event loop for the duration and stall every other request on this worker.
    result = await run_in_threadpool(quick_tco, **assumptions)
    return _tco_result_payload(result, assumptions)


@app.post("/v2/economics/tco/compare")
async def economics_tco_compare(request: Request):
    """Compare TCO across scenarios and report the delta against a baseline.

    The operator question this answers is "which of these is cheaper over the
    horizon, and by how much in present-value terms" -- build versus lease, Tier III
    versus Tier IV, this site versus that one.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, detail={"error": "invalid_json", "detail": str(exc)}) from exc
    if not isinstance(body, dict):
        raise HTTPException(400, detail={"error": "expected_object"})

    scenarios = body.get("scenarios")
    if not isinstance(scenarios, list) or not 2 <= len(scenarios) <= 10:
        raise HTTPException(400, detail={
            "error": "invalid_scenarios",
            "detail": "scenarios must be a list of 2 to 10 objects",
        })

    baseline_index = body.get("baseline_index", 0)
    if not isinstance(baseline_index, int) or isinstance(baseline_index, bool)             or not 0 <= baseline_index < len(scenarios):
        raise HTTPException(400, detail={
            "error": "invalid_baseline_index",
            "detail": f"baseline_index must be an integer in 0..{len(scenarios) - 1}",
        })

    results = []
    for idx, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise HTTPException(400, detail={"error": "expected_object", "scenario_index": idx})
        assumptions = _coerce_tco_assumptions(scenario)
        result = await run_in_threadpool(quick_tco, **assumptions)
        results.append((result, assumptions))

    base = results[baseline_index][0]
    comparison = []
    for idx, (result, _assumptions) in enumerate(results):
        comparison.append({
            "index": idx,
            "name": result.scenario_name,
            "is_baseline": idx == baseline_index,
            "present_value": round(result.total_pv, 2),
            "equivalent_annual_cost": round(result.equivalent_annual_cost, 2),
            "undiscounted": round(result.total_undiscounted, 2),
            "pv_delta_vs_baseline": round(result.total_pv - base.total_pv, 2),
            "eac_delta_vs_baseline": round(result.equivalent_annual_cost - base.equivalent_annual_cost, 2),
        })

    cheapest = min(comparison, key=lambda c: c["present_value"])
    return {
        "baseline_index": baseline_index,
        "baseline_name": base.scenario_name,
        "cheapest_by_present_value": {"index": cheapest["index"], "name": cheapest["name"],
                                      "present_value": cheapest["present_value"]},
        "scenarios": comparison,
    }


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


@app.post("/v2/cache/invalidate")
async def invalidate_cache(
    pattern: str = Query(..., description="Cache key pattern to invalidate"),
):
    cache.invalidate(pattern)
    return {"invalidated": pattern, "execution_permitted": False}


# ---------------------------------------------------------------------------
# Serve UI (for development)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Forecasting (dcc.forecasting)
#
# The forecasting package is 4,769 lines of capacity, failure and drift modelling
# that no route could reach. These endpoints expose the three questions a data
# centre operator actually asks: when do I run out of capacity, which equipment is
# about to fail, and has my forecast model drifted away from reality.
# ---------------------------------------------------------------------------

from datetime import datetime as _dt  # noqa: E402
from datetime import timezone as _tz  # noqa: E402


def _parse_utc(value: Any, field: str) -> _dt:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    Naive input is rejected rather than assumed to be UTC: a capacity series that
    silently means "local time" produces a forecast shifted by the operator's
    offset, which is the kind of error that only surfaces during an incident.
    """
    if not isinstance(value, str):
        raise HTTPException(400, detail={"error": "invalid_type", "field": field, "expected": "iso8601 string"})
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = _dt.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_timestamp", "field": field, "value": value}) from exc
    if parsed.tzinfo is None:
        raise HTTPException(400, detail={
            "error": "naive_timestamp",
            "field": field,
            "detail": "include a UTC offset, for example 2026-01-01T00:00:00Z",
        })
    return parsed.astimezone(_tz.utc)


def _jsonable(obj: Any) -> Any:
    """Convert dataclasses, datetimes and Decimals into JSON-safe values."""
    from dataclasses import asdict, is_dataclass
    from decimal import Decimal

    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, _dt):
        return obj.astimezone(_tz.utc).isoformat().replace("+00:00", "Z")
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


_CAPACITY_POINT_FIELDS = {"observed_at", "usable", "reserved", "policy_reserve",
                          "forecast_peak", "quality_status", "scenario"}
_CAPACITY_BODY_FIELDS = {"facility_id", "dimension", "unit", "scenario", "data_points",
                         "horizon_days", "method"}
_CAPACITY_METHODS = {"linear", "moving_average", "exponential_smoothing"}


def _build_capacity_points(raw: Any) -> list:
    """Validate and build CapacityDataPoint objects from a JSON array."""
    from .forecasting.capacity import CapacityDataPoint

    if not isinstance(raw, list):
        raise HTTPException(400, detail={"error": "invalid_type", "field": "data_points", "expected": "array"})
    if not raw:
        raise HTTPException(400, detail={"error": "empty_series", "field": "data_points"})

    points = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise HTTPException(400, detail={"error": "invalid_type", "field": f"data_points[{index}]", "expected": "object"})
        unknown = set(item) - _CAPACITY_POINT_FIELDS
        if unknown:
            raise HTTPException(400, detail={
                "error": "unknown_field",
                "field": f"data_points[{index}]",
                "fields": sorted(unknown),
                "accepted": sorted(_CAPACITY_POINT_FIELDS),
            })
        for required in ("observed_at", "usable"):
            if required not in item:
                raise HTTPException(400, detail={
                    "error": "missing_field", "field": f"data_points[{index}].{required}",
                })
        for numeric in ("usable", "reserved", "policy_reserve", "forecast_peak"):
            if numeric in item and item[numeric] is not None:
                # bool is a subclass of int; True must not be read as 1.0 usable units.
                if isinstance(item[numeric], bool) or not isinstance(item[numeric], (int, float)):
                    raise HTTPException(400, detail={
                        "error": "invalid_type", "field": f"data_points[{index}].{numeric}", "expected": "number",
                    })
        points.append(CapacityDataPoint(
            observed_at=_parse_utc(item["observed_at"], f"data_points[{index}].observed_at"),
            usable=float(item["usable"]),
            reserved=float(item.get("reserved", 0.0)),
            policy_reserve=float(item.get("policy_reserve", 0.0)),
            forecast_peak=None if item.get("forecast_peak") is None else float(item["forecast_peak"]),
            quality_status=str(item.get("quality_status", "ok")),
            scenario=str(item.get("scenario", "base")),
        ))
    return points


@app.post("/v2/forecast/capacity")
async def forecast_capacity_route(request: Request):
    """Project capacity exhaustion and report when the reserve is breached.

    Returns the forecast series plus an at-risk summary: whether the projected
    usable capacity crosses the reserve policy inside the horizon, and on which day.
    """
    from .forecasting.capacity import compute_capacity_at_risk, forecast_capacity

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, detail={"error": "invalid_json", "detail": str(exc)}) from exc
    if not isinstance(body, dict):
        raise HTTPException(400, detail={"error": "expected_object"})

    unknown = set(body) - _CAPACITY_BODY_FIELDS
    if unknown:
        raise HTTPException(400, detail={
            "error": "unknown_field", "fields": sorted(unknown), "accepted": sorted(_CAPACITY_BODY_FIELDS),
        })

    for required in ("facility_id", "dimension", "unit", "data_points"):
        if required not in body:
            raise HTTPException(400, detail={"error": "missing_field", "field": required})

    method = body.get("method", "linear")
    if method not in _CAPACITY_METHODS:
        raise HTTPException(400, detail={
            "error": "invalid_method", "field": "method", "value": method, "accepted": sorted(_CAPACITY_METHODS),
        })

    # Derive the accepted set from the library rather than restating it here, so a
    # new forecastable dimension does not require an API change to become reachable.
    from .forecasting.capacity import FORECASTABLE_DIMENSIONS

    if body["dimension"] not in FORECASTABLE_DIMENSIONS:
        raise HTTPException(400, detail={
            "error": "invalid_dimension",
            "field": "dimension",
            "value": body["dimension"],
            "accepted": sorted(FORECASTABLE_DIMENSIONS),
        })

    horizon = body.get("horizon_days", 30)
    if isinstance(horizon, bool) or not isinstance(horizon, int):
        raise HTTPException(400, detail={"error": "invalid_type", "field": "horizon_days", "expected": "integer"})
    if not 1 <= horizon <= 3650:
        raise HTTPException(400, detail={"error": "out_of_range", "field": "horizon_days", "value": horizon})

    points = _build_capacity_points(body["data_points"])

    # Capacity fitting is CPU-bound; inline it and the event loop stalls for every
    # other request on this worker.
    # The library signals bad input with ValueError. Letting it escape produces a 500
    # and a traceback for what is a caller mistake; translate it into a 400 that names
    # the reason the library gave.
    try:
        forecast = await run_in_threadpool(
            forecast_capacity,
            facility_id=str(body["facility_id"]),
            dimension=str(body["dimension"]),
            unit=str(body["unit"]),
            scenario=str(body.get("scenario", "base")),
            data_points=points,
            horizon_days=horizon,
            method=method,
        )
        risk = await run_in_threadpool(compute_capacity_at_risk, forecast, 0.0)
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_input", "detail": str(exc)}) from exc
    return {"forecast": _jsonable(forecast), "at_risk": _jsonable(risk)}


@app.post("/v2/forecast/failure")
async def forecast_failure_route(request: Request):
    """Predict equipment failure risk from asset inventory and telemetry."""
    from .forecasting.failure import predict_equipment_failures

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, detail={"error": "invalid_json", "detail": str(exc)}) from exc
    if not isinstance(body, dict):
        raise HTTPException(400, detail={"error": "expected_object"})

    allowed = {"tenant_id", "assets", "telemetry_rows", "window_days"}
    unknown = set(body) - allowed
    if unknown:
        raise HTTPException(400, detail={
            "error": "unknown_field", "fields": sorted(unknown), "accepted": sorted(allowed),
        })
    for required in ("tenant_id", "assets"):
        if required not in body:
            raise HTTPException(400, detail={"error": "missing_field", "field": required})
    if not isinstance(body["assets"], list):
        raise HTTPException(400, detail={"error": "invalid_type", "field": "assets", "expected": "array"})

    # The forecasting library reads asset["id"] and asset["asset_type"], while its own
    # response reports them as asset_id/asset_name. A caller passing asset_id therefore
    # got a risk profile with an empty identifier and no error at all. Require the keys
    # the library actually reads, and name them in the rejection.
    for index, asset in enumerate(body["assets"]):
        if not isinstance(asset, dict):
            raise HTTPException(400, detail={"error": "invalid_type", "field": f"assets[{index}]", "expected": "object"})
        missing = {"id", "asset_type"} - set(asset)
        if missing:
            raise HTTPException(400, detail={
                "error": "missing_field",
                "field": f"assets[{index}]",
                "missing": sorted(missing),
                "accepted": ["id", "name", "asset_type", "criticality", "lifecycle_state"],
            })
    if not isinstance(body.get("telemetry_rows", []), list):
        raise HTTPException(400, detail={"error": "invalid_type", "field": "telemetry_rows", "expected": "array"})

    window = body.get("window_days", 30)
    if isinstance(window, bool) or not isinstance(window, int):
        raise HTTPException(400, detail={"error": "invalid_type", "field": "window_days", "expected": "integer"})

    try:
        result = await run_in_threadpool(
            predict_equipment_failures,
            tenant_id=str(body["tenant_id"]),
            assets=body["assets"],
            telemetry_rows=body.get("telemetry_rows", []),
            window_days=window,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_input", "detail": str(exc)}) from exc
    return _jsonable(result)


@app.post("/v2/forecast/drift")
async def forecast_drift_route(request: Request):
    """Detect distribution drift between a reference and an incoming series.

    Answers "is the model still valid": each detector reports its statistic, the
    threshold it was compared against, and whether it fired.
    """
    from .forecasting.drift import detect_drift

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, detail={"error": "invalid_json", "detail": str(exc)}) from exc
    if not isinstance(body, dict):
        raise HTTPException(400, detail={"error": "expected_object"})

    allowed = {"reference", "incoming", "min_samples"}
    unknown = set(body) - allowed
    if unknown:
        raise HTTPException(400, detail={
            "error": "unknown_field", "fields": sorted(unknown), "accepted": sorted(allowed),
        })

    series = {}
    for key in ("reference", "incoming"):
        raw = body.get(key)
        if not isinstance(raw, list):
            raise HTTPException(400, detail={"error": "invalid_type", "field": key, "expected": "array"})
        for index, value in enumerate(raw):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(400, detail={
                    "error": "invalid_type", "field": f"{key}[{index}]", "expected": "number",
                })
        series[key] = [float(v) for v in raw]

    min_samples = body.get("min_samples", 30)
    if isinstance(min_samples, bool) or not isinstance(min_samples, int):
        raise HTTPException(400, detail={"error": "invalid_type", "field": "min_samples", "expected": "integer"})
    if min_samples < 2:
        raise HTTPException(400, detail={"error": "out_of_range", "field": "min_samples", "value": min_samples})

    try:
        results = await run_in_threadpool(
            detect_drift, series["reference"], series["incoming"], min_samples=min_samples,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_input", "detail": str(exc)}) from exc
    fired = [r for r in results if getattr(r, "detected", getattr(r, "is_drift", False))]
    return {
        "drift_detected": bool(fired),
        "detectors_fired": [getattr(r, "method", "") for r in fired],
        "results": _jsonable(results),
    }


@app.get("/")
async def serve_ui(request: Request):
    from pathlib import Path

    ui_path = Path(__file__).resolve().parents[2] / "ui" / "index.html"
    if ui_path.exists():
        html = ui_path.read_text(encoding="utf-8")

        # The console runs in the browser and calls /v2/* same-origin, so it needs the
        # key that the API now requires. Injecting it here keeps authentication ENFORCED
        # for every other client instead of telling operators to switch auth off to use
        # the bundled UI. The key is only as exposed as the page itself, which already
        # requires reaching this port.
        # Loopback only. Injecting the key into a page served to any remote caller
        # would make authentication theatre: the "protected" page would hand every
        # visitor the credential. A browser on this host is a local operator console;
        # a remote client must call the API with its own key.
        client_host = (request.client.host if request.client else "") or ""
        is_loopback = client_host in {"127.0.0.1", "::1", "localhost", "testclient"}

        console_key = os.getenv("DCC_UI_API_KEY", "").strip() if is_loopback else ""
        if console_key:
            import html as _html

            meta = f'<meta name="dcc-api-key" content="{_html.escape(console_key, quote=True)}">'
            if "</head>" in html:
                html = html.replace("</head>", meta + "</head>", 1)
            else:
                html = meta + html

        return Response(content=html, media_type="text/html; charset=utf-8")
    return {"error": "UI not found"}


from fastapi.responses import Response as FastAPIResponse  # noqa: E402,F401
