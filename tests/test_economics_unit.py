"""Tests for unit economics calculations."""
import unittest

from dcc.economics.unit import (
    NOT_PRICED,
    UNKNOWN,
    UnitEconomicsResult,
    compute_all_unit_economics,
    cost_per_kwh,
    cost_per_kw_year,
    cost_per_m2_year,
    cost_per_rack_year,
    cost_per_work_unit,
    equivalent_annual_cost,
)


class TestEquivalentAnnualCost(unittest.TestCase):
    """Tests for equivalent_annual_cost function."""

    def test_zero_discount_rate(self):
        """EAC = PV / n when r = 0."""
        self.assertAlmostEqual(equivalent_annual_cost(1000, 5, 0), 200.0)
        self.assertAlmostEqual(equivalent_annual_cost(0, 10, 0), 0.0)
        self.assertAlmostEqual(equivalent_annual_cost(500, 1, 0), 500.0)

    def test_positive_discount_rate(self):
        """EAC = PV * r / (1 - (1+r)^(-n)) when r > 0."""
        # PV=1000, n=5, r=0.1
        # EAC = 1000 * 0.1 / (1 - 1.1^(-5)) = 100 / (1 - 0.6209) = 100 / 0.3791 ≈ 263.80
        result = equivalent_annual_cost(1000, 5, 0.1)
        self.assertAlmostEqual(result, 263.80, places=2)

    def test_high_discount_rate(self):
        """Higher discount rate increases EAC."""
        eac_low = equivalent_annual_cost(1000, 5, 0.05)
        eac_high = equivalent_annual_cost(1000, 5, 0.15)
        self.assertGreater(eac_high, eac_low)

    def test_long_horizon(self):
        """Longer horizon decreases EAC."""
        eac_short = equivalent_annual_cost(1000, 5, 0.1)
        eac_long = equivalent_annual_cost(1000, 20, 0.1)
        self.assertLess(eac_long, eac_short)

    def test_invalid_pv(self):
        """Negative PV raises ValueError."""
        with self.assertRaises(ValueError):
            equivalent_annual_cost(-100, 5, 0.1)

    def test_invalid_years(self):
        """Non-positive years raises ValueError."""
        with self.assertRaises(ValueError):
            equivalent_annual_cost(1000, 0, 0.1)
        with self.assertRaises(ValueError):
            equivalent_annual_cost(1000, -5, 0.1)

    def test_invalid_rate(self):
        """Rate outside [0, 1) raises ValueError."""
        with self.assertRaises(ValueError):
            equivalent_annual_cost(1000, 5, -0.1)
        with self.assertRaises(ValueError):
            equivalent_annual_cost(1000, 5, 1.0)
        with self.assertRaises(ValueError):
            equivalent_annual_cost(1000, 5, 1.5)

    def test_zero_pv(self):
        """Zero PV returns zero EAC."""
        self.assertEqual(equivalent_annual_cost(0, 5, 0.1), 0.0)


class TestCostPerKwYear(unittest.TestCase):
    """Tests for cost_per_kw_year function."""

    def test_basic_calculation(self):
        """Basic cost per kW-year calculation."""
        result = cost_per_kw_year(10000, 100)
        self.assertEqual(result.value, 100.0)
        self.assertEqual(result.unit, "USD/kW-year")
        self.assertEqual(result.status, "ok")

    def test_zero_capacity(self):
        """Zero capacity returns unknown status."""
        result = cost_per_kw_year(10000, 0)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_capacity(self):
        """Negative capacity returns unknown status."""
        result = cost_per_kw_year(10000, -10)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_cost(self):
        """Negative cost returns not_priced status."""
        result = cost_per_kw_year(-1000, 100)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "not_priced")

    def test_zero_cost(self):
        """Zero cost returns zero value."""
        result = cost_per_kw_year(0, 100)
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.status, "ok")


class TestCostPerRackYear(unittest.TestCase):
    """Tests for cost_per_rack_year function."""

    def test_basic_calculation(self):
        """Basic cost per rack-year calculation."""
        result = cost_per_rack_year(50000, 50)
        self.assertEqual(result.value, 1000.0)
        self.assertEqual(result.unit, "USD/rack-year")
        self.assertEqual(result.status, "ok")

    def test_zero_racks(self):
        """Zero racks returns unknown status."""
        result = cost_per_rack_year(50000, 0)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_racks(self):
        """Negative racks returns unknown status."""
        result = cost_per_rack_year(50000, -5)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_cost(self):
        """Negative cost returns not_priced status."""
        result = cost_per_rack_year(-1000, 50)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "not_priced")


class TestCostPerM2Year(unittest.TestCase):
    """Tests for cost_per_m2_year function."""

    def test_basic_calculation(self):
        """Basic cost per m²-year calculation."""
        result = cost_per_m2_year(20000, 500)
        self.assertEqual(result.value, 40.0)
        self.assertEqual(result.unit, "USD/m²-year")
        self.assertEqual(result.status, "ok")

    def test_zero_area(self):
        """Zero area returns unknown status."""
        result = cost_per_m2_year(20000, 0)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_area(self):
        """Negative area returns unknown status."""
        result = cost_per_m2_year(20000, -100)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_cost(self):
        """Negative cost returns not_priced status."""
        result = cost_per_m2_year(-500, 500)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "not_priced")


