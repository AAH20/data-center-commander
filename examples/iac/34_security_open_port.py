"""Example: Detect open ports.

Demonstrates detecting unrestricted port access.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine, SecurityAlertType

resources = [
    {
        "id": "r1",
        "resource_type": "aws_instance",
        "open_ports": [{"port": 22, "cidr": "0.0.0.0/0"}],
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
    print(f"    Severity: {a.finding.severity.value}")
    print(f"    Remediation: {a.finding.remediation}")
