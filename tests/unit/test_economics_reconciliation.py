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

CURRENCY = "USD"


def _rollup_rows() -> list[dict]:
    return [
        {
            "currency": CURRENCY,
            "phase": "construction",
            "present_value_base": Decimal("100000"),
            "present_value_low": Decimal("90000"),
            "present_value_high": Decimal("110000"),
            "first_period_cost": Decimal("50000"),
            "line_count": 3,
            "unpriced_lines": 1,
            "synthetic_lines": 0,
        }
    ]


def _actual_rows() -> list[dict]:
    return [
        {
            "currency": CURRENCY,
            "phase": "construction",
            "amount": Decimal("105000"),
            "accounting_period": "2024-01",
            "estimate_line_id": "l1",
        }
    ]


def _estimate_row(estimate_id: str = "e1") -> dict:
    return {"id": estimate_id, "name": "Phase 1 Build", "currency": CURRENCY}


class TestVarianceThresholds(unittest.TestCase):
    def test_creation(self):
        t = VarianceThresholds()
        self.assertEqual(t.favorable_pct, Decimal("-0.10"))
        self.assertEqual(t.unfavorable_pct, Decimal("0.10"))
        self.assertEqual(t.significant_pct, Decimal("0.20"))

    def test_from_dict(self):
        data = {"favorable_pct": -0.15, "unfavorable_pct": 0.15}
        t = VarianceThresholds.from_dict(data)
        self.assertEqual(t.favorable_pct, Decimal("-0.15"))
        self.assertEqual(t.unfavorable_pct, Decimal("0.15"))
        # Not supplied -> default retained.
        self.assertEqual(t.significant_pct, Decimal("0.20"))

    def test_from_none(self):
        t = VarianceThresholds.from_dict(None)
        self.assertEqual(t.favorable_pct, Decimal("-0.10"))


class TestPhaseVariance(unittest.TestCase):
    def test_creation(self):
        v = PhaseVariance(phase="electrical")
        self.assertEqual(v.phase, "electrical")
        self.assertEqual(v.variance, Decimal("0"))
        self.assertEqual(v.classification, "none")
        self.assertEqual(v.currency, "USD")


class TestPeriodVariance(unittest.TestCase):
    def test_creation(self):
        v = PeriodVariance(period="2024-01")
        self.assertEqual(v.period, "2024-01")
        self.assertEqual(v.actual_amount, Decimal("0"))
        self.assertEqual(v.classification, "none")


class TestLineVariance(unittest.TestCase):
    def test_creation(self):
        v = LineVariance(
            line_id="l1",
            line_no=1,
            description="Switchgear",
            phase="electrical",
        )
        self.assertEqual(v.line_id, "l1")
        self.assertEqual(v.line_no, 1)
        self.assertEqual(v.description, "Switchgear")
        self.assertEqual(v.phase, "electrical")
        self.assertEqual(v.variance, Decimal("0"))


class TestReconciliationSummary(unittest.TestCase):
    def test_creation(self):
        s = ReconciliationSummary(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
        )
        self.assertEqual(s.estimate_id, "e1")
        self.assertEqual(s.currency, CURRENCY)
        self.assertEqual(s.total_estimate_base, Decimal("0"))
        self.assertFalse(s.execution_permitted)


