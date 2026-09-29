"""Tests for cross-source consistency validation."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from dcc.validation.consistency import (
    ConsistencyReport,
    Finding,
    Severity,
    run_consistency_validation,
    reconcile_energy_sources,
    validate_asset_references,
    validate_capacity_headroom,
    validate_kpi_vs_telemetry,
    validate_cost_rollup,
    validate_workflow_facility_linkage,
    validate_tenant_boundary,
    validate_temporal_consistency,
    validate_unit_consistency,
    validate_provenance_consistency,
    validate_pue_consistency,
    validate_price_freshness,
    validate_estimate_price_links,
    validate_energy_allocation_coverage,
    validate_connector_data_freshness,
)


def _row(**kwargs):
    """Helper to create a dict row."""
    return kwargs


class TestEnergyReconciliation(unittest.TestCase):
    def test_pass_within_tolerance(self):
        facility = [_row(value_numeric=1000.0)]
        submeters = [_row(value_numeric=600.0), _row(value_numeric=380.0)]
        findings = reconcile_energy_sources(
            facility_meter_readings=facility,
            submeter_readings=submeters,
            tolerance_pct=5.0,
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_at_double_tolerance(self):
        facility = [_row(value_numeric=1000.0)]
        submeters = [_row(value_numeric=930.0)]
        findings = reconcile_energy_sources(
            facility_meter_readings=facility,
            submeter_readings=submeters,
            tolerance_pct=5.0,
        )
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_fail_beyond_double_tolerance(self):
        facility = [_row(value_numeric=1000.0)]
        submeters = [_row(value_numeric=100.0)]
        findings = reconcile_energy_sources(
            facility_meter_readings=facility,
            submeter_readings=submeters,
            tolerance_pct=5.0,
        )
        self.assertEqual(findings[0].severity, Severity.FAIL)

    def test_skip_when_empty(self):
        findings = reconcile_energy_sources(
            facility_meter_readings=[],
            submeter_readings=[],
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)

    def test_skip_when_both_zero(self):
        facility = [_row(value_numeric=0.0)]
        submeters = [_row(value_numeric=0.0)]
        findings = reconcile_energy_sources(
            facility_meter_readings=facility,
            submeter_readings=submeters,
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestAssetReferences(unittest.TestCase):
    def test_pass_all_references_valid(self):
        assets = [_row(id="a1"), _row(id="a2")]
        work_orders = [_row(asset_id="a1"), _row(asset_id="a2")]
        findings = validate_asset_references(work_orders=work_orders, assets=assets)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_fail_orphaned_references(self):
        assets = [_row(id="a1")]
        work_orders = [_row(asset_id="a1"), _row(asset_id="ghost")]
        findings = validate_asset_references(work_orders=work_orders, assets=assets)
        self.assertEqual(findings[0].severity, Severity.FAIL)
        self.assertIn("ghost", findings[0].detail)

    def test_skip_no_work_orders(self):
        findings = validate_asset_references(work_orders=[], assets=[_row(id="a1")])
        self.assertEqual(findings[0].severity, Severity.SKIP)

    def test_skip_empty_asset_registry(self):
        findings = validate_asset_references(work_orders=[_row(asset_id="a1")], assets=[])
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestCapacityHeadroom(unittest.TestCase):
    def test_pass_within_capacity(self):
        capacity = [_row(usable=1000.0)]
        loads = [_row(value_numeric=800.0)]
        findings = validate_capacity_headroom(
            capacity_snapshots=capacity,
            it_load_readings=loads,
        )
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_slightly_over(self):
        capacity = [_row(usable=1000.0)]
        loads = [_row(value_numeric=1050.0)]
        findings = validate_capacity_headroom(
            capacity_snapshots=capacity,
            it_load_readings=loads,
            tolerance_pct=10.0,
        )
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_fail_significantly_over(self):
        capacity = [_row(usable=1000.0)]
        loads = [_row(value_numeric=1500.0)]
        findings = validate_capacity_headroom(
            capacity_snapshots=capacity,
            it_load_readings=loads,
            tolerance_pct=10.0,
        )
        self.assertEqual(findings[0].severity, Severity.FAIL)

    def test_skip_missing_data(self):
        findings = validate_capacity_headroom(
            capacity_snapshots=[],
            it_load_readings=[_row(value_numeric=100.0)],
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestKpiVsTelemetry(unittest.TestCase):
    def test_pass_matching(self):
        kpi = [_row(value_numeric=1000.0, name="Facility energy", unit="kWh")]
        telemetry = [_row(value_numeric=600.0), _row(value_numeric=400.0)]
        findings = validate_kpi_vs_telemetry(
            kpi_observations=kpi,
            telemetry_readings=telemetry,
        )
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_divergent(self):
        kpi = [_row(value_numeric=2000.0, name="Facility energy", unit="kWh")]
        telemetry = [_row(value_numeric=600.0), _row(value_numeric=400.0)]
        findings = validate_kpi_vs_telemetry(
            kpi_observations=kpi,
            telemetry_readings=telemetry,
        )
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_no_kpi(self):
        findings = validate_kpi_vs_telemetry(
            kpi_observations=[],
            telemetry_readings=[_row(value_numeric=100.0)],
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)

    def test_skip_non_energy_kpi(self):
        kpi = [_row(value_numeric=2.0, name="PUE", unit="ratio")]
        telemetry = [_row(value_numeric=100.0)]
        findings = validate_kpi_vs_telemetry(
            kpi_observations=kpi,
            telemetry_readings=telemetry,
        )
        self.assertEqual(len(findings), 0)


class TestCostRollup(unittest.TestCase):
    def test_pass_matching(self):
        items = [_row(extended_base=1000.0), _row(extended_base=2000.0)]
        rollup = [_row(present_value_base=3000.0)]
        findings = validate_cost_rollup(line_items=items, cost_rollup=rollup)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_divergent(self):
        items = [_row(extended_base=1000.0)]
        rollup = [_row(present_value_base=5000.0)]
        findings = validate_cost_rollup(line_items=items, cost_rollup=rollup)
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_empty(self):
        findings = validate_cost_rollup(line_items=[], cost_rollup=[])
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestWorkflowFacilityLinkage(unittest.TestCase):
    def test_pass_all_linked(self):
        facilities = [_row(id="f1"), _row(id="f2")]
        workflows = [_row(facility_id="f1"), _row(facility_id="f2")]
        findings = validate_workflow_facility_linkage(workflows=workflows, facilities=facilities)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_fail_orphaned(self):
        facilities = [_row(id="f1")]
        workflows = [_row(facility_id="f1"), _row(facility_id="ghost")]
        findings = validate_workflow_facility_linkage(workflows=workflows, facilities=facilities)
        self.assertEqual(findings[0].severity, Severity.FAIL)

    def test_skip_no_workflows(self):
        findings = validate_workflow_facility_linkage(workflows=[], facilities=[_row(id="f1")])
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestTenantBoundary(unittest.TestCase):
    def test_pass_all_scoped(self):
        sources = {
            "telemetry": [_row(tenant_id="t1"), _row(tenant_id="t1")],
            "assets": [_row(tenant_id="t1")],
        }
        findings = validate_tenant_boundary(sources=sources, tenant_id="t1")
        self.assertTrue(all(f.severity == Severity.PASS for f in findings))

    def test_fail_foreign_tenant(self):
        sources = {
            "telemetry": [_row(tenant_id="t1"), _row(tenant_id="evil")],
        }
        findings = validate_tenant_boundary(sources=sources, tenant_id="t1")
        self.assertEqual(findings[0].severity, Severity.FAIL)

    def test_skip_no_sources(self):
        findings = validate_tenant_boundary(sources={}, tenant_id="t1")
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestTemporalConsistency(unittest.TestCase):
    def test_pass_recent(self):
        now = datetime.now()
        readings = [_row(observed_at=now - timedelta(hours=1))]
        findings = validate_temporal_consistency(readings=readings, max_age_days=90)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_stale(self):
        old = datetime.now() - timedelta(days=200)
        readings = [_row(observed_at=old)]
        findings = validate_temporal_consistency(readings=readings, max_age_days=90)
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_warn_future(self):
        future = datetime.now() + timedelta(days=5)
        readings = [_row(observed_at=future)]
        findings = validate_temporal_consistency(readings=readings, max_age_days=90)
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_empty(self):
        findings = validate_temporal_consistency(readings=[], max_age_days=90)
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestUnitConsistency(unittest.TestCase):
    def test_pass_consistent(self):
        sources = {"meter_a": [_row(reported_unit="kWh")], "meter_b": [_row(reported_unit="kWh")]}
        findings = validate_unit_consistency(sources=sources, expected_unit="kWh")
        self.assertTrue(all(f.severity == Severity.PASS for f in findings))

    def test_warn_mismatched(self):
        sources = {"meter_a": [_row(reported_unit="kWh"), _row(reported_unit="MWh")]}
        findings = validate_unit_consistency(sources=sources, expected_unit="kWh")
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_no_sources(self):
        findings = validate_unit_consistency(sources={}, expected_unit="kWh")
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestProvenanceConsistency(unittest.TestCase):
    def test_pass_all_synthetic(self):
        sources = {
            "telemetry": [_row(provenance={"synthetic": True})],
            "kpi": [_row(provenance={"synthetic": True})],
        }
        findings = validate_provenance_consistency(sources=sources)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_pass_all_real(self):
        sources = {
            "telemetry": [_row(provenance={"synthetic": False})],
            "kpi": [_row(provenance={})],
        }
        findings = validate_provenance_consistency(sources=sources)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_mixed(self):
        sources = {
            "telemetry": [_row(provenance={"synthetic": True})],
            "kpi": [_row(provenance={})],
        }
        findings = validate_provenance_consistency(sources=sources)
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_insufficient(self):
        sources = {"telemetry": [_row(provenance={"synthetic": True})]}
        findings = validate_provenance_consistency(sources=sources)
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestPueConsistency(unittest.TestCase):
    def test_pass_matching(self):
        findings = validate_pue_consistency(
            facility_energy_kwh=2000.0,
            it_energy_kwh=1000.0,
            reported_pue=2.0,
        )
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_divergent(self):
        findings = validate_pue_consistency(
            facility_energy_kwh=2000.0,
            it_energy_kwh=1000.0,
            reported_pue=3.0,
        )
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_no_reported(self):
        findings = validate_pue_consistency(
            facility_energy_kwh=2000.0,
            it_energy_kwh=1000.0,
            reported_pue=None,
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)

    def test_skip_zero_it(self):
        findings = validate_pue_consistency(
            facility_energy_kwh=2000.0,
            it_energy_kwh=0.0,
            reported_pue=2.0,
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestPriceFreshness(unittest.TestCase):
    def test_pass_recent(self):
        now = datetime.now()
        prices = [_row(observed_at=now - timedelta(days=30))]
        findings = validate_price_freshness(price_observations=prices, max_age_days=365)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_stale(self):
        old = datetime.now() - timedelta(days=500)
        prices = [_row(observed_at=old)]
        findings = validate_price_freshness(price_observations=prices, max_age_days=365)
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_empty(self):
        findings = validate_price_freshness(price_observations=[], max_age_days=365)
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestEstimatePriceLinks(unittest.TestCase):
    def test_pass_all_valid(self):
        prices = [_row(id="p1", quality_status="approved")]
        items = [_row(pricing_status="sourced", price_observation_id="p1", description="Item 1")]
        findings = validate_estimate_price_links(line_items=items, price_observations=prices)
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_fail_broken_ref(self):
        prices = [_row(id="p1", quality_status="approved")]
        items = [_row(pricing_status="sourced", price_observation_id="ghost", description="Item 1")]
        findings = validate_estimate_price_links(line_items=items, price_observations=prices)
        self.assertEqual(findings[0].severity, Severity.FAIL)

    def test_warn_unapproved(self):
        prices = [_row(id="p1", quality_status="reviewed")]
        items = [_row(pricing_status="sourced", price_observation_id="p1", description="Item 1")]
        findings = validate_estimate_price_links(line_items=items, price_observations=prices)
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_no_items(self):
        findings = validate_estimate_price_links(line_items=[], price_observations=[_row(id="p1")])
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestEnergyAllocationCoverage(unittest.TestCase):
    def test_pass_high_coverage(self):
        allocations = [_row(energy_kwh=900.0)]
        findings = validate_energy_allocation_coverage(
            energy_allocations=allocations,
            total_energy_kwh=1000.0,
            min_coverage_pct=80.0,
        )
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_low_coverage(self):
        allocations = [_row(energy_kwh=500.0)]
        findings = validate_energy_allocation_coverage(
            energy_allocations=allocations,
            total_energy_kwh=1000.0,
            min_coverage_pct=80.0,
        )
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_fail_very_low_coverage(self):
        allocations = [_row(energy_kwh=100.0)]
        findings = validate_energy_allocation_coverage(
            energy_allocations=allocations,
            total_energy_kwh=1000.0,
            min_coverage_pct=80.0,
        )
        self.assertEqual(findings[0].severity, Severity.FAIL)

    def test_skip_no_allocations(self):
        findings = validate_energy_allocation_coverage(
            energy_allocations=[],
            total_energy_kwh=1000.0,
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestConnectorDataFreshness(unittest.TestCase):
    def test_pass_recent(self):
        now = datetime.now()
        connectors = [_row(id="c1", name="Connector A", status="active")]
        readings = [_row(connector_id="c1", observed_at=now - timedelta(hours=1))]
        findings = validate_connector_data_freshness(
            connectors=connectors,
            latest_readings=readings,
        )
        self.assertEqual(findings[0].severity, Severity.PASS)

    def test_warn_stale(self):
        old = datetime.now() - timedelta(hours=48)
        connectors = [_row(id="c1", name="Connector A", status="active")]
        readings = [_row(connector_id="c1", observed_at=old)]
        findings = validate_connector_data_freshness(
            connectors=connectors,
            latest_readings=readings,
            max_stale_hours=24.0,
        )
        self.assertEqual(findings[0].severity, Severity.WARN)

    def test_skip_no_connectors(self):
        findings = validate_connector_data_freshness(
            connectors=[],
            latest_readings=[_row(connector_id="c1")],
        )
        self.assertEqual(findings[0].severity, Severity.SKIP)


class TestRunConsistencyValidation(unittest.TestCase):
    def test_empty_inputs_produces_skip_report(self):
        report = run_consistency_validation(tenant_id="t1")
        self.assertIsInstance(report, ConsistencyReport)
        self.assertTrue(len(report.findings) > 0)
        # All should be SKIP since no data provided
        self.assertTrue(all(f.severity == Severity.SKIP for f in report.findings))

    def test_full_data_produces_mixed_report(self):
        now = datetime.now()
        report = run_consistency_validation(
            tenant_id="t1",
            facility_meter_readings=[_row(value_numeric=1000.0, tenant_id="t1")],
            submeter_readings=[_row(value_numeric=950.0, tenant_id="t1")],
            work_orders=[_row(asset_id="a1", tenant_id="t1")],
            assets=[_row(id="a1", tenant_id="t1")],
            capacity_snapshots=[_row(usable=1200.0, tenant_id="t1")],
            it_load_readings=[_row(value_numeric=800.0, tenant_id="t1")],
            kpi_observations=[_row(value_numeric=1000.0, name="Facility energy", unit="kWh", tenant_id="t1")],
            telemetry_readings=[_row(value_numeric=1000.0, observed_at=now, tenant_id="t1")],
            line_items=[_row(extended_base=1000.0, tenant_id="t1")],
            cost_rollup=[_row(present_value_base=1000.0, tenant_id="t1")],
            workflows=[_row(facility_id="f1", tenant_id="t1")],
            facilities=[_row(id="f1", tenant_id="t1")],
            energy_allocations=[_row(energy_kwh=900.0, tenant_id="t1")],
            price_observations=[_row(observed_at=now, tenant_id="t1")],
            connectors=[_row(id="c1", status="active", tenant_id="t1")],
            reported_pue=1.25,
        )
        self.assertIsInstance(report, ConsistencyReport)
        self.assertTrue(len(report.findings) > 0)
        # Should have a mix of PASS and possibly WARN/FAIL
        severities = {f.severity for f in report.findings}
        self.assertIn(Severity.PASS, severities)

    def test_report_to_dict(self):
        report = ConsistencyReport()
        report.add(Finding(check="test", severity=Severity.PASS, message="ok"))
        d = report.to_dict()
        self.assertTrue(d["passed"])
        self.assertEqual(d["total_findings"], 1)
        self.assertEqual(d["findings"][0]["check"], "test")

    def test_report_failures_and_warnings(self):
        report = ConsistencyReport()
        report.add(Finding(check="a", severity=Severity.PASS, message="ok"))
        report.add(Finding(check="b", severity=Severity.WARN, message="warn"))
        report.add(Finding(check="c", severity=Severity.FAIL, message="fail"))
        self.assertFalse(report.passed)
        self.assertEqual(report.failure_count, 1)
        self.assertEqual(report.warning_count, 1)


class TestFinding(unittest.TestCase):
    def test_to_dict(self):
        f = Finding(
            check="test_check",
            severity=Severity.WARN,
            message="test message",
            source_a="src_a",
            source_b="src_b",
            detail="extra detail",
        )
        d = f.to_dict()
        self.assertEqual(d["check"], "test_check")
        self.assertEqual(d["severity"], "warn")
        self.assertEqual(d["message"], "test message")
        self.assertEqual(d["source_a"], "src_a")
        self.assertEqual(d["source_b"], "src_b")
        self.assertEqual(d["detail"], "extra detail")


if __name__ == "__main__":
    unittest.main()
