"""Example: Drift rate calculation.

Demonstrates how drift rate is calculated.
"""
from dcc.iac_observability.drift import DriftDetector

# 3 desired, 3 actual, 1 drifted = 1/6 = 16.67%
desired = {
    "i-1": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-2": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
    "i-3": {"resource_type": "aws_instance", "name": "web-3", "instance_type": "t3.micro"},
}
actual = {
    "i-1": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-2": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.large"},
    "i-3": {"resource_type": "aws_instance", "name": "web-3", "instance_type": "t3.micro"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Total desired: {result.total_desired}")
print(f"Total actual: {result.total_actual}")
print(f"Total drifted: {result.total_drifted}")
print(f"Drift rate: {result.drift_rate:.2%}")
print(f"Has drift: {result.has_drift}")
