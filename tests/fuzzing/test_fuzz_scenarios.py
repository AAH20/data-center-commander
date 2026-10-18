"""Fuzz tests for scenario modeling engine using Hypothesis."""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.economics.scenarios import (
    ScenarioAssumptions,
    CostBreakdown,
    DeploymentScenario,
    ScenarioEngine,
    compare_scenarios,
    evaluate_scenario,
    run_sensitivity,
)


# Strategies
currency_codes = st.sampled_from(["USD", "EUR", "GBP", "JPY"])

non_negative_floats = st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)

positive_floats = st.floats(min_value=0.001, max_value=1e9, allow_nan=False, allow_infinity=False)

discount_rates = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

horizon_months = st.integers(min_value=1, max_value=120)

scenario_types = st.sampled_from(["on-prem", "cloud", "hybrid"])


class TestScenarioFuzz:
    """Fuzz scenario modeling with various inputs."""

    @given(
        currency=currency_codes,
        horizon=horizon_months,
        discount_rate=discount_rates,
        useful_units=positive_floats,
    )
    @settings(max_examples=100)
    def test_scenario_assumptions_validation(self, currency, horizon, discount_rate, useful_units):
        """ScenarioAssumptions should accept valid inputs."""
        assumptions = ScenarioAssumptions(
            currency=currency,
            horizon_months=horizon,
            annual_discount_rate=discount_rate,
            useful_units_per_month=useful_units,
        )
        assert assumptions.currency == currency
        assert assumptions.horizon_months == horizon

    @given(
        capex=non_negative_floats,
        site=non_negative_floats,
        migration=non_negative_floats,
        power=non_negative_floats,
        software=non_negative_floats,
        maintenance=non_negative_floats,
        labor=non_negative_floats,
        network=non_negative_floats,
        backup=non_negative_floats,
        other=non_negative_floats,
        refresh=non_negative_floats,
        refresh_month=st.integers(min_value=0, max_value=120),
        exit_cost=non_negative_floats,
        residual=non_negative_floats,
    )
    @settings(max_examples=100)
    def test_cost_breakdown_creation(self, capex, site, migration, power, software,
                                      maintenance, labor, network, backup, other,
                                      refresh, refresh_month, exit_cost, residual):
        """CostBreakdown should accept any non-negative values."""
        costs = CostBreakdown(
            capex=capex, site=site, migration=migration,
            power_monthly=power, software_monthly=software,
            maintenance_monthly=maintenance, labor_monthly=labor,
            network_monthly=network, backup_monthly=backup,
            other_monthly=other, refresh=refresh,
            refresh_month=refresh_month, exit_cost=exit_cost,
            residual_value=residual,
        )
        assert costs.total_upfront >= 0
        assert costs.total_monthly >= 0

    @given(
        name=st.text(min_size=1, max_size=120),
        scenario_type=scenario_types,
        currency=currency_codes,
        horizon=horizon_months,
        discount_rate=discount_rates,
        capex=non_negative_floats,
        power=non_negative_floats,
    )
    @settings(max_examples=100)
    def test_evaluate_scenario(self, name, scenario_type, currency, horizon, discount_rate, capex, power):
        """evaluate_scenario should handle any valid scenario."""
        assumptions = ScenarioAssumptions(
            currency=currency,
            horizon_months=horizon,
            annual_discount_rate=discount_rate,
            useful_units_per_month=1.0,
        )
        costs = CostBreakdown(capex=capex, power_monthly=power)
        scenario = DeploymentScenario(
            name=name,
            costs=costs,
            assumptions=assumptions,
            scenario_type=scenario_type,
        )
        result = evaluate_scenario(scenario)
        assert result.scenario_name == name
        assert result.horizon_months == horizon
        assert result.currency == currency

    @given(
        num_scenarios=st.integers(min_value=1, max_value=5),
        currency=currency_codes,
        horizon=horizon_months,
    )
    @settings(max_examples=100)
    def test_compare_scenarios(self, num_scenarios, currency, horizon):
        """compare_scenarios should handle any number of scenarios."""
        scenarios = []
        for i in range(num_scenarios):
            assumptions = ScenarioAssumptions(
                currency=currency,
                horizon_months=horizon,
                annual_discount_rate=0.08,
                useful_units_per_month=1.0,
            )
            costs = CostBreakdown(
                capex=1000.0 * (i + 1),
                power_monthly=100.0 * (i + 1),
            )
            scenarios.append(DeploymentScenario(
                name=f"scenario-{i}",
                costs=costs,
                assumptions=assumptions,
            ))
        comparison = compare_scenarios(scenarios)
        assert len(comparison.scenarios) == num_scenarios
        assert comparison.baseline_index == 0

    @given(
        currency=currency_codes,
        horizon=horizon_months,
        discount_rate=discount_rates,
        capex=non_negative_floats,
        power=non_negative_floats,
        param_name=st.sampled_from(["discount_rate", "power_monthly", "capex", "labor_monthly"]),
        values=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_run_sensitivity(self, currency, horizon, discount_rate, capex, power, param_name, values):
        """run_sensitivity should handle any valid parameter and values."""
        assumptions = ScenarioAssumptions(
            currency=currency,
            horizon_months=horizon,
            annual_discount_rate=discount_rate,
            useful_units_per_month=1.0,
        )
        costs = CostBreakdown(capex=capex, power_monthly=power)
        scenario = DeploymentScenario(
            name="test",
            costs=costs,
            assumptions=assumptions,
        )
        try:
            result = run_sensitivity(scenario, param_name, values)
            assert result.parameter_name == param_name
            assert len(result.npv_results) == len(values)
        except ValueError:
            pass  # Expected for invalid parameter values

    @given(
        num_scenarios=st.integers(min_value=1, max_value=5),
        currency=currency_codes,
        horizon=horizon_months,
    )
    @settings(max_examples=100)
    def test_scenario_engine(self, num_scenarios, currency, horizon):
        """ScenarioEngine should handle any number of scenarios."""
        engine = ScenarioEngine()
        for i in range(num_scenarios):
            assumptions = ScenarioAssumptions(
                currency=currency,
                horizon_months=horizon,
                annual_discount_rate=0.08,
                useful_units_per_month=1.0,
            )
            costs = CostBreakdown(capex=1000.0 * (i + 1))
            engine.add_scenario(DeploymentScenario(
                name=f"scenario-{i}",
                costs=costs,
                assumptions=assumptions,
            ))
        assert engine.count == num_scenarios
        results = engine.evaluate()
        assert len(results) == num_scenarios
