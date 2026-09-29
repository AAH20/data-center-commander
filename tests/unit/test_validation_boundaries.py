"""Unit tests for dcc.validation.boundaries module."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from dcc.validation.boundaries import (
    Severity,
    Finding,
    ValidationResult,
    ENERGY_UNIT_TO_KWH,
    POWER_UNIT_TO_KW,
    VALID_DIRECTIONS,
    USABLE_QUALITY,
    VALID_ALLOCATION_METHODS,
    validate_meter_boundary,
    validate_interval_alignment,
    validate_unit_compatibility,
    validate_quality_gate,
    validate_allocation_rule,
    validate_energy_balance,
    validate_tenant_scope,
    validate_measurement_continuity,
    validate_power_factor_range,
    validate_pue_range,
    validate_cooling_efficiency,
    validate_temperature_bounds,
    validate_pressure_bounds,
    validate_humidity_bounds,
    validate_flow_rate_bounds,
    validate_voltage_bounds,
    validate_current_bounds,
    validate_frequency_bounds,
    validate_carbon_intensity_bounds,
    validate_data_completeness,
    validate_duplicate_timestamps,
    validate_monotonic_timestamps,
    validate_value_range,
    validate_sign_consistency,
    validate_meter_direction,
    validate_allocation_method,
    validate_quality_status,
    validate_energy_unit,
    validate_power_unit,
    convert_energy_to_kwh,
    convert_power_to_kw,
    compute_energy_from_power,
    compute_power_from_energy,
    compute_pue,
    compute_cooling_load,
    compute_carbon_emissions,
    compute_dcime,
    compute_ups_runtime,
    compute_energy_cost,
    compute_demand_cost,
    compute_total_cost,
    compute_cost_per_kwh,
    compute_cost_per_kw,
    compute_cost_per_rack,
    compute_cost_per_m2,
    compute_cost_per_kwh_it,
    compute_cost_per_kwh_facility,
    compute_equivalent_annual_cost,
    compute_net_present_value,
    compute_internal_rate_of_return,
    compute_payback_period,
    compute_return_on_investment,
    compute_levelized_cost_of_energy,
    compute_carbon_abatement_cost,
    compute_energy_reuse_effectiveness,
    compute_water_usage_effectiveness,
    compute_carbon_usage_effectiveness,
    compute_it_equipment_utilization,
    compute_rack_space_utilization,
    compute_power_usage_effectiveness,
    compute_data_center_infrastructure_efficiency,
)


class TestSeverity(unittest.TestCase):
    def test_severity_values(self):
        self.assertEqual(Severity.INFO.value, "info")
        self.assertEqual(Severity.WARNING.value, "warning")
        self.assertEqual(Severity.ERROR.value, "error")
        self.assertEqual(Severity.CRITICAL.value, "critical")

    def test_severity_comparison(self):
        self.assertNotEqual(Severity.INFO, Severity.WARNING)
        self.assertNotEqual(Severity.ERROR, Severity.CRITICAL)


class TestFinding(unittest.TestCase):
    def test_finding_creation(self):
        f = Finding(code="TEST001", severity=Severity.INFO, message="Test")
        self.assertEqual(f.code, "TEST001")
        self.assertEqual(f.severity, Severity.INFO)
        self.assertEqual(f.message, "Test")
        self.assertIsNone(f.field)
        self.assertEqual(f.context, {})

    def test_finding_to_dict(self):
        f = Finding(code="E001", severity=Severity.ERROR, message="Error", field="x", context={"k": "v"})
        d = f.to_dict()
        self.assertEqual(d["code"], "E001")
        self.assertEqual(d["severity"], "error")
        self.assertEqual(d["message"], "Error")
        self.assertEqual(d["field"], "x")
        self.assertEqual(d["context"], {"k": "v"})


class TestValidationResult(unittest.TestCase):
    def test_passed_by_default(self):
        r = ValidationResult(passed=True)
        self.assertTrue(r.passed)
        self.assertEqual(r.findings, [])
        self.assertEqual(r.metrics, {})

    def test_add_info_keeps_passed(self):
        r = ValidationResult(passed=True)
        r.add(Finding(code="I", severity=Severity.INFO, message="ok"))
        self.assertTrue(r.passed)

    def test_add_warning_keeps_passed(self):
        r = ValidationResult(passed=True)
        r.add(Finding(code="W", severity=Severity.WARNING, message="warn"))
        self.assertTrue(r.passed)

    def test_add_error_fails(self):
        r = ValidationResult(passed=True)
        r.add(Finding(code="E", severity=Severity.ERROR, message="err"))
        self.assertFalse(r.passed)

    def test_add_critical_fails(self):
        r = ValidationResult(passed=True)
        r.add(Finding(code="C", severity=Severity.CRITICAL, message="crit"))
        self.assertFalse(r.passed)

    def test_to_dict(self):
        r = ValidationResult(passed=True)
        r.add(Finding(code="I", severity=Severity.INFO, message="ok"))
        d = r.to_dict()
        self.assertTrue(d["passed"])
        self.assertEqual(len(d["findings"]), 1)


class TestUnitCompatibility(unittest.TestCase):
    def test_energy_unit_to_kwh(self):
        self.assertEqual(ENERGY_UNIT_TO_KWH["kwh"], Decimal("1"))
        self.assertEqual(ENERGY_UNIT_TO_KWH["wh"], Decimal("0.001"))
        self.assertEqual(ENERGY_UNIT_TO_KWH["mwh"], Decimal("1000"))

    def test_power_unit_to_kw(self):
        self.assertEqual(POWER_UNIT_TO_KW["kw"], Decimal("1"))
        self.assertEqual(POWER_UNIT_TO_KW["w"], Decimal("0.001"))
        self.assertEqual(POWER_UNIT_TO_KW["mw"], Decimal("1000"))

    def test_valid_directions(self):
        self.assertIn("import", VALID_DIRECTIONS)
        self.assertIn("export", VALID_DIRECTIONS)
        self.assertIn("bidirectional", VALID_DIRECTIONS)
        self.assertIn("internal", VALID_DIRECTIONS)

    def test_usable_quality(self):
        self.assertIn("good", USABLE_QUALITY)
        self.assertIn("estimated", USABLE_QUALITY)

    def test_valid_allocation_methods(self):
        self.assertIn("direct_meter", VALID_ALLOCATION_METHODS)
        self.assertIn("device_model", VALID_ALLOCATION_METHODS)
        self.assertIn("capacity_share", VALID_ALLOCATION_METHODS)


class TestValidateMeterBoundary(unittest.TestCase):
    def test_valid_boundary(self):
        result = validate_meter_boundary(
            meter_id="m1",
            direction="import",
            tenant_id="t1",
            readings=[{"timestamp": "2024-01-01T00:00:00Z", "value": 100}],
        )
        self.assertIsInstance(result, ValidationResult)

    def test_invalid_direction(self):
        result = validate_meter_boundary(
            meter_id="m1",
            direction="invalid",
            tenant_id="t1",
            readings=[],
        )
        self.assertFalse(result.passed)

    def test_empty_readings(self):
        result = validate_meter_boundary(
            meter_id="m1",
            direction="import",
            tenant_id="t1",
            readings=[],
        )
        self.assertIsInstance(result, ValidationResult)


class TestValidateIntervalAlignment(unittest.TestCase):
    def test_aligned_intervals(self):
        result = validate_interval_alignment(
            interval_seconds=300,
            timestamps=[datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)],
        )
        self.assertIsInstance(result, ValidationResult)

    def test_misaligned_intervals(self):
        result = validate_interval_alignment(
            interval_seconds=300,
            timestamps=[datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)],
        )
        self.assertIsInstance(result, ValidationResult)


class TestValidateUnitCompatibility(unittest.TestCase):
    def test_compatible_units(self):
        result = validate_unit_compatibility(
            source_unit="kwh",
            target_unit="mwh",
        )
        self.assertIsInstance(result, ValidationResult)

    def test_incompatible_units(self):
        result = validate_unit_compatibility(
            source_unit="kwh",
            target_unit="kw",
        )
        self.assertFalse(result.passed)


class TestValidateQualityGate(unittest.TestCase):
    def test_good_quality(self):
        result = validate_quality_gate(
            quality_status="good",
            value=100.0,
        )
        self.assertIsInstance(result, ValidationResult)

    def test_bad_quality(self):
        result = validate_quality_gate(
            quality_status="bad",
            value=100.0,
        )
        self.assertFalse(result.passed)


class TestValidateAllocationRule(unittest.TestCase):
    def test_valid_allocation(self):
        result = validate_allocation_rule(
            method="direct_meter",
            total=Decimal("100"),
            allocated=Decimal("100"),
        )
        self.assertIsInstance(result, ValidationResult)

    def test_over_allocation(self):
        result = validate_allocation_rule(
            method="direct_meter",
            total=Decimal("100"),
            allocated=Decimal("150"),
        )
        self.assertFalse(result.passed)


class TestValidateEnergyBalance(unittest.TestCase):
    def test_balanced(self):
        result = validate_energy_balance(
            import_kwh=Decimal("100"),
            export_kwh=Decimal("0"),
            losses_kwh=Decimal("5"),
        )
        self.assertIsInstance(result, ValidationResult)

    def test_unbalanced(self):
        result = validate_energy_balance(
            import_kwh=Decimal("100"),
            export_kwh=Decimal("50"),
            losses_kwh=Decimal("5"),
        )
        self.assertFalse(result.passed)


class TestValidateTenantScope(unittest.TestCase):
    def test_matching_tenants(self):
        result = validate_tenant_scope(
            tenant_id="t1",
            records=[{"tenant_id": "t1"}, {"tenant_id": "t1"}],
        )
        self.assertTrue(result.passed)

    def test_mismatched_tenants(self):
        result = validate_tenant_scope(
            tenant_id="t1",
            records=[{"tenant_id": "t1"}, {"tenant_id": "t2"}],
        )
        self.assertFalse(result.passed)


class TestValidateMeasurementContinuity(unittest.TestCase):
    def test_continuous(self):
        result = validate_measurement_continuity(
            timestamps=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
            ],
            expected_interval_seconds=300,
        )
        self.assertIsInstance(result, ValidationResult)

    def test_gap_detected(self):
        result = validate_measurement_continuity(
            timestamps=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
            ],
            expected_interval_seconds=300,
        )
        self.assertFalse(result.passed)


class TestValidatePowerFactorRange(unittest.TestCase):
    def test_valid_pf(self):
        result = validate_power_factor_range(0.95)
        self.assertTrue(result.passed)

    def test_invalid_pf_high(self):
        result = validate_power_factor_range(1.5)
        self.assertFalse(result.passed)

    def test_invalid_pf_low(self):
        result = validate_power_factor_range(-0.5)
        self.assertFalse(result.passed)


class TestValidatePueRange(unittest.TestCase):
    def test_valid_pue(self):
        result = validate_pue_range(1.5)
        self.assertTrue(result.passed)

    def test_invalid_pue(self):
        result = validate_pue_range(0.5)
        self.assertFalse(result.passed)


class TestValidateCoolingEfficiency(unittest.TestCase):
    def test_valid_cop(self):
        result = validate_cooling_efficiency(3.0)
        self.assertTrue(result.passed)

    def test_invalid_cop(self):
        result = validate_cooling_efficiency(0.5)
        self.assertFalse(result.passed)


class TestValidateTemperatureBounds(unittest.TestCase):
    def test_valid_temp(self):
        result = validate_temperature_bounds(22.0)
        self.assertTrue(result.passed)

    def test_invalid_temp_high(self):
        result = validate_temperature_bounds(100.0)
        self.assertFalse(result.passed)

    def test_invalid_temp_low(self):
        result = validate_temperature_bounds(-50.0)
        self.assertFalse(result.passed)


class TestValidatePressureBounds(unittest.TestCase):
    def test_valid_pressure(self):
        result = validate_pressure_bounds(101325.0)
        self.assertTrue(result.passed)

    def test_invalid_pressure(self):
        result = validate_pressure_bounds(-100.0)
        self.assertFalse(result.passed)


class TestValidateHumidityBounds(unittest.TestCase):
    def test_valid_humidity(self):
        result = validate_humidity_bounds(50.0)
        self.assertTrue(result.passed)

    def test_invalid_humidity_high(self):
        result = validate_humidity_bounds(150.0)
        self.assertFalse(result.passed)

    def test_invalid_humidity_low(self):
        result = validate_humidity_bounds(-10.0)
        self.assertFalse(result.passed)


class TestValidateFlowRateBounds(unittest.TestCase):
    def test_valid_flow(self):
        result = validate_flow_rate_bounds(100.0)
        self.assertTrue(result.passed)

    def test_invalid_flow(self):
        result = validate_flow_rate_bounds(-5.0)
        self.assertFalse(result.passed)


class TestValidateVoltageBounds(unittest.TestCase):
    def test_valid_voltage(self):
        result = validate_voltage_bounds(230.0)
        self.assertTrue(result.passed)

    def test_invalid_voltage(self):
        result = validate_voltage_bounds(-10.0)
        self.assertFalse(result.passed)


class TestValidateCurrentBounds(unittest.TestCase):
    def test_valid_current(self):
        result = validate_current_bounds(50.0)
        self.assertTrue(result.passed)

    def test_invalid_current(self):
        result = validate_current_bounds(-5.0)
        self.assertFalse(result.passed)


class TestValidateFrequencyBounds(unittest.TestCase):
    def test_valid_frequency(self):
        result = validate_frequency_bounds(60.0)
        self.assertTrue(result.passed)

    def test_invalid_frequency(self):
        result = validate_frequency_bounds(0.0)
        self.assertFalse(result.passed)


class TestValidateCarbonIntensityBounds(unittest.TestCase):
    def test_valid_carbon(self):
        result = validate_carbon_intensity_bounds(0.5)
        self.assertTrue(result.passed)

    def test_invalid_carbon(self):
        result = validate_carbon_intensity_bounds(-0.1)
        self.assertFalse(result.passed)


class TestValidateDataCompleteness(unittest.TestCase):
    def test_complete(self):
        result = validate_data_completeness(
            records=[{"a": 1, "b": 2}],
            required_fields=["a", "b"],
        )
        self.assertTrue(result.passed)

    def test_incomplete(self):
        result = validate_data_completeness(
            records=[{"a": 1}],
            required_fields=["a", "b"],
        )
        self.assertFalse(result.passed)


class TestValidateDuplicateTimestamps(unittest.TestCase):
    def test_no_duplicates(self):
        result = validate_duplicate_timestamps(
            timestamps=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
            ],
        )
        self.assertTrue(result.passed)

    def test_duplicates_found(self):
        result = validate_duplicate_timestamps(
            timestamps=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            ],
        )
        self.assertFalse(result.passed)


class TestValidateMonotonicTimestamps(unittest.TestCase):
    def test_monotonic(self):
        result = validate_monotonic_timestamps(
            timestamps=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
            ],
        )
        self.assertTrue(result.passed)

    def test_non_monotonic(self):
        result = validate_monotonic_timestamps(
            timestamps=[
                datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            ],
        )
        self.assertFalse(result.passed)


class TestValidateValueRange(unittest.TestCase):
    def test_in_range(self):
        result = validate_value_range(50.0, min_val=0.0, max_val=100.0)
        self.assertTrue(result.passed)

    def test_below_range(self):
        result = validate_value_range(-10.0, min_val=0.0, max_val=100.0)
        self.assertFalse(result.passed)

    def test_above_range(self):
        result = validate_value_range(150.0, min_val=0.0, max_val=100.0)
        self.assertFalse(result.passed)


class TestValidateSignConsistency(unittest.TestCase):
    def test_consistent_positive(self):
        result = validate_sign_consistency(
            values=[1.0, 2.0, 3.0],
            expected_sign="positive",
        )
        self.assertTrue(result.passed)

    def test_inconsistent_sign(self):
        result = validate_sign_consistency(
            values=[1.0, -2.0, 3.0],
            expected_sign="positive",
        )
        self.assertFalse(result.passed)


class TestValidateMeterDirection(unittest.TestCase):
    def test_valid_import(self):
        result = validate_meter_direction("import")
        self.assertTrue(result.passed)

    def test_valid_export(self):
        result = validate_meter_direction("export")
        self.assertTrue(result.passed)

    def test_invalid_direction(self):
        result = validate_meter_direction("sideways")
        self.assertFalse(result.passed)


class TestValidateAllocationMethod(unittest.TestCase):
    def test_valid_method(self):
        result = validate_allocation_method("direct_meter")
        self.assertTrue(result.passed)

    def test_invalid_method(self):
        result = validate_allocation_method("magic")
        self.assertFalse(result.passed)


class TestValidateQualityStatus(unittest.TestCase):
    def test_good(self):
        result = validate_quality_status("good")
        self.assertTrue(result.passed)

    def test_estimated(self):
        result = validate_quality_status("estimated")
        self.assertTrue(result.passed)

    def test_bad(self):
        result = validate_quality_status("bad")
        self.assertFalse(result.passed)


class TestValidateEnergyUnit(unittest.TestCase):
    def test_valid_kwh(self):
        result = validate_energy_unit("kwh")
        self.assertTrue(result.passed)

    def test_valid_mwh(self):
        result = validate_energy_unit("mwh")
        self.assertTrue(result.passed)

    def test_invalid_unit(self):
        result = validate_energy_unit("invalid")
        self.assertFalse(result.passed)


class TestValidatePowerUnit(unittest.TestCase):
    def test_valid_kw(self):
        result = validate_power_unit("kw")
        self.assertTrue(result.passed)

    def test_valid_mw(self):
        result = validate_power_unit("mw")
        self.assertTrue(result.passed)

    def test_invalid_unit(self):
        result = validate_power_unit("invalid")
        self.assertFalse(result.passed)


class TestConvertEnergyToKwh(unittest.TestCase):
    def test_kwh_to_kwh(self):
        self.assertEqual(convert_energy_to_kwh(Decimal("100"), "kwh"), Decimal("100"))

    def test_wh_to_kwh(self):
        self.assertEqual(convert_energy_to_kwh(Decimal("1000"), "wh"), Decimal("1"))

    def test_mwh_to_kwh(self):
        self.assertEqual(convert_energy_to_kwh(Decimal("1"), "mwh"), Decimal("1000"))


class TestConvertPowerToKw(unittest.TestCase):
    def test_kw_to_kw(self):
        self.assertEqual(convert_power_to_kw(Decimal("100"), "kw"), Decimal("100"))

    def test_w_to_kw(self):
        self.assertEqual(convert_power_to_kw(Decimal("1000"), "w"), Decimal("1"))

    def test_mw_to_kw(self):
        self.assertEqual(convert_power_to_kw(Decimal("1"), "mw"), Decimal("1000"))


class TestComputeEnergyFromPower(unittest.TestCase):
    def test_basic(self):
        result = compute_energy_from_power(10.0, 5.0)
        self.assertAlmostEqual(result, 50.0)

    def test_zero_power(self):
        result = compute_energy_from_power(0.0, 5.0)
        self.assertAlmostEqual(result, 0.0)


class TestComputePowerFromEnergy(unittest.TestCase):
    def test_basic(self):
        result = compute_power_from_energy(50.0, 5.0)
        self.assertAlmostEqual(result, 10.0)

    def test_zero_duration(self):
        with self.assertRaises(ValueError):
            compute_power_from_energy(50.0, 0.0)


class TestComputePue(unittest.TestCase):
    def test_basic(self):
        result = compute_pue(150.0, 100.0)
        self.assertAlmostEqual(result, 1.5)

    def test_zero_it(self):
        with self.assertRaises(ValueError):
            compute_pue(150.0, 0.0)


class TestComputeCoolingLoad(unittest.TestCase):
    def test_basic(self):
        result = compute_cooling_load(100.0, 0.45)
        self.assertAlmostEqual(result, 45.0)


class TestComputeCarbonEmissions(unittest.TestCase):
    def test_basic(self):
        result = compute_carbon_emissions(1000.0, 0.5)
        self.assertAlmostEqual(result, 500.0)


class TestComputeDcime(unittest.TestCase):
    def test_basic(self):
        result = compute_dcime(100.0, 150.0)
        self.assertAlmostEqual(result, 100.0 / 150.0)


class TestComputeUpsRuntime(unittest.TestCase):
    def test_basic(self):
        result = compute_ups_runtime(100.0, 50.0, 0.9)
        self.assertAlmostEqual(result, 100.0 / (50.0 * 0.9))


class TestComputeEnergyCost(unittest.TestCase):
    def test_basic(self):
        result = compute_energy_cost(1000.0, 0.10)
        self.assertAlmostEqual(result, 100.0)


class TestComputeDemandCost(unittest.TestCase):
    def test_basic(self):
        result = compute_demand_cost(50.0, 15.0)
        self.assertAlmostEqual(result, 750.0)


class TestComputeTotalCost(unittest.TestCase):
    def test_basic(self):
        result = compute_total_cost(100.0, 50.0, 25.0)
        self.assertAlmostEqual(result, 175.0)


class TestComputeCostPerKwh(unittest.TestCase):
    def test_basic(self):
        result = compute_cost_per_kwh(100.0, 1000.0)
        self.assertAlmostEqual(result, 0.1)


class TestComputeCostPerKw(unittest.TestCase):
    def test_basic(self):
        result = compute_cost_per_kw(1000.0, 100.0)
        self.assertAlmostEqual(result, 10.0)


class TestComputeCostPerRack(unittest.TestCase):
    def test_basic(self):
        result = compute_cost_per_rack(50000.0, 100.0)
        self.assertAlmostEqual(result, 500.0)


class TestComputeCostPerM2(unittest.TestCase):
    def test_basic(self):
        result = compute_cost_per_m2(100000.0, 500.0)
        self.assertAlmostEqual(result, 200.0)


class TestComputeCostPerKwhIt(unittest.TestCase):
    def test_basic(self):
        result = compute_cost_per_kwh_it(100.0, 500.0)
        self.assertAlmostEqual(result, 0.2)


class TestComputeCostPerKwhFacility(unittest.TestCase):
    def test_basic(self):
        result = compute_cost_per_kwh_facility(150.0, 500.0)
        self.assertAlmostEqual(result, 0.3)


class TestComputeEquivalentAnnualCost(unittest.TestCase):
    def test_basic(self):
        result = compute_equivalent_annual_cost(10000.0, 10, 0.08)
        self.assertGreater(result, 0)


class TestComputeNetPresentValue(unittest.TestCase):
    def test_basic(self):
        result = compute_net_present_value([-1000, 500, 500, 500], 0.1)
        self.assertGreater(result, 0)


class TestComputeInternalRateOfReturn(unittest.TestCase):
    def test_basic(self):
        result = compute_internal_rate_of_return([-1000, 500, 500, 500])
        self.assertIsNotNone(result)


class TestComputePaybackPeriod(unittest.TestCase):
    def test_basic(self):
        result = compute_payback_period(1000.0, 250.0)
        self.assertAlmostEqual(result, 4.0)


class TestComputeReturnOnInvestment(unittest.TestCase):
    def test_basic(self):
        result = compute_return_on_investment(1500.0, 1000.0)
        self.assertAlmostEqual(result, 0.5)


class TestComputeLevelizedCostOfEnergy(unittest.TestCase):
    def test_basic(self):
        result = compute_levelized_cost_of_energy(1000000.0, 500000.0)
        self.assertAlmostEqual(result, 2.0)


class TestComputeCarbonAbatementCost(unittest.TestCase):
    def test_basic(self):
        result = compute_carbon_abatement_cost(100000.0, 500.0)
        self.assertAlmostEqual(result, 200.0)


class TestComputeEnergyReuseEffectiveness(unittest.TestCase):
    def test_basic(self):
        result = compute_energy_reuse_effectiveness(50.0, 100.0)
        self.assertAlmostEqual(result, 0.5)


class TestComputeWaterUsageEffectiveness(unittest.TestCase):
    def test_basic(self):
        result = compute_water_usage_effectiveness(1000.0, 500.0)
        self.assertAlmostEqual(result, 2.0)


class TestComputeCarbonUsageEffectiveness(unittest.TestCase):
    def test_basic(self):
        result = compute_carbon_usage_effectiveness(1000.0, 500.0)
        self.assertAlmostEqual(result, 2.0)


class TestComputeItEquipmentUtilization(unittest.TestCase):
    def test_basic(self):
        result = compute_it_equipment_utilization(80.0, 100.0)
        self.assertAlmostEqual(result, 0.8)


class TestComputeRackSpaceUtilization(unittest.TestCase):
    def test_basic(self):
        result = compute_rack_space_utilization(40.0, 50.0)
        self.assertAlmostEqual(result, 0.8)


class TestComputePowerUsageEffectiveness(unittest.TestCase):
    def test_basic(self):
        result = compute_power_usage_effectiveness(100.0, 150.0)
        self.assertAlmostEqual(result, 100.0 / 150.0)


class TestComputeDataCenterInfrastructureEfficiency(unittest.TestCase):
    def test_basic(self):
        result = compute_data_center_infrastructure_efficiency(100.0, 150.0)
        self.assertAlmostEqual(result, 100.0 / 150.0)


if __name__ == "__main__":
    unittest.main()
