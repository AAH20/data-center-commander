"""Example: Escalated price projection.

Applies an annual escalation rate to a base price.
"""
from decimal import Decimal
from dcc.economics.prices import compute_escalated_price

base_price = Decimal("100000")
escalated = compute_escalated_price(
    base_price=base_price,
    escalation_rate=Decimal("0.03"),
    periods=5,
)
print(f"Base: ${base_price:,.2f}")
print(f"After 5 years at 3%: ${escalated:,.2f}")
