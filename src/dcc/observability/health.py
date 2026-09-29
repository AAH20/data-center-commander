"""Comprehensive health monitoring for Data Center Commander.

Provides unified health checks for:
  - Database (connectivity, schema, RLS, migration state)
  - Adapters (via AdapterRegistry — cloud, EPMS, BMS, CMMS, etc.)
  - External services (cloud pricing APIs, weather, carbon intensity)

All checks are bounded with timeouts and never raise — they return
structured HealthCheckResult objects suitable for monitoring and alerting.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ..adapters.registry import (
    AdapterCapability,
    AdapterRegistry,
    HealthStatus,
    get_registry,
)


# ---------------------------------------------------------------------------
# Health check result types
# ---------------------------------------------------------------------------


class CheckStatus(Enum):
    """Status of an individual health check."""
    OK = "ok"
    DEGRADED = "degraded"
    FAIL = "fail"
    SKIP = "skip"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: CheckStatus
    latency_ms: float
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "detail": self.detail,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class SystemHealthReport:
    """Aggregated health report for the entire system."""
    status: CheckStatus
    checked_at: str
    checks: list[HealthCheckResult]
    total_latency_ms: float
    healthy_count: int
    degraded_count: int
    failed_count: int
    skipped_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checked_at": self.checked_at,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "summary": {
                "healthy": self.healthy_count,
                "degraded": self.degraded_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
                "total": len(self.checks),
            },
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Database health checks
# ---------------------------------------------------------------------------


def _check_database_connectivity() -> HealthCheckResult:
    """Check that the database is reachable and responsive."""
    name = "database.connectivity"
    start = time.monotonic()
    try:
        dsn = os.environ.get("DCC_DATABASE_URL", "")
        if not dsn:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="DCC_DATABASE_URL not configured",
            )
        try:
            from psycopg import connect
        except ImportError:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="psycopg not installed",
            )
        conn = connect(dsn, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        finally:
            conn.close()
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK,
            latency_ms=latency,
            detail="connected",
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_database_schema() -> HealthCheckResult:
    """Check that required schema tables exist."""
    name = "database.schema"
    start = time.monotonic()
    try:
        dsn = os.environ.get("DCC_DATABASE_URL", "")
        if not dsn:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="DCC_DATABASE_URL not configured",
            )
        try:
            from psycopg import connect
        except ImportError:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="psycopg not installed",
            )
        conn = connect(dsn, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('dcc.tenants') IS NOT NULL AS tenants, "
                    "to_regclass('dcc.assets') IS NOT NULL AS assets, "
                    "to_regclass('dcc.evidence_events') IS NOT NULL AS evidence, "
                    "to_regclass('dcc.telemetry_readings') IS NOT NULL AS telemetry, "
                    "to_regclass('dcc.connectors') IS NOT NULL AS connectors, "
                    "to_regclass('dcc.kpi_observations') IS NOT NULL AS kpi, "
                    "to_regclass('dcc.operational_workflows') IS NOT NULL AS workflows"
                )
                row = cur.fetchone()
        finally:
            conn.close()
        latency = (time.monotonic() - start) * 1000
        if row is None:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.FAIL,
                latency_ms=latency,
                detail="schema query returned no rows",
            )
        tables = {
            "tenants": row[0],
            "assets": row[1],
            "evidence_events": row[2],
            "telemetry_readings": row[3],
            "connectors": row[4],
            "kpi_observations": row[5],
            "operational_workflows": row[6],
        }
        missing = [t for t, present in tables.items() if not present]
        if missing:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.DEGRADED,
                latency_ms=latency,
                detail=f"missing tables: {', '.join(missing)}",
                metadata={"missing_tables": missing, "present_tables": [t for t, p in tables.items() if p]},
            )
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK,
            latency_ms=latency,
            detail="all required tables present",
            metadata={"tables": list(tables.keys())},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_database_rls() -> HealthCheckResult:
    """Check that Row-Level Security is enforced on tenant-scoped tables."""
    name = "database.rls"
    start = time.monotonic()
    try:
        dsn = os.environ.get("DCC_DATABASE_URL", "")
        if not dsn:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="DCC_DATABASE_URL not configured",
            )
        try:
            from psycopg import connect
        except ImportError:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="psycopg not installed",
            )
        conn = connect(dsn, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'dcc' AND c.relname = ANY(%s)",
                    (["assets", "evidence_events", "telemetry_readings", "connectors"],),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        latency = (time.monotonic() - start) * 1000
        if not rows:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.FAIL,
                latency_ms=latency,
                detail="no RLS tables found in dcc schema",
            )
        policies = {row[0]: {"rls": row[1], "force_rls": row[2]} for row in rows}
        required = {"assets", "evidence_events", "telemetry_readings", "connectors"}
        missing = required - set(policies)
        not_enforced = [t for t, p in policies.items() if not p["rls"] or not p["force_rls"]]
        if missing:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.DEGRADED,
                latency_ms=latency,
                detail=f"tables without RLS check: {', '.join(missing)}",
                metadata={"missing": list(missing), "policies": policies},
            )
        if not_enforced:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.FAIL,
                latency_ms=latency,
                detail=f"RLS not enforced on: {', '.join(not_enforced)}",
                metadata={"not_enforced": not_enforced, "policies": policies},
            )
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK,
            latency_ms=latency,
            detail="RLS enforced on all tenant-scoped tables",
            metadata={"tables": list(policies.keys())},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_database_migrations() -> HealthCheckResult:
    """Check that the schema version is current."""
    name = "database.migrations"
    start = time.monotonic()
    try:
        dsn = os.environ.get("DCC_DATABASE_URL", "")
        if not dsn:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="DCC_DATABASE_URL not configured",
            )
        try:
            from psycopg import connect
        except ImportError:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.SKIP,
                latency_ms=(time.monotonic() - start) * 1000,
                detail="psycopg not installed",
            )
        conn = connect(dsn, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                # Check if schema_migrations table exists
                cur.execute(
                    "SELECT to_regclass('dcc.schema_migrations') IS NOT NULL"
                )
                has_migrations = cur.fetchone()[0]
                if not has_migrations:
                    return HealthCheckResult(
                        name=name,
                        status=CheckStatus.DEGRADED,
                        latency_ms=(time.monotonic() - start) * 1000,
                        detail="schema_migrations table not found — migrations not tracked",
                    )
                cur.execute(
                    "SELECT version, applied_at FROM dcc.schema_migrations "
                    "ORDER BY applied_at DESC LIMIT 1"
                )
                row = cur.fetchone()
        finally:
            conn.close()
        latency = (time.monotonic() - start) * 1000
        if row is None:
            return HealthCheckResult(
                name=name,
                status=CheckStatus.DEGRADED,
                latency_ms=latency,
                detail="no migrations recorded",
            )
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK,
            latency_ms=latency,
            detail=f"latest migration: {row[0]}",
            metadata={"latest_version": row[0], "applied_at": str(row[1])},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# Adapter health checks
# ---------------------------------------------------------------------------


def _check_adapter_registry(registry: AdapterRegistry | None = None) -> list[HealthCheckResult]:
    """Check health of all registered adapters."""
    name = "adapters.registry"
    start = time.monotonic()
    reg = registry or get_registry()
    results: list[HealthCheckResult] = []

    # Check that the registry has adapters registered
    adapter_names = reg.adapter_names
    if not adapter_names:
        results.append(HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=(time.monotonic() - start) * 1000,
            detail="no adapters registered",
        ))
        return results

    # Run health checks for each adapter
    for adapter_name in adapter_names:
        check_start = time.monotonic()
        try:
            health = reg.check_health(adapter_name)
            latency = (time.monotonic() - check_start) * 1000
            status_map = {
                HealthStatus.HEALTHY: CheckStatus.OK,
                HealthStatus.DEGRADED: CheckStatus.DEGRADED,
                HealthStatus.UNHEALTHY: CheckStatus.FAIL,
                HealthStatus.UNKNOWN: CheckStatus.UNKNOWN,
            }
            results.append(HealthCheckResult(
                name=f"adapter.{adapter_name}",
                status=status_map.get(health.status, CheckStatus.UNKNOWN),
                latency_ms=latency,
                detail=health.detail or health.status.value,
                metadata={
                    "consecutive_failures": health.consecutive_failures,
                    "last_success_at": health.last_success_at,
                },
            ))
        except Exception as exc:
            latency = (time.monotonic() - check_start) * 1000
            results.append(HealthCheckResult(
                name=f"adapter.{adapter_name}",
                status=CheckStatus.FAIL,
                latency_ms=latency,
                detail=f"{type(exc).__name__}: {exc}",
            ))

    return results


def _check_cloud_providers() -> list[HealthCheckResult]:
    """Check cloud provider pricing API endpoints."""
    results: list[HealthCheckResult] = []

    # AWS Pricing API
    start = time.monotonic()
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            "https://api.pricing.us-east-1.amazonaws.com/v1.0/offers/AmazonEC2/index.json",
            headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
            method="HEAD",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        latency = (time.monotonic() - start) * 1000
        results.append(HealthCheckResult(
            name="external.aws_pricing",
            status=CheckStatus.OK if status < 400 else CheckStatus.DEGRADED,
            latency_ms=latency,
            detail=f"HTTP {status}",
            metadata={"endpoint": "https://api.pricing.us-east-1.amazonaws.com"},
        ))
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        results.append(HealthCheckResult(
            name="external.aws_pricing",
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        ))

    # Azure Retail Prices API
    start = time.monotonic()
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            "https://prices.azure.com/api/retail/prices?$top=1",
            headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        latency = (time.monotonic() - start) * 1000
        results.append(HealthCheckResult(
            name="external.azure_pricing",
            status=CheckStatus.OK if status < 400 else CheckStatus.DEGRADED,
            latency_ms=latency,
            detail=f"HTTP {status}",
            metadata={"endpoint": "https://prices.azure.com/api/retail/prices"},
        ))
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        results.append(HealthCheckResult(
            name="external.azure_pricing",
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        ))

    # Google Cloud Billing API
    start = time.monotonic()
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            "https://cloudbilling.googleapis.com/v1/services",
            headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        latency = (time.monotonic() - start) * 1000
        results.append(HealthCheckResult(
            name="external.gcp_billing",
            status=CheckStatus.OK if status < 400 else CheckStatus.DEGRADED,
            latency_ms=latency,
            detail=f"HTTP {status}",
            metadata={"endpoint": "https://cloudbilling.googleapis.com/v1"},
        ))
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        results.append(HealthCheckResult(
            name="external.gcp_billing",
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        ))

    return results


def _check_weather_service() -> HealthCheckResult:
    """Check Open-Meteo weather API availability."""
    name = "external.weather"
    start = time.monotonic()
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m",
            headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK if status < 400 else CheckStatus.DEGRADED,
            latency_ms=latency,
            detail=f"HTTP {status}",
            metadata={"endpoint": "https://api.open-meteo.com/v1/forecast"},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_carbon_intensity_service() -> HealthCheckResult:
    """Check Electricity Maps carbon intensity API availability."""
    name = "external.carbon_intensity"
    start = time.monotonic()
    api_key = os.environ.get("ELECTRICITY_MAP_API_KEY", "")
    if not api_key:
        return HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=(time.monotonic() - start) * 1000,
            detail="ELECTRICITY_MAP_API_KEY not configured",
        )
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            "https://api.electricitymap.org/v3/carbon-intensity/latest?lat=52.52&lon=13.41",
            headers={
                "Accept": "application/json",
                "User-Agent": "DataCenterCommander/0.1",
                "auth-token": api_key,
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK if status < 400 else CheckStatus.DEGRADED,
            latency_ms=latency,
            detail=f"HTTP {status}",
            metadata={"endpoint": "https://api.electricitymap.org/v3/carbon-intensity/latest"},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# External adapter health checks (BMS, Hypervisor, OEM, Utility)
# ---------------------------------------------------------------------------


def _check_bms_gateway() -> HealthCheckResult:
    """Check BMS gateway health if configured."""
    name = "external.bms_gateway"
    start = time.monotonic()
    endpoint = os.environ.get("BMS_GATEWAY_ENDPOINT", "")
    if not endpoint:
        return HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=(time.monotonic() - start) * 1000,
            detail="BMS_GATEWAY_ENDPOINT not configured",
        )
    try:
        from ..adapters.bms import health_check as bms_health
        result = bms_health(endpoint=endpoint)
        latency = (time.monotonic() - start) * 1000
        healthy = result.get("healthy", False)
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK if healthy else CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"healthy={healthy}",
            metadata={"checks": result.get("checks", {}), "details": result.get("details", {})},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_hypervisor_gateway() -> HealthCheckResult:
    """Check hypervisor gateway health if configured."""
    name = "external.hypervisor_gateway"
    start = time.monotonic()
    endpoint = os.environ.get("HYPERVISOR_GATEWAY_ENDPOINT", "")
    if not endpoint:
        return HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=(time.monotonic() - start) * 1000,
            detail="HYPERVISOR_GATEWAY_ENDPOINT not configured",
        )
    try:
        from ..adapters.hypervisor import health_check as hv_health
        result = hv_health(endpoint=endpoint)
        latency = (time.monotonic() - start) * 1000
        healthy = result.get("healthy", False)
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK if healthy else CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"healthy={healthy}",
            metadata={"checks": result.get("checks", {}), "details": result.get("details", {})},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_oem_redfish() -> HealthCheckResult:
    """Check OEM Redfish endpoint health if configured."""
    name = "external.oem_redfish"
    start = time.monotonic()
    endpoint = os.environ.get("OEM_REDFISH_ENDPOINT", "")
    if not endpoint:
        return HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=(time.monotonic() - start) * 1000,
            detail="OEM_REDFISH_ENDPOINT not configured",
        )
    try:
        from ..adapters.oem import health_check as oem_health
        result = oem_health(endpoint=endpoint)
        latency = (time.monotonic() - start) * 1000
        healthy = result.get("healthy", False)
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK if healthy else CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"healthy={healthy}",
            metadata={"checks": result.get("checks", {}), "details": result.get("details", {})},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_utility_gateway() -> HealthCheckResult:
    """Check utility gateway health if configured."""
    name = "external.utility_gateway"
    start = time.monotonic()
    endpoint = os.environ.get("UTILITY_GATEWAY_ENDPOINT", "")
    if not endpoint:
        return HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=(time.monotonic() - start) * 1000,
            detail="UTILITY_GATEWAY_ENDPOINT not configured",
        )
    try:
        from ..adapters.utility import health_check as util_health
        result = util_health(endpoint=endpoint)
        latency = (time.monotonic() - start) * 1000
        healthy = result.get("healthy", False)
        return HealthCheckResult(
            name=name,
            status=CheckStatus.OK if healthy else CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"healthy={healthy}",
            metadata={"checks": result.get("checks", {}), "details": result.get("details", {})},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.FAIL,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# System resource checks
# ---------------------------------------------------------------------------


def _check_disk_space() -> HealthCheckResult:
    """Check available disk space."""
    name = "system.disk_space"
    start = time.monotonic()
    try:
        import shutil
        usage = shutil.disk_usage("/")
        latency = (time.monotonic() - start) * 1000
        free_pct = (usage.free / usage.total) * 100 if usage.total > 0 else 0
        if free_pct < 5:
            status = CheckStatus.FAIL
        elif free_pct < 15:
            status = CheckStatus.DEGRADED
        else:
            status = CheckStatus.OK
        return HealthCheckResult(
            name=name,
            status=status,
            latency_ms=latency,
            detail=f"{free_pct:.1f}% free ({usage.free // (1024**3)} GB / {usage.total // (1024**3)} GB)",
            metadata={
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "free_percent": round(free_pct, 1),
            },
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.UNKNOWN,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_memory() -> HealthCheckResult:
    """Check system memory usage."""
    name = "system.memory"
    start = time.monotonic()
    try:
        import psutil
        mem = psutil.virtual_memory()
        latency = (time.monotonic() - start) * 1000
        if mem.percent > 95:
            status = CheckStatus.FAIL
        elif mem.percent > 85:
            status = CheckStatus.DEGRADED
        else:
            status = CheckStatus.OK
        return HealthCheckResult(
            name=name,
            status=status,
            latency_ms=latency,
            detail=f"{mem.percent}% used ({mem.used // (1024**2)} MB / {mem.total // (1024**2)} MB)",
            metadata={
                "total_bytes": mem.total,
                "available_bytes": mem.available,
                "used_bytes": mem.used,
                "percent": mem.percent,
            },
        )
    except ImportError:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.SKIP,
            latency_ms=latency,
            detail="psutil not installed",
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            name=name,
            status=CheckStatus.UNKNOWN,
            latency_ms=latency,
            detail=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# Comprehensive health check runner
# ---------------------------------------------------------------------------


def run_health_checks(
    *,
    include_database: bool = True,
    include_adapters: bool = True,
    include_external: bool = True,
    include_system: bool = True,
    adapter_registry: AdapterRegistry | None = None,
) -> SystemHealthReport:
    """Run all configured health checks and return a comprehensive report.

    Args:
        include_database: Run database connectivity, schema, RLS, and migration checks.
        include_adapters: Run adapter registry health checks.
        include_external: Run external service checks (cloud, weather, carbon, gateways).
        include_system: Run system resource checks (disk, memory).
        adapter_registry: Optional adapter registry instance (uses default if None).

    Returns:
        SystemHealthReport with all check results and aggregated status.
    """
    all_checks: list[HealthCheckResult] = []

    if include_database:
        all_checks.append(_check_database_connectivity())
        all_checks.append(_check_database_schema())
        all_checks.append(_check_database_rls())
        all_checks.append(_check_database_migrations())

    if include_adapters:
        all_checks.extend(_check_adapter_registry(adapter_registry))

    if include_external:
        all_checks.extend(_check_cloud_providers())
        all_checks.append(_check_weather_service())
        all_checks.append(_check_carbon_intensity_service())
        all_checks.append(_check_bms_gateway())
        all_checks.append(_check_hypervisor_gateway())
        all_checks.append(_check_oem_redfish())
        all_checks.append(_check_utility_gateway())

    if include_system:
        all_checks.append(_check_disk_space())
        all_checks.append(_check_memory())

    # Aggregate results
    healthy = sum(1 for c in all_checks if c.status is CheckStatus.OK)
    degraded = sum(1 for c in all_checks if c.status is CheckStatus.DEGRADED)
    failed = sum(1 for c in all_checks if c.status is CheckStatus.FAIL)
    skipped = sum(1 for c in all_checks if c.status is CheckStatus.SKIP)
    total_latency = sum(c.latency_ms for c in all_checks)

    # Determine overall status
    if failed > 0:
        overall = CheckStatus.FAIL
    elif degraded > 0:
        overall = CheckStatus.DEGRADED
    elif healthy > 0:
        overall = CheckStatus.OK
    else:
        overall = CheckStatus.UNKNOWN

    return SystemHealthReport(
        status=overall,
        checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        checks=all_checks,
        total_latency_ms=total_latency,
        healthy_count=healthy,
        degraded_count=degraded,
        failed_count=failed,
        skipped_count=skipped,
    )


def quick_health() -> dict[str, Any]:
    """Run a quick health check (database + adapters only).

    Returns a minimal dict suitable for load balancer health probes.
    """
    report = run_health_checks(
        include_database=True,
        include_adapters=True,
        include_external=False,
        include_system=False,
    )
    return {
        "status": report.status.value,
        "healthy": report.healthy_count,
        "degraded": report.degraded_count,
        "failed": report.failed_count,
        "skipped": report.skipped_count,
        "checked_at": report.checked_at,
    }


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "CheckStatus",
    "HealthCheckResult",
    "SystemHealthReport",
    "run_health_checks",
    "quick_health",
]
