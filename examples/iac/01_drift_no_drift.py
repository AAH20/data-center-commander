"""Example: Basic drift detection with no drift.

Demonstrates comparing desired and actual state when they match.
"""
from dcc.iac_observability.drift import DriftDetector

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-456": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-456": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
print(f"Total drifted: {result.total_drifted}")
print(f"Drift rate: {result.drift_rate:.2%}")
