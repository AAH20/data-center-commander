"""Example: Evaluate a single deployment scenario.

Computes NPV, cost/unit, and cash flow metrics for one scenario.
"""
from dcc.economics.scenarios import (
    DeploymentScenario, CostBreakdown, ScenarioAssumptions, evaluate_scenario,
)

scenario = DeploymentScenario(
    name="On-Prem 2MW",
    costs=CostBreakdown(
        capex=8_000_000, site=2_000_000, migration=500_000,
        power_monthly=80_000, software_monthly=20_000,
        maintenance_monthly=40_000, labor_monthly=60_000,
        network_monthly=15_000, backup_monthly=10_000,
        refresh=2_000_000, refresh_month=36,
        exit_cost=500_000, residual_value=1_500_000,
    ),
    assumptions=ScenarioAssumptions(
        currency="USD", horizon_months=60, annual_discount_rate=0.08,
        useful_units_per_month=100_000, useful_unit_name="requests",
    ),
    scenario_type="on-prem",
)
result = evaluate_scenario(scenario)
print(f"NPV: ${result.npv:,.2f}")
print(f"Cost/unit: ${result.cost_per_unit:.4f}")
print(f"Year 1 cash: ${result.year_one_cash:,.2f}")
