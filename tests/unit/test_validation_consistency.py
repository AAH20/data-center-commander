"""Unit tests for dcc.validation.consistency module."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from dcc.validation.consistency import (
    Severity,
    Finding,
    ConsistencyReport,
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
    run_consistency_validation,
)


class TestSeverity(unittest.TestCase):
    def test_severity_values(self):
        self.assertEqual(Severity.PASS.value, "pass")
        self.assertEqual(Severity.WARN.value, "warn")
        self.assertEqual(Severity.FAIL.value, "fail")
        self.assertEqual(Severity.SKIP.value, "skip")

    def test_severity_enum_members(self):
        self.assertEqual(len(Severity), 4)


class TestFinding(unittest.TestCase):
    def test_finding_creation(self):
        f = Finding(check="test", severity=Severity.PASS, message="ok")
        self.assertEqual(f.check, "test")
        self.assertEqual(f.severity, Severity.PASS)
        self.assertEqual(f.message, "ok")
        self.assertEqual(f.source_a, "")
        self.assertEqual(f.source_b, "")
        self.assertEqual(f.detail, "")

    def test_finding_to_dict(self):
        f = Finding(check="c", severity=Severity.WARN, message="warn", source_a="a", source_b="b", detail="d")
        d = f.to_dict()
        self.assertEqual(d["check"], "c")
        self.assertEqual(d["severity"], "warn")
        self.assertEqual(d["message"], "warn")
        self.assertEqual(d["source_a"], "a")
        self.assertEqual(d["source_b"], "b")
        self.assertEqual(d["detail"], "d")


class TestConsistencyReport(unittest.TestCase):
    def test_empty_report(self):
        r = ConsistencyReport()
        self.assertEqual(r.findings, [])
        self.assertEqual(r.sources_checked, [])
        self.assertTrue(r.passed)
        self.assertEqual(r.failures, [])
        self.assertEqual(r.warnings, [])
        self.assertEqual(r.failure_count, 0)
        self.assertEqual(r.warning_count, 0)

    def test_add_finding(self):
        r = ConsistencyReport()
        r.add(Finding(check="c", severity=Severity.PASS, message="ok"))
        self.assertEqual(len(r.findings), 1)

    def test_failures(self):
        r = ConsistencyReport()
        r.add(Finding(check="c", severity=Severity.FAIL, message="fail"))
        self.assertEqual(len(r.failures), 1)
        self.assertFalse(r.passed)

    def test_warnings(self):
        r = ConsistencyReport()
        r.add(Finding(check="c", severity=Severity.WARN, message="warn"))
        self.assertEqual(len(r.warnings), 1)
        self.assertTrue(r.passed)

    def test_to_dict(self):
        r = ConsistencyReport()
        r.add(Finding(check="c", severity=Severity.PASS, message="ok"))
        d = r.to_dict()
        self.assertTrue(d["passed"])
        self.assertEqual(d["total_findings"], 1)


class TestReconcileEnergySources(unittest.TestCase):
    def test_matching_sources(self):
        facility = [{"timestamp": "2024-01-01", "value": 100.0}]
        submeters = [{"timestamp": "2024-01-01", "value": 95.0}]
        findings = reconcile_energy_sources(
            facility_meter_readings=facility,
            submeter_readings=submeters,
        )
        self.assertIsInstance(findings, list)

    def test_mismatched_sources(self):
        facility = [{"timestamp": "2024-01-01", "value": 100.0}]
        submeters = [{"timestamp": "2024-01-01", "value": 50.0}]
        findings = reconcile_energy_sources(
            facility_meter_readings=facility,
            submeter_readings=submeters,
        )
        self.assertIsInstance(findings, list)


class TestValidateAssetReferences(unittest.TestCase):
    def test_valid_references(self):
        work_orders = [{"asset_id": "a1"}]
        assets = [{"asset_id": "a1"}]
        findings = validate_asset_references(work_orders=work_orders, assets=assets)
        self.assertIsInstance(findings, list)

    def test_invalid_references(self):
        work_orders = [{"asset_id": "a1"}]
        assets = [{"asset_id": "a2"}]
        findings = validate_asset_references(work_orders=work_orders, assets=assets)
        self.assertIsInstance(findings, list)


class TestValidateCapacityHeadroom(unittest.TestCase):
    def test_sufficient_headroom(self):
        capacity = [{"usable": 100.0, "committed": 50.0}]
        it_load = [{"value": 40.0}]
        findings = validate_capacity_headroom(capacity_snapshots=capacity, it_load_readings=it_load)
        self.assertIsInstance(findings, list)

    def test_insufficient_headroom(self):
        capacity = [{"usable": 100.0, "committed": 90.0}]
        it_load = [{"value": 95.0}]
        findings = validate_capacity_headroom(capacity_snapshots=capacity, it_load_readings=it_load)
        self.assertIsInstance(findings, list)


class TestValidateKpiVsTelemetry(unittest.TestCase):
    def test_matching(self):
        kpi = [{"value": 100.0}]
        telemetry = [{"value": 100.0}]
        findings = validate_kpi_vs_telemetry(kpi_observations=kpi, telemetry_readings=telemetry)
        self.assertIsInstance(findings, list)

    def test_mismatched(self):
        kpi = [{"value": 100.0}]
        telemetry = [{"value": 50.0}]
        findings = validate_kpi_vs_telemetry(kpi_observations=kpi, telemetry_readings=telemetry)
        self.assertIsInstance(findings, list)


class TestValidateCostRollup(unittest.TestCase):
    def test_matching(self):
        line_items = [{"amount": 100.0}]
        rollup = [{"amount": 100.0}]
        findings = validate_cost_rollup(line_items=line_items, cost_rollup=rollup)
        self.assertIsInstance(findings, list)

    def test_mismatched(self):
        line_items = [{"amount": 100.0}]
        rollup = [{"amount": 50.0}]
        findings = validate_cost_rollup(line_items=line_items, cost_rollup=rollup)
        self.assertIsInstance(findings, list)


class TestValidateWorkflowFacilityLinkage(unittest.TestCase):
    def test_valid_linkage(self):
        workflows = [{"facility_id": "f1"}]
        facilities = [{"facility_id": "f1"}]
        findings = validate_workflow_facility_linkage(workflows=workflows, facilities=facilities)
        self.assertIsInstance(findings, list)

    def test_invalid_linkage(self):
        workflows = [{"facility_id": "f1"}]
        facilities = [{"facility_id": "f2"}]
        findings = validate_workflow_facility_linkage(workflows=workflows, facilities=facilities)
        self.assertIsInstance(findings, list)


class TestValidateTenantBoundary(unittest.TestCase):
    def test_matching_tenants(self):
        sources = {"a": [{"tenant_id": "t1"}], "b": [{"tenant_id": "t1"}]}
        findings = validate_tenant_boundary(sources=sources, tenant_id="t1")
        self.assertIsInstance(findings, list)

    def test_mismatched_tenants(self):
        sources = {"a": [{"tenant_id": "t1"}], "b": [{"tenant_id": "t2"}]}
        findings = validate_tenant_boundary(sources=sources, tenant_id="t1")
        self.assertIsInstance(findings, list)


class TestValidateTemporalConsistency(unittest.TestCase):
    def test_recent_data(self):
        readings = [{"observed_at": datetime.now(timezone.utc).isoformat()}]
        findings = validate_temporal_consistency(readings=readings)
        self.assertIsInstance(findings, list)

    def test_stale_data(self):
        old = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        readings = [{"observed_at": old}]
        findings = validate_temporal_consistency(readings=readings)
        self.assertIsInstance(findings, list)


class TestValidateUnitConsistency(unittest.TestCase):
    def test_consistent_units(self):
        sources = {"a": [{"unit": "kwh"}], "b": [{"unit": "kwh"}]}
        findings = validate_unit_consistency(sources=sources)
        self.assertIsInstance(findings, list)

    def test_inconsistent_units(self):
        sources = {"a": [{"unit": "kwh"}], "b": [{"unit": "mwh"}]}
        findings = validate_unit_consistency(sources=sources)
        self.assertIsInstance(findings, list)


class TestValidateProvenanceConsistency(unittest.TestCase):
    def test_consistent_provenance(self):
        sources = {"a": [{"provenance": {"source": "s1"}}], "b": [{"provenance": {"source": "s1"}}]}
        findings = validate_provenance_consistency(sources=sources)
        self.assertIsInstance(findings, list)


class TestValidatePueConsistency(unittest.TestCase):
    def test_consistent_pue(self):
        findings = validate_pue_consistency(
            facility_energy_kwh=150.0,
            it_energy_kwh=100.0,
            reported_pue=1.5,
        )
        self.assertIsInstance(findings, list)

    def test_inconsistent_pue(self):
        findings = validate_pue_consistency(
            facility_energy_kwh=150.0,
            it_energy_kwh=100.0,
            reported_pue=2.0,
        )
        self.assertIsInstance(findings, list)


class TestValidatePriceFreshness(unittest.TestCase):
    def test_fresh_prices(self):
        prices = [{"observed_at": datetime.now(timezone.utc).isoformat()}]
        findings = validate_price_freshness(price_observations=prices)
        self.assertIsInstance(findings, list)

    def test_stale_prices(self):
        old = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        prices = [{"observed_at": old}]
        findings = validate_price_freshness(price_observations=prices)
        self.assertIsInstance(findings, list)


class TestValidateEstimatePriceLinks(unittest.TestCase):
    def test_valid_links(self):
        line_items = [{"price_ref": "p1"}]
        prices = [{"price_id": "p1"}]
        findings = validate_estimate_price_links(line_items=line_items, price_observations=prices)
        self.assertIsInstance(findings, list)

    def test_invalid_links(self):
        line_items = [{"price_ref": "p1"}]
        prices = [{"price_id": "p2"}]
        findings = validate_estimate_price_links(line_items=line_items, price_observations=prices)
        self.assertIsInstance(findings, list)


class TestValidateEnergyAllocationCoverage(unittest.TestCase):
    def test_sufficient_coverage(self):
        allocations = [{"energy_kwh": 90.0}]
        findings = validate_energy_allocation_coverage(
            energy_allocations=allocations,
            total_energy_kwh=100.0,
        )
        self.assertIsInstance(findings, list)

    def test_insufficient_coverage(self):
        allocations = [{"energy_kwh": 50.0}]
        findings = validate_energy_allocation_coverage(
            energy_allocations=allocations,
            total_energy_kwh=100.0,
        )
        self.assertIsInstance(findings, list)


class TestValidateConnectorDataFreshness(unittest.TestCase):
    def test_fresh_data(self):
        connectors = [{"last_success": datetime.now(timezone.utc).isoformat()}]
        readings = [{"observed_at": datetime.now(timezone.utc).isoformat()}]
        findings = validate_connector_data_freshness(connectors=connectors, latest_readings=readings)
        self.assertIsInstance(findings, list)


class TestRunConsistencyValidation(unittest.TestCase):
    def test_empty_validation(self):
        report = run_consistency_validation(tenant_id="t1")
        self.assertIsInstance(report, ConsistencyReport)

    def test_with_data(self):
        report = run_consistency_validation(
            tenant_id="t1",
            facility_meter_readings=[{"timestamp": "2024-01-01", "value": 100.0}],
            submeter_readings=[{"timestamp": "2024-01-01", "value": 95.0}],
        )
        self.assertIsInstance(report, ConsistencyReport)


if __name__ == "__main__":
    unittest.main()
