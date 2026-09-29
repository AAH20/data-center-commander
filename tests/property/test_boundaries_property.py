"""Property-based tests for boundary and interval validation.

Tests invariants that should hold for all valid inputs:
- Meter boundary validation is deterministic
- Direction-sign consistency is monotonic
- Interval alignment detects overlaps correctly
- Allocation bounds are enforced
- Energy balance conservation holds
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from dcc.validation.boundaries import (
    Finding,
    Severity,
    ValidationResult,
    validate_energy_allocation,
    validate_energy_balance,
    validate_energy_budget,
    validate_meter_boundary,
    validate_meter_readings_batch,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

finite_floats = st.floats(
    min_value=-1e12,
    max_value=1e12,
    allow_nan=False,
    allow_infinity=False,
)

positive_floats = st.floats(
    min_value=0.001,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)

directions = st.sampled_from(["import", "export", "bidirectional", "internal"])
quality_statuses = st.sampled_from(["good", "estimated", "unknown", "bad", "missing"])

valid_directions = st.sampled_from(["import", "export", "bidirectional", "internal"])
invalid_directions = st.sampled_from(["", "invalid", "INPUT", "Import", "expor"])

energy_units = st.sampled_from(["kWh", "Wh", "MWh", "GWh", "J", "MJ", "BTU"])
power_units = st.sampled_from(["kW", "W", "MW", "GW"])


def make_reading(
    value: float,
    quality: str = "good",
    interval_start: datetime | None = None,
    interval_end: datetime | None = None,
) -> dict:
    """Create a meter reading dict."""
    r: dict = {"value_numeric": value, "quality_status": quality}
    if interval_start is not None:
        r["interval_start"] = interval_start
    if interval_end is not None:
        r["interval_end"] = interval_end
    return r


def make_base_time() -> datetime:
    """Create a base datetime for interval tests."""
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Meter boundary validation properties
# ---------------------------------------------------------------------------


@given(
    direction=valid_directions,
    unit=energy_units,
    readings=st.lists(
        st.fixed_dictionaries({
            "value_numeric": finite_floats,
            "quality_status": quality_statuses,
        }),
        min_size=0,
        max_size=20,
    ),
)
@settings(max_examples=200)
def test_meter_boundary_valid_direction_passes(direction, unit, readings):
    """Valid direction and energy unit should not produce ERROR findings."""
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    error_findings = [f for f in result.findings if f.severity == Severity.ERROR]
    assert len(error_findings) == 0, f"Unexpected errors: {[f.message for f in error_findings]}"


@given(
    direction=invalid_directions,
    unit=energy_units,
)
@settings(max_examples=100)
def test_meter_boundary_invalid_direction_fails(direction, unit):
    """Invalid direction should produce an ERROR finding."""
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=[],
    )
    error_findings = [f for f in result.findings if f.severity == Severity.ERROR]
    assert len(error_findings) >= 1
    assert any(f.code == "invalid_direction" for f in error_findings)


@given(
    direction=directions,
    unit=st.sampled_from(["invalid", "", "xyz"]),
)
@settings(max_examples=100)
def test_meter_boundary_unknown_unit_fails(direction, unit):
    """Unknown unit should produce an ERROR finding."""
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=[],
    )
    error_findings = [f for f in result.findings if f.severity == Severity.ERROR]
    assert len(error_findings) >= 1


@given(
    direction=st.sampled_from(["import"]),
    unit=energy_units,
    values=st.lists(
        st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=200)
def test_meter_boundary_import_positive_values_pass(direction, unit, values):
    """Import meter with positive values should not produce sign warnings."""
    readings = [make_reading(v) for v in values]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    sign_findings = [f for f in result.findings if f.code == "sign_direction_mismatch"]
    assert len(sign_findings) == 0


@given(
    direction=st.sampled_from(["import"]),
    unit=energy_units,
    values=st.lists(
        st.floats(min_value=-1e6, max_value=-0.001, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=200)
def test_meter_boundary_import_negative_values_warns(direction, unit, values):
    """Import meter with negative values should produce sign warnings."""
    readings = [make_reading(v) for v in values]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    sign_findings = [f for f in result.findings if f.code == "sign_direction_mismatch"]
    assert len(sign_findings) >= 1


@given(
    direction=st.sampled_from(["export"]),
    unit=energy_units,
    values=st.lists(
        st.floats(min_value=0.001, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=200)
def test_meter_boundary_export_positive_values_warns(direction, unit, values):
    """Export meter with positive values should produce sign warnings."""
    readings = [make_reading(v) for v in values]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    sign_findings = [f for f in result.findings if f.code == "sign_direction_mismatch"]
    assert len(sign_findings) >= 1


@given(
    direction=st.sampled_from(["export"]),
    unit=energy_units,
    values=st.lists(
        st.floats(min_value=-1e6, max_value=0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=200)
def test_meter_boundary_export_negative_values_pass(direction, unit, values):
    """Export meter with negative values should not produce sign warnings."""
    readings = [make_reading(v) for v in values]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    sign_findings = [f for f in result.findings if f.code == "sign_direction_mismatch"]
    assert len(sign_findings) == 0


# ---------------------------------------------------------------------------
# Interval alignment properties
# ---------------------------------------------------------------------------


@given(
    num_readings=st.integers(min_value=2, max_value=20),
    interval_seconds=st.integers(min_value=60, max_value=3600),
)
@settings(max_examples=200)
def test_interval_no_overlap_when_sequential(num_readings, interval_seconds):
    """Sequential non-overlapping intervals should not produce overlap errors."""
    base = make_base_time()
    readings = []
    for i in range(num_readings):
        start = base + timedelta(seconds=i * interval_seconds)
        end = start + timedelta(seconds=interval_seconds)
        readings.append(make_reading(float(i + 1), interval_start=start, interval_end=end))
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction="import",
        unit="kWh",
        readings=readings,
    )
    overlap_findings = [f for f in result.findings if f.code == "overlapping_intervals"]
    assert len(overlap_findings) == 0


@given(
    num_readings=st.integers(min_value=2, max_value=10),
    interval_seconds=st.integers(min_value=60, max_value=3600),
)
@settings(max_examples=200)
def test_interval_overlap_detected(num_readings, interval_seconds):
    """Overlapping intervals should produce overlap errors."""
    base = make_base_time()
    readings = []
    for i in range(num_readings):
        # All start at the same time -> guaranteed overlap
        start = base
        end = start + timedelta(seconds=interval_seconds)
        readings.append(make_reading(float(i + 1), interval_start=start, interval_end=end))
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction="import",
        unit="kWh",
        readings=readings,
    )
    overlap_findings = [f for f in result.findings if f.code == "overlapping_intervals"]
    assert len(overlap_findings) >= 1


@given(
    num_readings=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=200)
def test_interval_inverted_detected(num_readings):
    """Inverted intervals (end <= start) should produce errors."""
    base = make_base_time()
    readings = []
    for i in range(num_readings):
        start = base + timedelta(hours=i + 1)
        end = base + timedelta(hours=i)  # end before start
        readings.append(make_reading(float(i + 1), interval_start=start, interval_end=end))
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction="import",
        unit="kWh",
        readings=readings,
    )
    inverted_findings = [f for f in result.findings if f.code == "inverted_interval"]
    assert len(inverted_findings) >= 1


# ---------------------------------------------------------------------------
# Quality gate properties
# ---------------------------------------------------------------------------


@given(
    direction=valid_directions,
    unit=energy_units,
    quality=st.sampled_from(["bad", "missing", "unknown"]),
    num_readings=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=200)
def test_quality_gate_unusable_warns(direction, unit, quality, num_readings):
    """Unusable quality status should produce warnings."""
    readings = [make_reading(100.0, quality=quality) for _ in range(num_readings)]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    quality_findings = [f for f in result.findings if f.code == "quality_gate_failed"]
    assert len(quality_findings) >= 1


@given(
    direction=valid_directions,
    unit=energy_units,
    num_readings=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=200)
def test_quality_gate_all_unusable_errors(direction, unit, num_readings):
    """All readings unusable should produce an ERROR."""
    readings = [make_reading(100.0, quality="bad") for _ in range(num_readings)]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    all_unusable = [f for f in result.findings if f.code == "all_readings_unusable"]
    assert len(all_unusable) >= 1


@given(
    direction=valid_directions,
    unit=energy_units,
    num_readings=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=200)
def test_quality_gate_good_passes(direction, unit, num_readings):
    """Good quality status should not produce quality warnings."""
    readings = [make_reading(100.0, quality="good") for _ in range(num_readings)]
    result = validate_meter_boundary(
        meter_id="test-meter",
        boundary="energy",
        direction=direction,
        unit=unit,
        readings=readings,
    )
    quality_findings = [f for f in result.findings if f.code == "quality_gate_failed"]
    assert len(quality_findings) == 0


# ---------------------------------------------------------------------------
# Energy balance properties
# ---------------------------------------------------------------------------


@given(
    facility_energy=positive_floats,
    it_energy=positive_floats,
)
@settings(max_examples=200)
def test_energy_balance_conservation(facility_energy, it_energy):
    """Facility energy should be >= IT energy for valid data."""
    if facility_energy >= it_energy:
        result = validate_energy_balance(
            facility_energy_kwh=facility_energy,
            it_energy_kwh=it_energy,
        )
        conservation_findings = [f for f in result.findings if f.code == "energy_conservation_violation"]
        assert len(conservation_findings) == 0


@given(
    facility_energy=positive_floats,
    it_energy=positive_floats,
)
@settings(max_examples=200)
def test_energy_balance_violation_detected(facility_energy, it_energy):
    """Facility < IT should produce a CRITICAL finding."""
    if facility_energy < it_energy:
        result = validate_energy_balance(
            facility_energy_kwh=facility_energy,
            it_energy_kwh=it_energy,
        )
        conservation_findings = [f for f in result.findings if f.code == "energy_conservation_violation"]
        assert len(conservation_findings) >= 1
        assert conservation_findings[0].severity == Severity.CRITICAL


@given(
    facility_energy=positive_floats,
    it_energy=positive_floats,
)
@settings(max_examples=200)
def test_energy_balance_pue_computed(facility_energy, it_energy):
    """PUE should be computed when both energies are positive."""
    if it_energy > 0:
        result = validate_energy_balance(
            facility_energy_kwh=facility_energy,
            it_energy_kwh=it_energy,
        )
        assert "computed_pue" in result.metrics
        expected_pue = facility_energy / it_energy
        assert abs(result.metrics["computed_pue"] - expected_pue) < 0.001


@given(
    facility_energy=positive_floats,
    it_energy=positive_floats,
    pue_value=st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_energy_balance_pue_mismatch_detected(facility_energy, it_energy, pue_value):
    """When reported PUE differs from computed, should produce a finding."""
    if it_energy > 0:
        computed_pue = facility_energy / it_energy
        if abs(computed_pue - pue_value) / pue_value > 0.05:
            result = validate_energy_balance(
                facility_energy_kwh=facility_energy,
                it_energy_kwh=it_energy,
                pue_value=pue_value,
                tolerance_pct=5.0,
            )
            pue_findings = [f for f in result.findings if f.code == "pue_mismatch"]
            assert len(pue_findings) >= 1


# ---------------------------------------------------------------------------
# Energy allocation properties
# ---------------------------------------------------------------------------


@given(
    energy_kwh=positive_floats,
    lower_bound=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    upper_bound=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_allocation_bounds_enforced(energy_kwh, lower_bound, upper_bound):
    """Energy outside bounds should produce ERROR findings."""
    if lower_bound > upper_bound:
        lower_bound, upper_bound = upper_bound, lower_bound
    result = validate_energy_allocation(
        allocation_id="test-alloc",
        workload_id="test-workload",
        window_start=make_base_time(),
        window_end=make_base_time() + timedelta(hours=1),
        energy_kwh=energy_kwh,
        allocation_method="direct_meter",
        lower_bound_kwh=lower_bound,
        upper_bound_kwh=upper_bound,
        formula_version="v1",
        provenance={"source": "test"},
    )
    if energy_kwh < lower_bound:
        assert any(f.code == "energy_below_lower_bound" for f in result.findings)
    if energy_kwh > upper_bound:
        assert any(f.code == "energy_above_upper_bound" for f in result.findings)


@given(
    energy_kwh=positive_floats,
)
@settings(max_examples=200)
def test_allocation_negative_energy_fails(energy_kwh):
    """Negative energy should produce an ERROR."""
    result = validate_energy_allocation(
        allocation_id="test-alloc",
        workload_id="test-workload",
        window_start=make_base_time(),
        window_end=make_base_time() + timedelta(hours=1),
        energy_kwh=-energy_kwh,
        allocation_method="direct_meter",
        formula_version="v1",
        provenance={"source": "test"},
    )
    assert any(f.code == "negative_energy" for f in result.findings)


@given(
    energy_kwh=positive_floats,
)
@settings(max_examples=200)
def test_allocation_missing_formula_version_fails(energy_kwh):
    """Missing formula_version should produce an ERROR."""
    result = validate_energy_allocation(
        allocation_id="test-alloc",
        workload_id="test-workload",
        window_start=make_base_time(),
        window_end=make_base_time() + timedelta(hours=1),
        energy_kwh=energy_kwh,
        allocation_method="direct_meter",
        formula_version="",
        provenance={"source": "test"},
    )
    assert any(f.code == "missing_formula_version" for f in result.findings)


@given(
    energy_kwh=positive_floats,
)
@settings(max_examples=200)
def test_allocation_missing_provenance_fails(energy_kwh):
    """Missing provenance should produce an ERROR."""
    result = validate_energy_allocation(
        allocation_id="test-alloc",
        workload_id="test-workload",
        window_start=make_base_time(),
        window_end=make_base_time() + timedelta(hours=1),
        energy_kwh=energy_kwh,
        allocation_method="direct_meter",
        formula_version="v1",
        provenance=None,
    )
    assert any(f.code == "missing_provenance" for f in result.findings)


@given(
    energy_kwh=positive_floats,
    method=st.sampled_from(["direct_meter", "device_model", "capacity_share", "shared", "unallocated"]),
)
@settings(max_examples=200)
def test_allocation_valid_method_passes(energy_kwh, method):
    """Valid allocation method should not produce method errors."""
    result = validate_energy_allocation(
        allocation_id="test-alloc",
        workload_id="test-workload",
        window_start=make_base_time(),
        window_end=make_base_time() + timedelta(hours=1),
        energy_kwh=energy_kwh,
        allocation_method=method,
        formula_version="v1",
        provenance={"source": "test"},
    )
    method_findings = [f for f in result.findings if f.code == "invalid_allocation_method"]
    assert len(method_findings) == 0


@given(
    energy_kwh=positive_floats,
)
@settings(max_examples=200)
def test_allocation_invalid_method_fails(energy_kwh):
    """Invalid allocation method should produce an ERROR."""
    result = validate_energy_allocation(
        allocation_id="test-alloc",
        workload_id="test-workload",
        window_start=make_base_time(),
        window_end=make_base_time() + timedelta(hours=1),
        energy_kwh=energy_kwh,
        allocation_method="invalid_method",
        formula_version="v1",
        provenance={"source": "test"},
    )
    assert any(f.code == "invalid_allocation_method" for f in result.findings)


# ---------------------------------------------------------------------------
# Energy budget properties
# ---------------------------------------------------------------------------


@given(
    budget=positive_floats,
    allocated=positive_floats,
)
@settings(max_examples=200)
def test_budget_exceeded_detected(budget, allocated):
    """Allocated > budget should produce an ERROR."""
    if allocated > budget:
        result = validate_energy_budget(
            workload_id="test-workload",
            energy_budget_kwh=budget,
            allocated_kwh=allocated,
        )
        assert any(f.code == "budget_exceeded" for f in result.findings)


@given(
    budget=positive_floats,
    allocated=positive_floats,
)
@settings(max_examples=200)
def test_budget_within_passes(budget, allocated):
    """Allocated <= budget should not produce budget_exceeded error."""
    if allocated <= budget:
        result = validate_energy_budget(
            workload_id="test-workload",
            energy_budget_kwh=budget,
            allocated_kwh=allocated,
        )
        budget_findings = [f for f in result.findings if f.code == "budget_exceeded"]
        assert len(budget_findings) == 0


@given(
    allocated=positive_floats,
)
@settings(max_examples=100)
def test_budget_no_budget_info(allocated):
    """No budget declared should produce an INFO finding."""
    result = validate_energy_budget(
        workload_id="test-workload",
        energy_budget_kwh=None,
        allocated_kwh=allocated,
    )
    assert any(f.code == "no_budget" for f in result.findings)


# ---------------------------------------------------------------------------
# ValidationResult properties
# ---------------------------------------------------------------------------


@given(
    num_errors=st.integers(min_value=0, max_value=10),
    num_warnings=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
def test_validation_result_passed_logic(num_errors, num_warnings):
    """Result should be passed=False if any ERROR or CRITICAL findings exist."""
    result = ValidationResult(passed=True)
    for i in range(num_errors):
        result.add(Finding(code=f"err-{i}", severity=Severity.ERROR, message="error"))
    for i in range(num_warnings):
        result.add(Finding(code=f"warn-{i}", severity=Severity.WARNING, message="warning"))
    assert result.passed == (num_errors == 0)


@given(
    num_critical=st.integers(min_value=0, max_value=5),
    num_info=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_validation_result_critical_fails(num_critical, num_info):
    """Any CRITICAL finding should make passed=False."""
    result = ValidationResult(passed=True)
    for i in range(num_critical):
        result.add(Finding(code=f"crit-{i}", severity=Severity.CRITICAL, message="critical"))
    for i in range(num_info):
        result.add(Finding(code=f"info-{i}", severity=Severity.INFO, message="info"))
    assert result.passed == (num_critical == 0)
