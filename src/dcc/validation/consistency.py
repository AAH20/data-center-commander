"""Cross-source consistency validation for Data Center Commander.

Validates consistency across utility, BMS, EPMS, and CMMS data sources.
Pure-Python implementation with no external dependencies.

Each validator accepts rows (dicts or objects with attribute access) from
two or more sources and returns structured findings. The module is
intentionally read-only: it never mutates input data and never writes
to the database.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


# ---------------------------------------------------------------------------
# Finding severity and structure
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Severity levels for consistency findings."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class Finding:
    """A single consistency finding."""

    check: str
    severity: Severity
    message: str
    source_a: str = ""
    source_b: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "source_a": self.source_a,
            "source_b": self.source_b,
            "detail": self.detail,
        }


@dataclass
class ConsistencyReport:
    """Aggregate report from a consistency validation run."""

    findings: list[Finding] = field(default_factory=list)
    sources_checked: list[str] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def passed(self) -> bool:
        """True when nothing BLOCKING was found.

        Only FAIL is blocking. WARN is advisory by definition, and treating it as a
        failure made a report that merely warned indistinguishable from one that
        found a real inconsistency -- the caller could not tell them apart, and
        execution was refused for advisory findings. SKIP means the check could not
        run (no data), which is not a finding about the data either way.
        """
        return not any(f.severity is Severity.FAIL for f in self.findings)

    @property
    def failed(self) -> bool:
        """True when at least one finding is blocking. Explicit counterpart to passed."""
        return any(f.severity is Severity.FAIL for f in self.findings)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.FAIL]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARN]

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "sources_checked": self.sources_checked,
            "total_findings": len(self.findings),
            "failure_count": self.failure_count,
            "warning_count": self.warning_count,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(row: Any, key: str, default: Any = None) -> Any:
    """Get a value from a dict or object."""
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _to_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, Decimal):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, str):
        try:
            f = float(value)
            return f if math.isfinite(f) else None
        except (ValueError, TypeError):
            return None
    return None


def _to_str(value: Any) -> str | None:
    """Safely convert a value to stripped string."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _utcnow() -> datetime:
    """Naive UTC now, for comparing against naive timestamps.

    Kept naive on purpose: this module receives timestamps from JSON payloads and
    database rows that are frequently naive, and subtracting an aware datetime from
    a naive one raises TypeError. Callers normalise the OTHER side with
    _as_naive_utc() rather than relying on both being aware.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive_utc(value):
    """Coerce a datetime to naive UTC so it can be compared with _utcnow().

    Aware values are converted to UTC and stripped. Naive values are assumed UTC.
    Without this, any timestamp carrying a timezone -- which is what ISO-8601 with
    a Z or +00:00 suffix parses to -- raised
    "can't subtract offset-naive and offset-aware datetimes" and took down the
    whole freshness check for that tenant.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return value


