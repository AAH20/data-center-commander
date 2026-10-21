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


def _scenario(name="test", **costs):
    """Build a DeploymentScenario. `costs` is required and takes a CostBreakdown."""
    return DeploymentScenario(name=name, costs=CostBreakdown(**costs))


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

    def test_totals(self):
        c = CostBreakdown(capex=1000.0, site=500.0, power_monthly=100.0, labor_monthly=50.0)
        self.assertEqual(c.total_upfront, 1500.0)
        self.assertEqual(c.total_monthly, 150.0)


class TestDeploymentScenario(unittest.TestCase):
    def test_creation(self):
        s = DeploymentScenario(
            name="test",
            costs=CostBreakdown(capex=100000.0, power_monthly=1000.0),
            assumptions=ScenarioAssumptions(),
        )
        self.assertEqual(s.name, "test")
        self.assertEqual(s.costs.capex, 100000.0)

    def test_costs_required(self):
        # `costs` is a required field on DeploymentScenario, not an optional default.
        with self.assertRaises(TypeError):
            DeploymentScenario(name="test")


class TestScenarioResult(unittest.TestCase):
    def test_creation(self):
        # ScenarioResult has no `total_cost` field: the engine reports NPV plus the
        # undiscounted lifecycle / monthly splits. It is produced by evaluate_scenario.
        r = evaluate_scenario(_scenario("test", capex=100000.0, power_monthly=1000.0))
        self.assertIsInstance(r, ScenarioResult)
        self.assertEqual(r.scenario_name, "test")
        self.assertEqual(r.total_upfront, 100000.0)
        self.assertEqual(r.total_monthly, 1000.0)
        self.assertEqual(r.horizon_months, 36)
        self.assertGreater(r.npv, 0)


class TestScenarioComparison(unittest.TestCase):
    def test_creation(self):
        # ScenarioComparison requires the evaluated results; build it via compare_scenarios.
        c = compare_scenarios([
            _scenario("a", capex=100000.0, power_monthly=1000.0),
            _scenario("b", capex=200000.0, power_monthly=800.0),
        ])
        self.assertIsInstance(c, ScenarioComparison)
        self.assertEqual(len(c.scenarios), 2)
        self.assertEqual(c.baseline_index, 0)
        self.assertEqual(c.lower_npv_index, 0)


class TestSensitivityAnalysis(unittest.TestCase):
    def test_creation(self):
        # SensitivityAnalysis requires measured series (values, NPV / cost-per-unit
        # results, ranges, elasticity), so it is only produced by run_sensitivity.
        s = run_sensitivity(_scenario(capex=100000.0), "discount_rate", [0.05, 0.08, 0.10])
        self.assertIsInstance(s, SensitivityAnalysis)
        self.assertEqual(s.parameter_name, "discount_rate")
        self.assertEqual(len(s.values_tested), 3)


class TestScenarioEngine(unittest.TestCase):
    def test_creation(self):
        e = ScenarioEngine()
        self.assertIsNotNone(e)


class TestEvaluateScenario(unittest.TestCase):
    def test_evaluate(self):
        s = _scenario("test", capex=100000.0, power_monthly=1000.0)
        result = evaluate_scenario(s)
        self.assertIsInstance(result, ScenarioResult)
        self.assertEqual(result.scenario_type, s.scenario_type)
        self.assertEqual(result.currency, "USD")


class TestCompareScenarios(unittest.TestCase):
    def test_compare(self):
        s1 = _scenario("a", capex=100000.0, power_monthly=1000.0)
        s2 = _scenario("b", capex=200000.0, power_monthly=800.0)
        result = compare_scenarios([s1, s2])
        self.assertIsInstance(result, ScenarioComparison)
        self.assertEqual([r.scenario_name for r in result.scenarios], ["a", "b"])
        self.assertEqual(len(result.npv_deltas), 2)
        self.assertTrue(result.summary)


class TestRunSensitivity(unittest.TestCase):
    def test_sensitivity(self):
        # run_sensitivity takes a scenario plus a supported parameter name. Supported
        # names are: capex, discount_rate, horizon_months, labor_monthly,
        # power_monthly, useful_units_per_month (there is no "cost" or
        # "annual_discount_rate").
        s = _scenario(capex=100000.0, power_monthly=1000.0)
        result = run_sensitivity(s, "power_monthly", [800.0, 1000.0, 1200.0])
        self.assertIsInstance(result, SensitivityAnalysis)
        self.assertEqual(result.values_tested, [800.0, 1000.0, 1200.0])
        self.assertEqual(len(result.npv_results), 3)

    def test_unknown_parameter(self):
        with self.assertRaises(ValueError):
            run_sensitivity(_scenario(capex=100000.0), "not_a_parameter", [1.0])


if __name__ == "__main__":
    unittest.main()
