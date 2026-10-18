"""Example: Compliance check with regex operator.

Demonstrates checking that an attribute matches a regex pattern.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity,
)

check = ComplianceCheck(
    check_id="ORG-1.3",
    name="Naming Convention",
    description="Ensure resources follow naming convention",
    severity=ComplianceSeverity.MEDIUM,
    category="tagging",
    attribute="name",
    expected_value=r"^prod-.*",
    operator="regex",
)

resources = [
    {"id": "r1", "resource_type": "aws_instance", "name": "prod-server-1"},
    {"id": "r2", "resource_type": "aws_instance", "name": "staging-server-1"},
]

engine = ComplianceEngine([check])
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
