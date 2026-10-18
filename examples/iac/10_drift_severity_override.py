"""Example: Custom severity overrides.

Demonstrates overriding default severity levels for drift types.
"""
from dcc.iac_observability.drift import DriftDetector, DriftType, DriftSeverity

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "prod"}},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "dev"}},
}

# Default severity for tag drift is LOW
detector1 = DriftDetector()
result1 = detector1.detect(desired, actual)
print(f"Default severity: {result1.drifts[0].severity.value}")

# Override to HIGH
detector2 = DriftDetector(severity_overrides={DriftType.TAG_DRIFT: DriftSeverity.HIGH})
result2 = detector2.detect(desired, actual)
print(f"Overridden severity: {result2.drifts[0].severity.value}")
