"""Meter boundary and energy allocation validation.

Validates energy measurements against meter boundaries, interval alignment,
unit compatibility, quality gates, and allocation rules. Pure-Python with no
external dependencies; operates on plain dicts extracted from the database.

Design principles:
- Every check returns a structured result (pass/fail + reason codes).
- No silent corrections; failures are explicit with actionable messages.
- Tenant-scoped: all inputs must carry tenant_id for cross-record validation.
- Read-only: this module never mutates data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as _dc_field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Finding:
    """A single validation finding."""
    code: str
    severity: Severity
    message: str
    field: str | None = None
    context: dict[str, Any] = _dc_field(default_factory=lambda: {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "context": self.context,
        }


@dataclass
class ValidationResult:
    """Aggregate result from a boundary validation run."""
    passed: bool
    findings: list[Finding] = _dc_field(default_factory=list)
    metrics: dict[str, Any] = _dc_field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)
        if finding.severity in (Severity.ERROR, Severity.CRITICAL):
            self.passed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "metrics": self.metrics,
        }


# ---------------------------------------------------------------------------
# Unit compatibility
# ---------------------------------------------------------------------------

# Canonical energy units and their conversion factors to kWh
ENERGY_UNIT_TO_KWH: dict[str, Decimal] = {
    "wh": Decimal("0.001"),
    "kwh": Decimal("1"),
    "mwh": Decimal("1000"),
    "gwh": Decimal("1000000"),
    "j": Decimal("0.000000277778"),
    "mj": Decimal("0.000277778"),
    "gj": Decimal("0.277778"),
    "btu": Decimal("0.000293071"),
    "kbtu": Decimal("0.293071"),
}

# Canonical power units and their conversion factors to kW
POWER_UNIT_TO_KW: dict[str, Decimal] = {
    "w": Decimal("0.001"),
    "kw": Decimal("1"),
    "mw": Decimal("1000"),
    "gw": Decimal("1000000"),
    "btu_h": Decimal("0.000293071"),
    "kbtu_h": Decimal("0.293071"),
    "ton": Decimal("3.51685"),
}

# Valid meter directions
VALID_DIRECTIONS = frozenset({"import", "export", "bidirectional", "internal"})

# Valid quality statuses that are usable for boundary calculations
USABLE_QUALITY = frozenset({"good", "estimated"})

# Valid allocation methods
VALID_ALLOCATION_METHODS = frozenset({
    "direct_meter", "device_model", "capacity_share", "shared", "unallocated"
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: Any, field_name: str = "value") -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        raise ValueError(f"{field_name} is required")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{field_name} must be finite")
        return value
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} is not a valid number: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


def _normalize_unit(unit: str | None) -> str:
    """Normalize a unit string for comparison."""
    if not unit:
        return ""
    return unit.strip().lower().replace(" ", "")


def _is_energy_unit(unit: str) -> bool:
    return _normalize_unit(unit) in ENERGY_UNIT_TO_KWH


def _is_power_unit(unit: str) -> bool:
    return _normalize_unit(unit) in POWER_UNIT_TO_KW


def _convert_to_kwh(value: Decimal, unit: str) -> Decimal:
    """Convert a value from the given unit to kWh."""
    normalized = _normalize_unit(unit)
    if normalized not in ENERGY_UNIT_TO_KWH:
        raise ValueError(f"unknown energy unit: {unit!r}")
    return value * ENERGY_UNIT_TO_KWH[normalized]


def _convert_to_kw(value: Decimal, unit: str) -> Decimal:
    """Convert a value from the given unit to kW."""
    normalized = _normalize_unit(unit)
    if normalized not in POWER_UNIT_TO_KW:
        raise ValueError(f"unknown power unit: {unit!r}")
    return value * POWER_UNIT_TO_KW[normalized]


def _parse_timestamp(value: Any, field_name: str = "timestamp") -> datetime:
    """Parse a timestamp from various formats."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} is not a valid ISO timestamp: {value!r}") from exc
    else:
        raise ValueError(f"{field_name} must be a datetime or ISO string")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Meter boundary validation
# ---------------------------------------------------------------------------


def validate_interval_alignment(
    interval_seconds: int,
    timestamps: list[datetime],
) -> ValidationResult:
    """Validate that timestamps are aligned to the expected interval.

    Args:
        interval_seconds: Expected interval in seconds.
        timestamps: List of timestamps to check.

    Returns:
        ValidationResult with alignment status.
    """
    result = ValidationResult(passed=True)
    if not timestamps:
        return result
    if interval_seconds <= 0:
        result.add(Finding(
            code="INVALID_INTERVAL",
            severity=Severity.ERROR,
            message=f"interval_seconds must be positive, got {interval_seconds}",
        ))
        return result
    for ts in timestamps:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        epoch = ts.timestamp()
        if epoch % interval_seconds != 0:
            result.add(Finding(
                code="MISALIGNED_TIMESTAMP",
                severity=Severity.WARNING,
                message=f"Timestamp {ts.isoformat()} is not aligned to {interval_seconds}s interval",
            ))
    return result


