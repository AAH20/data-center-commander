"""Example: Compliance check with exists operator.

Demonstrates checking that an attribute exists.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity,
)

check = ComplianceCheck(
    check_id="ORG-1.1",
    name="Tags Present",
    description="Ensure all resources have tags",
    severity=ComplianceSeverity.LOW,
    category="tagging",
    attribute="tags",
    operator="exists",
)

resources = [
    {"id": "r1", "resource_type": "aws_instance", "tags": {"env": "prod"}},
    {"id": "r2", "resource_type": "aws_instance"},
]

engine = ComplianceEngine([check])
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
