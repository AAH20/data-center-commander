"""Example: Detect size/capacity drift.

Detects instance type, capacity, or tier changes.
"""
from dcc.iac_observability.drift import DriftDetector

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-456": {"resource_type": "aws_instance", "name": "db-1", "instance_type": "t3.small"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.large"},
    "i-456": {"resource_type": "aws_instance", "name": "db-1", "instance_type": "t3.small"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name}")
    print(f"    Changed: {d.changed_attributes}")
