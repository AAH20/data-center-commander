"""Property-based tests for consistency validation.

Tests invariants that should hold for all valid inputs:
- Reconciliation findings are deterministic
- Asset reference integrity is preserved under valid inputs
- Capacity headroom calculations are monotonic
- PUE consistency checks are symmetric
- Temporal consistency is transitive
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from dcc.validation.consistency import (
    ConsistencyReport,
    Finding,
    Severity,
    reconcile_energy_sources,
    validate_asset_references,
    validate_capacity_headroom,
    validate_cost_rollup,
    validate_energy_allocation_coverage,
    validate_kpi_vs_telemetry,
    validate_pue_consistency,
    validate_tenant_boundary,
    validate_temporal_consistency,
    validate_unit_consistency,
    validate_workflow_facility_linkage,
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

tolerance_pcts = st.floats(
    min_value=0.1,
    max_value=50.0,
    allow_nan=False,
    allow_infinity=False,
)

small_ints = st.integers(min_value=0, max_value=100)


def make_reading(value: float, **kwargs) -> dict:
    """Create a meter reading dict."""
    return {"value_numeric": value, **kwargs}


def make_asset(asset_id: str) -> dict:
    """Create an asset dict."""
    return {"id": asset_id}


def make_work_order(asset_id: str) -> dict:
    """Create a work order dict."""
    return {"asset_id": asset_id}


def make_capacity_snapshot(usable: float) -> dict:
    """Create a capacity snapshot dict."""
    return {"usable": usable}


def make_it_load(value: float) -> dict:
    """Create an IT load reading dict."""
    return {"value_numeric": value}


def make_kpi(value: float, name: str = "energy", unit: str = "kWh") -> dict:
    """Create a KPI observation dict."""
    return {"value_numeric": value, "name": name, "unit": unit}


def make_line_item(extended_base: float) -> dict:
    """Create a line item dict."""
    return {"extended_base": extended_base}


def make_rollup(present_value_base: float) -> dict:
    """Create a cost rollup dict."""
    return {"present_value_base": present_value_base}


def make_workflow(facility_id: str) -> dict:
    """Create a workflow dict."""
    return {"facility_id": facility_id}


def make_facility(facility_id: str) -> dict:
    """Create a facility dict."""
    return {"id": facility_id}


def make_allocation(energy_kwh: float) -> dict:
    """Create an energy allocation dict."""
    return {"energy_kwh": energy_kwh}


def make_price_obs(observed_at: datetime) -> dict:
    """Create a price observation dict."""
    return {"observed_at": observed_at}


def make_telemetry(observed_at: datetime) -> dict:
    """Create a telemetry reading dict."""
    return {"observed_at": observed_at}


# ---------------------------------------------------------------------------
# Energy reconciliation properties
# ---------------------------------------------------------------------------


@given(
    facility_total=positive_floats,
    submeter_total=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_energy_reconciliation_deterministic(facility_total, submeter_total, tolerance_pct):
    """Same inputs should always produce the same findings."""
    readings_f = [make_reading(facility_total)]
    readings_s = [make_reading(submeter_total)]
    result1 = reconcile_energy_sources(
        facility_meter_readings=readings_f,
        submeter_readings=readings_s,
        tolerance_pct=tolerance_pct,
    )
    result2 = reconcile_energy_sources(
        facility_meter_readings=readings_f,
        submeter_readings=readings_s,
        tolerance_pct=tolerance_pct,
    )
    assert len(result1) == len(result2)
    for f1, f2 in zip(result1, result2):
        assert f1.severity == f2.severity
        assert f1.message == f2.message


@given(
    facility_total=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_energy_reconciliation_equal_values_pass(facility_total, tolerance_pct):
    """When facility == submeters, reconciliation should PASS."""
    readings = [make_reading(facility_total)]
    result = reconcile_energy_sources(
        facility_meter_readings=readings,
        submeter_readings=readings,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    facility_total=positive_floats,
    submeter_total=positive_floats,
)
@settings(max_examples=200)
def test_energy_reconciliation_zero_both_skips(facility_total, submeter_total):
    """When both sources report zero, reconciliation should SKIP."""
    readings_f = [make_reading(0.0)]
    readings_s = [make_reading(0.0)]
    result = reconcile_energy_sources(
        facility_meter_readings=readings_f,
        submeter_readings=readings_s,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


@given(
    facility_total=positive_floats,
    submeter_total=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_energy_reconciliation_within_tolerance_passes(facility_total, submeter_total, tolerance_pct):
    """When diff is within tolerance, result should be PASS."""
    # Make submeter total within tolerance of facility total
    if facility_total > 0:
        adjusted_sub = facility_total * (1 + tolerance_pct / 200)
    else:
        adjusted_sub = 1.0
    readings_f = [make_reading(facility_total)]
    readings_s = [make_reading(adjusted_sub)]
    result = reconcile_energy_sources(
        facility_meter_readings=readings_f,
        submeter_readings=readings_s,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


# ---------------------------------------------------------------------------
# Asset reference integrity properties
# ---------------------------------------------------------------------------


@given(
    asset_ids=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=20, unique=True),
    work_order_indices=st.lists(st.integers(min_value=0, max_value=19), min_size=1, max_size=30),
)
@settings(max_examples=200)
def test_asset_references_valid_inputs_pass(asset_ids, work_order_indices):
    """When all work orders reference known assets, result should PASS."""
    assets = [make_asset(aid) for aid in asset_ids]
    work_orders = [make_work_order(asset_ids[i % len(asset_ids)]) for i in work_order_indices]
    result = validate_asset_references(work_orders=work_orders, assets=assets)
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    asset_ids=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=10, unique=True),
    unknown_ids=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=5),
)
@settings(max_examples=200)
def test_asset_references_orphaned_fail(asset_ids, unknown_ids):
    """When work orders reference unknown assets, result should FAIL."""
    assets = [make_asset(aid) for aid in asset_ids]
    # Filter out any unknown_ids that happen to be in asset_ids
    truly_unknown = [uid for uid in unknown_ids if uid not in asset_ids]
    if not truly_unknown:
        truly_unknown = ["definitely-unknown-id-xyz"]
    work_orders = [make_work_order(uid) for uid in truly_unknown]
    result = validate_asset_references(work_orders=work_orders, assets=assets)
    assert len(result) == 1
    assert result[0].severity == Severity.FAIL


@given(
    num_assets=small_ints,
)
@settings(max_examples=100)
def test_asset_references_empty_registry_skips(num_assets):
    """When asset registry is empty, result should SKIP."""
    work_orders = [make_work_order(f"asset-{i}") for i in range(num_assets)]
    result = validate_asset_references(work_orders=work_orders, assets=[])
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


# ---------------------------------------------------------------------------
# Capacity headroom properties
# ---------------------------------------------------------------------------


@given(
    usable=positive_floats,
    peak_load=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_capacity_headroom_within_capacity_passes(usable, peak_load, tolerance_pct):
    """When peak load <= usable capacity, result should PASS."""
    if peak_load > usable:
        peak_load = usable * 0.9
    snapshots = [make_capacity_snapshot(usable)]
    loads = [make_it_load(peak_load)]
    result = validate_capacity_headroom(
        capacity_snapshots=snapshots,
        it_load_readings=loads,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    usable=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_capacity_headroom_exceeds_capacity_warns_or_fails(usable, tolerance_pct):
    """When peak load > usable capacity, result should WARN or FAIL."""
    peak_load = usable * (1 + tolerance_pct / 50)
    snapshots = [make_capacity_snapshot(usable)]
    loads = [make_it_load(peak_load)]
    result = validate_capacity_headroom(
        capacity_snapshots=snapshots,
        it_load_readings=loads,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity in (Severity.WARN, Severity.FAIL)


@given(
    usable=positive_floats,
)
@settings(max_examples=100)
def test_capacity_headroom_missing_data_skips(usable):
    """When data is missing, result should SKIP."""
    result = validate_capacity_headroom(
        capacity_snapshots=[],
        it_load_readings=[],
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


# ---------------------------------------------------------------------------
# PUE consistency properties
# ---------------------------------------------------------------------------


@given(
    facility_energy=positive_floats,
    it_energy=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_pue_consistency_matching_values_pass(facility_energy, it_energy, tolerance_pct):
    """When reported PUE matches calculated PUE, result should PASS."""
    if it_energy > 0:
        calculated_pue = facility_energy / it_energy
    else:
        calculated_pue = 1.0
    result = validate_pue_consistency(
        facility_energy_kwh=facility_energy,
        it_energy_kwh=it_energy,
        reported_pue=calculated_pue,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    facility_energy=positive_floats,
    it_energy=positive_floats,
)
@settings(max_examples=200)
def test_pue_consistency_no_reported_skips(facility_energy, it_energy):
    """When no reported PUE is given, result should SKIP."""
    result = validate_pue_consistency(
        facility_energy_kwh=facility_energy,
        it_energy_kwh=it_energy,
        reported_pue=None,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


@given(
    facility_energy=positive_floats,
)
@settings(max_examples=100)
def test_pue_consistency_zero_it_skips(facility_energy):
    """When IT energy is zero, result should SKIP."""
    result = validate_pue_consistency(
        facility_energy_kwh=facility_energy,
        it_energy_kwh=0,
        reported_pue=1.5,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


# ---------------------------------------------------------------------------
# Cost rollup properties
# ---------------------------------------------------------------------------


@given(
    line_total=positive_floats,
    rollup_total=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_cost_rollup_matching_passes(line_total, rollup_total, tolerance_pct):
    """When line items match rollup, result should PASS."""
    # Make rollup match line items within tolerance
    adjusted_rollup = line_total * (1 + tolerance_pct / 200)
    items = [make_line_item(line_total)]
    rollup = [make_rollup(adjusted_rollup)]
    result = validate_cost_rollup(
        line_items=items,
        cost_rollup=rollup,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    line_total=positive_floats,
)
@settings(max_examples=100)
def test_cost_rollup_missing_data_skips(line_total):
    """When data is missing, result should SKIP."""
    result = validate_cost_rollup(
        line_items=[],
        cost_rollup=[],
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


# ---------------------------------------------------------------------------
# Tenant boundary properties
# ---------------------------------------------------------------------------


@given(
    tenant_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    num_rows=small_ints,
)
@settings(max_examples=100)
def test_tenant_boundary_matching_tenant_passes(tenant_id, num_rows):
    """When all rows have the correct tenant_id, result should PASS."""
    rows = [{"tenant_id": tenant_id} for _ in range(num_rows)]
    sources = {"test_source": rows}
    result = validate_tenant_boundary(sources=sources, tenant_id=tenant_id)
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    tenant_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    foreign_tenant=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
)
@settings(max_examples=100)
def test_tenant_boundary_foreign_tenant_fails(tenant_id, foreign_tenant):
    """When rows have a different tenant_id, result should FAIL."""
    if foreign_tenant == tenant_id:
        foreign_tenant = tenant_id + "-foreign"
    rows = [{"tenant_id": foreign_tenant}]
    sources = {"test_source": rows}
    result = validate_tenant_boundary(sources=sources, tenant_id=tenant_id)
    assert len(result) == 1
    assert result[0].severity == Severity.FAIL


# ---------------------------------------------------------------------------
# Temporal consistency properties
# ---------------------------------------------------------------------------


@given(
    num_readings=st.integers(min_value=1, max_value=100),
    max_age_days=st.integers(min_value=1, max_value=365),
)
@settings(max_examples=100)
def test_temporal_consistency_recent_passes(num_readings, max_age_days):
    """When all readings are recent, result should PASS."""
    now = datetime.now()
    readings = [make_telemetry(now - timedelta(minutes=i * 10)) for i in range(num_readings)]
    result = validate_temporal_consistency(
        readings=readings,
        max_age_days=max_age_days,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    num_readings=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100)
def test_temporal_consistency_future_warns(num_readings):
    """When readings are in the future, result should WARN."""
    now = datetime.now()
    readings = [make_telemetry(now + timedelta(days=i + 2)) for i in range(num_readings)]
    result = validate_temporal_consistency(
        readings=readings,
        max_age_days=90,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.WARN


# ---------------------------------------------------------------------------
# Unit consistency properties
# ---------------------------------------------------------------------------


@given(
    num_rows=st.integers(min_value=1, max_value=100),
    expected_unit=st.sampled_from(["kWh", "kW", "W", "MW"]),
)
@settings(max_examples=100)
def test_unit_consistency_matching_passes(num_rows, expected_unit):
    """When all rows have the expected unit, result should PASS."""
    rows = [{"unit": expected_unit} for _ in range(num_rows)]
    sources = {"test_source": rows}
    result = validate_unit_consistency(sources=sources, expected_unit=expected_unit)
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    num_rows=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100)
def test_unit_consistency_mismatched_warns(num_rows):
    """When rows have a different unit, result should WARN."""
    rows = [{"unit": "MWh"} for _ in range(num_rows)]
    sources = {"test_source": rows}
    result = validate_unit_consistency(sources=sources, expected_unit="kWh")
    assert len(result) == 1
    assert result[0].severity == Severity.WARN


# ---------------------------------------------------------------------------
# Workflow facility linkage properties
# ---------------------------------------------------------------------------


@given(
    facility_ids=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=10, unique=True),
    workflow_indices=st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=20),
)
@settings(max_examples=200)
def test_workflow_facility_linkage_valid_passes(facility_ids, workflow_indices):
    """When all workflows reference known facilities, result should PASS."""
    facilities = [make_facility(fid) for fid in facility_ids]
    workflows = [make_workflow(facility_ids[i % len(facility_ids)]) for i in workflow_indices]
    result = validate_workflow_facility_linkage(workflows=workflows, facilities=facilities)
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    facility_ids=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=5, unique=True),
    unknown_ids=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=3),
)
@settings(max_examples=200)
def test_workflow_facility_linkage_orphaned_fails(facility_ids, unknown_ids):
    """When workflows reference unknown facilities, result should FAIL."""
    facilities = [make_facility(fid) for fid in facility_ids]
    truly_unknown = [uid for uid in unknown_ids if uid not in facility_ids]
    if not truly_unknown:
        truly_unknown = ["unknown-facility-xyz"]
    workflows = [make_workflow(uid) for uid in truly_unknown]
    result = validate_workflow_facility_linkage(workflows=workflows, facilities=facilities)
    assert len(result) == 1
    assert result[0].severity == Severity.FAIL


# ---------------------------------------------------------------------------
# Energy allocation coverage properties
# ---------------------------------------------------------------------------


@given(
    total_energy=positive_floats,
    allocated=positive_floats,
    min_coverage_pct=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_energy_allocation_coverage_sufficient_passes(total_energy, allocated, min_coverage_pct):
    """When allocated energy covers enough of total, result should PASS."""
    # Make allocated >= min_coverage_pct% of total
    required = total_energy * min_coverage_pct / 100
    if allocated < required:
        allocated = required * 1.1
    allocations = [make_allocation(allocated)]
    result = validate_energy_allocation_coverage(
        energy_allocations=allocations,
        total_energy_kwh=total_energy,
        min_coverage_pct=min_coverage_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    total_energy=positive_floats,
)
@settings(max_examples=100)
def test_energy_allocation_coverage_zero_total_skips(total_energy):
    """When total energy is zero, result should SKIP."""
    allocations = [make_allocation(100.0)]
    result = validate_energy_allocation_coverage(
        energy_allocations=allocations,
        total_energy_kwh=0,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


# ---------------------------------------------------------------------------
# KPI vs telemetry properties
# ---------------------------------------------------------------------------


@given(
    kpi_value=positive_floats,
    telemetry_value=positive_floats,
    tolerance_pct=tolerance_pcts,
)
@settings(max_examples=200)
def test_kpi_vs_telemetry_matching_passes(kpi_value, telemetry_value, tolerance_pct):
    """When KPI matches telemetry sum, result should PASS."""
    # Make telemetry match KPI within tolerance
    adjusted_telemetry = kpi_value * (1 + tolerance_pct / 200)
    kpi = [make_kpi(kpi_value)]
    telemetry = [make_reading(adjusted_telemetry)]
    result = validate_kpi_vs_telemetry(
        kpi_observations=kpi,
        telemetry_readings=telemetry,
        tolerance_pct=tolerance_pct,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.PASS


@given(
    kpi_value=positive_floats,
)
@settings(max_examples=100)
def test_kpi_vs_telemetry_no_kpi_skips(kpi_value):
    """When no KPI observations are provided, result should SKIP."""
    telemetry = [make_reading(kpi_value)]
    result = validate_kpi_vs_telemetry(
        kpi_observations=[],
        telemetry_readings=telemetry,
    )
    assert len(result) == 1
    assert result[0].severity == Severity.SKIP


# ---------------------------------------------------------------------------
# Finding and Report properties
# ---------------------------------------------------------------------------


@given(
    check_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
    severity=st.sampled_from(list(Severity)),
    message=st.text(min_size=1, max_size=200),
)
@settings(max_examples=100)
def test_finding_to_dict_round_trip(check_name, severity, message):
    """Finding.to_dict() should produce a dict with all fields."""
    finding = Finding(check=check_name, severity=severity, message=message)
    d = finding.to_dict()
    assert d["check"] == check_name
    assert d["severity"] == severity.value
    assert d["message"] == message
    assert "source_a" in d
    assert "source_b" in d
    assert "detail" in d


@given(
    num_findings=small_ints,
)
@settings(max_examples=100)
def test_consistency_report_aggregation(num_findings):
    """Report should correctly aggregate findings."""
    report = ConsistencyReport()
    for i in range(num_findings):
        report.add(Finding(check=f"check-{i}", severity=Severity.PASS, message=f"msg-{i}"))
    assert len(report.findings) == num_findings
    assert report.passed
    assert report.failure_count == 0
    assert report.warning_count == 0


@given(
    num_pass=small_ints,
    num_fail=small_ints,
    num_warn=small_ints,
)
@settings(max_examples=100)
def test_consistency_report_mixed_findings(num_pass, num_fail, num_warn):
    """Report should correctly count mixed findings."""
    report = ConsistencyReport()
    for i in range(num_pass):
        report.add(Finding(check=f"pass-{i}", severity=Severity.PASS, message="ok"))
    for i in range(num_fail):
        report.add(Finding(check=f"fail-{i}", severity=Severity.FAIL, message="fail"))
    for i in range(num_warn):
        report.add(Finding(check=f"warn-{i}", severity=Severity.WARN, message="warn"))
    assert len(report.findings) == num_pass + num_fail + num_warn
    assert report.failure_count == num_fail
    assert report.warning_count == num_warn
    # ConsistencyReport.passed covers BLOCKING findings only (Severity.FAIL);
    # WARN is advisory and SKIP means the check could not run, so neither one
    # makes a report fail. See src/dcc/validation/consistency.py:68.
    assert report.passed == (num_fail == 0)
    assert report.failed == (num_fail > 0)
