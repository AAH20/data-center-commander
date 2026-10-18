"""Unit tests for dcc.economics.scenarios module."""
import unittest

from dcc.economics.scenarios import (
    ScenarioAssumptions,
    CostBreakdown,
    DeploymentScenario,
    ScenarioResult,
    ScenarioComparison,
    SensitivityAnalysis,
    ScenarioEngine,
    evaluate_scenario,
    compare_scenarios,
    run_sensitivity,
)


class TestScenarioAssumptions(unittest.TestCase):
    def test_creation(self):
        a = ScenarioAssumptions()
        self.assertEqual(a.currency, "USD")
        self.assertEqual(a.horizon_months, 36)

    def test_custom(self):
        a = ScenarioAssumptions(
            currency="EUR",
            horizon_months=24,
            annual_discount_rate=0.10,
        )
        self.assertEqual(a.currency, "EUR")

    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            ScenarioAssumptions(currency="INVALID")

    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):
            ScenarioAssumptions(horizon_months=0)


class TestCostBreakdown(unittest.TestCase):
    def test_creation(self):
        c = CostBreakdown()
        self.assertIsNotNone(c)


class TestDeploymentScenario(unittest.TestCase):
    def test_creation(self):
        s = DeploymentScenario(
            name="test",
            assumptions=ScenarioAssumptions(),
        )
        self.assertEqual(s.name, "test")


class TestScenarioResult(unittest.TestCase):
    def test_creation(self):
        r = ScenarioResult(
            scenario_name="test",
            total_cost=100000.0,
        )
        self.assertEqual(r.scenario_name, "test")


class TestScenarioComparison(unittest.TestCase):
    def test_creation(self):
        c = ScenarioComparison()
        self.assertIsNotNone(c)


class TestSensitivityAnalysis(unittest.TestCase):
    def test_creation(self):
        s = SensitivityAnalysis()
        self.assertIsNotNone(s)


class TestScenarioEngine(unittest.TestCase):
    def test_creation(self):
        e = ScenarioEngine()
        self.assertIsNotNone(e)


class TestEvaluateScenario(unittest.TestCase):
    def test_evaluate(self):
        s = DeploymentScenario(
            name="test",
            assumptions=ScenarioAssumptions(),
        )
        result = evaluate_scenario(s)
        self.assertIsInstance(result, ScenarioResult)


class TestCompareScenarios(unittest.TestCase):
    def test_compare(self):
        s1 = DeploymentScenario(name="a", assumptions=ScenarioAssumptions())
        s2 = DeploymentScenario(name="b", assumptions=ScenarioAssumptions())
        result = compare_scenarios([s1, s2])
        self.assertIsInstance(result, ScenarioComparison)


class TestRunSensitivity(unittest.TestCase):
    def test_sensitivity(self):
        s = DeploymentScenario(name="test", assumptions=ScenarioAssumptions())
        result = run_sensitivity(s, "cost", [0.8, 1.0, 1.2])
        self.assertIsInstance(result, SensitivityAnalysis)


if __name__ == "__main__":
    unittest.main()
