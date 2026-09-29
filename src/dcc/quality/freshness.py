"""Data freshness SLA monitoring for Data Center Commander.

Tracks data age per source and alerts on SLA violations.
All queries are read-only and tenant-scoped.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


# ── SLA thresholds (in hours) ──────────────────────────────────────────
DEFAULT_SLA_HOURS: dict[str, int] = {
    "telemetry_readings": 1,       # Real-time telemetry: 1 hour
    "kpi_observations": 26,        # Daily KPIs: ~1 day
    "capacity_snapshots": 26,      # Daily capacity: ~1 day
    "price_observations": 72,      # Prices: 3 days (varies by source_kind)
    "connectors": 26,              # Connector last success: ~1 day
    "assets": 168,                 # Asset observed_at: 7 days
    "cost_actuals": 720,           # Monthly actuals: 30 days
    "energy_allocations": 26,      # Daily allocations: ~1 day
}

# Per-source-kind SLA overrides for price_observations
PRICE_SOURCE_KIND_SLA_HOURS: dict[str, int] = {
    "vendor_api": 24,          # Vendor APIs: daily refresh
    "vendor_quote": 168,       # Quotes: 7 days
    "contract": 720,           # Contracts: 30 days
    "utility_tariff": 168,     # Tariffs: 7 days
    "public_benchmark": 72,    # Public benchmarks: 3 days
    "manual": 168,             # Manual entries: 7 days
    "synthetic_demo": 999999,  # Synthetic: no SLA
}


@dataclass
class SourceFreshness:
    """Freshness status for a single data source."""
    source: str
    table: str
    latest_timestamp: str | None
    age_hours: float | None
    sla_hours: int
    status: str  # "ok" | "warning" | "violation" | "no_data"
    row_count: int = 0
    detail: str = ""


@dataclass
class FreshnessReport:
    """Complete freshness report for a tenant."""
    tenant_id: str
    checked_at: str
    sources: list[SourceFreshness] = field(default_factory=list)
    overall_status: str = "ok"  # "ok" | "warning" | "violation"
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _hours_since(timestamp: dt.datetime | None, *, now: dt.datetime | None = None) -> float | None:
    """Calculate hours since a timestamp. Returns None if timestamp is None."""
    if timestamp is None:
        return None
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
    delta = now - timestamp
    return max(0.0, delta.total_seconds() / 3600.0)


def evaluate_sla(age_hours: float | None, sla_hours: int, *, row_count: int = 1) -> str:
    """Evaluate freshness against an SLA threshold.

    Returns:
        "no_data" if age_hours is None or row_count is 0
        "violation" if age exceeds SLA
        "warning" if age exceeds 80% of SLA
        "ok" otherwise
    """
    if age_hours is None or row_count == 0:
        return "no_data"
    if age_hours > sla_hours:
        return "violation"
    if age_hours > sla_hours * 0.8:
        return "warning"
    return "ok"


def _query_source_freshness(
    conn: Any,
    tenant_id: str,
    source: str,
    table: str,
    timestamp_column: str,
    sla_hours: int,
    *,
    additional_where: str = "",
    params: tuple = (),
    now: dt.datetime | None = None,
) -> SourceFreshness:
    """Query the latest timestamp and row count for a source."""
    where_clause = f"tenant_id=%s::uuid"
    if additional_where:
        where_clause += f" AND {additional_where}"
    query = (
        f"SELECT {timestamp_column} AS latest, count(*)::int AS row_count "
        f"FROM dcc.{table} WHERE {where_clause} "
        f"GROUP BY {timestamp_column} ORDER BY {timestamp_column} DESC LIMIT 1"
    )
    row = conn.execute(query, (tenant_id, *params)).fetchone()
    if row is None:
        return SourceFreshness(
            source=source,
            table=table,
            latest_timestamp=None,
            age_hours=None,
            sla_hours=sla_hours,
            status="no_data",
            row_count=0,
            detail=f"No rows in dcc.{table}",
        )
    latest = row["latest"]
    if hasattr(latest, "isoformat"):
        latest_str = latest.isoformat()
    else:
        latest_str = str(latest)
    age = _hours_since(latest, now=now)
    status = evaluate_sla(age, sla_hours, row_count=row["row_count"])
    return SourceFreshness(
        source=source,
        table=table,
        latest_timestamp=latest_str,
        age_hours=round(age, 2) if age is not None else None,
        sla_hours=sla_hours,
        status=status,
        row_count=row["row_count"],
    )


def _query_price_observations_freshness(
    conn: Any,
    tenant_id: str,
    *,
    now: dt.datetime | None = None,
) -> list[SourceFreshness]:
    """Query price_observations freshness broken down by source_kind."""
    rows = conn.execute(
        "SELECT source_kind, max(observed_at) AS latest, count(*)::int AS row_count "
        "FROM dcc.price_observations WHERE tenant_id=%s::uuid "
        "GROUP BY source_kind ORDER BY source_kind",
        (tenant_id,),
    ).fetchall()
    results = []
    for row in rows:
        kind = row["source_kind"]
        sla = PRICE_SOURCE_KIND_SLA_HOURS.get(kind, DEFAULT_SLA_HOURS["price_observations"])
        latest = row["latest"]
        if hasattr(latest, "isoformat"):
            latest_str = latest.isoformat()
        else:
            latest_str = str(latest)
        age = _hours_since(latest, now=now)
        status = evaluate_sla(age, sla, row_count=row["row_count"])
        results.append(SourceFreshness(
            source=f"price_observations:{kind}",
            table="price_observations",
            latest_timestamp=latest_str,
            age_hours=round(age, 2) if age is not None else None,
            sla_hours=sla,
            status=status,
            row_count=row["row_count"],
        ))
    if not results:
        results.append(SourceFreshness(
            source="price_observations",
            table="price_observations",
            latest_timestamp=None,
            age_hours=None,
            sla_hours=DEFAULT_SLA_HOURS["price_observations"],
            status="no_data",
            row_count=0,
            detail="No price observations",
        ))
    return results


def get_source_freshness(
    pool: Any,
    tenant_id: str,
    *,
    now: dt.datetime | None = None,
) -> list[SourceFreshness]:
    """Get freshness status for all monitored sources.

    Args:
        pool: Database connection pool (psycopg_pool.ConnectionPool)
        tenant_id: Tenant UUID string
        now: Optional reference time for testing

    Returns:
        List of SourceFreshness for each monitored source
    """
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)

    results: list[SourceFreshness] = []
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (tenant_id,))

            # Telemetry readings (real-time)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="telemetry_readings",
                table="telemetry_readings",
                timestamp_column="observed_at",
                sla_hours=DEFAULT_SLA_HOURS["telemetry_readings"],
                now=now,
            ))

            # KPI observations (daily)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="kpi_observations",
                table="kpi_observations",
                timestamp_column="window_end",
                sla_hours=DEFAULT_SLA_HOURS["kpi_observations"],
                now=now,
            ))

            # Capacity snapshots (daily)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="capacity_snapshots",
                table="capacity_snapshots",
                timestamp_column="observed_at",
                sla_hours=DEFAULT_SLA_HOURS["capacity_snapshots"],
                now=now,
            ))

            # Price observations (by source_kind)
            results.extend(_query_price_observations_freshness(conn, tenant_id, now=now))

            # Connectors (last success)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="connectors",
                table="connectors",
                timestamp_column="last_success_at",
                sla_hours=DEFAULT_SLA_HOURS["connectors"],
                now=now,
            ))

            # Assets (observed_at)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="assets",
                table="assets",
                timestamp_column="observed_at",
                sla_hours=DEFAULT_SLA_HOURS["assets"],
                now=now,
            ))

            # Cost actuals (monthly)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="cost_actuals",
                table="cost_actuals",
                timestamp_column="occurred_at",
                sla_hours=DEFAULT_SLA_HOURS["cost_actuals"],
                now=now,
            ))

            # Energy allocations (daily)
            results.append(_query_source_freshness(
                conn, tenant_id,
                source="energy_allocations",
                table="energy_allocations",
                timestamp_column="window_end",
                sla_hours=DEFAULT_SLA_HOURS["energy_allocations"],
                now=now,
            ))

    return results


def build_freshness_report(
    tenant_id: str,
    sources: list[SourceFreshness],
    *,
    now: dt.datetime | None = None,
) -> FreshnessReport:
    """Build a complete freshness report from source results."""
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)

    violations = [s.source for s in sources if s.status == "violation"]
    warnings = [s.source for s in sources if s.status == "warning"]

    if violations:
        overall = "violation"
    elif warnings:
        overall = "warning"
    else:
        overall = "ok"

    return FreshnessReport(
        tenant_id=tenant_id,
        checked_at=now.isoformat(),
        sources=sources,
        overall_status=overall,
        violations=violations,
        warnings=warnings,
    )


def check_freshness(
    pool: Any,
    tenant_id: str,
    *,
    now: dt.datetime | None = None,
) -> FreshnessReport:
    """Main entry point: check data freshness for a tenant.

    Args:
        pool: Database connection pool
        tenant_id: Tenant UUID string
        now: Optional reference time for testing

    Returns:
        FreshnessReport with per-source status and overall health
    """
    sources = get_source_freshness(pool, tenant_id, now=now)
    return build_freshness_report(tenant_id, sources, now=now)


def format_freshness_report(report: FreshnessReport) -> dict[str, Any]:
    """Convert a FreshnessReport to a JSON-serializable dict."""
    return {
        "tenant_id": report.tenant_id,
        "checked_at": report.checked_at,
        "overall_status": report.overall_status,
        "violations": report.violations,
        "warnings": report.warnings,
        "sources": [
            {
                "source": s.source,
                "table": s.table,
                "latest_timestamp": s.latest_timestamp,
                "age_hours": s.age_hours,
                "sla_hours": s.sla_hours,
                "status": s.status,
                "row_count": s.row_count,
                "detail": s.detail,
            }
            for s in report.sources
        ],
        "execution_permitted": False,
    }
