"""Example: Bottom-up estimator with explicit line items.

Demonstrates the BottomUpEstimator with manually specified components.
"""
from dcc.economics.estimates import (
    BottomUpEstimator, ComponentQuantity, CostBehavior, CostPhase,
)

estimator = BottomUpEstimator(
    currency="USD",
    horizon_years=10,
    discount_rate=0.08,
)
estimator.add_component(
    ComponentQuantity(
        component="UPS System",
        quantity=4,
        unit="system",
        phase=CostPhase.ELECTRICAL,
        cost_behavior=CostBehavior.ONE_TIME,
        base_unit_cost=250_000,
    )
)
estimator.add_component(
    ComponentQuantity(
        component="Generator",
        quantity=2,
        unit="unit",
        phase=CostPhase.MECHANICAL,
        cost_behavior=CostBehavior.ONE_TIME,
        base_unit_cost=400_000,
    )
)
result = estimator.estimate()
print(f"Total PV: ${result.total_pv:,.2f}")
print(f"Line count: {len(result.line_items)}")
