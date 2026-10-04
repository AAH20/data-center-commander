"""Async API layer for Data Center Commander.

Replaces the monolithic ThreadingHTTPServer with FastAPI + Uvicorn.
Adds pagination, caching, rate limiting, and optimization endpoints.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .optimization_kernels import (
    Asset,
    CapacityDimension,
    EnergyRequest,
    NetworkNode,
    Technician,
    WorkOrder,
    Workload,
    capacity_allocation,
    clarke_wright_savings,
    dsatur_zoning,
    first_fit_decreasing,
    max_min_fair_energy_allocation,
)


# ---------------------------------------------------------------------------
# Configuration
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
    except Exception:
        raise ValueError("invalid cursor")


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
        except ImportError:
            raise HTTPException(status_code=503, detail="postgres_extra_required")
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
        except Exception:
            await _pool.close()
            raise HTTPException(status_code=503, detail="database_unavailable")
    return _pool


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    try:
        await get_pool()
    except Exception:
        pass
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
        async with pool.connection() as conn:
            async with conn.transaction():
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
    async with pool.connection() as conn:
        async with conn.transaction():
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
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            rows = await conn.fetch(
                "SELECT a.external_id,a.asset_type,a.name,a.manufacturer,a.model,a.lifecycle_state,a.criticality,a.observed_at,f.name AS facility_name,s.name AS space_name "
                "FROM dcc.assets a LEFT JOIN dcc.spaces s ON s.tenant_id=a.tenant_id AND s.id=a.space_id "
                "LEFT JOIN dcc.facilities f ON f.tenant_id=s.tenant_id AND f.id=s.facility_id "
                "WHERE a.tenant_id=$1::uuid ORDER BY a.lifecycle_state,a.name LIMIT $2 OFFSET $3",
                tenant_id, limit + 1, offset,
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
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            rows = await conn.fetch(
                "SELECT f.id::text,f.code,f.name,f.facility_type,f.status,s.code AS site_code,s.name AS site_name "
                "FROM dcc.facilities f JOIN dcc.sites s ON s.tenant_id=f.tenant_id AND s.id=f.site_id "
                "WHERE f.tenant_id=$1::uuid ORDER BY s.name,f.name LIMIT $2 OFFSET $3",
                tenant_id, limit + 1, offset,
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
    async with pool.connection() as conn:
        async with conn.transaction():
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
    async with pool.connection() as conn:
        async with conn.transaction():
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
                tenant_id, window_days,
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
        work_orders, technicians,
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
async def verify_evidence_chain(
    tenant_id: str = Query(..., regex=r"^[0-9a-fA-F-]{36}$"),
):
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            rows = await conn.fetch(
                "SELECT sequence,event_type,occurred_at,event_hash FROM dcc.evidence_events "
                "WHERE tenant_id=$1::uuid ORDER BY sequence",
                tenant_id,
            )

    # Verify hash chain
    previous_hash = ""
    results = []
    for row in rows:
        # Recompute hash (simplified — full implementation would use dcc.verify_evidence_chain)
        import hashlib
        computed = hashlib.sha256(
            f"{previous_hash}{row['event_type']}{row['occurred_at']}".encode()
        ).hexdigest()
        results.append({
            "sequence": row["sequence"],
            "event_type": row["event_type"],
            "occurred_at": row["occurred_at"],
            "is_valid": computed == row["event_hash"],
        })
        previous_hash = row["event_hash"]

    return {
        "tenant_id": tenant_id,
        "total_events": len(results),
        "valid_events": sum(1 for r in results if r["is_valid"]),
        "invalid_events": sum(1 for r in results if not r["is_valid"]),
        "chain_valid": all(r["is_valid"] for r in results),
        "events": results,
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


from fastapi.responses import Response  # noqa: E402
