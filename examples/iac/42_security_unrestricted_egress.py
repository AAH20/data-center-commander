"""Example: Detect unrestricted egress.

Demonstrates detecting unrestricted outbound rules.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine

resources = [
    {
        "id": "r1",
        "resource_type": "aws_security_group",
        "egress_rules": [{"cidr": "0.0.0.0/0", "port": 0}],
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
