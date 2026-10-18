"""Example: Detect credential drift.

Detects SSH key, certificate, or secret changes (critical severity).
"""
from dcc.iac_observability.drift import DriftDetector, DriftType

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "key": "old-key-pair"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "key": "new-key-pair"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name}")
    print(f"    Severity: {d.severity.value}")
    print(f"    Description: {d.description}")
