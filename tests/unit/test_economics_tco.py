"""Unit tests for dcc.economics.tco module."""
import unittest

from dcc.economics.tco import (
    TCOAssumptions,
    TCOCostBreakdown,
    YearlyCashFlow,
    TCOResult,
    TCOScenario,
    TCOComparison,
    TCOSensitivity,
    TCOEngine,
    evaluate_tco,
    compare_tco,
    run_tco_sensitivity,
    quick_tco,
)


class TestTCOAssumptions(unittest.TestCase):
    def test_creation(self):
        a = TCOAssumptions()
        self.assertEqual(a.currency, "USD")
        self.assertEqual(a.horizon_years, 10)

    def test_custom(self):
        a = TCOAssumptions(
            currency="EUR",
            horizon_years=5,
            annual_discount_rate=0.10,
        )
        self.assertEqual(a.currency, "EUR")

    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            TCOAssumptions(currency="INVALID")

    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):
            TCOAssumptions(horizon_years=0)


class TestTCOCostBreakdown(unittest.TestCase):
    def test_creation(self):
        c = TCOCostBreakdown()
        self.assertIsNotNone(c)


class TestYearlyCashFlow(unittest.TestCase):
    def test_creation(self):
        y = YearlyCashFlow(year=1)
        self.assertEqual(y.year, 1)


class TestTCOResult(unittest.TestCase):
    def test_creation(self):
        r = TCOResult(
            total_cost=100000.0,
            assumptions=TCOAssumptions(),
        )
        self.assertEqual(r.total_cost, 100000.0)


class TestTCOScenario(unittest.TestCase):
    def test_creation(self):
        s = TCOScenario(
            name="test",
            assumptions=TCOAssumptions(),
        )
        self.assertEqual(s.name, "test")


class TestTCOComparison(unittest.TestCase):
    def test_creation(self):
        c = TCOComparison()
        self.assertIsNotNone(c)


class TestTCOSensitivity(unittest.TestCase):
    def test_creation(self):
        s = TCOSensitivity()
        self.assertIsNotNone(s)


class TestTCOEngine(unittest.TestCase):
    def test_creation(self):
        e = TCOEngine()
        self.assertIsNotNone(e)


class TestEvaluateTco(unittest.TestCase):
    def test_evaluate(self):
        result = evaluate_tco(
            assumptions=TCOAssumptions(),
            upfront_costs=[("capex", 100000.0)],
            annual_costs=[("opex", 10000.0)],
        )
        self.assertIsInstance(result, TCOResult)


class TestCompareTco(unittest.TestCase):
    def test_compare(self):
        a = TCOAssumptions()
        b = TCOAssumptions(currency="EUR")
        result = compare_tco(a, b)
        self.assertIsInstance(result, TCOComparison)


class TestRunTcoSensitivity(unittest.TestCase):
    def test_sensitivity(self):
        a = TCOAssumptions()
        result = run_tco_sensitivity(a, "discount_rate", [0.05, 0.08, 0.10])
        self.assertIsInstance(result, TCOSensitivity)


class TestQuickTco(unittest.TestCase):
    def test_quick(self):
        result = quick_tco(
            upfront=100000.0,
            annual_opex=10000.0,
            years=10,
        )
        self.assertIsInstance(result, TCOResult)


if __name__ == "__main__":
    unittest.main()
