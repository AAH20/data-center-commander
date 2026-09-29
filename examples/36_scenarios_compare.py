"""Example: Compare multiple deployment scenarios.

Side-by-side NPV and cost-per-unit comparison.
"""
from dcc.economics.scenarios import (
    DeploymentScenario, CostBreakdown, ScenarioAssumptions, compare_scenarios,
)

onprem = DeploymentScenario(
    name="On-Prem",
    costs=CostBreakdown(capex=10_000_000, power_monthly=100_000, labor_monthly=80_000, maintenance_monthly=50_000),
    assumptions=ScenarioAssumptions(currency="USD", horizon_months=60),
    scenario_type="on-prem",
)
cloud = DeploymentScenario(
    name="Cloud",
    costs=CostBreakdown(capex=500_000, software_monthly=300_000, network_monthly=50_000),
    assumptions=ScenarioAssumptions(currency="USD", horizon_months=60),
    scenario_type="cloud",
)
comparison = compare_scenarios([onprem, cloud])
print(comparison.summary)
