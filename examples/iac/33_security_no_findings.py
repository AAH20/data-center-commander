"""Example: Security evaluation with no findings.

Demonstrates evaluating resources that pass all security checks.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine

resources = [
    {
        "id": "r1",
        "resource_type": "aws_instance",
        "encrypted": True,
        "publicly_accessible": False,
        "logging_enabled": True,
        "mfa_enabled": True,
        "open_ports": [{"port": 443, "cidr": "0.0.0.0/0"}],
    },
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
print(f"Total alerts: {report.total_alerts}")
print(f"Open alerts: {report.open_alerts}")
print(f"Has critical: {report.has_critical}")
