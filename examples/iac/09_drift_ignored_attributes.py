"""Example: Custom ignored attributes.

Demonstrates ignoring specific attributes during drift detection.
"""
from dcc.iac_observability.drift import DriftDetector

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "metadata": "old", "created_at": "2024-01-01"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "metadata": "new", "created_at": "2024-06-01"},
}

# Without custom ignores - metadata change is detected
detector1 = DriftDetector()
result1 = detector1.detect(desired, actual)
print(f"Without ignore - has drift: {result1.has_drift}")

# With custom ignores - metadata change is ignored
detector2 = DriftDetector(ignored_attributes={"id", "metadata", "created_at"})
result2 = detector2.detect(desired, actual)
print(f"With ignore - has drift: {result2.has_drift}")
