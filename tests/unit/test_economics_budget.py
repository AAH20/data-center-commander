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


class TestMonthlyBudget(unittest.TestCase):
    def test_creation(self):
        m = MonthlyBudget(
            month=1,
            total=Decimal("10000"),
        )
        self.assertEqual(m.month, 1)
        self.assertEqual(m.total, Decimal("10000"))


class TestBudgetForecast(unittest.TestCase):
    def test_creation(self):
        f = BudgetForecast(
            total=Decimal("100000"),
            currency="USD",
        )
        self.assertEqual(f.total, Decimal("100000"))


class TestForecastBudget(unittest.TestCase):
    def test_forecast(self):
        lines = [
            BudgetLine(
                line_id="l1",
                description="Test",
                phase="construction",
                cost_behavior="one_time",
                quantity=Decimal("100"),
                waste_factor=Decimal("0.05"),
                base_unit_cost=Decimal("1000"),
                low_unit_cost=None,
                high_unit_cost=None,
                currency="USD",
                escalation_pct=Decimal("0.03"),
                recurrence_months=None,
                start_month=0,
                useful_life_months=None,
                pricing_status="budgetary",
            ),
        ]
        result = forecast_budget(lines, months=12)
        self.assertIsInstance(result, BudgetForecast)


class TestForecastFromEstimate(unittest.TestCase):
    def test_forecast(self):
        lines = [
            BudgetLine(
                line_id="l1",
                description="Test",
                phase="construction",
                cost_behavior="one_time",
                quantity=Decimal("100"),
                waste_factor=Decimal("0.05"),
                base_unit_cost=Decimal("1000"),
                low_unit_cost=None,
                high_unit_cost=None,
                currency="USD",
                escalation_pct=Decimal("0.03"),
                recurrence_months=None,
                start_month=0,
                useful_life_months=None,
                pricing_status="budgetary",
            ),
        ]
        result = forecast_from_estimate(lines, months=12)
        self.assertIsInstance(result, BudgetForecast)


class TestCompareScenarios(unittest.TestCase):
    def test_compare(self):
        base = [BudgetLine(
            line_id="l1",
            description="Test",
            phase="construction",
            cost_behavior="one_time",
            quantity=Decimal("100"),
            waste_factor=Decimal("0.05"),
            base_unit_cost=Decimal("1000"),
            low_unit_cost=None,
            high_unit_cost=None,
            currency="USD",
            escalation_pct=Decimal("0.03"),
            recurrence_months=None,
            start_month=0,
            useful_life_months=None,
            pricing_status="budgetary",
        )]
        result = compare_scenarios(base, base)
        self.assertIsInstance(result, dict)


class TestComputeUnitEconomics(unittest.TestCase):
    def test_compute(self):
        result = compute_unit_economics(
            total_cost=Decimal("100000"),
            total_kw=Decimal("100"),
        )
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
