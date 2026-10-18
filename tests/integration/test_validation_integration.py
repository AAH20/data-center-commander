"""Integration tests for validation modules.

Tests boundaries, consistency, intervals, schema, and units validation.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal


class TestBoundariesIntegration(unittest.TestCase):
    """Integration tests for boundary validation."""

    def test_validation_result_pass(self):
        from dcc.validation.boundaries import ValidationResult, Finding, Severity
        result = ValidationResult(passed=True)
        result.add(Finding(code="TEST", severity=Severity.INFO, message="Test"))
        self.assertTrue(result.passed)

    def test_validation_result_fail_on_error(self):
        from dcc.validation.boundaries import ValidationResult, Finding, Severity
        result = ValidationResult(passed=True)
        result.add(Finding(code="ERR", severity=Severity.ERROR, message="Error"))
        self.assertFalse(result.passed)

    def test_validation_result_fail_on_critical(self):
        from dcc.validation.boundaries import ValidationResult, Finding, Severity
        result = ValidationResult(passed=True)
        result.add(Finding(code="CRIT", severity=Severity.CRITICAL, message="Critical"))
        self.assertFalse(result.passed)

    def test_validation_result_to_dict(self):
        from dcc.validation.boundaries import ValidationResult, Finding, Severity
        result = ValidationResult(passed=True)
        result.add(Finding(code="TEST", severity=Severity.INFO, message="Test"))
        d = result.to_dict()
        self.assertIn("passed", d)
        self.assertIn("findings", d)

    def test_finding_to_dict(self):
        from dcc.validation.boundaries import Finding, Severity
        finding = Finding(code="TEST", severity=Severity.INFO, message="Test", field="test_field")
        d = finding.to_dict()
        self.assertEqual(d["code"], "TEST")
        self.assertEqual(d["severity"], "info")

    def test_energy_unit_to_kwh(self):
        from dcc.validation.boundaries import ENERGY_UNIT_TO_KWH
        self.assertIn("wh", ENERGY_UNIT_TO_KWH)
        self.assertIn("kwh", ENERGY_UNIT_TO_KWH)
        self.assertIn("mwh", ENERGY_UNIT_TO_KWH)

    def test_validate_meter_reading(self):
        from dcc.validation.boundaries import validate_meter_reading
        result = validate_meter_reading(
            reading={"value": 100.0, "unit": "kWh", "timestamp": "2026-01-01T00:00:00Z"},
            meter_boundary={"min": 0, "max": 10000},
        )
        self.assertIsNotNone(result)

    def test_validate_energy_allocation(self):
        from dcc.validation.boundaries import validate_energy_allocation
        result = validate_energy_allocation(
            allocation={"energy_kwh": 1000, "coverage": 0.9},
            total_energy=1200,
        )
        self.assertIsNotNone(result)


class TestConsistencyIntegration(unittest.TestCase):
    """Integration tests for consistency validation."""

    def test_consistency_report_pass(self):
        from dcc.validation.consistency import ConsistencyReport, Finding, Severity
        report = ConsistencyReport()
        report.add(Finding(check="test", severity=Severity.PASS, message="OK"))
        self.assertTrue(report.passed)

    def test_consistency_report_fail(self):
        from dcc.validation.consistency import ConsistencyReport, Finding, Severity
        report = ConsistencyReport()
        report.add(Finding(check="test", severity=Severity.FAIL, message="Fail"))
        self.assertFalse(report.passed)

    def test_consistency_report_warnings(self):
        from dcc.validation.consistency import ConsistencyReport, Finding, Severity
        report = ConsistencyReport()
        report.add(Finding(check="test", severity=Severity.WARN, message="Warning"))
        self.assertEqual(len(report.warnings), 1)

    def test_consistency_report_failures(self):
        from dcc.validation.consistency import ConsistencyReport, Finding, Severity
        report = ConsistencyReport()
        report.add(Finding(check="test", severity=Severity.FAIL, message="Fail"))
        self.assertEqual(len(report.failures), 1)

    def test_finding_to_dict(self):
        from dcc.validation.consistency import Finding, Severity
        finding = Finding(check="test", severity=Severity.PASS, message="OK", source_a="a", source_b="b")
        d = finding.to_dict()
        self.assertEqual(d["check"], "test")
        self.assertEqual(d["severity"], "pass")

    def test_reconcile_energy_sources(self):
        from dcc.validation.consistency import reconcile_energy_sources
        result = reconcile_energy_sources(
            source_a={"total_kwh": 1000},
            source_b={"total_kwh": 1000},
        )
        self.assertIsNotNone(result)

    def test_validate_asset_references(self):
        from dcc.validation.consistency import validate_asset_references
        result = validate_asset_references(
            assets=[{"id": "a1", "name": "Asset 1"}],
            references=[{"asset_id": "a1"}],
        )
        self.assertIsNotNone(result)

    def test_validate_capacity_headroom(self):
        from dcc.validation.consistency import validate_capacity_headroom
        result = validate_capacity_headroom(
            usable=100,
            reserved=60,
            policy_reserve=10,
        )
        self.assertIsNotNone(result)

    def test_validate_kpi_vs_telemetry(self):
        from dcc.validation.consistency import validate_kpi_vs_telemetry
        result = validate_kpi_vs_telemetry(
            kpi_value=100,
            telemetry_sum=100,
        )
        self.assertIsNotNone(result)

    def test_validate_cost_rollup(self):
        from dcc.validation.consistency import validate_cost_rollup
        result = validate_cost_rollup(
            line_items=[{"extended_base": 100, "extended_low": 90, "extended_high": 110}],
            rollup={"present_value_base": 100},
        )
        self.assertIsNotNone(result)

    def test_validate_workflow_facility_linkage(self):
        from dcc.validation.consistency import validate_workflow_facility_linkage
        result = validate_workflow_facility_linkage(
            workflows=[{"id": "w1", "facility_id": "f1"}],
            facilities=[{"id": "f1"}],
        )
        self.assertIsNotNone(result)

    def test_validate_tenant_boundary(self):
        from dcc.validation.consistency import validate_tenant_boundary
        result = validate_tenant_boundary(
            tenant_id="t1",
            rows=[{"tenant_id": "t1", "id": "r1"}],
        )
        self.assertIsNotNone(result)

    def test_validate_temporal_consistency(self):
        from dcc.validation.consistency import validate_temporal_consistency
        result = validate_temporal_consistency(
            events=[
                {"id": "e1", "occurred_at": "2026-01-01T00:00:00Z"},
                {"id": "e2", "occurred_at": "2026-01-02T00:00:00Z"},
            ],
        )
        self.assertIsNotNone(result)

    def test_validate_unit_consistency(self):
        from dcc.validation.consistency import validate_unit_consistency
        result = validate_unit_consistency(
            readings=[
                {"value": 100, "unit": "kWh"},
                {"value": 200, "unit": "kWh"},
            ],
        )
        self.assertIsNotNone(result)

    def test_validate_provenance_consistency(self):
        from dcc.validation.consistency import validate_provenance_consistency
        result = validate_provenance_consistency(
            events=[
                {"id": "e1", "provenance": {"source": "test"}},
            ],
        )
        self.assertIsNotNone(result)

    def test_validate_pue_consistency(self):
        from dcc.validation.consistency import validate_pue_consistency
        result = validate_pue_consistency(
            it_energy=100,
            total_energy=150,
        )
        self.assertIsNotNone(result)

    def test_validate_price_freshness(self):
        from dcc.validation.consistency import validate_price_freshness
        result = validate_price_freshness(
            prices=[
                {"item_code": "SRV-1", "observed_at": "2026-01-01T00:00:00Z"},
            ],
            max_age_days=30,
        )
        self.assertIsNotNone(result)

    def test_validate_estimate_price_links(self):
        from dcc.validation.consistency import validate_estimate_price_links
        result = validate_estimate_price_links(
            line_items=[{"price_observation_id": "p1", "pricing_status": "sourced"}],
            prices=[{"id": "p1", "quality_status": "approved"}],
        )
        self.assertIsNotNone(result)

    def test_validate_energy_allocation_coverage(self):
        from dcc.validation.consistency import validate_energy_allocation_coverage
        result = validate_energy_allocation_coverage(
            allocations=[
                {"workload_id": "w1", "coverage": 0.9},
            ],
            workloads=[{"id": "w1"}, {"id": "w2"}],
        )
        self.assertIsNotNone(result)

    def test_validate_connector_data_freshness(self):
        from dcc.validation.consistency import validate_connector_data_freshness
        result = validate_connector_data_freshness(
            connectors=[
                {"id": "c1", "last_success_at": "2026-01-01T00:00:00Z"},
            ],
            max_age_hours=24,
        )
        self.assertIsNotNone(result)


class TestIntervalsIntegration(unittest.TestCase):
    """Integration tests for interval alignment."""

    def test_interval_seconds(self):
        from dcc.validation.intervals import interval_seconds
        self.assertEqual(interval_seconds("1min"), 60)
        self.assertEqual(interval_seconds("5min"), 300)
        self.assertEqual(interval_seconds("15min"), 900)
        self.assertEqual(interval_seconds("1hr"), 3600)

    def test_interval_seconds_rejects_invalid(self):
        from dcc.validation.intervals import interval_seconds
        with self.assertRaises(ValueError):
            interval_seconds("invalid")

    def test_interval_name(self):
        from dcc.validation.intervals import interval_name
        self.assertEqual(interval_name(60), "1min")
        self.assertEqual(interval_name(300), "5min")
        self.assertEqual(interval_name(900), "15min")
        self.assertEqual(interval_name(3600), "1hr")

    def test_interval_name_rejects_invalid(self):
        from dcc.validation.intervals import interval_name
        with self.assertRaises(ValueError):
            interval_name(123)

    def test_floor_timestamp(self):
        from dcc.validation.intervals import floor_timestamp
        ts = datetime(2026, 1, 1, 0, 7, 30, tzinfo=timezone.utc)
        result = floor_timestamp(ts, 300)
        self.assertEqual(result.minute, 5)

    def test_floor_timestamp_rejects_zero(self):
        from dcc.validation.intervals import floor_timestamp
        with self.assertRaises(ValueError):
            floor_timestamp(datetime.now(timezone.utc), 0)

    def test_align_timestamp(self):
        from dcc.validation.intervals import align_timestamp
        ts = datetime(2026, 1, 1, 0, 7, 30, tzinfo=timezone.utc)
        result = align_timestamp(ts, 300)
        self.assertEqual(result.minute, 5)

    def test_detect_gaps(self):
        from dcc.validation.intervals import detect_gaps, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc), value=3),
        ]
        gaps = detect_gaps(points, expected_interval=300)
        self.assertIsNotNone(gaps)

    def test_downsample(self):
        from dcc.validation.intervals import downsample, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
        ]
        result = downsample(points, interval=600, aggregation="mean")
        self.assertIsNotNone(result)

    def test_upsample(self):
        from dcc.validation.intervals import upsample, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc), value=2),
        ]
        result = upsample(points, interval=300, method="forward_fill")
        self.assertIsNotNone(result)

    def test_coverage_report(self):
        from dcc.validation.intervals import coverage_report, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
        ]
        report = coverage_report(points, start=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), end=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc), expected_interval=300)
        self.assertIsNotNone(report)

    def test_resample(self):
        from dcc.validation.intervals import resample, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
        ]
        result = resample(points, interval=600)
        self.assertIsNotNone(result)

    def test_align_series(self):
        from dcc.validation.intervals import align_series, DataPoint
        series_a = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
        ]
        series_b = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=2),
        ]
        result = align_series(series_a, series_b)
        self.assertIsNotNone(result)

    def test_merge_aligned(self):
        from dcc.validation.intervals import merge_aligned, DataPoint
        series_a = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
        ]
        series_b = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=2),
        ]
        result = merge_aligned(series_a, series_b)
        self.assertIsNotNone(result)


class TestSchemaIntegration(unittest.TestCase):
    """Integration tests for schema validation."""

    def test_validate_tenant_id(self):
        from dcc.validation.schema import validate_tenant_id
        result = validate_tenant_id("dcc00000-0000-4000-8000-000000000001")
        self.assertEqual(result, "dcc00000-0000-4000-8000-000000000001")

    def test_validate_tenant_id_rejects_invalid(self):
        from dcc.validation.schema import validate_tenant_id, ValidationError
        with self.assertRaises(ValidationError):
            validate_tenant_id("not-a-uuid")

    def test_validate_window_days(self):
        from dcc.validation.schema import validate_window_days
        self.assertEqual(validate_window_days(30), 30)

    def test_validate_window_days_rejects_zero(self):
        from dcc.validation.schema import validate_window_days, ValidationError
        with self.assertRaises(ValidationError):
            validate_window_days(0)

    def test_validate_window_days_rejects_over_90(self):
        from dcc.validation.schema import validate_window_days, ValidationError
        with self.assertRaises(ValidationError):
            validate_window_days(91)

    def test_validate_currency_code(self):
        from dcc.validation.schema import validate_currency_code
        self.assertEqual(validate_currency_code("USD"), "USD")

    def test_validate_currency_code_rejects_invalid(self):
        from dcc.validation.schema import validate_currency_code, ValidationError
        with self.assertRaises(ValidationError):
            validate_currency_code("US")

    def test_validate_service_name(self):
        from dcc.validation.schema import validate_service_name
        result = validate_service_name("Virtual Machines")
        self.assertEqual(result, "Virtual Machines")

    def test_validate_service_name_rejects_invalid(self):
        from dcc.validation.schema import validate_service_name, ValidationError
        with self.assertRaises(ValidationError):
            validate_service_name("Virtual Machines'; DROP TABLE--")

    def test_validate_region(self):
        from dcc.validation.schema import validate_region
        result = validate_region("eastus")
        self.assertEqual(result, "eastus")

    def test_validate_sku(self):
        from dcc.validation.schema import validate_sku
        result = validate_sku("Standard_D2s_v5")
        self.assertEqual(result, "Standard_D2s_v5")

    def test_validate_sku_query(self):
        from dcc.validation.schema import validate_sku_query
        result = validate_sku_query("Standard D2s v5")
        self.assertEqual(result, "Standard D2s v5")

    def test_validate_api_key(self):
        from dcc.validation.schema import validate_api_key
        result = validate_api_key("test-key-123")
        self.assertEqual(result, "test-key-123")

    def test_validate_api_key_rejects_empty(self):
        from dcc.validation.schema import validate_api_key, ValidationError
        with self.assertRaises(ValidationError):
            validate_api_key("")

    def test_schema_validator_class(self):
        from dcc.validation.schema import SchemaValidator
        validator = SchemaValidator()
        self.assertIsNotNone(validator)

    def test_validation_error_with_field(self):
        from dcc.validation.schema import ValidationError
        error = ValidationError("Test error", field="test_field")
        self.assertEqual(error.field, "test_field")

    def test_constraint_violation(self):
        from dcc.validation.schema import ConstraintViolation
        error = ConstraintViolation("Test", field="test_field", constraint="test_constraint")
        self.assertEqual(error.constraint, "test_constraint")


class TestUnitsIntegration(unittest.TestCase):
    """Integration tests for unit conversion."""

    def test_convert_power(self):
        from dcc.validation.units import convert, get_registry
        registry = get_registry()
        result = convert(1000, "W", "kW")
        self.assertAlmostEqual(float(result.value), 1.0)

    def test_convert_energy(self):
        from dcc.validation.units import convert
        result = convert(1000, "Wh", "kWh")
        self.assertAlmostEqual(float(result.value), 1.0)

    def test_convert_temperature_c_to_f(self):
        from dcc.validation.units import convert_temperature
        result = convert_temperature(0, "C", "F")
        self.assertAlmostEqual(float(result.value), 32.0)

    def test_convert_temperature_f_to_c(self):
        from dcc.validation.units import convert_temperature
        result = convert_temperature(32, "F", "C")
        self.assertAlmostEqual(float(result.value), 0.0)

    def test_convert_temperature_c_to_k(self):
        from dcc.validation.units import convert_temperature
        result = convert_temperature(0, "C", "K")
        self.assertAlmostEqual(float(result.value), 273.15)

    def test_convert_with_power_factor(self):
        from dcc.validation.units import convert_with_power_factor
        result = convert_with_power_factor(1000, "W", "VA", power_factor=0.9)
        self.assertAlmostEqual(float(result.value), 1111.11, places=1)

    def test_get_registry_singleton(self):
        from dcc.validation.units import get_registry
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)

    def test_dimension_enum(self):
        from dcc.validation.units import Dimension
        self.assertEqual(Dimension.POWER, "power")
        self.assertEqual(Dimension.ENERGY, "energy")
        self.assertEqual(Dimension.TEMPERATURE, "temperature")

    def test_quantity_creation(self):
        from dcc.validation.units import Quantity, Unit, Dimension
        unit = Unit(name="Watt", symbol="W", dimension=Dimension.POWER)
        quantity = Quantity(value=Decimal("100"), unit=unit)
        self.assertEqual(quantity.value, Decimal("100"))

    def test_quantity_rejects_zero_sig_figs(self):
        from dcc.validation.units import Quantity, Unit, Dimension
        unit = Unit(name="Watt", symbol="W", dimension=Dimension.POWER)
        with self.assertRaises(ValueError):
            Quantity(value=Decimal("100"), unit=unit, sig_figs=0)

    def test_unit_rejects_zero_to_base(self):
        from dcc.validation.units import Unit, Dimension
        with self.assertRaises(ValueError):
            Unit(name="Invalid", symbol="X", dimension=Dimension.POWER, to_base=Decimal("0"))


if __name__ == "__main__":
    unittest.main()
