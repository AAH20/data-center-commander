"""Example: Build security dashboard data.

Demonstrates creating dashboard-ready security alert data.
"""
from dcc.iac_observability.security_alerts import SecurityAlertEngine, build_security_dashboard

resources = [
    {"id": "r1", "resource_type": "aws_instance", "open_ports": [{"port": 22, "cidr": "0.0.0.0/0"}]},
    {"id": "r2", "resource_type": "aws_s3_bucket", "publicly_accessible": True, "encrypted": False},
    {"id": "r3", "resource_type": "aws_instance", "encrypted": True, "publicly_accessible": False},
]

engine = SecurityAlertEngine()
report = engine.evaluate(resources)
dashboard = build_security_dashboard(report)
print(f"Total alerts: {dashboard['total_alerts']}")
print(f"Open alerts: {dashboard['open_alerts']}")
print(f"Has critical: {dashboard['has_critical']}")
print(f"Critical count: {dashboard['critical_count']}")
print(f"Severity counts: {dashboard['severity_counts']}")
print(f"Top alerts: {len(dashboard['top_alerts'])}")
