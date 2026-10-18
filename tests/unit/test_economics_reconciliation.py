"""Unit tests for dcc.economics.reconciliation module."""
import unittest
from decimal import Decimal

from dcc.economics.reconciliation import (
    VarianceThresholds,
    PhaseVariance,
    PeriodVariance,
    LineVariance,
    ReconciliationSummary,
    reconcile_estimate,
    reconcile_from_database_rows,
    reconcile_multiple,
)


class TestVarianceThresholds(unittest.TestCase):
    def test_creation(self):
        t = VarianceThresholds()
        self.assertEqual(t.favorable_pct, Decimal("-0.10"))
        self.assertEqual(t.unfavorable_pct, Decimal("0.10"))

    def test_from_dict(self):
        data = {"favorable_pct": -0.15, "unfavorable_pct": 0.15}
        t = VarianceThresholds.from_dict(data)
        self.assertEqual(t.favorable_pct, Decimal("-0.15"))

    def test_from_none(self):
        t = VarianceThresholds.from_dict(None)
        self.assertEqual(t.favorable_pct, Decimal("-0.10"))


class TestPhaseVariance(unittest.TestCase):
    def test_creation(self):
        v = PhaseVariance(phase="electrical")
        self.assertEqual(v.phase, "electrical")
        self.assertEqual(v.variance, Decimal("0"))


class TestPeriodVariance(unittest.TestCase):
    def test_creation(self):
        v = PeriodVariance(period="2024-01")
        self.assertEqual(v.period, "2024-01")


class TestLineVariance(unittest.TestCase):
    def test_creation(self):
        v = LineVariance(line_id="l1")
        self.assertEqual(v.line_id, "l1")


class TestReconciliationSummary(unittest.TestCase):
    def test_creation(self):
        s = ReconciliationSummary()
        self.assertIsNotNone(s)


class TestReconcileEstimate(unittest.TestCase):
    def test_reconcile(self):
        estimate = {"total": Decimal("100000")}
        actuals = [{"amount": Decimal("105000"), "phase": "construction"}]
        result = reconcile_estimate(estimate, actuals)
        self.assertIsInstance(result, ReconciliationSummary)


class TestReconcileFromDatabaseRows(unittest.TestCase):
    def test_reconcile(self):
        estimate_rows = [{"amount": Decimal("100000"), "phase": "construction"}]
        actual_rows = [{"amount": Decimal("105000"), "phase": "construction"}]
        result = reconcile_from_database_rows(estimate_rows, actual_rows)
        self.assertIsInstance(result, ReconciliationSummary)


class TestReconcileMultiple(unittest.TestCase):
    def test_reconcile(self):
        estimates = [{"id": "e1", "total": Decimal("100000")}]
        actuals = [{"estimate_id": "e1", "amount": Decimal("105000")}]
        result = reconcile_multiple(estimates, actuals)
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
