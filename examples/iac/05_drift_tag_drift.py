"""Example: Detect tag drift.

Detects when resource tags have changed.
"""
from dcc.iac_observability.drift import DriftDetector

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "prod", "cost_center": "cc1"}},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "dev", "cost_center": "cc1"}},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name} - severity: {d.severity.value}")