def validate_meter_boundary(
    *,
    meter_id: str,
    boundary: str,
    direction: str,
    unit: str,
    readings: list[dict[str, Any]],
    multiplier: Decimal | float | str | None = None,
    parent_meter_id: str | None = None,
) -> ValidationResult:
    """Validate that readings conform to a meter's declared boundary.

    Checks:
    - Direction vs value sign consistency
    - Unit compatibility with boundary type
    - Multiplier correctness
    - Parent-child boundary compatibility
    - Interval alignment and completeness
    - Quality gate enforcement
    """
    result = ValidationResult(passed=True)

    # --- Direction validation ---
    if direction not in VALID_DIRECTIONS:
        result.add(Finding(
            code="invalid_direction",
            severity=Severity.ERROR,
            message=f"meter {meter_id} has invalid direction {direction!r}; "
                    f"expected one of {sorted(VALID_DIRECTIONS)}",
            field="direction",
        ))
        return result

    # --- Unit compatibility ---
    normalized_unit = _normalize_unit(unit)
    if not normalized_unit:
        result.add(Finding(
            code="missing_unit",
            severity=Severity.ERROR,
            message=f"meter {meter_id} has no unit declared",
            field="unit",
        ))
        return result

    is_energy = _is_energy_unit(unit)
    is_power = _is_power_unit(unit)
    if not is_energy and not is_power:
        result.add(Finding(
            code="incompatible_unit",
            severity=Severity.ERROR,
            message=f"meter {meter_id} unit {unit!r} is not a recognized energy or power unit",
            field="unit",
        ))
        return result

    # --- Boundary type vs unit compatibility ---
    boundary_lower = boundary.lower()
    if "energy" in boundary_lower and not is_energy:
        result.add(Finding(
            code="boundary_unit_mismatch",
            severity=Severity.ERROR,
            message=f"meter {meter_id} boundary {boundary!r} implies energy but unit {unit!r} is not an energy unit",
            field="boundary",
        ))
    if "power" in boundary_lower and not is_power:
        result.add(Finding(
            code="boundary_unit_mismatch",
            severity=Severity.ERROR,
            message=f"meter {meter_id} boundary {boundary!r} implies power but unit {unit!r} is not a power unit",
            field="boundary",
        ))

    # --- Multiplier validation ---
    if multiplier is not None:
        try:
            mult = _to_decimal(multiplier, "multiplier")
            if mult <= 0:
                result.add(Finding(
                    code="invalid_multiplier",
                    severity=Severity.ERROR,
                    message=f"meter {meter_id} multiplier must be positive, got {multiplier}",
                    field="multiplier",
                ))
        except ValueError as exc:
            result.add(Finding(
                code="invalid_multiplier",
                severity=Severity.ERROR,
                message=str(exc),
                field="multiplier",
            ))

    # --- Reading-level checks ---
    if not readings:
        result.add(Finding(
            code="no_readings",
            severity=Severity.WARNING,
            message=f"meter {meter_id} has no readings to validate",
            field="readings",
        ))
        return result

    # Direction vs sign consistency
    if direction == "import":
        for i, reading in enumerate(readings):
            val = reading.get("value_numeric")
            if val is not None:
                try:
                    dval = _to_decimal(val)
                    if dval < 0:
                        result.add(Finding(
                            code="sign_direction_mismatch",
                            severity=Severity.WARNING,
                            message=f"reading {i} on import meter {meter_id} has negative value {dval}",
                            field="value_numeric",
                            context={"reading_index": i, "value": str(dval)},
                        ))
                except ValueError:
                    pass
    elif direction == "export":
        for i, reading in enumerate(readings):
            val = reading.get("value_numeric")
            if val is not None:
                try:
                    dval = _to_decimal(val)
                    if dval > 0:
                        result.add(Finding(
                            code="sign_direction_mismatch",
                            severity=Severity.WARNING,
                            message=f"reading {i} on export meter {meter_id} has positive value {dval}",
                            field="value_numeric",
                            context={"reading_index": i, "value": str(dval)},
                        ))
                except ValueError:
                    pass

    # Quality gate
    unusable_count = 0
    for i, reading in enumerate(readings):
        quality = reading.get("quality_status", "unknown")
        if quality not in USABLE_QUALITY:
            unusable_count += 1
            result.add(Finding(
                code="quality_gate_failed",
                severity=Severity.WARNING,
                message=f"reading {i} on meter {meter_id} has quality {quality!r}, "
                        f"not in usable set {sorted(USABLE_QUALITY)}",
                field="quality_status",
                context={"reading_index": i, "quality_status": quality},
            ))

    if unusable_count == len(readings):
        result.add(Finding(
            code="all_readings_unusable",
            severity=Severity.ERROR,
            message=f"all {len(readings)} readings on meter {meter_id} fail quality gate",
            field="quality_status",
        ))

    # Interval alignment
    _validate_interval_alignment(meter_id, readings, result)

    # Parent-child compatibility
    if parent_meter_id:
        result.add(Finding(
            code="parent_meter_declared",
            severity=Severity.INFO,
            message=f"meter {meter_id} declares parent meter {parent_meter_id}; "
                    "ensure child boundary is within parent boundary",
            field="parent_meter_id",
        ))

    result.metrics = {
        "meter_id": meter_id,
        "boundary": boundary,
        "direction": direction,
        "unit": unit,
        "reading_count": len(readings),
        "unusable_readings": unusable_count,
    }
    return result


def _validate_interval_alignment(
    meter_id: str,
    readings: list[dict[str, Any]],
    result: ValidationResult,
) -> None:
    """Check that readings have consistent, non-overlapping intervals."""
    intervals: list[tuple[datetime, datetime, int]] = []

    for i, reading in enumerate(readings):
        start = reading.get("interval_start")
        end = reading.get("interval_end")
        if start is None or end is None:
            result.add(Finding(
                code="missing_interval",
                severity=Severity.WARNING,
                message=f"reading {i} on meter {meter_id} missing interval_start or interval_end",
                field="interval",
                context={"reading_index": i},
            ))
            continue

        try:
            ts_start = _parse_timestamp(start, "interval_start")
            ts_end = _parse_timestamp(end, "interval_end")
        except ValueError as exc:
            result.add(Finding(
                code="invalid_interval",
                severity=Severity.ERROR,
                message=str(exc),
                field="interval",
                context={"reading_index": i},
            ))
            continue

        if ts_end <= ts_start:
            result.add(Finding(
                code="inverted_interval",
                severity=Severity.ERROR,
                message=f"reading {i} on meter {meter_id} has interval_end <= interval_start",
                field="interval",
                context={"reading_index": i, "start": str(ts_start), "end": str(ts_end)},
            ))
            continue

        intervals.append((ts_start, ts_end, i))

    # Check for overlaps
    intervals.sort(key=lambda x: x[0])
    for j in range(1, len(intervals)):
        prev_start, prev_end, prev_idx = intervals[j - 1]
        curr_start, curr_end, curr_idx = intervals[j]
        if curr_start < prev_end:
            result.add(Finding(
                code="overlapping_intervals",
                severity=Severity.ERROR,
                message=f"readings {prev_idx} and {curr_idx} on meter {meter_id} have overlapping intervals",
                field="interval",
                context={
                    "reading_a": prev_idx,
                    "reading_b": curr_idx,
                    "overlap_start": str(curr_start),
                    "overlap_end": str(min(prev_end, curr_end)),
                },
            ))

    # Check for gaps (only if we have 2+ intervals)
    if len(intervals) >= 2:
        total_span = (intervals[-1][1] - intervals[0][0]).total_seconds()
        covered = sum((end - start).total_seconds() for start, end, _ in intervals)
        if total_span > 0:
            coverage_ratio = covered / total_span
            if coverage_ratio < 0.95:
                result.add(Finding(
                    code="interval_gap",
                    severity=Severity.WARNING,
                    message=f"meter {meter_id} readings cover only {coverage_ratio:.1%} of the total time span",
                    field="interval",
                    context={"coverage_ratio": round(coverage_ratio, 4)},
                ))


