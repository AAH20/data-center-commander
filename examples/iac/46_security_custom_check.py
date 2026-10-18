"""Example: Custom security check.

Demonstrates adding a custom security check.
"""
from dcc.iac_observability.security_alerts import (
    SecurityAlertEngine, SecurityFinding, SecurityAlertType, SecurityAlertSeverity,
)

def custom_check(resource):
    """Custom check for specific resource configuration."""
    if resource.get("custom_flag"):
        return [SecurityFinding(
            alert_type=SecurityAlertType.MISSING_LOGGING,
            severity=SecurityAlertSeverity.LOW,
            resource_id=resource.get("id", "unknown"),
            resource_name=resource.get("name", "unknown"),
            resource_type=resource.get("resource_type", "unknown"),
            description="Custom finding: resource has custom_flag set",
        )]
    return []

engine = SecurityAlertEngine()
engine.add_check(custom_check)

resources = [
    {"id": "r1", "resource_type": "aws_instance", "custom_flag": True},
    {"id": "r2", "resource_type": "aws_instance"},
]

report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
