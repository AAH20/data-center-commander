"""Example: Compare budget scenarios.

Side-by-side comparison of multiple budget forecasts.
"""
from dcc.economics.budget import compare_scenarios

scenarios = [
    {"name": "Conservative", "line_items": [{"line_id": "1", "description": "Energy", "phase": "energy", "cost_behavior": "variable", "quantity": 1, "base_unit_cost": 500_000, "recurrence_months": 1}]},
    {"name": "Aggressive", "line_items": [{"line_id": "1", "description": "Energy", "phase": "energy", "cost_behavior": "variable", "quantity": 1, "base_unit_cost": 350_000, "recurrence_months": 1}]},
]
result = compare_scenarios(scenarios=scenarios)
for s in result["scenarios"]:
    print(f"  {s['name']}: ${s['total_base']:,.2f}")
print(f"Spread: ${result['variance']['spread']:,.2f}")
