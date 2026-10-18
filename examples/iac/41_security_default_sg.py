"""Example: Detect default security group usage.

Demonstrates detecting use of default security groups.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine

resources = [
    {
        "id": "r1",
        "resource_type": "aws_instance",
        "security_group": "default",
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
