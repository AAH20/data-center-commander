"""Example: Detect over-privileged access.

Demonstrates detecting wildcard permissions in IAM policies.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine, SecurityAlertType

resources = [
    {
        "id": "r1",
        "resource_type": "aws_iam_role",
        "policy": '{"Effect": "Allow", "Action": "*", "Resource": "*"}',
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
    print(f"    Severity: {a.finding.severity.value}")
