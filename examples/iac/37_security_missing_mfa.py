"""Example: Detect missing MFA.

Demonstrates detecting resources without MFA enabled.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine, SecurityAlertType

resources = [
    {
        "id": "r1",
        "resource_type": "aws_iam_user",
        "mfa_enabled": False,
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
