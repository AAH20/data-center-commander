"""Example: Sensitivity analysis on a scenario.

Varies discount rate to see impact on NPV.
"""
from dcc.economics.scenarios import (
    DeploymentScenario, CostBreakdown, ScenarioAssumptions, run_sensitivity,
)

scenario = DeploymentScenario(
    name="Base",
    costs=CostBreakdown(capex=5_000_000, power_monthly=50_000, labor_monthly=40_000),
    assumptions=ScenarioAssumptions(currency="USD", horizon_months=36, annual_discount_rate=0.08),
)
sens = run_sensitivity(scenario, "discount_rate", [0.04, 0.06, 0.08, 0.10, 0.12])
for val, npv in zip(sens.values_tested, sens.npv_results):
    print(f"  Discount {val:.0%}: NPV = ${npv:,.2f}")
print(f"NPV range: ${sens.npv_range[0]:,.2f} - ${sens.npv_range[1]:,.2f}")
