"""Domain service layer for Data Center Commander.

Each service owns one domain concept and provides a clean API for the
async layer. Services are stateless — all state lives in PostgreSQL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Database pool (shared with api_async)
# ---------------------------------------------------------------------------

_pool: Any = None


async def get_db_pool():
    global _pool
    if _pool is None:
        dsn = os.environ.get("DCC_DATABASE_URL", "")
        if not dsn:
            raise RuntimeError("database_not_configured")
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        _pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=2,
            max_size=20,
            timeout=5,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
        )
        await _pool.wait(timeout=5)
    return _pool


# ---------------------------------------------------------------------------
# Facility Service
# ---------------------------------------------------------------------------


@dataclass
class FacilitySummary:
    id: str
    code: str
    name: str
    facility_type: str
    status: str
    site_name: str
    asset_count: int = 0
    open_workflows: int = 0


class FacilityService:
    """Operations on facilities and their hierarchy."""

    @staticmethod
    async def list_facilities(
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)
            rows = await conn.fetch(
                "SELECT f.id::text,f.code,f.name,f.facility_type,f.status,"
                "s.name AS site_name,"
                "(SELECT count(*)::int FROM dcc.assets a WHERE a.tenant_id=f.tenant_id AND a.space_id IN "
                "(SELECT id FROM dcc.spaces sp WHERE sp.tenant_id=f.tenant_id AND sp.facility_id=f.id)) AS asset_count,"
                "(SELECT count(*)::int FROM dcc.operational_workflows w WHERE w.tenant_id=f.tenant_id AND w.facility_id=f.id AND w.status NOT IN ('closed','cancelled')) AS open_workflows "
                "FROM dcc.facilities f JOIN dcc.sites s ON s.tenant_id=f.tenant_id AND s.id=f.site_id "
                "WHERE f.tenant_id=$1::uuid ORDER BY s.name,f.name LIMIT $2 OFFSET $3",
                tenant_id,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    @staticmethod
    async def get_facility_detail(tenant_id: str, facility_id: str) -> dict[str, Any] | None:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)
            row = await conn.fetchrow(
                "SELECT f.*,s.name AS site_name,s.country_code,s.timezone "
                "FROM dcc.facilities f JOIN dcc.sites s ON s.tenant_id=f.tenant_id AND s.id=f.site_id "
                "WHERE f.tenant_id=$1::uuid AND f.id=$2::uuid",
                tenant_id,
                facility_id,
            )
            return dict(row) if row else None


# ---------------------------------------------------------------------------
# Asset Service
# ---------------------------------------------------------------------------


@dataclass
class AssetFilter:
    lifecycle_state: str | None = None
    asset_type: str | None = None
    criticality: str | None = None
    facility_id: str | None = None


class AssetService:
    """Operations on assets and their relationships."""

    @staticmethod
    async def list_assets(
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        filters: AssetFilter | None = None,
    ) -> list[dict[str, Any]]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            where = "WHERE a.tenant_id=$1::uuid"
            params: list[Any] = [tenant_id]
            pidx = 2

            if filters:
                if filters.lifecycle_state:
                    where += f" AND a.lifecycle_state=${pidx}"
                    params.append(filters.lifecycle_state)
                    pidx += 1
                if filters.asset_type:
                    where += f" AND a.asset_type=${pidx}"
                    params.append(filters.asset_type)
                    pidx += 1
                if filters.criticality:
                    where += f" AND a.criticality=${pidx}"
                    params.append(filters.criticality)
                    pidx += 1
                if filters.facility_id:
                    where += f" AND a.space_id IN (SELECT id FROM dcc.spaces WHERE facility_id=${pidx}::uuid)"
                    params.append(filters.facility_id)
                    pidx += 1

            rows = await conn.fetch(
                f"SELECT a.external_id,a.asset_type,a.name,a.manufacturer,a.model,"
                f"a.lifecycle_state,a.criticality,a.observed_at,"
                f"f.name AS facility_name,s.name AS space_name "
                f"FROM dcc.assets a "
                f"LEFT JOIN dcc.spaces s ON s.tenant_id=a.tenant_id AND s.id=a.space_id "
                f"LEFT JOIN dcc.facilities f ON f.tenant_id=s.tenant_id AND f.id=s.facility_id "
                f"{where} ORDER BY a.lifecycle_state,a.name LIMIT ${pidx} OFFSET ${pidx + 1}",
                *params,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    @staticmethod
    async def get_asset_topology(tenant_id: str) -> dict[str, list[dict[str, Any]]]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            nodes = await conn.fetch(
                "SELECT a.id::text AS id,'asset' AS kind,a.name AS label,a.asset_type AS type,"
                "a.lifecycle_state AS state,a.criticality,a.external_id,f.name AS facility "
                "FROM dcc.assets a LEFT JOIN dcc.spaces s ON s.tenant_id=a.tenant_id AND s.id=a.space_id "
                "LEFT JOIN dcc.facilities f ON f.tenant_id=s.tenant_id AND f.id=s.facility_id "
                "WHERE a.tenant_id=$1::uuid ORDER BY a.name LIMIT 500",
                tenant_id,
            )
            edges = await conn.fetch(
                "SELECT r.source_asset_id::text AS source,r.target_asset_id::text AS target,"
                "r.relation,r.confidence,r.valid_from,r.provenance "
                "FROM dcc.asset_relationships r "
                "JOIN dcc.assets a ON a.tenant_id=r.tenant_id AND a.id=r.source_asset_id "
                "JOIN dcc.assets b ON b.tenant_id=r.tenant_id AND b.id=r.target_asset_id "
                "WHERE r.tenant_id=$1::uuid AND r.valid_to IS NULL ORDER BY r.valid_from DESC LIMIT 1000",
                tenant_id,
            )
            return {
                "nodes": [dict(n) for n in nodes],
                "edges": [dict(e) for e in edges],
            }


# ---------------------------------------------------------------------------
# Energy Service
# ---------------------------------------------------------------------------


class EnergyService:
    """Operations on energy data, carbon factors, and allocations."""

    @staticmethod
    async def get_energy_summary(
        tenant_id: str,
        window_days: int = 30,
    ) -> dict[str, Any]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            # KPI series for energy-related metrics
            series = await conn.fetch(
                "SELECT d.metric_key,d.name,d.unit,date_trunc('day',o.window_end) AS bucket,"
                "avg(o.value_numeric) AS value,avg(o.coverage) AS coverage,avg(o.uncertainty) AS uncertainty,"
                "count(*)::int AS samples,bool_or(o.provenance->>'synthetic'='true') AS synthetic "
                "FROM dcc.kpi_observations o JOIN dcc.kpi_definitions d "
                "ON d.tenant_id=o.tenant_id AND d.id=o.kpi_definition_id "
                "WHERE o.tenant_id=$1::uuid AND o.window_end>=now()-($2*interval '1 day') "
                "AND d.metric_key IN ('facility_energy_kwh','it_energy_kwh','pue','carbon_kgco2e','useful_compute_per_kwh') "
                "GROUP BY d.metric_key,d.name,d.unit,date_trunc('day',o.window_end) "
                "ORDER BY d.metric_key,bucket LIMIT 5000",
                tenant_id,
                window_days,
            )

            # Telemetry quality distribution
            telemetry = await conn.fetch(
                "SELECT r.quality_status,count(*)::int AS samples,"
                "count(DISTINCT r.metric_id)::int AS metrics,count(DISTINCT r.asset_id)::int AS assets,"
                "max(r.observed_at) AS latest_observed_at "
                "FROM dcc.telemetry_readings r WHERE r.tenant_id=$1::uuid "
                "AND r.observed_at>=now()-($2*interval '1 day') GROUP BY r.quality_status ORDER BY r.quality_status",
                tenant_id,
                window_days,
            )

        return {
            "tenant_id": tenant_id,
            "window_days": window_days,
            "kpi_series": [dict(s) for s in series],
            "telemetry_quality": [dict(t) for t in telemetry],
            "read_only": True,
            "execution_permitted": False,
        }


# ---------------------------------------------------------------------------
# Cost Service
# ---------------------------------------------------------------------------


class CostService:
    """Operations on cost books, estimates, and actuals."""

    @staticmethod
    async def get_cost_summary(tenant_id: str) -> dict[str, Any]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            estimates = await conn.fetch(
                "SELECT e.id::text,e.project_code,e.name,e.lifecycle_phase,e.status,e.currency,e.geography,"
                "e.price_as_of,e.horizon_months,e.it_capacity_kw,e.facility_area_m2,e.rack_count,"
                "e.annual_it_energy_kwh,e.annual_useful_work,e.discount_rate,e.contingency_pct,"
                "e.assumptions,e.calculation_version,"
                "coalesce(r.lifecycle_pv,0) AS lifecycle_pv,coalesce(r.low_pv,0) AS low_pv,coalesce(r.high_pv,0) AS high_pv,"
                "coalesce(r.first_period_cost,0) AS first_period_cost,coalesce(r.line_count,0) AS line_count,"
                "coalesce(r.unpriced_lines,0) AS unpriced_lines,coalesce(r.synthetic_lines,0) AS synthetic_lines "
                "FROM dcc.estimate_projects e LEFT JOIN (SELECT tenant_id,estimate_id,currency,"
                "sum(present_value_base) AS lifecycle_pv,sum(present_value_low) AS low_pv,sum(present_value_high) AS high_pv,"
                "sum(first_period_cost) AS first_period_cost,sum(line_count) AS line_count,"
                "sum(unpriced_lines) AS unpriced_lines,sum(synthetic_lines) AS synthetic_lines "
                "FROM dcc.estimate_cost_rollup GROUP BY tenant_id,estimate_id,currency) r "
                "ON r.tenant_id=e.tenant_id AND r.estimate_id=e.id "
                "WHERE e.tenant_id=$1::uuid ORDER BY e.created_at DESC LIMIT 100",
                tenant_id,
            )
            prices = await conn.fetch(
                "SELECT p.item_code,p.description,p.category,p.quantity_unit,p.unit_price,p.currency,"
                "p.normalized_unit_price,b.currency AS book_currency,p.currency_basis_date,p.fx_to_book,p.geography,"
                "p.delivery_basis,p.observed_at,p.valid_from,p.valid_to,p.source_kind,p.source_name,p.source_ref,"
                "p.confidence,p.quality_status,p.provenance "
                "FROM dcc.price_observations p JOIN dcc.cost_books b ON b.tenant_id=p.tenant_id AND b.id=p.cost_book_id "
                "WHERE p.tenant_id=$1::uuid ORDER BY p.observed_at DESC LIMIT 500",
                tenant_id,
            )
            actuals = await conn.fetch(
                "SELECT accounting_period,cost_type,currency,sum(amount) AS actual_amount,count(*)::int AS entries,"
                "bool_or(provenance->>'synthetic'='true') AS synthetic "
                "FROM dcc.cost_actuals WHERE tenant_id=$1::uuid GROUP BY accounting_period,cost_type,currency "
                "ORDER BY accounting_period DESC,cost_type LIMIT 500",
                tenant_id,
            )

        return {
            "tenant_id": tenant_id,
            "estimates": [dict(e) for e in estimates],
            "prices": [dict(p) for p in prices],
            "actuals": [dict(a) for a in actuals],
            "read_only": True,
            "execution_permitted": False,
        }


# ---------------------------------------------------------------------------
# Workflow Service
# ---------------------------------------------------------------------------


class WorkflowService:
    """Operations on operational workflows and lifecycle management."""

    @staticmethod
    async def get_workflow_queue(
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = await get_db_pool()
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
                f"LIMIT {limit} OFFSET {offset}",
                *params,
            )
            return [dict(r) for r in rows]

    @staticmethod
    async def get_workflow_health(tenant_id: str) -> list[dict[str, Any]]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            rows = await conn.fetch(
                "SELECT workflow_type,status,priority,items,overdue,mean_age_days "
                "FROM dcc.mv_workflow_health WHERE tenant_id=$1::uuid",
                tenant_id,
            )
            return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Evidence Service
# ---------------------------------------------------------------------------


class EvidenceService:
    """Operations on the evidence chain and audit events."""

    @staticmethod
    async def get_evidence_events(
        tenant_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            rows = await conn.fetch(
                "SELECT sequence,event_type,occurred_at,actor_ref,subject_type,subject_id,event_hash "
                "FROM dcc.evidence_events WHERE tenant_id=$1::uuid ORDER BY sequence DESC LIMIT $2",
                tenant_id,
                limit,
            )
            return [dict(r) for r in rows]

    @staticmethod
    async def verify_chain(tenant_id: str) -> dict[str, Any]:
        """Verify the evidence hash chain for a tenant."""
        pool = await get_db_pool()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION READ ONLY")
            await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)

            rows = await conn.fetch(
                "SELECT sequence,event_type,occurred_at,event_hash FROM dcc.evidence_events "
                "WHERE tenant_id=$1::uuid ORDER BY sequence",
                tenant_id,
            )

        import hashlib

        previous_hash = ""
        results = []
        for row in rows:
            computed = hashlib.sha256(
                f"{previous_hash}{row['event_type']}{row['occurred_at']}".encode()
            ).hexdigest()
            results.append(
                {
                    "sequence": row["sequence"],
                    "event_type": row["event_type"],
                    "occurred_at": row["occurred_at"],
                    "is_valid": computed == row["event_hash"],
                }
            )
            previous_hash = row["event_hash"]

        return {
            "tenant_id": tenant_id,
            "total_events": len(results),
            "valid_events": sum(1 for r in results if r["is_valid"]),
            "invalid_events": sum(1 for r in results if not r["is_valid"]),
            "chain_valid": all(r["is_valid"] for r in results),
        }
