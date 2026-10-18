"""Example: Full IaC observability pipeline.

Demonstrates running all IaC observability checks in sequence.
"""
from dcc.iac_observability.drift import DriftDetector
from dcc.iac_observability.compliance import ComplianceEngine, get_default_checks
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector
from dcc.iac_observability.security_alerts import SecurityAlertEngine
from dcc.iac_observability.dashboard import IaCDashboard

# Sample infrastructure state
desired = {
    "i-1": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-2": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
}
actual = {
    "i-1": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.large"},
    "i-2": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
    "i-3": {"resource_type": "aws_instance", "name": "rogue", "instance_type": "t3.micro"},
}

resources = [
    {"id": "i-1", "resource_type": "aws_instance", "encrypted": True, "publicly_accessible": False,
     "tags": {"env": "prod"}, "logging_enabled": True},
    {"id": "i-2", "resource_type": "aws_instance", "encrypted": True, "publicly_accessible": False,
     "tags": {"env": "prod"}, "logging_enabled": True},
]

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 100.0}
    for d in range(1, 15)
]

# Run all checks
drift_result = DriftDetector().detect(desired, actual)
compliance_report = ComplianceEngine(get_default_checks()).evaluate(resources)
cost_report = CostAnomalyDetector().detect(cost_data)
security_report = SecurityAlertEngine().evaluate(resources)

# Build dashboard
dashboard = IaCDashboard()
dashboard.set_drift_result(drift_result)
dashboard.set_compliance_report(compliance_report)
dashboard.set_cost_report(cost_report)
dashboard.set_security_report(security_report)
report = dashboard.build()

print(f"Overall status: {report.status.value}")
for p in report.panels:
    print(f"  {p.name}: {p.status}")
