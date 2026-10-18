"""Example: Compliance check with custom evaluator function.

Demonstrates using a custom function for compliance evaluation.
"""
from dcc.iac_observability.compliance import (
    ComplianceCheck, ComplianceEngine, ComplianceSeverity,
)

def check_cost_center(resource):
    """Custom evaluator that checks for cost center tag."""
    tags = resource.get("tags", {})
    if isinstance(tags, dict) and "cost_center" in tags:
        return True, f"Cost center: {tags['cost_center']}"
    return False, "No cost center tag"

check = ComplianceCheck(
    check_id="ORG-1.4",
    name="Cost Center Tag",
    description="Ensure all resources have a cost center tag",
    severity=ComplianceSeverity.MEDIUM,
    category="tagging",
    evaluator=check_cost_center,
)

resources = [
    {"id": "r1", "resource_type": "aws_instance", "tags": {"cost_center": "cc-123"}},
    {"id": "r2", "resource_type": "aws_instance", "tags": {"env": "prod"}},
]

engine = ComplianceEngine([check])
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
for r in report.results:
    print(f"  {r.resource_id}: {r.status.value} - {r.detail}")
