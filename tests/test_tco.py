"""Tests for the TCO calculator."""
from __future__ import annotations

import unittest

from dcc.economics.tco import (
    TCOAssumptions,
    TCOComparison,
    TCOCostBreakdown,
    TCOEngine,
    TCOResult,
    TCOScenario,
    TCOSensitivity,
    YearlyCashFlow,
    compare_tco,
    evaluate_tco,
    quick_tco,
    run_tco_sensitivity,
    tco_breakdown_by_category,
    tco_cost_per_unit,
)


class TestTCOAssumptions(unittest.TestCase):
    """Tests for TCOAssumptions validation."""

    def test_valid_defaults(self):
        a = TCOAssumptions()
        self.assertEqual(a.currency, "USD")
        self.assertEqual(a.horizon_years, 10)
        self.assertAlmostEqual(a.annual_discount_rate, 0.08)
        self.assertAlmostEqual(a.energy_escalation_pct, 0.03)
        self.assertAlmostEqual(a.maintenance_escalation_pct, 0.025)
        self.assertAlmostEqual(a.labor_escalation_pct, 0.03)
        self.assertAlmostEqual(a.other_escalation_pct, 0.02)
        self.assertAlmostEqual(a.contingency_pct, 0.0)
        self.assertAlmostEqual(a.tax_rate, 0.0)
        self.assertFalse(a.include_tax)

    def test_custom_values(self):
        a = TCOAssumptions(
            currency="EUR",
            horizon_years=15,
            annual_discount_rate=0.12,
            energy_escalation_pct=0.05,
            maintenance_escalation_pct=0.03,
            labor_escalation_pct=0.04,
            other_escalation_pct=0.025,
            contingency_pct=0.1,
            tax_rate=0.25,
            include_tax=True,
        )
        self.assertEqual(a.currency, "EUR")
        self.assertEqual(a.horizon_years, 15)
        self.assertAlmostEqual(a.annual_discount_rate, 0.12)
        self.assertAlmostEqual(a.energy_escalation_pct, 0.05)
        self.assertAlmostEqual(a.contingency_pct, 0.1)
        self.assertAlmostEqual(a.tax_rate, 0.25)
        self.assertTrue(a.include_tax)

    def test_invalid_currency(self):
        for bad in ("US", "USDD", "usd", "12D", ""):
            with self.subTest(currency=bad), self.assertRaises(ValueError):
                TCOAssumptions(currency=bad)

    def test_invalid_horizon(self):
        for bad in (0, 51, -1, 1.5, True):
            with self.subTest(horizon=bad), self.assertRaises(ValueError):
                TCOAssumptions(horizon_years=bad)

    def test_invalid_discount_rate(self):
        for bad in (-0.01, 1.01, 2.0, True):
            with self.subTest(rate=bad), self.assertRaises(ValueError):
                TCOAssumptions(annual_discount_rate=bad)

    def test_invalid_escalation(self):
        for bad in (-1.5, 1.5, True):
            with self.subTest(rate=bad), self.assertRaises(ValueError):
                TCOAssumptions(energy_escalation_pct=bad)

    def test_invalid_contingency(self):
        for bad in (-0.1, 1.5, True):
            with self.subTest(val=bad), self.assertRaises(ValueError):
                TCOAssumptions(contingency_pct=bad)

    def test_invalid_tax_rate(self):
        for bad in (-0.1, 1.5, True):
            with self.subTest(val=bad), self.assertRaises(ValueError):
                TCOAssumptions(tax_rate=bad)


