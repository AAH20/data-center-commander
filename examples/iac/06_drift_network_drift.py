"""Example: Detect network drift.

Detects VPC, subnet, or security group changes (critical severity).
"""
from dcc.iac_observability.drift import DriftDetector, DriftType, DriftSeverity

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "vpc": "vpc-123", "subnet": "subnet-1"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "vpc": "vpc-456", "subnet": "subnet-2"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
print(f"Has drift: {result.has_drift}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name}")
    print(f"    Severity: {d.severity.value}")
    print(f"    Changed: {d.changed_attributes}")
