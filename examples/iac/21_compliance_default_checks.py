"""Example: Using default compliance checks.

Demonstrates the pre-built compliance checks.
"""
from dcc.iac_observability.compliance import ComplianceEngine, get_default_checks

checks = get_default_checks()
print(f"Number of default checks: {len(checks)}")
for c in checks:
    print(f"  {c.check_id}: {c.name} ({c.category})")

# Evaluate against a sample resource
resources = [
    {
        "id": "r1",
        "resource_type": "aws_s3_bucket",
        "encrypted": True,
        "publicly_accessible": False,
        "tags": {"environment": "prod", "cost_center": "cc1", "owner": "team-a"},
        "logging_enabled": True,
        "versioning_enabled": True,
    },
]
engine = ComplianceEngine(checks)
report = engine.evaluate(resources)
print(f"\nTotal checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
print(f"Compliance rate: {report.compliance_rate:.1%}")
