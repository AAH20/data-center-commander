"""Example: Detect modified resources.

Detects resources that exist in both states but have different attributes.
"""
from dcc.iac_observability.drift import DriftDetector

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.large"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name}")
    print(f"    Changed attributes: {d.changed_attributes}")
    print(f"    Desired: {d.desired_state}")
    print(f"    Actual:  {d.actual_state}")
