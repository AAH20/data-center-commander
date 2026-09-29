"""Example: Escalated price projection.

Applies an annual escalation rate to a base price.
"""
from dcc.economics.prices import compute_escalated_price

base_price = 100_000
escalated = compute_escalated_price(
    base_price=base_price,
    annual_escalation_pct=0.03,
    years=5,
)
print(f"Base: ${base_price:,.2f}")
print(f"After 5 years at 3%: ${escalated:,.2f}")
