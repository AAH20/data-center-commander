"""Example: Bottom-up estimator with explicit line items.

Demonstrates the BottomUpEstimator with manually specified components.
"""
from decimal import Decimal
from dcc.economics.estimates import (
    BottomUpEstimator, ComponentQuantity, CostBehavior, CostPhase,
    DeploymentSpec, DeploymentType,
)

spec = DeploymentSpec(
    name="DC 1MW",
    deployment_type=DeploymentType.GREENFIELD,
    it_capacity_kw=Decimal("1000"),
    rack_count=100,
    white_space_m2=Decimal("1500"),
    currency="USD",
    horizon_months=120,
    discount_rate=Decimal("0.08"),
    design_overrides={
        "components": [
            ComponentQuantity(
                phase=CostPhase.ELECTRICAL,
                description="UPS System",
                quantity=Decimal("4"),
                quantity_unit="system",
                cost_behavior=CostBehavior.ONE_TIME,
                unit_cost_override=Decimal("250000"),
            ),
            ComponentQuantity(
                phase=CostPhase.MECHANICAL,
                description="Generator",
                quantity=Decimal("2"),
                quantity_unit="unit",
                cost_behavior=CostBehavior.ONE_TIME,
                unit_cost_override=Decimal("400000"),
            ),
        ]
    },
)
estimator = BottomUpEstimator(spec)
result = estimator.estimate()
print(f"Total PV: ${result.total_pv_base:,.2f}")
print(f"Line count: {len(result.line_items)}")
