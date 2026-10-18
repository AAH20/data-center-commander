"""Example: Lifecycle cost calculator.

Computes year-by-year cash flows with escalation and refresh.
"""
from decimal import Decimal
from dcc.economics.estimates import (
    LifecycleCostCalculator, DeploymentSpec, DeploymentType,
    EstimateLineItem, CostBehavior,
)

spec = DeploymentSpec(
    name="DC 1MW",
    deployment_type=DeploymentType.GREENFIELD,
    it_capacity_kw=Decimal("1000"),
    rack_count=100,
    white_space_m2=Decimal("1500"),
    horizon_months=120,
    discount_rate=Decimal("0.08"),
)
calc = LifecycleCostCalculator(spec)
line_items = [
    EstimateLineItem(
        line_no=1, phase="civil", description="Initial Build",
        quantity=Decimal("1"), quantity_unit="lot",
        waste_factor=Decimal("0"), base_unit_cost=Decimal("2000000"),
        low_unit_cost=None, high_unit_cost=None, currency="USD",
        pricing_status="sourced", cost_behavior="one_time",
        recurrence_months=None, start_month=0, escalation_pct=Decimal("0"),
        extended_base=Decimal("2000000"), extended_low=Decimal("2000000"),
        extended_high=Decimal("2000000"),
    ),
    EstimateLineItem(
        line_no=2, phase="energy_opex", description="Annual Energy",
        quantity=Decimal("1"), quantity_unit="year",
        waste_factor=Decimal("0"), base_unit_cost=Decimal("400000"),
        low_unit_cost=None, high_unit_cost=None, currency="USD",
        pricing_status="sourced", cost_behavior="fixed_recurring",
        recurrence_months=12, start_month=1, escalation_pct=Decimal("0.03"),
        extended_base=Decimal("400000"), extended_low=Decimal("400000"),
        extended_high=Decimal("400000"),
    ),
]
total_pv, total_low, total_high = calc.calculate_pv(line_items)
print(f"Total PV: ${total_pv:,.2f}")
print(f"Low: ${total_low:,.2f}")
print(f"High: ${total_high:,.2f}")
