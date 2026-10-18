"""Example: Build compliance dashboard data.

Demonstrates creating dashboard-ready compliance data.
"""
from dcc.iac_observability.compliance import (
    ComplianceEngine, get_default_checks, build_compliance_dashboard,
)

checks = get_default_checks()
resources = [
    {
        "id": "r1",
        "resource_type": "aws_instance",
        "encrypted": True,
        "publicly_accessible": False,
        "tags": {"environment": "prod", "cost_center": "cc1", "owner": "team-a"},
        "logging_enabled": True,
        "monitoring_enabled": True,
    },
    {
        "id": "r2",
        "resource_type": "aws_s3_bucket",
        "encrypted": False,
        "publicly_accessible": True,
        "tags": {"environment": "dev"},
        "logging_enabled": False,
    },
]
engine = ComplianceEngine(checks)
report = engine.evaluate(resources)
dashboard = build_compliance_dashboard(report)
print(f"Compliance rate: {dashboard['compliance_rate']}%")
print(f"Overall status: {dashboard['overall_status']}")
print(f"Summary: {dashboard['summary']}")
print(f"By category: {dashboard['by_category']}")
print(f"Top failures: {len(dashboard['top_failures'])}")
