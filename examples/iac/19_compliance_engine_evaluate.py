"""Example: Compliance engine with multiple checks and resources.

Demonstrates evaluating multiple compliance checks against multiple resources.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity,
)

checks = [
    ComplianceCheck(
        check_id="CIS-1.1", name="Encryption", description="Encryption at rest",
        severity=ComplianceSeverity.HIGH, category="security",
        attribute="encrypted", expected_value=True, operator="eq",
    ),
    ComplianceCheck(
        check_id="CIS-1.2", name="No Public Access", description="Not publicly accessible",
        severity=ComplianceSeverity.CRITICAL, category="security",
        attribute="publicly_accessible", expected_value=False, operator="eq",
    ),
    ComplianceCheck(
        check_id="ORG-1.1", name="Tags Present", description="Has tags",
        severity=ComplianceSeverity.LOW, category="tagging",
        attribute="tags", operator="exists",
    ),
]

resources = [
    {"id": "r1", "resource_type": "aws_instance", "encrypted": True, "publicly_accessible": False, "tags": {"env": "prod"}},
    {"id": "r2", "resource_type": "aws_instance", "encrypted": False, "publicly_accessible": True},
    {"id": "r3", "resource_type": "aws_s3_bucket", "encrypted": True, "publicly_accessible": False, "tags": {"env": "dev"}},
]

engine = ComplianceEngine(checks)
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
print(f"Compliance rate: {report.compliance_rate:.1%}")
print(f"Overall status: {report.overall_status.value}")
