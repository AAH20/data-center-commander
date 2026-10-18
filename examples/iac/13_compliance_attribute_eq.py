"""Example: Compliance check with equality operator.

Demonstrates basic attribute equality compliance check.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity, ComplianceStatus,
)

check = ComplianceCheck(
    check_id="CIS-1.1",
    name="Encryption at Rest",
    description="Ensure encryption at rest is enabled",
    severity=ComplianceSeverity.HIGH,
    category="security",
    attribute="encrypted",
    expected_value=True,
    operator="eq",
)

resources = [
    {"id": "r1", "resource_type": "aws_ebs_volume", "encrypted": True},
    {"id": "r2", "resource_type": "aws_ebs_volume", "encrypted": False},
]

engine = ComplianceEngine([check])
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
print(f"Compliance rate: {report.compliance_rate:.1%}")