class TestReconcileEstimate(unittest.TestCase):
    def test_reconcile(self):
        result = reconcile_estimate(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
            estimate_rollup=_rollup_rows(),
            actuals=_actual_rows(),
        )
        self.assertIsInstance(result, dict)
        summary = result["summary"]
        self.assertEqual(summary["estimate_id"], "e1")
        self.assertEqual(summary["currency"], CURRENCY)
        self.assertEqual(summary["total_estimate_base"], Decimal("100000.00"))
        self.assertEqual(summary["total_actual"], Decimal("105000.00"))
        self.assertEqual(summary["total_variance"], Decimal("5000.00"))
        self.assertEqual(summary["phase_count"], 1)
        self.assertEqual(summary["actual_entry_count"], 1)
        self.assertEqual(summary["unpriced_line_count"], 1)
        self.assertEqual(summary["periods_with_actuals"], 1)
        self.assertEqual(summary["overall_classification"], "on_track")
        self.assertFalse(result["execution_permitted"])

    def test_phase_variance_detail(self):
        result = reconcile_estimate(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
            estimate_rollup=_rollup_rows(),
            actuals=_actual_rows(),
        )
        phase = result["by_phase"][0]
        self.assertEqual(phase["phase"], "construction")
        self.assertEqual(phase["actual_amount"], Decimal("105000.00"))
        self.assertEqual(phase["variance"], Decimal("5000.00"))
        # variance_pct is serialized as a percentage (5%).
        self.assertEqual(phase["variance_pct"], Decimal("5.00"))
        self.assertEqual(phase["classification"], "on_track")
        self.assertEqual(phase["line_count"], 3)

    def test_period_variance_detail(self):
        result = reconcile_estimate(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
            estimate_rollup=_rollup_rows(),
            actuals=_actual_rows(),
        )
        period = result["by_period"][0]
        self.assertEqual(period["period"], "2024-01")
        self.assertEqual(period["actual_amount"], Decimal("105000.00"))

    def test_line_variance_detail(self):
        line_items = [
            {
                "id": "l1",
                "line_no": 1,
                "description": "Switchgear",
                "phase": "construction",
                "extended_base": Decimal("100000"),
                "currency": CURRENCY,
            }
        ]
        result = reconcile_estimate(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
            estimate_rollup=_rollup_rows(),
            actuals=_actual_rows(),
            line_items=line_items,
        )
        self.assertEqual(result["summary"]["line_count"], 1)
        line = result["by_line"][0]
        self.assertEqual(line["line_id"], "l1")
        self.assertEqual(line["actual_amount"], Decimal("105000.00"))
        self.assertEqual(line["variance"], Decimal("5000.00"))

    def test_other_currency_actuals_are_excluded(self):
        actuals = _actual_rows() + [
            {"currency": "EUR", "phase": "construction", "amount": Decimal("999999")}
        ]
        result = reconcile_estimate(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
            estimate_rollup=_rollup_rows(),
            actuals=actuals,
        )
        self.assertEqual(result["summary"]["total_actual"], Decimal("105000.00"))
        self.assertEqual(result["summary"]["actual_entry_count"], 1)

    def test_custom_thresholds(self):
        thresholds = VarianceThresholds.from_dict(
            {"favorable_pct": -0.01, "unfavorable_pct": 0.01}
        )
        result = reconcile_estimate(
            estimate_id="e1",
            estimate_name="Phase 1 Build",
            currency=CURRENCY,
            estimate_rollup=_rollup_rows(),
            actuals=_actual_rows(),
            thresholds=thresholds,
        )
        self.assertEqual(result["summary"]["overall_classification"], "unfavorable")
        self.assertEqual(result["thresholds"]["unfavorable_pct"], 0.01)

    def test_keyword_only_signature(self):
        with self.assertRaises(TypeError):
            reconcile_estimate("e1", "Phase 1 Build")  # type: ignore[misc]


class TestReconcileFromDatabaseRows(unittest.TestCase):
    def test_reconcile(self):
        result = reconcile_from_database_rows(
            estimate_row=_estimate_row(),
            rollup_rows=_rollup_rows(),
            actual_rows=_actual_rows(),
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["estimate_id"], "e1")
        self.assertEqual(result["estimate_name"], "Phase 1 Build")
        self.assertEqual(result["currency"], CURRENCY)
        self.assertEqual(result["summary"]["total_variance"], Decimal("5000.00"))

    def test_keyword_only_signature(self):
        with self.assertRaises(TypeError):
            reconcile_from_database_rows(_estimate_row(), _rollup_rows())  # type: ignore[misc]


class TestReconcileMultiple(unittest.TestCase):
    def test_reconcile(self):
        estimates = [
            {
                "estimate_row": _estimate_row(),
                "rollup_rows": _rollup_rows(),
                "actual_rows": _actual_rows(),
            }
        ]
        result = reconcile_multiple(estimates=estimates)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["estimates"]), 1)
        combined = result["combined"]
        self.assertEqual(combined["estimate_count"], 1)
        self.assertEqual(combined["currencies"], [CURRENCY])
        self.assertFalse(combined["multi_currency"])
        self.assertEqual(combined["total_estimate_base"], Decimal("100000.00"))
        self.assertEqual(combined["total_actual"], Decimal("105000.00"))
        self.assertEqual(combined["total_variance"], Decimal("5000.00"))
        self.assertFalse(result["execution_permitted"])

    def test_requires_at_least_one_estimate(self):
        with self.assertRaises(ValueError):
            reconcile_multiple(estimates=[])

    def test_keyword_only_signature(self):
        with self.assertRaises(TypeError):
            reconcile_multiple([])  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
