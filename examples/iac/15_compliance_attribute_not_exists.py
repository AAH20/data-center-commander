"""Example: Compliance check with not_exists operator.

Demonstrates checking that an attribute does not exist.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity,
)

check = ComplianceCheck(
    check_id="SEC-1.1",
    name="No Public Access",
    description="Ensure resources are not publicly accessible",
    severity=ComplianceSeverity.CRITICAL,
    category="security",
    attribute="publicly_accessible",
    operator="not_exists",
)

resources = [
    {"id": "r1", "resource_type": "aws_s3_bucket"},
    {"id": "r2", "resource_type": "aws_s3_bucket", "publicly_accessible": True},
]

engine = ComplianceEngine([check])
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