class TestTCOCostBreakdown(unittest.TestCase):
    """Tests for TCOCostBreakdown."""

    def test_defaults(self):
        c = TCOCostBreakdown()
        self.assertEqual(c.total_upfront, 0.0)
        self.assertEqual(c.total_annual_opex, 0.0)
        self.assertEqual(c.terminal_net, 0.0)
        self.assertEqual(c.total_capex, 0.0)
        self.assertEqual(c.total_opex, 0.0)

    def test_upfront_total(self):
        c = TCOCostBreakdown(
            hardware_capex=1000,
            facility_capex=500,
            design_capex=200,
            commissioning_capex=100,
            migration_capex=50,
            software_capex=150,
        )
        self.assertEqual(c.total_upfront, 2000.0)

    def test_annual_opex_total(self):
        c = TCOCostBreakdown(
            energy_annual=100,
            maintenance_annual=50,
            labor_annual=80,
            network_annual=20,
            software_annual=30,
            insurance_annual=10,
            tax_annual=15,
            other_annual=5,
        )
        self.assertEqual(c.total_annual_opex, 310.0)

    def test_terminal_net(self):
        c = TCOCostBreakdown(decommission_cost=100, residual_value=30)
        self.assertEqual(c.terminal_net, 70.0)

    def test_total_capex_includes_refresh(self):
        c = TCOCostBreakdown(hardware_capex=1000, refresh_cost=500)
        self.assertEqual(c.total_capex, 1500.0)

    def test_invalid_negative_value(self):
        with self.assertRaises(ValueError):
            TCOCostBreakdown(hardware_capex=-100)

    def test_invalid_refresh_interval(self):
        with self.assertRaises(ValueError):
            TCOCostBreakdown(refresh_interval_years=-1)
        with self.assertRaises(ValueError):
            TCOCostBreakdown(refresh_interval_years=51)


