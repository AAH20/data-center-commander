"""Example: Detect outdated TLS.

Demonstrates detecting outdated TLS versions.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine, SecurityAlertType

resources = [
    {
        "id": "r1",
        "resource_type": "aws_lb",
        "tls_version": "TLSv1.0",
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
