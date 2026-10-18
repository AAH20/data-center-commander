"""Example: Compliance report overall status.

Demonstrates how overall status is determined from check results.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine,
)

# All pass
checks = [
    ComplianceCheck(
        check_id="c1", name="Check 1", description="Test",
        severity="high", category="security",
        attribute="encrypted", expected_value=True, operator="eq",
    ),
]
resources = [{"id": "r1", "encrypted": True}]
report = ComplianceEngine(checks).evaluate(resources)
print(f"All pass - status: {report.overall_status.value}")

# Some fail
resources = [{"id": "r1", "encrypted": True}, {"id": "r2", "encrypted": False}]
report = ComplianceEngine(checks).evaluate(resources)
print(f"Some fail - status: {report.overall_status.value}")
print(f"Compliance rate: {report.compliance_rate:.1%}")