class TestEvaluateTCO(unittest.TestCase):
    """Tests for evaluate_tco function."""

    def _make_scenario(self, **kwargs) -> TCOScenario:
        costs = TCOCostBreakdown(
            hardware_capex=kwargs.get("hardware_capex", 10000),
            facility_capex=kwargs.get("facility_capex", 5000),
            design_capex=kwargs.get("design_capex", 2000),
            commissioning_capex=kwargs.get("commissioning_capex", 1000),
            migration_capex=kwargs.get("migration_capex", 500),
            software_capex=kwargs.get("software_capex", 1500),
            energy_annual=kwargs.get("energy_annual", 1200),
            maintenance_annual=kwargs.get("maintenance_annual", 600),
            labor_annual=kwargs.get("labor_annual", 800),
            network_annual=kwargs.get("network_annual", 200),
            software_annual=kwargs.get("software_annual", 300),
            insurance_annual=kwargs.get("insurance_annual", 100),
            tax_annual=kwargs.get("tax_annual", 150),
            other_annual=kwargs.get("other_annual", 50),
            refresh_cost=kwargs.get("refresh_cost", 0),
            refresh_interval_years=kwargs.get("refresh_interval_years", 0),
            decommission_cost=kwargs.get("decommission_cost", 200),
            residual_value=kwargs.get("residual_value", 50),
        )
        assumptions = TCOAssumptions(
            currency=kwargs.get("currency", "USD"),
            horizon_years=kwargs.get("horizon_years", 10),
            annual_discount_rate=kwargs.get("annual_discount_rate", 0.08),
            energy_escalation_pct=kwargs.get("energy_escalation_pct", 0.03),
            maintenance_escalation_pct=kwargs.get("maintenance_escalation_pct", 0.025),
            labor_escalation_pct=kwargs.get("labor_escalation_pct", 0.03),
            other_escalation_pct=kwargs.get("other_escalation_pct", 0.02),
            contingency_pct=kwargs.get("contingency_pct", 0.0),
            tax_rate=kwargs.get("tax_rate", 0.0),
            include_tax=kwargs.get("include_tax", False),
        )
        return TCOScenario(
            name=kwargs.get("name", "Test Scenario"),
            costs=costs,
            assumptions=assumptions,
            scenario_type=kwargs.get("scenario_type", "on-prem"),
            it_capacity_kw=kwargs.get("it_capacity_kw"),
            rack_count=kwargs.get("rack_count"),
            area_m2=kwargs.get("area_m2"),
            annual_energy_kwh=kwargs.get("annual_energy_kwh"),
        )

    def test_basic_evaluation(self):
        scenario = self._make_scenario()
        result = evaluate_tco(scenario)

        self.assertEqual(result.scenario_name, "Test Scenario")
        self.assertEqual(result.scenario_type, "on-prem")
        self.assertEqual(result.horizon_years, 10)
        self.assertEqual(result.currency, "USD")
        self.assertGreater(result.total_capex, 0)
        self.assertGreater(result.total_opex, 0)
        self.assertGreater(result.total_undiscounted, 0)
        self.assertGreater(result.total_pv, 0)
        self.assertGreater(result.equivalent_annual_cost, 0)
        self.assertGreater(result.average_annual_cost, 0)
        self.assertGreater(result.year_zero_cash, 0)
        self.assertIsNotNone(result.yearly_cash_flows)
        self.assertEqual(len(result.yearly_cash_flows), 11)  # year 0 + 10 years

    def test_zero_discount_rate(self):
        scenario = self._make_scenario(annual_discount_rate=0.0)
        result = evaluate_tco(scenario)

        # With zero discount, PV should equal undiscounted total
        self.assertAlmostEqual(result.total_pv, result.total_undiscounted, places=2)

    def test_pv_less_than_undiscounted(self):
        scenario = self._make_scenario(annual_discount_rate=0.1)
        result = evaluate_tco(scenario)

        # With positive discount, PV should be less than undiscounted
        self.assertLess(result.total_pv, result.total_undiscounted)

    def test_escalation_increases_opex(self):
        scenario_no_esc = self._make_scenario(
            energy_escalation_pct=0.0,
            maintenance_escalation_pct=0.0,
            labor_escalation_pct=0.0,
            other_escalation_pct=0.0,
        )
        scenario_esc = self._make_scenario(
            energy_escalation_pct=0.05,
            maintenance_escalation_pct=0.05,
            labor_escalation_pct=0.05,
            other_escalation_pct=0.05,
        )
        result_no_esc = evaluate_tco(scenario_no_esc)
        result_esc = evaluate_tco(scenario_esc)

        self.assertGreater(result_esc.total_opex, result_no_esc.total_opex)

    def test_contingency_increases_costs(self):
        scenario_no_cont = self._make_scenario(contingency_pct=0.0)
        scenario_cont = self._make_scenario(contingency_pct=0.1)
        result_no_cont = evaluate_tco(scenario_no_cont)
        result_cont = evaluate_tco(scenario_cont)

        self.assertGreater(result_cont.total_undiscounted, result_no_cont.total_undiscounted)

    def test_refresh_cost_applied(self):
        scenario_no_refresh = self._make_scenario(refresh_cost=0, refresh_interval_years=0)
        scenario_refresh = self._make_scenario(refresh_cost=5000, refresh_interval_years=5)
        result_no_refresh = evaluate_tco(scenario_no_refresh)
        result_refresh = evaluate_tco(scenario_refresh)

        self.assertEqual(result_no_refresh.total_refresh, 0.0)
        self.assertGreater(result_refresh.total_refresh, 0.0)

    def test_unit_economics_kw(self):
        scenario = self._make_scenario(it_capacity_kw=100.0)
        result = evaluate_tco(scenario)

        self.assertIsNotNone(result.cost_per_kw_year)
        self.assertAlmostEqual(
            result.cost_per_kw_year,
            result.equivalent_annual_cost / 100.0,
            places=4,
        )

    def test_unit_economics_rack(self):
        scenario = self._make_scenario(rack_count=50.0)
        result = evaluate_tco(scenario)

        self.assertIsNotNone(result.cost_per_rack_year)
        self.assertAlmostEqual(
            result.cost_per_rack_year,
            result.equivalent_annual_cost / 50.0,
            places=4,
        )

    def test_unit_economics_m2(self):
        scenario = self._make_scenario(area_m2=500.0)
        result = evaluate_tco(scenario)

        self.assertIsNotNone(result.cost_per_m2_year)
        self.assertAlmostEqual(
            result.cost_per_m2_year,
            result.equivalent_annual_cost / 500.0,
            places=4,
        )

    def test_unit_economics_kwh(self):
        scenario = self._make_scenario(annual_energy_kwh=100000.0)
        result = evaluate_tco(scenario)

        self.assertIsNotNone(result.cost_per_kwh)
        total_energy = 100000.0 * 10  # 10 years
        self.assertAlmostEqual(
            result.cost_per_kwh,
            result.total_pv / total_energy,
            places=4,
        )

    def test_after_tax_analysis(self):
        scenario = self._make_scenario(
            include_tax=True,
            tax_rate=0.25,
        )
        result = evaluate_tco(scenario)

        self.assertIsNotNone(result.after_tax_pv)
        self.assertIsNotNone(result.after_tax_eac)
        # After-tax PV should be less than pre-tax PV
        self.assertLess(result.after_tax_pv, result.total_pv)

    def test_yearly_cash_flows_structure(self):
        scenario = self._make_scenario(horizon_years=5)
        result = evaluate_tco(scenario)

        self.assertEqual(len(result.yearly_cash_flows), 6)  # year 0 + 5 years
        # Year 0 should have capex
        self.assertGreater(result.yearly_cash_flows[0].capex, 0)
        # Year 1 should have opex
        self.assertGreater(result.yearly_cash_flows[1].opex, 0)
        # Last year should have terminal
        self.assertNotEqual(result.yearly_cash_flows[5].terminal, 0.0)

    def test_horizon_one_year(self):
        scenario = self._make_scenario(horizon_years=1)
        result = evaluate_tco(scenario)

        self.assertEqual(len(result.yearly_cash_flows), 2)  # year 0 + year 1
        self.assertEqual(result.horizon_years, 1)


