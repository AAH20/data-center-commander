"""Example: Budget forecast from line items.

Projects monthly and annual budgets with escalation and growth.
"""
from dcc.economics.budget import forecast_budget

line_items = [
    {"line_id": "1", "description": "Energy", "phase": "energy", "cost_behavior": "variable", "quantity": 1, "base_unit_cost": 400_000, "escalation_pct": 0.03, "recurrence_months": 1, "start_month": 0},
    {"line_id": "2", "description": "Maintenance", "phase": "maintenance", "cost_behavior": "fixed_recurring", "quantity": 1, "base_unit_cost": 100_000, "escalation_pct": 0.025, "recurrence_months": 1, "start_month": 0},
    {"line_id": "3", "description": "Hardware Refresh", "phase": "it", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 2_000_000, "start_month": 36},
]
result = forecast_budget(
    line_items=line_items,
    horizon_months=48,
    discount_rate=0.08,
    contingency_pct=0.05,
    growth_plan={"monthly_capacity_growth": 0.01, "monthly_cost_reduction": 0.005},
)
print(f"Total base: ${result['total_base']:,.2f}")
print(f"Total PV: ${result['total_pv_base']:,.2f}")
for annual in result["annual_totals"]:
    print(f"  Year {annual['year']}: ${annual['base']:,.2f}")