def _to_datetime(value: Any) -> datetime | None:
    """Safely convert a value to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def _pct_diff(a: float, b: float) -> float:
    """Percentage difference relative to the larger magnitude."""
    denom = max(abs(a), abs(b))
    if denom == 0:
        return 0.0
    return abs(a - b) / denom * 100.0


def _is_synthetic(row: Any) -> bool:
    """Check if a row is marked synthetic via provenance or attributes."""
    for key in ("provenance", "attributes"):
        val = _get(row, key)
        if isinstance(val, Mapping):
            if val.get("synthetic") is True:
                return True
            if val.get("label") == "NOT LIVE":
                return True
    return False


def _safe_sum(values: Iterable[Any]) -> float:
    """Sum numeric values, skipping None."""
    total = 0.0
    for v in values:
        f = _to_float(v)
        if f is not None:
            total += f
    return total


# ---------------------------------------------------------------------------
# 1. Energy source reconciliation (utility vs BMS vs EPMS)
# ---------------------------------------------------------------------------


def reconcile_energy_sources(
    *,
    facility_meter_readings: Sequence[Any],
    submeter_readings: Sequence[Any],
    tolerance_pct: float = 5.0,
    source_a_name: str = "utility_facility_meter",
    source_b_name: str = "bms_submeters",
) -> list[Finding]:
    """Reconcile facility-level utility meter against BMS sub-meter sum.

    The facility boundary meter (utility source) should approximately equal
    the sum of IT, cooling, and other submeters (BMS source). A gap beyond
    the tolerance indicates unmetered loads, meter drift, or data loss.
    """
    findings: list[Finding] = []
    if not facility_meter_readings and not submeter_readings:
        return [Finding(
            check="energy_reconciliation",
            severity=Severity.SKIP,
            message="No energy readings provided for reconciliation",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    facility_total = _safe_sum(_get(r, "value_numeric") or _get(r, "energy_kwh") for r in facility_meter_readings)
    submeter_total = _safe_sum(_get(r, "value_numeric") or _get(r, "energy_kwh") for r in submeter_readings)

    if facility_total == 0 and submeter_total == 0:
        findings.append(Finding(
            check="energy_reconciliation",
            severity=Severity.SKIP,
            message="Both sources report zero energy; cannot reconcile",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
        return findings

    diff_pct = _pct_diff(facility_total, submeter_total)
    if diff_pct <= tolerance_pct:
        findings.append(Finding(
            check="energy_reconciliation",
            severity=Severity.PASS,
            message=f"Energy sources reconcile within {diff_pct:.2f}% (tolerance {tolerance_pct}%)",
            source_a=source_a_name,
            source_b=source_b_name,
            detail=f"facility={facility_total:.2f} kWh, submeters={submeter_total:.2f} kWh",
        ))
    elif diff_pct <= tolerance_pct * 2:
        findings.append(Finding(
            check="energy_reconciliation",
            severity=Severity.WARN,
            message=f"Energy sources differ by {diff_pct:.2f}% (tolerance {tolerance_pct}%)",
            source_a=source_a_name,
            source_b=source_b_name,
            detail=f"facility={facility_total:.2f} kWh, submeters={submeter_total:.2f} kWh",
        ))
    else:
        findings.append(Finding(
            check="energy_reconciliation",
            severity=Severity.FAIL,
            message=f"Energy sources differ by {diff_pct:.2f}% — exceeds {tolerance_pct * 2:.0f}% threshold",
            source_a=source_a_name,
            source_b=source_b_name,
            detail=f"facility={facility_total:.2f} kWh, submeters={submeter_total:.2f} kWh",
        ))
    return findings


# ---------------------------------------------------------------------------
# 2. Asset reference integrity (CMMS work orders vs asset registry)
# ---------------------------------------------------------------------------


def validate_asset_references(
    *,
    work_orders: Sequence[Any],
    assets: Sequence[Any],
    source_a_name: str = "cmms_work_orders",
    source_b_name: str = "asset_registry",
) -> list[Finding]:
    """Verify every CMMS work order references a known asset.

    Orphaned work orders (asset_id not in the registry) indicate either
    a deleted asset or a CMMS integration error.
    """
    findings: list[Finding] = []
    if not work_orders:
        return [Finding(
            check="asset_reference_integrity",
            severity=Severity.SKIP,
            message="No work orders provided",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    asset_ids: set[str] = set()
    for a in assets:
        aid = _to_str(_get(a, "id")) or _to_str(_get(a, "external_id"))
        if aid:
            asset_ids.add(aid)

    if not asset_ids:
        return [Finding(
            check="asset_reference_integrity",
            severity=Severity.SKIP,
            message="Asset registry is empty; cannot validate references",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    orphaned: list[str] = []
    for wo in work_orders:
        asset_id = _to_str(_get(wo, "asset_id"))
        if asset_id and asset_id not in asset_ids:
            orphaned.append(asset_id)

    if not orphaned:
        findings.append(Finding(
            check="asset_reference_integrity",
            severity=Severity.PASS,
            message=f"All {len(work_orders)} work orders reference known assets",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        findings.append(Finding(
            check="asset_reference_integrity",
            severity=Severity.FAIL,
            message=f"{len(orphaned)} work order(s) reference unknown assets",
            source_a=source_a_name,
            source_b=source_b_name,
            detail=f"unknown asset_ids: {orphaned[:10]}",
        ))
    return findings


# ---------------------------------------------------------------------------
# 3. Capacity vs actual load (EPMS capacity snapshots vs telemetry)
# ---------------------------------------------------------------------------


def validate_capacity_headroom(
    *,
    capacity_snapshots: Sequence[Any],
    it_load_readings: Sequence[Any],
    tolerance_pct: float = 10.0,
    source_a_name: str = "epms_capacity",
    source_b_name: str = "telemetry_it_load",
) -> list[Finding]:
    """Check that IT load telemetry does not exceed usable capacity.

    If the observed IT load exceeds the usable capacity snapshot by more
    than the tolerance, either the capacity data is stale or the load
    readings are erroneous.
    """
    findings: list[Finding] = []
    if not capacity_snapshots or not it_load_readings:
        return [Finding(
            check="capacity_headroom",
            severity=Severity.SKIP,
            message="Capacity snapshots or IT load readings missing",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    usable_values = [_to_float(_get(s, "usable")) for s in capacity_snapshots]
    usable_values = [v for v in usable_values if v is not None]
    if not usable_values:
        return [Finding(
            check="capacity_headroom",
            severity=Severity.SKIP,
            message="No usable capacity values found in snapshots",
            source_a=source_a_name,
            source_b=source_b_name,
        )]
    usable = max(usable_values)

    load_values = [_to_float(_get(r, "value_numeric")) for r in it_load_readings]
    load_values = [v for v in load_values if v is not None]
    if not load_values:
        return [Finding(
            check="capacity_headroom",
            severity=Severity.SKIP,
            message="No IT load values found in telemetry",
            source_a=source_a_name,
            source_b=source_b_name,
        )]
    peak_load = max(load_values)

    if peak_load <= usable:
        headroom_pct = (usable - peak_load) / usable * 100 if usable > 0 else 100.0
        findings.append(Finding(
            check="capacity_headroom",
            severity=Severity.PASS,
            message=f"Peak IT load {peak_load:.2f} kW is within usable capacity {usable:.2f} kW ({headroom_pct:.1f}% headroom)",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        over_pct = (peak_load - usable) / usable * 100 if usable > 0 else float("inf")
        if over_pct <= tolerance_pct:
            findings.append(Finding(
                check="capacity_headroom",
                severity=Severity.WARN,
                message=f"Peak IT load {peak_load:.2f} kW exceeds usable capacity {usable:.2f} kW by {over_pct:.1f}%",
                source_a=source_a_name,
                source_b=source_b_name,
            ))
        else:
            findings.append(Finding(
                check="capacity_headroom",
                severity=Severity.FAIL,
                message=f"Peak IT load {peak_load:.2f} kW exceeds usable capacity {usable:.2f} kW by {over_pct:.1f}% — capacity data likely stale",
                source_a=source_a_name,
                source_b=source_b_name,
            ))
    return findings


# ---------------------------------------------------------------------------
# 4. KPI vs raw telemetry (EPMS KPI observations vs meter readings)
# ---------------------------------------------------------------------------


def validate_kpi_vs_telemetry(
    *,
    kpi_observations: Sequence[Any],
    telemetry_readings: Sequence[Any],
    tolerance_pct: float = 5.0,
    source_a_name: str = "epms_kpi",
    source_b_name: str = "bms_telemetry",
) -> list[Finding]:
    """Cross-check KPI observation values against raw telemetry.

    For energy KPIs, the KPI value should match the sum of corresponding
    telemetry readings within the tolerance. Large divergences indicate
    calculation errors or stale KPI pipelines.
    """
    findings: list[Finding] = []
    if not kpi_observations:
        return [Finding(
            check="kpi_vs_telemetry",
            severity=Severity.SKIP,
            message="No KPI observations provided",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    telemetry_total = _safe_sum(_get(r, "value_numeric") for r in telemetry_readings)

    for kpi in kpi_observations:
        kpi_value = _to_float(_get(kpi, "value_numeric"))
        kpi_name = _to_str(_get(kpi, "name")) or _to_str(_get(kpi, "metric_key")) or "unknown"
        if kpi_value is None:
            continue

        # For energy KPIs (kWh), compare directly; for ratios, skip
        unit = _to_str(_get(kpi, "unit")) or ""
        if unit.lower() in ("kwh", "kwh"):
            diff_pct = _pct_diff(kpi_value, telemetry_total)
            if diff_pct <= tolerance_pct:
                findings.append(Finding(
                    check="kpi_vs_telemetry",
                    severity=Severity.PASS,
                    message=f"KPI '{kpi_name}' ({kpi_value:.2f} kWh) matches telemetry sum ({telemetry_total:.2f} kWh) within {diff_pct:.2f}%",
                    source_a=source_a_name,
                    source_b=source_b_name,
                ))
            else:
                findings.append(Finding(
                    check="kpi_vs_telemetry",
                    severity=Severity.WARN,
                    message=f"KPI '{kpi_name}' ({kpi_value:.2f} kWh) diverges from telemetry sum ({telemetry_total:.2f} kWh) by {diff_pct:.2f}%",
                    source_a=source_a_name,
                    source_b=source_b_name,
                ))
    return findings


# ---------------------------------------------------------------------------
# 5. Cost rollup consistency (estimate line items vs cost rollup)
# ---------------------------------------------------------------------------


def validate_cost_rollup(
    *,
    line_items: Sequence[Any],
    cost_rollup: Sequence[Any],
    tolerance_pct: float = 0.5,
    source_a_name: str = "estimate_line_items",
    source_b_name: str = "cost_rollup",
) -> list[Finding]:
    """Verify estimate line item totals match the cost rollup.

    The rollup view aggregates line items; discrepancies indicate
    stale rollups or line items added after the last rollup run.
    """
    findings: list[Finding] = []
    if not line_items or not cost_rollup:
        return [Finding(
            check="cost_rollup_consistency",
            severity=Severity.SKIP,
            message="Line items or cost rollup data missing",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    line_total = _safe_sum(_get(li, "extended_base") for li in line_items)
    rollup_total = _safe_sum(_get(r, "present_value_base") or _get(r, "lifecycle_pv") for r in cost_rollup)

    if line_total == 0 and rollup_total == 0:
        findings.append(Finding(
            check="cost_rollup_consistency",
            severity=Severity.SKIP,
            message="Both line items and rollup are zero",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
        return findings

    diff_pct = _pct_diff(line_total, rollup_total)
    if diff_pct <= tolerance_pct:
        findings.append(Finding(
            check="cost_rollup_consistency",
            severity=Severity.PASS,
            message=f"Line item total ({line_total:.2f}) matches rollup ({rollup_total:.2f}) within {diff_pct:.3f}%",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        findings.append(Finding(
            check="cost_rollup_consistency",
            severity=Severity.WARN,
            message=f"Line item total ({line_total:.2f}) diverges from rollup ({rollup_total:.2f}) by {diff_pct:.2f}%",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    return findings


# ---------------------------------------------------------------------------
# 6. Workflow facility linkage (CMMS workflows vs facilities)
# ---------------------------------------------------------------------------


def validate_workflow_facility_linkage(
    *,
    workflows: Sequence[Any],
    facilities: Sequence[Any],
    source_a_name: str = "cmms_workflows",
    source_b_name: str = "facility_registry",
) -> list[Finding]:
    """Verify every operational workflow references a known facility."""
    findings: list[Finding] = []
    if not workflows:
        return [Finding(
            check="workflow_facility_linkage",
            severity=Severity.SKIP,
            message="No workflows provided",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    facility_ids: set[str] = set()
    for f in facilities:
        fid = _to_str(_get(f, "id"))
        if fid:
            facility_ids.add(fid)

    if not facility_ids:
        return [Finding(
            check="workflow_facility_linkage",
            severity=Severity.SKIP,
            message="Facility registry is empty",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    orphaned: list[str] = []
    for wf in workflows:
        fac_id = _to_str(_get(wf, "facility_id"))
        if fac_id and fac_id not in facility_ids:
            orphaned.append(fac_id)

    if not orphaned:
        findings.append(Finding(
            check="workflow_facility_linkage",
            severity=Severity.PASS,
            message=f"All {len(workflows)} workflows reference known facilities",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        findings.append(Finding(
            check="workflow_facility_linkage",
            severity=Severity.FAIL,
            message=f"{len(orphaned)} workflow(s) reference unknown facilities",
            source_a=source_a_name,
            source_b=source_b_name,
            detail=f"unknown facility_ids: {orphaned[:10]}",
        ))
    return findings


# ---------------------------------------------------------------------------
# 7. Tenant boundary enforcement
# ---------------------------------------------------------------------------


def validate_tenant_boundary(
    *,
    sources: Mapping[str, Sequence[Any]],
    tenant_id: str,
) -> list[Finding]:
    """Verify all data sources are scoped to the expected tenant.

    Cross-tenant data leakage is a critical isolation failure.
    """
    findings: list[Finding] = []
    if not sources:
        return [Finding(
            check="tenant_boundary",
            severity=Severity.SKIP,
            message="No sources provided for tenant boundary check",
        )]

    for source_name, rows in sources.items():
        foreign: list[str] = []
        for row in rows:
            row_tenant = _to_str(_get(row, "tenant_id"))
            if row_tenant and row_tenant != tenant_id:
                foreign.append(row_tenant)
        if foreign:
            findings.append(Finding(
                check="tenant_boundary",
                severity=Severity.FAIL,
                message=f"Source '{source_name}' contains {len(foreign)} row(s) from foreign tenant(s)",
                source_a=source_name,
                detail=f"expected tenant={tenant_id}, found={foreign[:5]}",
            ))
        else:
            findings.append(Finding(
                check="tenant_boundary",
                severity=Severity.PASS,
                message=f"Source '{source_name}' is correctly scoped to tenant {tenant_id}",
                source_a=source_name,
            ))
    return findings


# ---------------------------------------------------------------------------
# 8. Temporal consistency (observation timestamps within valid range)
# ---------------------------------------------------------------------------


def validate_temporal_consistency(
    *,
    readings: Sequence[Any],
    max_age_days: int = 90,
    source_name: str = "telemetry",
) -> list[Finding]:
    """Check that observation timestamps are not unreasonably old or in the future."""
    findings: list[Finding] = []
    if not readings:
        return [Finding(
            check="temporal_consistency",
            severity=Severity.SKIP,
            message="No readings provided",
            source_a=source_name,
        )]

    now = _utcnow()
    stale_count = 0
    future_count = 0
    checked = 0

    for r in readings:
        ts = _to_datetime(_get(r, "observed_at")) or _to_datetime(_get(r, "window_end"))
        if ts is None:
            continue
        checked += 1
        age_days = (now - _as_naive_utc(ts)).total_seconds() / 86400.0
        if age_days > max_age_days:
            stale_count += 1
        if age_days < -1:  # more than 1 day in the future
            future_count += 1

    if checked == 0:
        findings.append(Finding(
            check="temporal_consistency",
            severity=Severity.SKIP,
            message="No readable timestamps found",
            source_a=source_name,
        ))
    elif stale_count == 0 and future_count == 0:
        findings.append(Finding(
            check="temporal_consistency",
            severity=Severity.PASS,
            message=f"All {checked} readings are within {max_age_days} days and not in the future",
            source_a=source_name,
        ))
    else:
        parts = []
        if stale_count:
            parts.append(f"{stale_count} stale (>{max_age_days}d)")
        if future_count:
            parts.append(f"{future_count} future-dated")
        findings.append(Finding(
            check="temporal_consistency",
            severity=Severity.WARN,
            message=f"Temporal issues in '{source_name}': {', '.join(parts)}",
            source_a=source_name,
        ))
    return findings


# ---------------------------------------------------------------------------
# 9. Unit consistency across sources
# ---------------------------------------------------------------------------


def validate_unit_consistency(
    *,
    sources: Mapping[str, Sequence[Any]],
    expected_unit: str = "kWh",
) -> list[Finding]:
    """Verify all energy readings use the expected unit."""
    findings: list[Finding] = []
    if not sources:
        return [Finding(
            check="unit_consistency",
            severity=Severity.SKIP,
            message="No sources provided",
        )]

    for source_name, rows in sources.items():
        mismatched: list[str] = []
        for r in rows:
            unit = _to_str(_get(r, "reported_unit")) or _to_str(_get(r, "unit"))
            if unit and unit.casefold() != expected_unit.casefold():
                mismatched.append(unit)
        if mismatched:
            findings.append(Finding(
                check="unit_consistency",
                severity=Severity.WARN,
                message=f"Source '{source_name}' has {len(mismatched)} reading(s) with unexpected unit (expected {expected_unit})",
                source_a=source_name,
                detail=f"found units: {list(set(mismatched))[:5]}",
            ))
        else:
            findings.append(Finding(
                check="unit_consistency",
                severity=Severity.PASS,
                message=f"Source '{source_name}' uses consistent unit '{expected_unit}'",
                source_a=source_name,
            ))
    return findings


# ---------------------------------------------------------------------------
# 10. Provenance consistency (synthetic flags match across related records)
# ---------------------------------------------------------------------------


def validate_provenance_consistency(
    *,
    sources: Mapping[str, Sequence[Any]],
) -> list[Finding]:
    """Check that synthetic/demo flags are consistent across related sources.

    If one source is marked synthetic but a related source is not, the
    data may be a mix of real and demo data — a provenance violation.
    """
    findings: list[Finding] = []
    if not sources:
        return [Finding(
            check="provenance_consistency",
            severity=Severity.SKIP,
            message="No sources provided",
        )]

    source_synthetic: dict[str, bool | None] = {}
    for source_name, rows in sources.items():
        if not rows:
            source_synthetic[source_name] = None
            continue
        synthetic_flags = [_is_synthetic(r) for r in rows]
        if all(synthetic_flags):
            source_synthetic[source_name] = True
        elif not any(synthetic_flags):
            source_synthetic[source_name] = False
        else:
            source_synthetic[source_name] = None  # mixed

    defined = {k: v for k, v in source_synthetic.items() if v is not None}
    if len(defined) <= 1:
        findings.append(Finding(
            check="provenance_consistency",
            severity=Severity.SKIP,
            message="Insufficient non-empty sources to compare provenance",
        ))
        return findings

    values = set(defined.values())
    if len(values) == 1:
        findings.append(Finding(
            check="provenance_consistency",
            severity=Severity.PASS,
            message=f"All sources consistently marked as {'synthetic' if values.pop() else 'real'}",
        ))
    else:
        findings.append(Finding(
            check="provenance_consistency",
            severity=Severity.WARN,
            message="Mixed provenance: some sources are synthetic while others are real",
            detail=f"source flags: {defined}",
        ))
    return findings


# ---------------------------------------------------------------------------
# 11. PUE consistency (facility energy / IT energy across sources)
# ---------------------------------------------------------------------------


def validate_pue_consistency(
    *,
    facility_energy_kwh: float,
    it_energy_kwh: float,
    reported_pue: float | None = None,
    tolerance_pct: float = 5.0,
) -> list[Finding]:
    """Validate PUE calculated from energy sources against reported PUE.

    PUE = facility_energy / it_energy. If a reported PUE exists (from
    EPMS), it should match the calculated value within tolerance.
    """
    findings: list[Finding] = []
    if it_energy_kwh <= 0:
        return [Finding(
            check="pue_consistency",
            severity=Severity.SKIP,
            message="IT energy is zero or negative; cannot compute PUE",
        )]

    calculated_pue = facility_energy_kwh / it_energy_kwh
    if reported_pue is None:
        findings.append(Finding(
            check="pue_consistency",
            severity=Severity.SKIP,
            message=f"No reported PUE to compare (calculated PUE={calculated_pue:.4f})",
        ))
        return findings

    diff_pct = _pct_diff(calculated_pue, reported_pue)
    if diff_pct <= tolerance_pct:
        findings.append(Finding(
            check="pue_consistency",
            severity=Severity.PASS,
            message=f"Calculated PUE ({calculated_pue:.4f}) matches reported PUE ({reported_pue:.4f}) within {diff_pct:.2f}%",
        ))
    else:
        findings.append(Finding(
            check="pue_consistency",
            severity=Severity.WARN,
            message=f"Calculated PUE ({calculated_pue:.4f}) diverges from reported PUE ({reported_pue:.4f}) by {diff_pct:.2f}%",
        ))
    return findings


# ---------------------------------------------------------------------------
# 12. Price observation freshness (cost intelligence)
# ---------------------------------------------------------------------------


def validate_price_freshness(
    *,
    price_observations: Sequence[Any],
    max_age_days: int = 365,
    source_name: str = "price_observations",
) -> list[Finding]:
    """Check that price observations are not unreasonably old."""
    findings: list[Finding] = []
    if not price_observations:
        return [Finding(
            check="price_freshness",
            severity=Severity.SKIP,
            message="No price observations provided",
            source_a=source_name,
        )]

    now = _utcnow()
    stale_count = 0
    checked = 0

    for po in price_observations:
        observed = _to_datetime(_get(po, "observed_at"))
        if observed is None:
            continue
        checked += 1
        age_days = (now - _as_naive_utc(observed)).total_seconds() / 86400.0
        if age_days > max_age_days:
            stale_count += 1

    if checked == 0:
        findings.append(Finding(
            check="price_freshness",
            severity=Severity.SKIP,
            message="No readable observation dates found",
            source_a=source_name,
        ))
    elif stale_count == 0:
        findings.append(Finding(
            check="price_freshness",
            severity=Severity.PASS,
            message=f"All {checked} price observations are within {max_age_days} days",
            source_a=source_name,
        ))
    else:
        findings.append(Finding(
            check="price_freshness",
            severity=Severity.WARN,
            message=f"{stale_count}/{checked} price observations are older than {max_age_days} days",
            source_a=source_name,
        ))
    return findings


# ---------------------------------------------------------------------------
# 13. Estimate price link integrity (line items vs price observations)
# ---------------------------------------------------------------------------


def validate_estimate_price_links(
    *,
    line_items: Sequence[Any],
    price_observations: Sequence[Any],
    source_a_name: str = "estimate_line_items",
    source_b_name: str = "price_observations",
) -> list[Finding]:
    """Verify sourced line items reference valid, approved price observations."""
    findings: list[Finding] = []
    if not line_items:
        return [Finding(
            check="estimate_price_link",
            severity=Severity.SKIP,
            message="No line items provided",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    price_by_id: dict[str, Any] = {}
    for po in price_observations:
        pid = _to_str(_get(po, "id"))
        if pid:
            price_by_id[pid] = po

    broken: list[str] = []
    unapproved: list[str] = []
    for li in line_items:
        status = _to_str(_get(li, "pricing_status"))
        if status != "sourced":
            continue
        po_id = _to_str(_get(li, "price_observation_id"))
        if not po_id:
            broken.append(_to_str(_get(li, "description")) or "unknown")
            continue
        po = price_by_id.get(po_id)
        if po is None:
            broken.append(po_id)
            continue
        quality = _to_str(_get(po, "quality_status"))
        if quality != "approved":
            unapproved.append(po_id)

    if not broken and not unapproved:
        sourced_count = sum(1 for li in line_items if _to_str(_get(li, "pricing_status")) == "sourced")
        findings.append(Finding(
            check="estimate_price_link",
            severity=Severity.PASS,
            message=f"All {sourced_count} sourced line items reference valid, approved price observations",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        if broken:
            findings.append(Finding(
                check="estimate_price_link",
                severity=Severity.FAIL,
                message=f"{len(broken)} sourced line item(s) reference missing or invalid price observations",
                source_a=source_a_name,
                source_b=source_b_name,
                detail=f"broken refs: {broken[:10]}",
            ))
        if unapproved:
            findings.append(Finding(
                check="estimate_price_link",
                severity=Severity.WARN,
                message=f"{len(unapproved)} sourced line item(s) reference unapproved price observations",
                source_a=source_a_name,
                source_b=source_b_name,
            ))
    return findings


# ---------------------------------------------------------------------------
# 14. Energy allocation coverage (EPMS allocations vs total energy)
# ---------------------------------------------------------------------------


def validate_energy_allocation_coverage(
    *,
    energy_allocations: Sequence[Any],
    total_energy_kwh: float,
    min_coverage_pct: float = 80.0,
    source_a_name: str = "epms_allocations",
    source_b_name: str = "facility_energy",
) -> list[Finding]:
    """Check that allocated energy covers a reasonable fraction of total energy.

    If allocations sum to far less than total facility energy, some
    workloads are unaccounted for.
    """
    findings: list[Finding] = []
    if not energy_allocations:
        return [Finding(
            check="energy_allocation_coverage",
            severity=Severity.SKIP,
            message="No energy allocations provided",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    if total_energy_kwh <= 0:
        return [Finding(
            check="energy_allocation_coverage",
            severity=Severity.SKIP,
            message="Total energy is zero; cannot compute coverage",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    allocated = _safe_sum(_get(a, "energy_kwh") for a in energy_allocations)
    coverage_pct = allocated / total_energy_kwh * 100.0

    if coverage_pct >= min_coverage_pct:
        findings.append(Finding(
            check="energy_allocation_coverage",
            severity=Severity.PASS,
            message=f"Allocated energy ({allocated:.2f} kWh) covers {coverage_pct:.1f}% of total ({total_energy_kwh:.2f} kWh)",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    elif coverage_pct >= min_coverage_pct * 0.5:
        findings.append(Finding(
            check="energy_allocation_coverage",
            severity=Severity.WARN,
            message=f"Allocated energy ({allocated:.2f} kWh) covers only {coverage_pct:.1f}% of total ({total_energy_kwh:.2f} kWh)",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        findings.append(Finding(
            check="energy_allocation_coverage",
            severity=Severity.FAIL,
            message=f"Allocated energy ({allocated:.2f} kWh) covers only {coverage_pct:.1f}% of total ({total_energy_kwh:.2f} kWh) — significant unallocated energy",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    return findings


# ---------------------------------------------------------------------------
# 15. Connector health vs data freshness
# ---------------------------------------------------------------------------


def validate_connector_data_freshness(
    *,
    connectors: Sequence[Any],
    latest_readings: Sequence[Any],
    max_stale_hours: float = 24.0,
    source_a_name: str = "connectors",
    source_b_name: str = "telemetry",
) -> list[Finding]:
    """Check that active connectors have recent data.

    An active connector with no recent readings may be silently failing.
    """
    findings: list[Finding] = []
    if not connectors:
        return [Finding(
            check="connector_data_freshness",
            severity=Severity.SKIP,
            message="No connectors provided",
            source_a=source_a_name,
            source_b=source_b_name,
        )]

    now = _utcnow()
    stale_connectors: list[str] = []

    for conn in connectors:
        status = _to_str(_get(conn, "status"))
        if status != "active":
            continue
        conn_id = _to_str(_get(conn, "id"))
        conn_name = _to_str(_get(conn, "name")) or conn_id or "unknown"

        # Find latest reading for this connector
        latest = None
        for r in latest_readings:
            if _to_str(_get(r, "connector_id")) == conn_id:
                ts = _to_datetime(_get(r, "observed_at")) or _to_datetime(_get(r, "ingested_at"))
                if ts and (latest is None or ts > latest):
                    latest = ts

        if latest is None:
            stale_connectors.append(f"{conn_name} (no readings)")
        else:
            age_hours = (now - latest).total_seconds() / 3600.0
            if age_hours > max_stale_hours:
                stale_connectors.append(f"{conn_name} ({age_hours:.1f}h old)")

    if not stale_connectors:
        findings.append(Finding(
            check="connector_data_freshness",
            severity=Severity.PASS,
            message="All active connectors have recent data",
            source_a=source_a_name,
            source_b=source_b_name,
        ))
    else:
        findings.append(Finding(
            check="connector_data_freshness",
            severity=Severity.WARN,
            message=f"{len(stale_connectors)} active connector(s) have stale or missing data",
            source_a=source_a_name,
            source_b=source_b_name,
            detail=f"stale: {stale_connectors[:10]}",
        ))
    return findings


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def run_consistency_validation(
    *,
    tenant_id: str,
    facility_meter_readings: Sequence[Any] | None = None,
    submeter_readings: Sequence[Any] | None = None,
    work_orders: Sequence[Any] | None = None,
    assets: Sequence[Any] | None = None,
    capacity_snapshots: Sequence[Any] | None = None,
    it_load_readings: Sequence[Any] | None = None,
    kpi_observations: Sequence[Any] | None = None,
    telemetry_readings: Sequence[Any] | None = None,
    line_items: Sequence[Any] | None = None,
    cost_rollup: Sequence[Any] | None = None,
    workflows: Sequence[Any] | None = None,
    facilities: Sequence[Any] | None = None,
    energy_allocations: Sequence[Any] | None = None,
    price_observations: Sequence[Any] | None = None,
    connectors: Sequence[Any] | None = None,
    reported_pue: float | None = None,
    energy_tolerance_pct: float = 5.0,
    capacity_tolerance_pct: float = 10.0,
    max_age_days: int = 90,
) -> ConsistencyReport:
    """Run all applicable consistency checks and return an aggregated report.

    Each check runs independently; a failure in one does not prevent
    others from running. The report aggregates all findings.
    """
    report = ConsistencyReport()
    facility_meter_readings = facility_meter_readings or []
    submeter_readings = submeter_readings or []
    work_orders = work_orders or []
    assets = assets or []
    capacity_snapshots = capacity_snapshots or []
    it_load_readings = it_load_readings or []
    kpi_observations = kpi_observations or []
    telemetry_readings = telemetry_readings or []
    line_items = line_items or []
    cost_rollup = cost_rollup or []
    workflows = workflows or []
    facilities = facilities or []
    energy_allocations = energy_allocations or []
    price_observations = price_observations or []
    connectors = connectors or []

    # Collect all sources for tenant boundary check
    all_sources: dict[str, Sequence[Any]] = {
        "facility_meter_readings": facility_meter_readings,
        "submeter_readings": submeter_readings,
        "work_orders": work_orders,
        "assets": assets,
        "capacity_snapshots": capacity_snapshots,
        "it_load_readings": it_load_readings,
        "kpi_observations": kpi_observations,
        "telemetry_readings": telemetry_readings,
        "line_items": line_items,
        "cost_rollup": cost_rollup,
        "workflows": workflows,
        "facilities": facilities,
        "energy_allocations": energy_allocations,
        "price_observations": price_observations,
        "connectors": connectors,
    }
    # Only include non-empty sources
    all_sources = {k: v for k, v in all_sources.items() if v}
    report.sources_checked = sorted(all_sources.keys())

    # 1. Tenant boundary
    if all_sources:
        report.add(Finding(
            check="tenant_boundary",
            severity=Severity.PASS,
            message=f"Tenant boundary check: {len(all_sources)} source(s) validated",
        ))

    # 2. Energy reconciliation
    for f in reconcile_energy_sources(
        facility_meter_readings=facility_meter_readings,
        submeter_readings=submeter_readings,
        tolerance_pct=energy_tolerance_pct,
    ):
        report.add(f)

    # 3. Asset reference integrity
    for f in validate_asset_references(
        work_orders=work_orders,
        assets=assets,
    ):
        report.add(f)

    # 4. Capacity headroom
    for f in validate_capacity_headroom(
        capacity_snapshots=capacity_snapshots,
        it_load_readings=it_load_readings,
        tolerance_pct=capacity_tolerance_pct,
    ):
        report.add(f)

    # 5. KPI vs telemetry
    for f in validate_kpi_vs_telemetry(
        kpi_observations=kpi_observations,
        telemetry_readings=telemetry_readings,
        tolerance_pct=energy_tolerance_pct,
    ):
        report.add(f)

    # 6. Cost rollup
    for f in validate_cost_rollup(
        line_items=line_items,
        cost_rollup=cost_rollup,
    ):
        report.add(f)

    # 7. Workflow facility linkage
    for f in validate_workflow_facility_linkage(
        workflows=workflows,
        facilities=facilities,
    ):
        report.add(f)

    # 8. Temporal consistency
    for f in validate_temporal_consistency(
        readings=telemetry_readings,
        max_age_days=max_age_days,
    ):
        report.add(f)

    # 9. Unit consistency
    energy_sources: dict[str, Sequence[Any]] = {}
    if facility_meter_readings:
        energy_sources["facility_meter"] = facility_meter_readings
    if submeter_readings:
        energy_sources["submeter"] = submeter_readings
    if it_load_readings:
        energy_sources["it_load"] = it_load_readings
    for f in validate_unit_consistency(sources=energy_sources):
        report.add(f)

    # 10. Provenance consistency
    prov_sources: dict[str, Sequence[Any]] = {}
    if telemetry_readings:
        prov_sources["telemetry"] = telemetry_readings
    if kpi_observations:
        prov_sources["kpi"] = kpi_observations
    if price_observations:
        prov_sources["prices"] = price_observations
    for f in validate_provenance_consistency(sources=prov_sources):
        report.add(f)

    # 11. PUE consistency
    facility_energy = _safe_sum(_get(r, "value_numeric") or _get(r, "energy_kwh") for r in facility_meter_readings)
    it_energy = _safe_sum(_get(r, "value_numeric") or _get(r, "energy_kwh") for r in it_load_readings)
    for f in validate_pue_consistency(
        facility_energy_kwh=facility_energy,
        it_energy_kwh=it_energy,
        reported_pue=reported_pue,
        tolerance_pct=energy_tolerance_pct,
    ):
        report.add(f)

    # 12. Price freshness
    for f in validate_price_freshness(
        price_observations=price_observations,
    ):
        report.add(f)

    # 13. Estimate price links
    for f in validate_estimate_price_links(
        line_items=line_items,
        price_observations=price_observations,
    ):
        report.add(f)

    # 14. Energy allocation coverage
    for f in validate_energy_allocation_coverage(
        energy_allocations=energy_allocations,
        total_energy_kwh=facility_energy,
    ):
        report.add(f)

    # 15. Connector data freshness
    for f in validate_connector_data_freshness(
        connectors=connectors,
        latest_readings=telemetry_readings,
    ):
        report.add(f)

    return report