class TestCompareTCO(unittest.TestCase):
    """Tests for compare_tco function."""

    def _make_scenario(self, name: str, hardware_capex: float = 10000) -> TCOScenario:
        costs = TCOCostBreakdown(
            hardware_capex=hardware_capex,
            energy_annual=1000,
            maintenance_annual=500,
        )
        return TCOScenario(name=name, costs=costs)

    def test_compare_two_scenarios(self):
        s1 = self._make_scenario("Scenario A", hardware_capex=10000)
        s2 = self._make_scenario("Scenario B", hardware_capex=15000)
        comparison = compare_tco([s1, s2])

        self.assertEqual(len(comparison.scenarios), 2)
        self.assertEqual(comparison.baseline_index, 0)
        self.assertEqual(len(comparison.pv_deltas), 2)
        self.assertEqual(len(comparison.eac_deltas), 2)
        # Scenario B has higher capex, so PV delta should be positive
        self.assertGreater(comparison.pv_deltas[1], 0)
        # Scenario A should have lower PV
        self.assertEqual(comparison.lower_pv_index, 0)

    def test_compare_with_baseline(self):
        s1 = self._make_scenario("Scenario A", hardware_capex=10000)
        s2 = self._make_scenario("Scenario B", hardware_capex=15000)
        comparison = compare_tco([s1, s2], baseline_index=1)

        self.assertEqual(comparison.baseline_index, 1)
        # Scenario A has lower capex, so PV delta from B should be negative
        self.assertLess(comparison.pv_deltas[0], 0)

    def test_empty_scenarios_raises(self):
        with self.assertRaises(ValueError):
            compare_tco([])

    def test_invalid_baseline_raises(self):
        s1 = self._make_scenario("Scenario A")
        with self.assertRaises(ValueError):
            compare_tco([s1], baseline_index=5)


class TestRunTCOSensitivity(unittest.TestCase):
    """Tests for run_tco_sensitivity function."""

    def _make_scenario(self) -> TCOScenario:
        costs = TCOCostBreakdown(
            hardware_capex=10000,
            energy_annual=1200,
            maintenance_annual=600,
            labor_annual=800,
        )
        return TCOScenario(name="Test", costs=costs)

    def test_discount_rate_sensitivity(self):
        scenario = self._make_scenario()
        result = run_tco_sensitivity(scenario, "discount_rate", [0.05, 0.08, 0.12])

        self.assertEqual(result.parameter_name, "discount_rate")
        self.assertEqual(len(result.values_tested), 3)
        self.assertEqual(len(result.pv_results), 3)
        self.assertEqual(len(result.eac_results), 3)
        # Higher discount rate should generally increase EAC
        self.assertGreaterEqual(result.eac_results[2], result.eac_results[0])

    def test_horizon_sensitivity(self):
        scenario = self._make_scenario()
        result = run_tco_sensitivity(scenario, "horizon_years", [5, 10, 15])

        self.assertEqual(result.parameter_name, "horizon_years")
        self.assertEqual(len(result.pv_results), 3)

    def test_hardware_capex_sensitivity(self):
        scenario = self._make_scenario()
        result = run_tco_sensitivity(scenario, "hardware_capex", [5000, 10000, 20000])

        self.assertEqual(result.parameter_name, "hardware_capex")
        # Higher capex should increase PV
        self.assertGreater(result.pv_results[2], result.pv_results[0])

    def test_unsupported_parameter_raises(self):
        scenario = self._make_scenario()
        with self.assertRaises(ValueError):
            run_tco_sensitivity(scenario, "unsupported_param", [1, 2, 3])

    def test_empty_values_raises(self):
        scenario = self._make_scenario()
        with self.assertRaises(ValueError):
            run_tco_sensitivity(scenario, "discount_rate", [])


