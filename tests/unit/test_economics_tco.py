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


def _scenario(name="test", **costs):
    """Build a TCOScenario. `costs` is required and takes a TCOCostBreakdown."""
    return TCOScenario(name=name, costs=TCOCostBreakdown(**costs))


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

    def test_totals(self):
        c = TCOCostBreakdown(hardware_capex=1000.0, facility_capex=500.0, energy_annual=250.0)
        self.assertEqual(c.total_capex, 1500.0)
        self.assertEqual(c.total_opex, 250.0)


class TestYearlyCashFlow(unittest.TestCase):
    def test_creation(self):
        y = YearlyCashFlow(year=1)
        self.assertEqual(y.year, 1)


class TestTCOResult(unittest.TestCase):
    def test_creation(self):
        # TCOResult has no `total_cost` field: the engine reports split totals
        # (capex / opex / refresh / terminal) plus the PV aggregate. TCOResult is
        # produced by the engine, so exercise it through quick_tco.
        r = quick_tco(hardware_capex=100000.0, energy_annual=10000.0)
        self.assertIsInstance(r, TCOResult)
        self.assertEqual(r.total_capex, 100000.0)
        # Opex total is the undiscounted sum over the horizon, so it exceeds
        # 10 x 10,000 once energy escalation is applied.
        self.assertGreater(r.total_opex, 100000.0)
        self.assertGreater(r.total_pv, 0)
        self.assertEqual(r.horizon_years, 10)


class TestTCOScenario(unittest.TestCase):
    def test_creation(self):
        s = TCOScenario(
            name="test",
            costs=TCOCostBreakdown(hardware_capex=100000.0, energy_annual=10000.0),
            assumptions=TCOAssumptions(),
        )
        self.assertEqual(s.name, "test")
        self.assertEqual(s.costs.hardware_capex, 100000.0)

    def test_costs_required(self):
        # `costs` is a required field on TCOScenario, not an optional default.
        with self.assertRaises(TypeError):
            TCOScenario(name="test")


class TestTCOComparison(unittest.TestCase):
    def test_creation(self):
        # TCOComparison requires the evaluated scenario results; build it via compare_tco.
        c = compare_tco([
            _scenario("a", hardware_capex=100000.0),
            _scenario("b", hardware_capex=200000.0),
        ])
        self.assertIsInstance(c, TCOComparison)
        self.assertEqual(len(c.scenarios), 2)
        self.assertEqual(c.baseline_index, 0)
        self.assertEqual(c.lower_pv_index, 0)


class TestTCOSensitivity(unittest.TestCase):
    def test_creation(self):
        # TCOSensitivity requires measured series (values, results, ranges,
        # elasticity), so it is only produced by run_tco_sensitivity.
        s = run_tco_sensitivity(
            _scenario(hardware_capex=100000.0), "discount_rate", [0.05, 0.08, 0.10]
        )
        self.assertIsInstance(s, TCOSensitivity)
        self.assertEqual(s.parameter_name, "discount_rate")
        self.assertEqual(len(s.values_tested), 3)


class TestTCOEngine(unittest.TestCase):
    def test_creation(self):
        e = TCOEngine()
        self.assertIsNotNone(e)


class TestEvaluateTco(unittest.TestCase):
    def test_evaluate(self):
        # evaluate_tco takes a single TCOScenario; the old form passed assumptions
        # plus separate upfront/annual cost lists, which no longer exists.
        result = evaluate_tco(
            _scenario("on-prem", hardware_capex=100000.0, energy_annual=10000.0)
        )
        self.assertIsInstance(result, TCOResult)
        self.assertEqual(result.scenario_name, "on-prem")
        self.assertGreater(result.total_pv, 0)
        self.assertEqual(len(result.yearly_cash_flows), 11)  # year 0 + 10-year horizon


class TestCompareTco(unittest.TestCase):
    def test_compare(self):
        # compare_tco takes a list of scenarios (plus an optional baseline index).
        a = _scenario("a", hardware_capex=100000.0, energy_annual=10000.0)
        b = _scenario("b", hardware_capex=200000.0, energy_annual=8000.0)
        result = compare_tco([a, b])
        self.assertIsInstance(result, TCOComparison)
        self.assertEqual(result.scenarios[0].scenario_name, "a")
        self.assertEqual(len(result.pv_deltas), 2)
        self.assertTrue(result.summary)


class TestRunTcoSensitivity(unittest.TestCase):
    def test_sensitivity(self):
        # run_tco_sensitivity takes a scenario, not bare assumptions. Supported
        # parameters are: contingency, discount_rate, energy_annual,
        # energy_escalation, hardware_capex, horizon_years, labor_escalation,
        # maintenance_escalation (there is no "capex" or "annual_discount_rate").
        result = run_tco_sensitivity(
            _scenario(hardware_capex=100000.0), "discount_rate", [0.05, 0.08, 0.10]
        )
        self.assertIsInstance(result, TCOSensitivity)
        self.assertEqual(result.values_tested, [0.05, 0.08, 0.10])
        self.assertEqual(len(result.pv_results), 3)

    def test_unknown_parameter(self):
        with self.assertRaises(ValueError):
            run_tco_sensitivity(
                _scenario(hardware_capex=100000.0), "not_a_parameter", [1.0]
            )


class TestQuickTco(unittest.TestCase):
    def test_quick(self):
        # quick_tco is keyword-only and takes itemised capex/opex inputs; the old
        # `upfront` / `annual_opex` / `years` names do not exist.
        result = quick_tco(
            hardware_capex=100000.0,
            energy_annual=10000.0,
            horizon_years=10,
        )
        self.assertIsInstance(result, TCOResult)
        self.assertEqual(result.total_capex, 100000.0)
        self.assertEqual(result.horizon_years, 10)


if __name__ == "__main__":
    unittest.main()
