"""Example: Detect resources added outside IaC.

Detects resources that exist in actual state but not in desired state.
"""
from dcc.iac_observability.drift import DriftDetector, DriftType

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-999": {"resource_type": "aws_instance", "name": "rogue", "instance_type": "t3.large"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
print(f"Total drifted: {result.total_drifted}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name} ({d.resource_id}) - {d.description}")
