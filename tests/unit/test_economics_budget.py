"""Unit tests for dcc.economics.budget module."""
import unittest
from decimal import Decimal

from dcc.economics.budget import (
    GrowthPlan,
    BudgetLine,
    MonthlyBudget,
    BudgetForecast,
    forecast_budget,
    forecast_from_estimate,
    compare_scenarios,
    compute_unit_economics,
)


def _line_item(**overrides):
    """A minimal valid one-time line item dict.

    The public API (forecast_budget / forecast_from_estimate / compare_scenarios)
    accepts raw dicts and validates them itself; BudgetLine is only the internal
    validated representation.
    """
    item = {
        "line_id": "l1",
        "description": "Test",
        "phase": "construction",
        "cost_behavior": "one_time",
        "quantity": 100,
        "waste_factor": "0.05",
        "base_unit_cost": 1000,
        "currency": "USD",
        "escalation_pct": "0.03",
        "start_month": 0,
        "pricing_status": "budgetary",
    }
    item.update(overrides)
    return item


class TestGrowthPlan(unittest.TestCase):
    def test_creation(self):
        g = GrowthPlan()
        self.assertEqual(g.monthly_capacity_growth, Decimal("0"))
        self.assertEqual(g.monthly_cost_reduction, Decimal("0"))

    def test_with_growth(self):
        g = GrowthPlan(
            monthly_capacity_growth=Decimal("0.02"),
            monthly_cost_reduction=Decimal("0.01"),
        )
        self.assertEqual(g.monthly_capacity_growth, Decimal("0.02"))

    def test_from_dict(self):
        data = {
            "monthly_capacity_growth": 0.02,
            "monthly_cost_reduction": 0.01,
        }
        g = GrowthPlan.from_dict(data)
        self.assertEqual(g.monthly_capacity_growth, Decimal("0.02"))

    def test_from_none(self):
        g = GrowthPlan.from_dict(None)
        self.assertEqual(g.monthly_capacity_growth, Decimal("0"))


class TestBudgetLine(unittest.TestCase):
    def test_creation(self):
        line = BudgetLine(
            line_id="l1",
            description="Test line",
            phase="construction",
            cost_behavior="one_time",
            quantity=Decimal("100"),
            waste_factor=Decimal("0.05"),
            base_unit_cost=Decimal("1000"),
            low_unit_cost=Decimal("900"),
            high_unit_cost=Decimal("1100"),
            currency="USD",
            escalation_pct=Decimal("0.03"),
            recurrence_months=None,
            start_month=0,
            useful_life_months=None,
            pricing_status="budgetary",
        )
        self.assertEqual(line.line_id, "l1")
        self.assertEqual(line.currency, "USD")

    def test_extended_base_applies_waste(self):
        # extended_base = quantity * (1 + waste_factor) * base_unit_cost
        line = BudgetLine(
            line_id="l1",
            description="Test line",
            phase="construction",
            cost_behavior="one_time",
            quantity=Decimal("100"),
            waste_factor=Decimal("0.05"),
            base_unit_cost=Decimal("1000"),
            low_unit_cost=None,
            high_unit_cost=None,
            currency="USD",
            escalation_pct=Decimal("0"),
            recurrence_months=None,
            start_month=0,
            useful_life_months=None,
            pricing_status="budgetary",
        )
        self.assertEqual(line.extended_base, Decimal("105000"))


class TestMonthlyBudget(unittest.TestCase):
    def test_creation(self):
        # MonthlyBudget has no `total` field: a month is described by the
        # base/low/high scenario triple (plus present values), not one number.
        m = MonthlyBudget(
            month=1,
            base=Decimal("10000"),
        )
        self.assertEqual(m.month, 1)
        self.assertEqual(m.base, Decimal("10000"))
        # Unspecified scenario fields default to zero rather than None.
        self.assertEqual(m.low, Decimal("0"))
        self.assertEqual(m.present_value_base, Decimal("0"))


