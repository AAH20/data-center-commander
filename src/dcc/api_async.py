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
):
    """Verify the evidence hash chain for one tenant.

    This endpoint previously recomputed the hash inline over
    ``previous_hash + event_type + occurred_at`` while the chain is written over a
    much larger payload, so no stored row could ever validate. It now delegates to
    the single canonical implementation in ``dcc.provenance.evidence``, which the
    writer also uses. See that module for why the payload is defined as it is.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

        rows = await conn.fetch(
            "SELECT tenant_id,sequence,id,event_type,occurred_at,actor_ref,"
            "subject_type,subject_id,payload,previous_hash,event_hash "
            "FROM dcc.evidence_events "
            "WHERE tenant_id=$1::uuid ORDER BY sequence",
            tenant_id,
        )

    result = verify_evidence_chain([dict(r) for r in rows])
    return {"tenant_id": tenant_id, **result}



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


@app.get("/")
async def serve_ui():
    from pathlib import Path

    ui_path = Path(__file__).resolve().parents[2] / "ui" / "index.html"
    if ui_path.exists():
        return Response(
            content=ui_path.read_bytes(),
            media_type="text/html; charset=utf-8",
        )
    return {"error": "UI not found"}


from fastapi.responses import Response as FastAPIResponse  # noqa: E402,F401
