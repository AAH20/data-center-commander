"""Example: Compliance check with contains operator.

Demonstrates checking that an attribute contains a value.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity,
)

check = ComplianceCheck(
    check_id="ORG-1.2",
    name="Environment Tag",
    description="Ensure environment tag is present",
    severity=ComplianceSeverity.MEDIUM,
    category="tagging",
    attribute="name",
    expected_value="prod",
    operator="contains",
)

resources = [
    {"id": "r1", "resource_type": "aws_instance", "name": "prod-server-1"},
    {"id": "r2", "resource_type": "aws_instance", "name": "dev-server-1"},
]

engine = ComplianceEngine([check])
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