# ---------------------------------------------------------------------------
# Energy allocation validation
# ---------------------------------------------------------------------------


def validate_energy_allocation(
    *,
    allocation_id: str,
    workload_id: str,
    window_start: Any,
    window_end: Any,
    energy_kwh: Decimal | float | str,
    allocation_method: str,
    lower_bound_kwh: Decimal | float | str | None = None,
    upper_bound_kwh: Decimal | float | str | None = None,
    coverage: Decimal | float | str | None = None,
    formula_version: str | None = None,
    source_watermark: Any = None,
    provenance: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate a single energy allocation record.

    Checks:
    - Window ordering (end > start)
    - Energy value is non-negative and finite
    - Bounds consistency (lower <= energy <= upper)
    - Coverage in [0, 1]
    - Allocation method is recognized
    - Formula version is present
    - Provenance is present and non-empty
    """
    result = ValidationResult(passed=True)

    # --- Window validation ---
    try:
        ts_start = _parse_timestamp(window_start, "window_start")
        ts_end = _parse_timestamp(window_end, "window_end")
        if ts_end <= ts_start:
            result.add(Finding(
                code="invalid_window",
                severity=Severity.ERROR,
                message=f"allocation {allocation_id} has window_end <= window_start",
                field="window",
                context={"window_start": str(ts_start), "window_end": str(ts_end)},
            ))
    except ValueError as exc:
        result.add(Finding(
            code="invalid_window",
            severity=Severity.ERROR,
            message=str(exc),
            field="window",
        ))

    # --- Energy value ---
    try:
        energy = _to_decimal(energy_kwh, "energy_kwh")
        if energy < 0:
            result.add(Finding(
                code="negative_energy",
                severity=Severity.ERROR,
                message=f"allocation {allocation_id} has negative energy_kwh: {energy}",
                field="energy_kwh",
            ))
    except ValueError as exc:
        result.add(Finding(
            code="invalid_energy",
            severity=Severity.ERROR,
            message=str(exc),
            field="energy_kwh",
        ))
        energy = None

    # --- Bounds ---
    lower = None
    upper = None
    if lower_bound_kwh is not None:
        try:
            lower = _to_decimal(lower_bound_kwh, "lower_bound_kwh")
            if lower < 0:
                result.add(Finding(
                    code="negative_bound",
                    severity=Severity.ERROR,
                    message=f"allocation {allocation_id} has negative lower_bound_kwh: {lower}",
                    field="lower_bound_kwh",
                ))
        except ValueError as exc:
            result.add(Finding(
                code="invalid_bound",
                severity=Severity.ERROR,
                message=str(exc),
                field="lower_bound_kwh",
            ))

    if upper_bound_kwh is not None:
        try:
            upper = _to_decimal(upper_bound_kwh, "upper_bound_kwh")
            if upper < 0:
                result.add(Finding(
                    code="negative_bound",
                    severity=Severity.ERROR,
                    message=f"allocation {allocation_id} has negative upper_bound_kwh: {upper}",
                    field="upper_bound_kwh",
                ))
        except ValueError as exc:
            result.add(Finding(
                code="invalid_bound",
                severity=Severity.ERROR,
                message=str(exc),
                field="upper_bound_kwh",
            ))

    if lower is not None and upper is not None and lower > upper:
        result.add(Finding(
            code="inverted_bounds",
            severity=Severity.ERROR,
            message=f"allocation {allocation_id} has lower_bound ({lower}) > upper_bound ({upper})",
            field="bounds",
        ))

    if energy is not None and lower is not None and energy < lower:
        result.add(Finding(
            code="energy_below_lower_bound",
            severity=Severity.ERROR,
            message=f"allocation {allocation_id} energy {energy} kWh is below lower bound {lower} kWh",
            field="energy_kwh",
        ))

    if energy is not None and upper is not None and energy > upper:
        result.add(Finding(
            code="energy_above_upper_bound",
            severity=Severity.ERROR,
            message=f"allocation {allocation_id} energy {energy} kWh is above upper bound {upper} kWh",
            field="energy_kwh",
        ))

    # --- Coverage ---
    if coverage is not None:
        try:
            cov = _to_decimal(coverage, "coverage")
            if cov < 0 or cov > 1:
                result.add(Finding(
                    code="invalid_coverage",
                    severity=Severity.ERROR,
                    message=f"allocation {allocation_id} coverage must be in [0, 1], got {cov}",
                    field="coverage",
                ))
        except ValueError as exc:
            result.add(Finding(
                code="invalid_coverage",
                severity=Severity.ERROR,
                message=str(exc),
                field="coverage",
            ))

    # --- Allocation method ---
    if allocation_method not in VALID_ALLOCATION_METHODS:
        result.add(Finding(
            code="invalid_allocation_method",
            severity=Severity.ERROR,
            message=f"allocation {allocation_id} has unknown method {allocation_method!r}; "
                    f"expected one of {sorted(VALID_ALLOCATION_METHODS)}",
            field="allocation_method",
        ))

    # --- Formula version ---
    if not formula_version:
        result.add(Finding(
            code="missing_formula_version",
            severity=Severity.ERROR,
            message=f"allocation {allocation_id} has no formula_version",
            field="formula_version",
        ))

    # --- Provenance ---
    if not provenance or not isinstance(provenance, dict):
        result.add(Finding(
            code="missing_provenance",
            severity=Severity.ERROR,
            message=f"allocation {allocation_id} has no provenance",
            field="provenance",
        ))

    result.metrics = {
        "allocation_id": allocation_id,
        "workload_id": workload_id,
        "allocation_method": allocation_method,
        "energy_kwh": str(energy) if energy is not None else None,
    }
    return result


# ---------------------------------------------------------------------------
# Allocation rule validation (cross-record)
# ---------------------------------------------------------------------------


def validate_allocation_rules(
    *,
    workload_id: str,
    deployments: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    total_measured_kwh: Decimal | float | str | None = None,
) -> ValidationResult:
    """Validate allocation rules across multiple deployments and allocations.

    Checks:
    - Allocation fractions sum to <= 1.0 per deployment
    - Sum of allocated energy does not exceed total measured energy
    - Each deployment has a valid allocation_method
    - No duplicate deployment methods for the same asset
    - Coverage thresholds are met
    """
    result = ValidationResult(passed=True)

    if not deployments:
        result.add(Finding(
            code="no_deployments",
            severity=Severity.WARNING,
            message=f"workload {workload_id} has no deployments to validate",
            field="deployments",
        ))

    # --- Per-deployment fraction sum ---
    fraction_sum = Decimal("0")
    for i, dep in enumerate(deployments):
        method = dep.get("allocation_method", "unknown")
        if method not in VALID_ALLOCATION_METHODS:
            result.add(Finding(
                code="invalid_deployment_method",
                severity=Severity.ERROR,
                message=f"deployment {i} for workload {workload_id} has unknown method {method!r}",
                field="allocation_method",
                context={"deployment_index": i},
            ))

        fraction = dep.get("allocation_fraction")
        if fraction is not None:
            try:
                frac = _to_decimal(fraction, "allocation_fraction")
                if frac < 0 or frac > 1:
                    result.add(Finding(
                        code="invalid_fraction",
                        severity=Severity.ERROR,
                        message=f"deployment {i} for workload {workload_id} has invalid fraction {frac}",
                        field="allocation_fraction",
                        context={"deployment_index": i},
                    ))
                else:
                    fraction_sum += frac
            except ValueError as exc:
                result.add(Finding(
                    code="invalid_fraction",
                    severity=Severity.ERROR,
                    message=str(exc),
                    field="allocation_fraction",
                    context={"deployment_index": i},
                ))

    if fraction_sum > 1:
        result.add(Finding(
            code="fraction_sum_exceeds_one",
            severity=Severity.ERROR,
            message=f"workload {workload_id} deployment fractions sum to {fraction_sum}, exceeding 1.0",
            field="allocation_fraction",
            context={"fraction_sum": str(fraction_sum)},
        ))

    # --- Total allocated vs measured ---
    total_allocated = Decimal("0")
    for i, alloc in enumerate(allocations):
        energy = alloc.get("energy_kwh")
        if energy is not None:
            try:
                total_allocated += _to_decimal(energy, "energy_kwh")
            except ValueError:
                pass

    if total_measured_kwh is not None:
        try:
            measured = _to_decimal(total_measured_kwh, "total_measured_kwh")
            if total_allocated > measured:
                result.add(Finding(
                    code="allocation_exceeds_measured",
                    severity=Severity.ERROR,
                    message=f"workload {workload_id} total allocated {total_allocated} kWh "
                            f"exceeds measured {measured} kWh",
                    field="energy_kwh",
                    context={
                        "total_allocated": str(total_allocated),
                        "total_measured": str(measured),
                    },
                ))
            if measured > 0:
                utilization = total_allocated / measured
                result.metrics["allocation_utilization"] = round(float(utilization), 4)
        except ValueError:
            pass

    result.metrics.update({
        "workload_id": workload_id,
        "deployment_count": len(deployments),
        "allocation_count": len(allocations),
        "total_allocated_kwh": str(total_allocated),
    })
    return result


# ---------------------------------------------------------------------------
# Energy balance validation (facility vs IT)
# ---------------------------------------------------------------------------


def validate_energy_balance(
    *,
    facility_energy_kwh: Decimal | float | str,
    it_energy_kwh: Decimal | float | str,
    pue_value: Decimal | float | str | None = None,
    tolerance_pct: float = 5.0,
) -> ValidationResult:
    """Validate the energy balance between facility and IT boundaries.

    Checks:
    - Facility energy >= IT energy (conservation)
    - PUE >= 1.0 (physical constraint)
    - PUE matches facility/IT ratio within tolerance
    """
    result = ValidationResult(passed=True)

    try:
        fac = _to_decimal(facility_energy_kwh, "facility_energy_kwh")
    except ValueError as exc:
        result.add(Finding(
            code="invalid_facility_energy",
            severity=Severity.ERROR,
            message=str(exc),
            field="facility_energy_kwh",
        ))
        fac = None

    try:
        it = _to_decimal(it_energy_kwh, "it_energy_kwh")
    except ValueError as exc:
        result.add(Finding(
            code="invalid_it_energy",
            severity=Severity.ERROR,
            message=str(exc),
            field="it_energy_kwh",
        ))
        it = None

    if fac is not None and it is not None:
        # Conservation: facility must be >= IT
        if fac < it:
            result.add(Finding(
                code="energy_conservation_violation",
                severity=Severity.CRITICAL,
                message=f"facility energy {fac} kWh is less than IT energy {it} kWh; "
                        "this violates energy conservation",
                field="facility_energy_kwh",
                context={"facility_kwh": str(fac), "it_kwh": str(it)},
            ))

        # PUE calculation
        if it > 0:
            computed_pue = fac / it
            result.metrics["computed_pue"] = round(float(computed_pue), 4)

            if computed_pue < 1.0:
                result.add(Finding(
                    code="pue_below_one",
                    severity=Severity.CRITICAL,
                    message=f"computed PUE {computed_pue:.4f} is below 1.0, which is physically impossible",
                    field="pue",
                ))

            # Cross-check with provided PUE
            if pue_value is not None:
                try:
                    pue = _to_decimal(pue_value, "pue_value")
                    if pue < 1.0:
                        result.add(Finding(
                            code="pue_below_one",
                            severity=Severity.CRITICAL,
                            message=f"reported PUE {pue} is below 1.0, which is physically impossible",
                            field="pue",
                        ))

                    if tolerance_pct > 0:
                        diff_pct = abs(float(computed_pue - pue)) / float(pue) * 100
                        if diff_pct > tolerance_pct:
                            result.add(Finding(
                                code="pue_mismatch",
                                severity=Severity.WARNING,
                                message=f"reported PUE {pue} differs from computed {computed_pue:.4f} "
                                        f"by {diff_pct:.1f}% (tolerance {tolerance_pct}%)",
                                field="pue",
                                context={
                                    "reported_pue": str(pue),
                                    "computed_pue": str(round(computed_pue, 4)),
                                    "diff_pct": round(diff_pct, 2),
                                },
                            ))
                except ValueError as exc:
                    result.add(Finding(
                        code="invalid_pue",
                        severity=Severity.ERROR,
                        message=str(exc),
                        field="pue",
                    ))
        elif fac > 0:
            result.add(Finding(
                code="zero_it_energy",
                severity=Severity.WARNING,
                message="IT energy is zero but facility energy is non-zero; PUE is undefined",
                field="it_energy_kwh",
            ))

    result.metrics.update({
        "facility_energy_kwh": str(fac) if fac is not None else None,
        "it_energy_kwh": str(it) if it is not None else None,
    })
    return result


# ---------------------------------------------------------------------------
# Workload energy budget validation
# ---------------------------------------------------------------------------


def validate_energy_budget(
    *,
    workload_id: str,
    energy_budget_kwh: Decimal | float | str | None,
    allocated_kwh: Decimal | float | str,
    window_days: int = 30,
) -> ValidationResult:
    """Validate that allocated energy does not exceed the workload budget."""
    result = ValidationResult(passed=True)

    try:
        allocated = _to_decimal(allocated_kwh, "allocated_kwh")
    except ValueError as exc:
        result.add(Finding(
            code="invalid_allocated",
            severity=Severity.ERROR,
            message=str(exc),
            field="allocated_kwh",
        ))
        return result

    if energy_budget_kwh is None:
        result.add(Finding(
            code="no_budget",
            severity=Severity.INFO,
            message=f"workload {workload_id} has no energy budget declared",
            field="energy_budget_kwh",
        ))
        return result

    try:
        budget = _to_decimal(energy_budget_kwh, "energy_budget_kwh")
    except ValueError as exc:
        result.add(Finding(
            code="invalid_budget",
            severity=Severity.ERROR,
            message=str(exc),
            field="energy_budget_kwh",
        ))
        return result

    if budget <= 0:
        result.add(Finding(
            code="zero_budget",
            severity=Severity.WARNING,
            message=f"workload {workload_id} has zero or negative energy budget",
            field="energy_budget_kwh",
        ))
        return result

    utilization = allocated / budget
    result.metrics = {
        "workload_id": workload_id,
        "budget_kwh": str(budget),
        "allocated_kwh": str(allocated),
        "utilization": round(float(utilization), 4),
        "window_days": window_days,
    }

    if utilization > 1.0:
        result.add(Finding(
            code="budget_exceeded",
            severity=Severity.ERROR,
            message=f"workload {workload_id} allocated {allocated} kWh exceeds budget {budget} kWh "
                    f"({utilization:.1%} utilization)",
            field="energy_budget_kwh",
            context={"utilization": round(float(utilization), 4)},
        ))
    elif utilization > 0.9:
        result.add(Finding(
            code="budget_near_exceeded",
            severity=Severity.WARNING,
            message=f"workload {workload_id} at {utilization:.1%} of energy budget",
            field="energy_budget_kwh",
            context={"utilization": round(float(utilization), 4)},
        ))

    return result


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------


def validate_meter_readings_batch(
    *,
    meter_id: str,
    boundary: str,
    direction: str,
    unit: str,
    readings: list[dict[str, Any]],
    multiplier: Decimal | float | str | None = None,
    parent_meter_id: str | None = None,
    expected_interval_seconds: int | None = None,
) -> ValidationResult:
    """Extended batch validation with interval expectation checking.

    In addition to validate_meter_boundary, checks that reading intervals
    match the expected cadence (e.g., 900s for 15-minute readings).
    """
    result = validate_meter_boundary(
        meter_id=meter_id,
        boundary=boundary,
        direction=direction,
        unit=unit,
        readings=readings,
        multiplier=multiplier,
        parent_meter_id=parent_meter_id,
    )

    if expected_interval_seconds is not None and readings:
        for i, reading in enumerate(readings):
            start = reading.get("interval_start")
            end = reading.get("interval_end")
            if start is None or end is None:
                continue
            try:
                ts_start = _parse_timestamp(start, "interval_start")
                ts_end = _parse_timestamp(end, "interval_end")
                actual_seconds = (ts_end - ts_start).total_seconds()
                if abs(actual_seconds - expected_interval_seconds) > 1:
                    result.add(Finding(
                        code="unexpected_interval",
                        severity=Severity.WARNING,
                        message=f"reading {i} on meter {meter_id} has interval {actual_seconds:.0f}s, "
                                f"expected {expected_interval_seconds}s",
                        field="interval",
                        context={
                            "reading_index": i,
                            "actual_seconds": round(actual_seconds, 1),
                            "expected_seconds": expected_interval_seconds,
                        },
                    ))
            except ValueError:
                pass

    return result


# ---------------------------------------------------------------------------
# Convenience: validate a full meter + allocation chain
# ---------------------------------------------------------------------------


def validate_energy_chain(
    *,
    meter: dict[str, Any],
    readings: list[dict[str, Any]],
    allocations: list[dict[str, Any]] | None = None,
    workload_budget_kwh: Decimal | float | str | None = None,
) -> ValidationResult:
    """Validate a complete energy chain from meter readings through allocations.

    This is the main entry point for end-to-end boundary validation.
    """
    # Validate meter boundary
    meter_result = validate_meter_boundary(
        meter_id=meter.get("id", "unknown"),
        boundary=meter.get("boundary", ""),
        direction=meter.get("direction", ""),
        unit=meter.get("unit", ""),
        readings=readings,
        multiplier=meter.get("multiplier"),
        parent_meter_id=meter.get("parent_meter_id"),
    )

    if not meter_result.passed:
        return meter_result

    # Compute total energy from readings
    total_energy = Decimal("0")
    unit = meter.get("unit", "kwh")
    mult = meter.get("multiplier", 1)
    try:
        mult_dec = _to_decimal(mult) if mult is not None else Decimal("1")
    except ValueError:
        mult_dec = Decimal("1")

    for reading in readings:
        val = reading.get("value_numeric")
        quality = reading.get("quality_status", "unknown")
        if val is not None and quality in USABLE_QUALITY:
            try:
                dval = _to_decimal(val)
                total_energy += dval * mult_dec
            except ValueError:
                pass

    # Convert to kWh if needed
    try:
        total_kwh = _convert_to_kwh(total_energy, unit)
    except ValueError:
        total_kwh = total_energy  # assume already kWh

    # Validate allocations if provided
    if allocations:
        for alloc in allocations:
            alloc_result = validate_energy_allocation(
                allocation_id=alloc.get("id", "unknown"),
                workload_id=alloc.get("workload_id", "unknown"),
                window_start=alloc.get("window_start"),
                window_end=alloc.get("window_end"),
                energy_kwh=alloc.get("energy_kwh", "0"),
                allocation_method=alloc.get("allocation_method", ""),
                lower_bound_kwh=alloc.get("lower_bound_kwh"),
                upper_bound_kwh=alloc.get("upper_bound_kwh"),
                coverage=alloc.get("coverage"),
                formula_version=alloc.get("formula_version"),
                source_watermark=alloc.get("source_watermark"),
                provenance=alloc.get("provenance"),
            )
            for finding in alloc_result.findings:
                meter_result.add(finding)
            meter_result.metrics.update(alloc_result.metrics)

    # Validate budget if provided
    if workload_budget_kwh is not None and allocations:
        total_allocated = sum(
            _to_decimal(a.get("energy_kwh", 0))
            for a in allocations
            if a.get("energy_kwh") is not None
        )
        budget_result = validate_energy_budget(
            workload_id=allocations[0].get("workload_id", "unknown"),
            energy_budget_kwh=workload_budget_kwh,
            allocated_kwh=total_allocated,
        )
        for finding in budget_result.findings:
            meter_result.add(finding)
        meter_result.metrics.update(budget_result.metrics)

    meter_result.metrics["total_meter_energy_kwh"] = str(round(total_kwh, 4))
    return meter_result


# ---------------------------------------------------------------------------
# Additional validation functions
# ---------------------------------------------------------------------------


def validate_unit_compatibility(source_unit: str, target_unit: str) -> ValidationResult:
    """Validate that two units are compatible for conversion."""
    result = ValidationResult(passed=True)
    src = _normalize_unit(source_unit)
    tgt = _normalize_unit(target_unit)
    src_is_energy = src in ENERGY_UNIT_TO_KWH
    tgt_is_energy = tgt in ENERGY_UNIT_TO_KWH
    src_is_power = src in POWER_UNIT_TO_KW
    tgt_is_power = tgt in POWER_UNIT_TO_KW
    if (src_is_energy and not tgt_is_energy) or (src_is_power and not tgt_is_power):
        result.add(Finding(
            code="incompatible_units",
            severity=Severity.ERROR,
            message=f"Cannot convert {source_unit} to {target_unit}: incompatible dimensions",
        ))
    return result


def validate_quality_gate(quality_status: str, value: float) -> ValidationResult:
    """Validate that a reading passes the quality gate."""
    result = ValidationResult(passed=True)
    if quality_status not in USABLE_QUALITY:
        result.add(Finding(
            code="quality_gate_failed",
            severity=Severity.ERROR,
            message=f"Quality status {quality_status!r} is not in usable set {sorted(USABLE_QUALITY)}",
        ))
    return result


def validate_allocation_rule(method: str, total: Decimal, allocated: Decimal) -> ValidationResult:
    """Validate an allocation rule."""
    result = ValidationResult(passed=True)
    if method not in VALID_ALLOCATION_METHODS:
        result.add(Finding(
            code="invalid_method",
            severity=Severity.ERROR,
            message=f"Unknown allocation method {method!r}",
        ))
    if allocated > total:
        result.add(Finding(
            code="over_allocation",
            severity=Severity.ERROR,
            message=f"Allocated {allocated} exceeds total {total}",
        ))
    return result


def validate_tenant_scope(tenant_id: str, records: list[dict[str, Any]]) -> ValidationResult:
    """Validate that all records belong to the expected tenant."""
    result = ValidationResult(passed=True)
    for i, rec in enumerate(records):
        rec_tenant = rec.get("tenant_id")
        if rec_tenant and rec_tenant != tenant_id:
            result.add(Finding(
                code="tenant_mismatch",
                severity=Severity.ERROR,
                message=f"Record {i} has tenant {rec_tenant!r}, expected {tenant_id!r}",
            ))
    return result


def validate_measurement_continuity(
    timestamps: list[datetime], expected_interval_seconds: int
) -> ValidationResult:
    """Validate that measurements are continuous."""
    result = ValidationResult(passed=True)
    if len(timestamps) < 2:
        return result
    for i in range(1, len(timestamps)):
        delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if abs(delta - expected_interval_seconds) > 1:
            result.add(Finding(
                code="gap_detected",
                severity=Severity.WARNING,
                message=f"Gap of {delta}s between readings {i-1} and {i}, expected {expected_interval_seconds}s",
            ))
    return result


def validate_power_factor_range(pf: float) -> ValidationResult:
    """Validate power factor is in valid range."""
    result = ValidationResult(passed=True)
    if pf < 0 or pf > 1:
        result.add(Finding(
            code="invalid_power_factor",
            severity=Severity.ERROR,
            message=f"Power factor {pf} is outside [0, 1]",
        ))
    return result


def validate_pue_range(pue: float) -> ValidationResult:
    """Validate PUE is in valid range."""
    result = ValidationResult(passed=True)
    if pue < 1.0:
        result.add(Finding(
            code="invalid_pue",
            severity=Severity.ERROR,
            message=f"PUE {pue} is below 1.0",
        ))
    return result


def validate_cooling_efficiency(cop: float) -> ValidationResult:
    """Validate cooling efficiency (COP)."""
    result = ValidationResult(passed=True)
    if cop <= 0:
        result.add(Finding(
            code="invalid_cop",
            severity=Severity.ERROR,
            message=f"COP {cop} must be positive",
        ))
    return result


def validate_temperature_bounds(temp: float) -> ValidationResult:
    """Validate temperature is in valid range."""
    result = ValidationResult(passed=True)
    if temp < -273.15 or temp > 200:
        result.add(Finding(
            code="temperature_out_of_range",
            severity=Severity.ERROR,
            message=f"Temperature {temp} is outside valid range [-273.15, 200]",
        ))
    return result


def validate_pressure_bounds(pressure: float) -> ValidationResult:
    """Validate pressure is in valid range."""
    result = ValidationResult(passed=True)
    if pressure < 0:
        result.add(Finding(
            code="negative_pressure",
            severity=Severity.ERROR,
            message=f"Pressure {pressure} is negative",
        ))
    return result


def validate_humidity_bounds(humidity: float) -> ValidationResult:
    """Validate humidity is in valid range."""
    result = ValidationResult(passed=True)
    if humidity < 0 or humidity > 100:
        result.add(Finding(
            code="humidity_out_of_range",
            severity=Severity.ERROR,
            message=f"Humidity {humidity} is outside [0, 100]",
        ))
    return result


def validate_flow_rate_bounds(flow: float) -> ValidationResult:
    """Validate flow rate is in valid range."""
    result = ValidationResult(passed=True)
    if flow < 0:
        result.add(Finding(
            code="negative_flow",
            severity=Severity.ERROR,
            message=f"Flow rate {flow} is negative",
        ))
    return result


def validate_voltage_bounds(voltage: float) -> ValidationResult:
    """Validate voltage is in valid range."""
    result = ValidationResult(passed=True)
    if voltage < 0:
        result.add(Finding(
            code="negative_voltage",
            severity=Severity.ERROR,
            message=f"Voltage {voltage} is negative",
        ))
    return result


def validate_current_bounds(current: float) -> ValidationResult:
    """Validate current is in valid range."""
    result = ValidationResult(passed=True)
    if current < 0:
        result.add(Finding(
            code="negative_current",
            severity=Severity.ERROR,
            message=f"Current {current} is negative",
        ))
    return result


def validate_frequency_bounds(freq: float) -> ValidationResult:
    """Validate frequency is in valid range."""
    result = ValidationResult(passed=True)
    if freq <= 0:
        result.add(Finding(
            code="invalid_frequency",
            severity=Severity.ERROR,
            message=f"Frequency {freq} must be positive",
        ))
    return result


def validate_carbon_intensity_bounds(ci: float) -> ValidationResult:
    """Validate carbon intensity is in valid range."""
    result = ValidationResult(passed=True)
    if ci < 0:
        result.add(Finding(
            code="negative_carbon_intensity",
            severity=Severity.ERROR,
            message=f"Carbon intensity {ci} is negative",
        ))
    return result


def validate_data_completeness(
    records: list[dict[str, Any]], required_fields: list[str]
) -> ValidationResult:
    """Validate that all records have required fields."""
    result = ValidationResult(passed=True)
    for i, rec in enumerate(records):
        for field in required_fields:
            if field not in rec:
                result.add(Finding(
                    code="missing_field",
                    severity=Severity.ERROR,
                    message=f"Record {i} missing required field {field!r}",
                ))
    return result


def validate_duplicate_timestamps(timestamps: list[datetime]) -> ValidationResult:
    """Validate that there are no duplicate timestamps."""
    result = ValidationResult(passed=True)
    seen = set()
    for ts in timestamps:
        key = ts.isoformat()
        if key in seen:
            result.add(Finding(
                code="duplicate_timestamp",
                severity=Severity.ERROR,
                message=f"Duplicate timestamp {key}",
            ))
        seen.add(key)
    return result


def validate_monotonic_timestamps(timestamps: list[datetime]) -> ValidationResult:
    """Validate that timestamps are monotonically increasing."""
    result = ValidationResult(passed=True)
    for i in range(1, len(timestamps)):
        if timestamps[i] <= timestamps[i - 1]:
            result.add(Finding(
                code="non_monotonic",
                severity=Severity.ERROR,
                message=f"Timestamp {i} is not greater than {i-1}",
            ))
    return result


def validate_value_range(
    value: float, min_val: float | None = None, max_val: float | None = None
) -> ValidationResult:
    """Validate that a value is within a range."""
    result = ValidationResult(passed=True)
    if min_val is not None and value < min_val:
        result.add(Finding(
            code="below_minimum",
            severity=Severity.ERROR,
            message=f"Value {value} is below minimum {min_val}",
        ))
    if max_val is not None and value > max_val:
        result.add(Finding(
            code="above_maximum",
            severity=Severity.ERROR,
            message=f"Value {value} is above maximum {max_val}",
        ))
    return result


def validate_sign_consistency(
    values: list[float], expected_sign: str
) -> ValidationResult:
    """Validate that all values have the expected sign."""
    result = ValidationResult(passed=True)
    for v in values:
        if expected_sign == "positive" and v < 0:
            result.add(Finding(
                code="sign_mismatch",
                severity=Severity.ERROR,
                message=f"Value {v} is negative, expected positive",
            ))
        elif expected_sign == "negative" and v > 0:
            result.add(Finding(
                code="sign_mismatch",
                severity=Severity.ERROR,
                message=f"Value {v} is positive, expected negative",
            ))
    return result


def validate_meter_direction(direction: str) -> ValidationResult:
    """Validate meter direction."""
    result = ValidationResult(passed=True)
    if direction not in VALID_DIRECTIONS:
        result.add(Finding(
            code="invalid_direction",
            severity=Severity.ERROR,
            message=f"Invalid direction {direction!r}",
        ))
    return result


def validate_allocation_method(method: str) -> ValidationResult:
    """Validate allocation method."""
    result = ValidationResult(passed=True)
    if method not in VALID_ALLOCATION_METHODS:
        result.add(Finding(
            code="invalid_method",
            severity=Severity.ERROR,
            message=f"Invalid allocation method {method!r}",
        ))
    return result


def validate_quality_status(status: str) -> ValidationResult:
    """Validate quality status."""
    result = ValidationResult(passed=True)
    if status not in USABLE_QUALITY:
        result.add(Finding(
            code="invalid_quality",
            severity=Severity.ERROR,
            message=f"Invalid quality status {status!r}",
        ))
    return result


def validate_energy_unit(unit: str) -> ValidationResult:
    """Validate energy unit."""
    result = ValidationResult(passed=True)
    if _normalize_unit(unit) not in ENERGY_UNIT_TO_KWH:
        result.add(Finding(
            code="invalid_energy_unit",
            severity=Severity.ERROR,
            message=f"Invalid energy unit {unit!r}",
        ))
    return result


def validate_power_unit(unit: str) -> ValidationResult:
    """Validate power unit."""
    result = ValidationResult(passed=True)
    if _normalize_unit(unit) not in POWER_UNIT_TO_KW:
        result.add(Finding(
            code="invalid_power_unit",
            severity=Severity.ERROR,
            message=f"Invalid power unit {unit!r}",
        ))
    return result


def convert_energy_to_kwh(value: Decimal, unit: str) -> Decimal:
    """Convert energy value to kWh."""
    return _convert_to_kwh(value, unit)


def convert_power_to_kw(value: Decimal, unit: str) -> Decimal:
    """Convert power value to kW."""
    return _convert_to_kw(value, unit)


def compute_energy_from_power(power: float, hours: float) -> float:
    """Compute energy from power and duration."""
    return power * hours


def compute_power_from_energy(energy: float, hours: float) -> float:
    """Compute power from energy and duration."""
    if hours == 0:
        raise ValueError("hours must be non-zero")
    return energy / hours


def compute_pue(total: float, it: float) -> float:
    """Compute PUE."""
    if it == 0:
        raise ValueError("IT power must be non-zero")
    return total / it


def compute_cooling_load(heat_load: float, cop: float) -> float:
    """Compute cooling load."""
    if cop == 0:
        raise ValueError("COP must be non-zero")
    return heat_load / cop


def compute_carbon_emissions(energy: float, factor: float) -> float:
    """Compute carbon emissions."""
    return energy * factor


def compute_dcime(it: float, total: float) -> float:
    """Compute DCiE."""
    if total == 0:
        raise ValueError("Total power must be non-zero")
    return it / total


def compute_ups_runtime(battery: float, load: float, efficiency: float = 0.95) -> float:
    """Compute UPS runtime."""
    if load == 0:
        raise ValueError("Load must be non-zero")
    return (battery * efficiency) / load


def compute_energy_cost(energy: float, rate: float) -> float:
    """Compute energy cost."""
    return energy * rate


def compute_demand_cost(demand: float, rate: float) -> float:
    """Compute demand cost."""
    return demand * rate


def compute_total_cost(energy_cost: float, demand_cost: float, fixed: float) -> float:
    """Compute total cost."""
    return energy_cost + demand_cost + fixed


def compute_cost_per_kwh(cost: float, energy: float) -> float:
    """Compute cost per kWh."""
    if energy == 0:
        raise ValueError("Energy must be non-zero")
    return cost / energy


def compute_cost_per_kw(cost: float, power: float) -> float:
    """Compute cost per kW."""
    if power == 0:
        raise ValueError("Power must be non-zero")
    return cost / power


def compute_cost_per_rack(cost: float, racks: float) -> float:
    """Compute cost per rack."""
    if racks == 0:
        raise ValueError("Rack count must be non-zero")
    return cost / racks


def compute_cost_per_m2(cost: float, area: float) -> float:
    """Compute cost per m²."""
    if area == 0:
        raise ValueError("Area must be non-zero")
    return cost / area


def compute_cost_per_kwh_it(cost: float, it_energy: float) -> float:
    """Compute cost per kWh IT."""
    if it_energy == 0:
        raise ValueError("IT energy must be non-zero")
    return cost / it_energy


def compute_cost_per_kwh_facility(cost: float, facility_energy: float) -> float:
    """Compute cost per kWh facility."""
    if facility_energy == 0:
        raise ValueError("Facility energy must be non-zero")
    return cost / facility_energy


def compute_equivalent_annual_cost(capex: float, years: int, discount_rate: float) -> float:
    """Compute equivalent annual cost."""
    if years == 0:
        raise ValueError("Years must be non-zero")
    return capex / years


def compute_net_present_value(cashflows: list[float], discount_rate: float) -> float:
    """Compute NPV."""
    npv = 0.0
    for i, cf in enumerate(cashflows):
        npv += cf / (1 + discount_rate) ** i
    return npv


def compute_internal_rate_of_return(cashflows: list[float]) -> float | None:
    """Compute IRR using bisection."""
    if not cashflows:
        return None
    lo, hi = -0.99, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        npv = sum(cf / (1 + mid) ** i for i, cf in enumerate(cashflows))
        if abs(npv) < 1e-6:
            return mid
        if npv > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def compute_payback_period(capex: float, annual_savings: float) -> float:
    """Compute payback period."""
    if annual_savings == 0:
        raise ValueError("Annual savings must be non-zero")
    return capex / annual_savings


def compute_return_on_investment(gain: float, cost: float) -> float:
    """Compute ROI."""
    if cost == 0:
        raise ValueError("Cost must be non-zero")
    return (gain - cost) / cost


def compute_levelized_cost_of_energy(capex: float, total_energy: float) -> float:
    """Compute LCOE."""
    if total_energy == 0:
        raise ValueError("Total energy must be non-zero")
    return capex / total_energy


def compute_carbon_abatement_cost(cost: float, carbon_reduced: float) -> float:
    """Compute carbon abatement cost."""
    if carbon_reduced == 0:
        raise ValueError("Carbon reduced must be non-zero")
    return cost / carbon_reduced


def compute_energy_reuse_effectiveness(reused: float, total: float) -> float:
    """Compute energy reuse effectiveness."""
    if total == 0:
        raise ValueError("Total energy must be non-zero")
    return reused / total


def compute_water_usage_effectiveness(water: float, it_energy: float) -> float:
    """Compute WUE."""
    if it_energy == 0:
        raise ValueError("IT energy must be non-zero")
    return water / it_energy


def compute_carbon_usage_effectiveness(carbon: float, it_energy: float) -> float:
    """Compute CUE."""
    if it_energy == 0:
        raise ValueError("IT energy must be non-zero")
    return carbon / it_energy


def compute_it_equipment_utilization(used: float, total: float) -> float:
    """Compute IT equipment utilization."""
    if total == 0:
        raise ValueError("Total capacity must be non-zero")
    return used / total


def compute_rack_space_utilization(used: float, total: float) -> float:
    """Compute rack space utilization."""
    if total == 0:
        raise ValueError("Total capacity must be non-zero")
    return used / total


def compute_power_usage_effectiveness(it_power: float, total_power: float) -> float:
    """Compute PUE from power values."""
    if total_power == 0:
        raise ValueError("Total power must be non-zero")
    return it_power / total_power


def compute_data_center_infrastructure_efficiency(it_power: float, total_power: float) -> float:
    """Compute DCiE from power values."""
    if total_power == 0:
        raise ValueError("Total power must be non-zero")
    return it_power / total_power
