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
        from dcc.validation.boundaries import validate_meter_boundary, ValidationResult
        result = validate_meter_boundary(
            meter_id="m1",
            boundary="facility",
            direction="import",
            unit="kWh",
            readings=[{"value": 100.0, "unit": "kWh", "timestamp": "2026-01-01T00:00:00Z"}],
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_energy_allocation(self):
        from dcc.validation.boundaries import validate_energy_allocation, ValidationResult
        result = validate_energy_allocation(
            allocation_id="a1",
            workload_id="w1",
            window_start="2026-01-01T00:00:00Z",
            window_end="2026-01-01T01:00:00Z",
            energy_kwh=1000,
            allocation_method="proportional",
            coverage=0.9,
        )
        self.assertIsInstance(result, ValidationResult)


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
        from dcc.validation.consistency import reconcile_energy_sources, Severity
        result = reconcile_energy_sources(
            facility_meter_readings=[{"value_numeric": 1000}],
            submeter_readings=[{"value_numeric": 1000}],
        )
        self.assertIsNotNone(result)
        self.assertNotIn(Severity.FAIL, [f.severity for f in result])

    def test_validate_asset_references(self):
        from dcc.validation.consistency import validate_asset_references, Severity
        result = validate_asset_references(
            work_orders=[{"asset_id": "a1"}],
            assets=[{"id": "a1"}],
        )
        self.assertIsNotNone(result)
        self.assertNotIn(Severity.FAIL, [f.severity for f in result])

    def test_validate_capacity_headroom(self):
        from dcc.validation.consistency import validate_capacity_headroom
        result = validate_capacity_headroom(
            capacity_snapshots=[{"usable": 100, "reserved": 60, "policy_reserve": 10}],
            it_load_readings=[{"value_numeric": 30}],
        )
        self.assertIsNotNone(result)

    def test_validate_kpi_vs_telemetry(self):
        from dcc.validation.consistency import validate_kpi_vs_telemetry, Severity
        result = validate_kpi_vs_telemetry(
            kpi_observations=[{"value_numeric": 100}],
            telemetry_readings=[{"value_numeric": 100}],
        )
        self.assertIsNotNone(result)
        self.assertNotIn(Severity.FAIL, [f.severity for f in result])

    def test_validate_cost_rollup(self):
        from dcc.validation.consistency import validate_cost_rollup
        result = validate_cost_rollup(
            line_items=[{"extended_base": 100}],
            cost_rollup=[{"present_value_base": 100}],
        )
        self.assertIsNotNone(result)

    def test_validate_workflow_facility_linkage(self):
        from dcc.validation.consistency import validate_workflow_facility_linkage, Severity
        result = validate_workflow_facility_linkage(
            workflows=[{"facility_id": "f1"}],
            facilities=[{"id": "f1"}],
        )
        self.assertIsNotNone(result)
        self.assertNotIn(Severity.FAIL, [f.severity for f in result])

    def test_validate_tenant_boundary(self):
        from dcc.validation.consistency import validate_tenant_boundary, Severity
        result = validate_tenant_boundary(
            sources={"assets": [{"tenant_id": "t1", "id": "r1"}]},
            tenant_id="t1",
        )
        self.assertIsNotNone(result)
        self.assertNotIn(Severity.FAIL, [f.severity for f in result])

    def test_validate_temporal_consistency(self):
        from dcc.validation.consistency import validate_temporal_consistency
        result = validate_temporal_consistency(
            readings=[
                {"id": "e1", "observed_at": "2026-01-01T00:00:00Z"},
                {"id": "e2", "observed_at": "2026-01-02T00:00:00Z"},
            ],
            max_age_days=3650,
        )
        self.assertIsNotNone(result)

    def test_validate_unit_consistency(self):
        from dcc.validation.consistency import validate_unit_consistency
        result = validate_unit_consistency(
            sources={"telemetry": [{"value": 100, "unit": "kWh"}, {"value": 200, "unit": "kWh"}]},
            expected_unit="kWh",
        )
        self.assertIsNotNone(result)

    def test_validate_provenance_consistency(self):
        from dcc.validation.consistency import validate_provenance_consistency
        result = validate_provenance_consistency(
            sources={
                "telemetry": [{"id": "e1", "provenance": {"source": "test"}}],
                "prices": [{"id": "p1", "provenance": {"source": "test"}}],
            },
        )
        self.assertIsNotNone(result)

    def test_validate_pue_consistency(self):
        from dcc.validation.consistency import validate_pue_consistency, Severity
        result = validate_pue_consistency(
            facility_energy_kwh=150,
            it_energy_kwh=100,
            reported_pue=1.5,
        )
        self.assertIsNotNone(result)
        self.assertNotIn(Severity.FAIL, [f.severity for f in result])

    def test_validate_price_freshness(self):
        from dcc.validation.consistency import validate_price_freshness
        result = validate_price_freshness(
            price_observations=[
                {"item_code": "SRV-1", "observed_at": "2026-01-01T00:00:00Z"},
            ],
            max_age_days=3650,
        )
        self.assertIsNotNone(result)

    def test_validate_estimate_price_links(self):
        from dcc.validation.consistency import validate_estimate_price_links
        result = validate_estimate_price_links(
            line_items=[{"price_observation_id": "p1", "pricing_status": "sourced"}],
            price_observations=[{"id": "p1", "quality_status": "approved"}],
        )
        self.assertIsNotNone(result)

    def test_validate_energy_allocation_coverage(self):
        from dcc.validation.consistency import validate_energy_allocation_coverage
        result = validate_energy_allocation_coverage(
            energy_allocations=[{"energy_kwh": 900}],
            total_energy_kwh=1000,
        )
        self.assertIsNotNone(result)

    def test_validate_connector_data_freshness(self):
        from dcc.validation.consistency import validate_connector_data_freshness
        result = validate_connector_data_freshness(
            connectors=[{"id": "c1"}],
            latest_readings=[{"connector_id": "c1", "observed_at": "2026-01-01T00:00:00Z"}],
            max_stale_hours=24,
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
        from dcc.validation.intervals import detect_gaps, TimeSeries, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc), value=3),
        ]
        gaps = detect_gaps(TimeSeries(name="s", interval=300, points=points))
        self.assertIsNotNone(gaps)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].expected_points, 1)

    def test_downsample(self):
        from dcc.validation.intervals import downsample, TimeSeries, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
        ]
        result = downsample(TimeSeries(name="s", interval=300, points=points), 600)
        self.assertIsNotNone(result)
        self.assertEqual(result.interval, 600)
        self.assertEqual([p.value for p in result.points], [1.5])

    def test_upsample(self):
        from dcc.validation.intervals import upsample, TimeSeries, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc), value=2),
        ]
        result = upsample(TimeSeries(name="s", interval=600, points=points), 300)
        self.assertIsNotNone(result)
        self.assertEqual(result.interval, 300)
        self.assertEqual(len(result.points), 3)

    def test_coverage_report(self):
        from dcc.validation.intervals import coverage_report, TimeSeries, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
        ]
        report = coverage_report(
            [TimeSeries(name="s", interval=300, points=points)],
            300,
            start=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            end=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(report)
        self.assertEqual(report.total_expected, 3)

    def test_resample(self):
        from dcc.validation.intervals import resample, TimeSeries, DataPoint
        points = [
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1),
            DataPoint(timestamp=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc), value=2),
        ]
        result = resample(TimeSeries(name="s", interval=300, points=points), 600)
        self.assertIsNotNone(result)
        self.assertEqual(result.interval, 600)

    def test_align_series(self):
        from dcc.validation.intervals import align_series, TimeSeries, DataPoint
        series_a = TimeSeries(
            name="a", interval=300,
            points=[DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1)],
        )
        series_b = TimeSeries(
            name="b", interval=600,
            points=[DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=2)],
        )
        result = align_series([series_a, series_b])
        self.assertIsNotNone(result)
        # Aligned series share a single target interval.
        self.assertEqual({s.interval for s in result}, {600})

    def test_merge_aligned(self):
        from dcc.validation.intervals import merge_aligned, TimeSeries, DataPoint
        series_a = TimeSeries(
            name="a", interval=300,
            points=[DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=1)],
        )
        series_b = TimeSeries(
            name="b", interval=300,
            points=[DataPoint(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=2)],
        )
        result = merge_aligned([series_a, series_b])
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["a"], 1.0)
        self.assertEqual(result[0]["b"], 2.0)


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
        validator = SchemaValidator(
            "asset",
            {"asset_id": {"type": str, "required": True}},
        )
        self.assertEqual(validator.validate({"asset_id": "a1"}), {"asset_id": "a1"})

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
        from dcc.validation.units import convert
        result = convert(1000, "kW", source_unit="W")
        self.assertAlmostEqual(float(result.value), 1.0)

    def test_convert_energy(self):
        from dcc.validation.units import convert
        result = convert(1000, "kWh", source_unit="Wh")
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
        # Dimension is a plain Enum; compare on .value, not against the bare string.
        self.assertEqual(Dimension.POWER.value, "power")
        self.assertEqual(Dimension.ENERGY.value, "energy")
        self.assertEqual(Dimension.TEMPERATURE.value, "temperature")

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
