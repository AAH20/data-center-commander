"""Example: Detect secret exposure.

Demonstrates detecting secrets in configuration.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine

resources = [
    {
        "id": "r1",
        "resource_type": "aws_instance",
        "user_data": "password=secret123",
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
    print(f"    Severity: {a.finding.severity.value}")
