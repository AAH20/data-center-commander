"""Example: Detect missing logging.

Demonstrates detecting resources without audit logging.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine, SecurityAlertType

resources = [
    {
        "id": "r1",
        "resource_type": "aws_s3_bucket",
        "logging_enabled": False,
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
for a in report.alerts:
    print(f"  {a.finding.alert_type.value}: {a.finding.description}")