class TestCostPerKwh(unittest.TestCase):
    """Tests for cost_per_kwh function."""

    def test_it_boundary_only(self):
        """IT boundary calculation without facility energy."""
        result = cost_per_kwh(1000, 5000)
        self.assertIn("it_boundary", result)
        self.assertNotIn("facility_boundary", result)
        self.assertEqual(result["it_boundary"].value, 0.2)
        self.assertEqual(result["it_boundary"].unit, "USD/kWh")
        self.assertEqual(result["it_boundary"].status, "ok")

    def test_both_boundaries(self):
        """Both IT and facility boundary calculations."""
        result = cost_per_kwh(1000, 5000, 8000)
        self.assertIn("it_boundary", result)
        self.assertIn("facility_boundary", result)
        self.assertEqual(result["it_boundary"].value, 0.2)
        self.assertEqual(result["facility_boundary"].value, 0.125)

    def test_zero_it_energy(self):
        """Zero IT energy returns unknown status."""
        result = cost_per_kwh(1000, 0)
        self.assertIsNone(result["it_boundary"].value)
        self.assertEqual(result["it_boundary"].status, "unknown")

    def test_zero_facility_energy(self):
        """Zero facility energy returns unknown status."""
        result = cost_per_kwh(1000, 5000, 0)
        self.assertIsNone(result["facility_boundary"].value)
        self.assertEqual(result["facility_boundary"].status, "unknown")

    def test_negative_energy_cost(self):
        """Negative energy cost returns not_priced status."""
        result = cost_per_kwh(-100, 5000)
        self.assertIsNone(result["it_boundary"].value)
        self.assertEqual(result["it_boundary"].status, "not_priced")

    def test_facility_boundary_without_it_energy(self):
        """Facility boundary works even if IT energy is invalid."""
        result = cost_per_kwh(1000, 0, 8000)
        self.assertIsNone(result["it_boundary"].value)
        self.assertEqual(result["facility_boundary"].value, 0.125)


class TestCostPerWorkUnit(unittest.TestCase):
    """Tests for cost_per_work_unit function."""

    def test_basic_calculation(self):
        """Basic cost per work unit calculation."""
        result = cost_per_work_unit(5000, 10000)
        self.assertEqual(result.value, 0.5)
        self.assertEqual(result.unit, "USD/work-unit")
        self.assertEqual(result.status, "ok")

    def test_zero_work(self):
        """Zero work returns unknown status."""
        result = cost_per_work_unit(5000, 0)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_work(self):
        """Negative work returns unknown status."""
        result = cost_per_work_unit(5000, -100)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_negative_cost(self):
        """Negative cost returns not_priced status."""
        result = cost_per_work_unit(-100, 10000)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "not_priced")


class TestComputeAllUnitEconomics(unittest.TestCase):
    """Tests for compute_all_unit_economics function."""

    def test_full_calculation(self):
        """All metrics computed with valid inputs."""
        results = compute_all_unit_economics(
            present_value=100000,
            years=10,
            discount_rate=0.08,
            it_capacity_kw=500,
            rack_count=100,
            area_m2=2000,
            energy_cost=50000,
            it_energy_kwh=2000000,
            facility_energy_kwh=3000000,
            allocated_cost=30000,
            useful_work=1000000,
        )

        self.assertIn("eac", results)
        self.assertIn("cost_per_kw", results)
        self.assertIn("cost_per_rack", results)
        self.assertIn("cost_per_m2", results)
        self.assertIn("cost_per_kwh", results)
        self.assertIn("cost_per_work", results)

        # Verify EAC is reasonable
        self.assertGreater(results["eac"], 0)

        # Verify unit costs
        self.assertEqual(results["cost_per_kw"].status, "ok")
        self.assertEqual(results["cost_per_rack"].status, "ok")
        self.assertEqual(results["cost_per_m2"].status, "ok")
        self.assertEqual(results["cost_per_work"].status, "ok")

    def test_without_optional_params(self):
        """Calculation without optional work unit parameters."""
        results = compute_all_unit_economics(
            present_value=100000,
            years=10,
            discount_rate=0.08,
            it_capacity_kw=500,
            rack_count=100,
            area_m2=2000,
            energy_cost=50000,
            it_energy_kwh=2000000,
        )

        self.assertIn("eac", results)
        self.assertIn("cost_per_kw", results)
        self.assertNotIn("cost_per_work", results)

    def test_with_zero_discount_rate(self):
        """Calculation with zero discount rate."""
        results = compute_all_unit_economics(
            present_value=100000,
            years=10,
            discount_rate=0,
            it_capacity_kw=500,
            rack_count=100,
            area_m2=2000,
            energy_cost=50000,
            it_energy_kwh=2000000,
        )

        # EAC = 100000 / 10 = 10000
        self.assertEqual(results["eac"], 10000.0)


class TestSentinelValues(unittest.TestCase):
    """Tests for sentinel values."""

    def test_not_priced_value(self):
        """NOT_PRICED sentinel is correct."""
        self.assertEqual(NOT_PRICED, "Not priced")

    def test_unknown_value(self):
        """UNKNOWN sentinel is correct."""
        self.assertEqual(UNKNOWN, "Unknown")


class TestUnitEconomicsResult(unittest.TestCase):
    """Tests for UnitEconomicsResult dataclass."""

    def test_creation(self):
        """Result can be created with all fields."""
        result = UnitEconomicsResult(
            value=100.0,
            unit="USD/kW-year",
            status="ok",
        )
        self.assertEqual(result.value, 100.0)
        self.assertEqual(result.unit, "USD/kW-year")
        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.detail)

    def test_with_detail(self):
        """Result can include detail message."""
        result = UnitEconomicsResult(
            value=None,
            unit="USD/kW-year",
            status="unknown",
            detail="IT capacity must be positive",
        )
        self.assertIsNone(result.value)
        self.assertEqual(result.detail, "IT capacity must be positive")


if __name__ == "__main__":
    unittest.main()