class TestBudgetForecast(unittest.TestCase):
    def test_creation(self):
        # BudgetForecast has no `total` field; totals are carried per scenario
        # (base/low/high) and again for present value.
        f = BudgetForecast(
            horizon_months=12,
            currency="USD",
            discount_rate=Decimal("0"),
            contingency_pct=Decimal("0"),
            monthly_budgets=[],
            total_base=Decimal("100000"),
            total_low=Decimal("100000"),
            total_high=Decimal("100000"),
            total_pv_base=Decimal("100000"),
            total_pv_low=Decimal("100000"),
            total_pv_high=Decimal("100000"),
            annual_totals=[],
            phase_totals={},
            growth_plan=GrowthPlan(),
        )
        self.assertEqual(f.total_base, Decimal("100000"))
        self.assertEqual(f.currency, "USD")
        # Defaults to not permitting execution: a forecast never authorises spend.
        self.assertFalse(f.execution_permitted)


class TestForecastBudget(unittest.TestCase):
    def test_forecast(self):
        # forecast_budget is keyword-only and returns a plain dict (serialised
        # via _forecast_to_dict), not a BudgetForecast instance.
        result = forecast_budget(line_items=[_line_item()], horizon_months=12)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["horizon_months"], 12)
        self.assertEqual(len(result["monthly_budgets"]), 12)
        # 100 units * (1 + 0.05 waste) * 1000 = 105000, spent once in month 0.
        self.assertEqual(result["total_base"], Decimal("105000.00"))

    def test_forecast_is_low_high_bounded(self):
        # With no explicit low/high unit costs the bounds collapse onto base.
        result = forecast_budget(line_items=[_line_item()], horizon_months=12)
        self.assertEqual(result["total_low"], result["total_base"])
        self.assertEqual(result["total_high"], result["total_base"])

    def test_horizon_must_be_in_range(self):
        with self.assertRaises(ValueError):
            forecast_budget(line_items=[_line_item()], horizon_months=0)


class TestForecastFromEstimate(unittest.TestCase):
    def test_forecast(self):
        # forecast_from_estimate additionally requires estimate_id and returns
        # the same dict shape as forecast_budget, tagged with that id.
        result = forecast_from_estimate(
            estimate_id="est-1",
            line_items=[_line_item()],
            horizon_months=12,
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["estimate_id"], "est-1")
        self.assertEqual(result["horizon_months"], 12)


class TestCompareScenarios(unittest.TestCase):
    def test_compare(self):
        # compare_scenarios is keyword-only and takes a list of scenario DICTS
        # (each with 'name' and 'line_items'), not positional line-item lists.
        result = compare_scenarios(
            scenarios=[
                {"name": "base", "line_items": [_line_item()]},
                {"name": "base_again", "line_items": [_line_item()]},
            ]
        )
        self.assertIsInstance(result, dict)
        self.assertEqual([s["name"] for s in result["scenarios"]], ["base", "base_again"])
        # Identical scenarios => zero spread.
        self.assertEqual(result["variance"]["spread"], Decimal("0.00"))

    def test_empty_scenarios_rejected(self):
        with self.assertRaises(ValueError):
            compare_scenarios(scenarios=[])


class TestComputeUnitEconomics(unittest.TestCase):
    def test_compute(self):
        # compute_unit_economics lives in budget.py (not economics/unit.py) and
        # is denominated by a horizon in YEARS, not by total_kw.
        result = compute_unit_economics(
            total_cost=Decimal("100000"),
            horizon_years=Decimal("10"),
        )
        self.assertIsInstance(result, dict)
        # Zero discount rate => straight-line EAC = PV / years.
        self.assertEqual(result["equivalent_annual_cost"], Decimal("10000.00"))
        self.assertNotIn("cost_per_unit", result)

    def test_cost_per_unit_with_denominator(self):
        result = compute_unit_economics(
            total_cost=Decimal("100000"),
            horizon_years=Decimal("10"),
            discount_rate=Decimal("0.08"),
            denominator=Decimal("100"),
            denominator_unit="kW",
        )
        self.assertEqual(result["denominator_unit"], "kW")
        self.assertEqual(result["cost_per_unit"], Decimal("149.03"))

    def test_horizon_must_be_positive(self):
        with self.assertRaises(ValueError):
            compute_unit_economics(total_cost=Decimal("100000"), horizon_years=Decimal("0"))


if __name__ == "__main__":
    unittest.main()
