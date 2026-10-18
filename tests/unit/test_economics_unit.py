"""Unit tests for dcc.economics.unit module."""
import unittest

from dcc.economics.unit import (
    UnitEconomicsResult,
    NOT_PRICED,
    UNKNOWN,
    equivalent_annual_cost,
    cost_per_kw_year,
    cost_per_rack_year,
    cost_per_m2_year,
    cost_per_kwh,
    cost_per_work_unit,
    compute_all_unit_economics,
)


class TestUnitEconomicsResult(unittest.TestCase):
    def test_creation(self):
        r = UnitEconomicsResult(
            value=100.0,
            unit="USD/kW-year",
            status="ok",
        )
        self.assertEqual(r.value, 100.0)
        self.assertEqual(r.unit, "USD/kW-year")

    def test_not_priced(self):
        r = UnitEconomicsResult(
            value=None,
            unit="USD/kW-year",
            status="not_priced",
        )
        self.assertIsNone(r.value)

    def test_unknown(self):
        r = UnitEconomicsResult(
            value=None,
            unit="USD/kW-year",
            status="unknown",
        )
        self.assertIsNone(r.value)


class TestEquivalentAnnualCost(unittest.TestCase):
    def test_basic(self):
        result = equivalent_annual_cost(10000, 10, 0.08)
        self.assertGreater(result, 0)

    def test_zero_rate(self):
        result = equivalent_annual_cost(10000, 10, 0.0)
        self.assertAlmostEqual(result, 1000.0)

    def test_negative_pv(self):
        with self.assertRaises(ValueError):
            equivalent_annual_cost(-1000, 10, 0.08)

    def test_zero_years(self):
        with self.assertRaises(ValueError):
            equivalent_annual_cost(10000, 0, 0.08)


class TestCostPerKwYear(unittest.TestCase):
    def test_basic(self):
        result = cost_per_kw_year(100000, 100)
        self.assertGreater(result, 0)

    def test_zero_kw(self):
        with self.assertRaises(ValueError):
            cost_per_kw_year(100000, 0)


class TestCostPerRackYear(unittest.TestCase):
    def test_basic(self):
        result = cost_per_rack_year(50000, 100)
        self.assertGreater(result, 0)


class TestCostPerM2Year(unittest.TestCase):
    def test_basic(self):
        result = cost_per_m2_year(100000, 500)
        self.assertGreater(result, 0)


class TestCostPerKwh(unittest.TestCase):
    def test_basic(self):
        result = cost_per_kwh(10000, 50000)
        self.assertGreater(result, 0)


class TestCostPerWorkUnit(unittest.TestCase):
    def test_basic(self):
        result = cost_per_work_unit(10000, 1000)
        self.assertGreater(result, 0)


class TestComputeAllUnitEconomics(unittest.TestCase):
    def test_compute(self):
        result = compute_all_unit_economics(
            total_cost=100000,
            total_kw=100,
            total_racks=50,
            total_m2=500,
            total_kwh=50000,
        )
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