class TestTCOEngine(unittest.TestCase):
    """Tests for TCOEngine class."""

    def _make_scenario(self, name: str, hardware_capex: float = 10000) -> TCOScenario:
        costs = TCOCostBreakdown(
            hardware_capex=hardware_capex,
            energy_annual=1000,
        )
        return TCOScenario(name=name, costs=costs)

    def test_add_and_evaluate(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        engine.add_scenario(self._make_scenario("B", hardware_capex=15000))

        self.assertEqual(engine.count, 2)
        results = engine.evaluate()
        self.assertEqual(len(results), 2)

    def test_evaluate_by_name(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        engine.add_scenario(self._make_scenario("B", hardware_capex=15000))

        result = engine.evaluate("A")
        self.assertEqual(result.scenario_name, "A")

    def test_evaluate_not_found(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        with self.assertRaises(ValueError):
            engine.evaluate("Z")

    def test_compare(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        engine.add_scenario(self._make_scenario("B", hardware_capex=15000))

        comparison = engine.compare()
        self.assertEqual(len(comparison.scenarios), 2)

    def test_compare_with_baseline(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        engine.add_scenario(self._make_scenario("B", hardware_capex=15000))

        comparison = engine.compare(baseline="B")
        self.assertEqual(comparison.baseline_index, 1)

    def test_sensitivity(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))

        result = engine.sensitivity("discount_rate", [0.05, 0.1])
        self.assertEqual(result.parameter_name, "discount_rate")

    def test_remove_scenario(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        engine.add_scenario(self._make_scenario("B"))
        engine.remove_scenario("A")

        self.assertEqual(engine.count, 1)
        self.assertEqual(engine.scenarios[0].name, "B")

    def test_clear(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        engine.clear()
        self.assertEqual(engine.count, 0)

    def test_to_dict(self):
        engine = TCOEngine()
        engine.add_scenario(self._make_scenario("A"))
        data = engine.to_dict()

        self.assertEqual(data["scenario_count"], 1)
        self.assertEqual(len(data["scenarios"]), 1)
        self.assertIn("result", data["scenarios"][0])


class TestQuickTCO(unittest.TestCase):
    """Tests for quick_tco convenience function."""

    def test_basic_quick_tco(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            maintenance_annual=600,
            horizon_years=10,
        )

        self.assertIsInstance(result, TCOResult)
        self.assertEqual(result.horizon_years, 10)
        self.assertGreater(result.total_pv, 0)
        self.assertGreater(result.equivalent_annual_cost, 0)

    def test_quick_tco_with_units(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            horizon_years=10,
            it_capacity_kw=100.0,
            rack_count=50.0,
            area_m2=500.0,
            annual_energy_kwh=100000.0,
        )

        self.assertIsNotNone(result.cost_per_kw_year)
        self.assertIsNotNone(result.cost_per_rack_year)
        self.assertIsNotNone(result.cost_per_m2_year)
        self.assertIsNotNone(result.cost_per_kwh)

    def test_quick_tco_zero_costs(self):
        result = quick_tco(horizon_years=5)

        self.assertEqual(result.total_capex, 0.0)
        self.assertEqual(result.total_opex, 0.0)
        self.assertEqual(result.total_pv, 0.0)


class TestTCOBreakdownByCategory(unittest.TestCase):
    """Tests for tco_breakdown_by_category function."""

    def test_breakdown(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            maintenance_annual=600,
            horizon_years=10,
        )
        breakdown = tco_breakdown_by_category(result)

        self.assertIn("capex", breakdown)
        self.assertIn("opex", breakdown)
        self.assertIn("refresh", breakdown)
        self.assertIn("terminal", breakdown)
        self.assertIn("total", breakdown)
        self.assertAlmostEqual(
            breakdown["total"],
            breakdown["capex"] + breakdown["opex"] + breakdown["refresh"] + breakdown["terminal"],
            places=2,
        )


class TestTCOCostPerUnit(unittest.TestCase):
    """Tests for tco_cost_per_unit function."""

    def test_cost_per_kw(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            horizon_years=10,
        )
        cost = tco_cost_per_unit(result, "kw", 100.0)
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(cost, result.equivalent_annual_cost / 100.0, places=4)

    def test_cost_per_rack(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            horizon_years=10,
        )
        cost = tco_cost_per_unit(result, "rack", 50.0)
        self.assertIsNotNone(cost)

    def test_cost_per_m2(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            horizon_years=10,
        )
        cost = tco_cost_per_unit(result, "m2", 500.0)
        self.assertIsNotNone(cost)

    def test_cost_per_kwh(self):
        result = quick_tco(
            hardware_capex=10000,
            energy_annual=1200,
            horizon_years=10,
            annual_energy_kwh=100000.0,
        )
        cost = tco_cost_per_unit(result, "kwh", 1000000.0)
        self.assertIsNotNone(cost)

    def test_zero_denominator_returns_none(self):
        result = quick_tco(horizon_years=5)
        cost = tco_cost_per_unit(result, "kw", 0.0)
        self.assertIsNone(cost)

    def test_negative_denominator_returns_none(self):
        result = quick_tco(horizon_years=5)
        cost = tco_cost_per_unit(result, "kw", -10.0)
        self.assertIsNone(cost)

    def test_unsupported_unit_type(self):
        result = quick_tco(horizon_years=5)
        with self.assertRaises(ValueError):
            tco_cost_per_unit(result, "unsupported", 100.0)


class TestTCOScenario(unittest.TestCase):
    """Tests for TCOScenario validation."""

    def test_valid_scenario(self):
        costs = TCOCostBreakdown(hardware_capex=1000)
        scenario = TCOScenario(name="Test", costs=costs)
        self.assertEqual(scenario.name, "Test")
        self.assertEqual(scenario.scenario_type, "on-prem")

    def test_invalid_name(self):
        costs = TCOCostBreakdown(hardware_capex=1000)
        with self.assertRaises(ValueError):
            TCOScenario(name="", costs=costs)
        with self.assertRaises(ValueError):
            TCOScenario(name="   ", costs=costs)

    def test_invalid_scenario_type(self):
        costs = TCOCostBreakdown(hardware_capex=1000)
        with self.assertRaises(ValueError):
            TCOScenario(name="Test", costs=costs, scenario_type="")

    def test_invalid_tags(self):
        costs = TCOCostBreakdown(hardware_capex=1000)
        with self.assertRaises(ValueError):
            TCOScenario(name="Test", costs=costs, tags="not_a_list")

    def test_invalid_metadata(self):
        costs = TCOCostBreakdown(hardware_capex=1000)
        with self.assertRaises(ValueError):
            TCOScenario(name="Test", costs=costs, metadata="not_a_dict")


class TestYearlyCashFlow(unittest.TestCase):
    """Tests for YearlyCashFlow dataclass."""

    def test_creation(self):
        flow = YearlyCashFlow(
            year=1,
            opex=1000.0,
            total_undiscounted=1000.0,
            discount_factor=0.9,
            total_discounted=900.0,
        )
        self.assertEqual(flow.year, 1)
        self.assertEqual(flow.opex, 1000.0)
        self.assertEqual(flow.total_discounted, 900.0)


if __name__ == "__main__":
    unittest.main()
