"""Example: Component sizing engine.

Shows how the sizing engine derives quantities from design parameters.
"""
from dcc.economics.estimates import ComponentSizingEngine, DeploymentSpec, DeploymentType

spec = DeploymentSpec(
    deployment_type=DeploymentType.ONPREM,
    it_capacity_kw=3000,
    rack_count=300,
    area_m2=5000,
)
engine = ComponentSizingEngine(spec)
components = engine.size_components()
for comp in components:
    print(f"  {comp.component}: {comp.quantity} {comp.unit}")
