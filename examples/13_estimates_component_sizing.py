"""Example: Component sizing engine.

Shows how the sizing engine derives quantities from design parameters.
"""
from decimal import Decimal
from dcc.economics.estimates import ComponentSizingEngine, DeploymentSpec, DeploymentType

spec = DeploymentSpec(
    name="DC 3MW",
    deployment_type=DeploymentType.GREENFIELD,
    it_capacity_kw=Decimal("3000"),
    rack_count=300,
    white_space_m2=Decimal("5000"),
)
engine = ComponentSizingEngine(spec)
components = engine.size_all_components()
for comp in components:
    print(f"  {comp.description}: {comp.quantity} {comp.quantity_unit}")
