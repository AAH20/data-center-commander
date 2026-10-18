"""Example: Detect resources removed from IaC.

Detects resources that exist in desired state but not in actual state.
"""
from dcc.iac_observability.drift import DriftDetector

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-789": {"resource_type": "aws_instance", "name": "old-server", "instance_type": "t3.micro"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name} - severity: {d.severity.value}")
