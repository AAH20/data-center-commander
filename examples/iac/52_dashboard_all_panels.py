"""Example: Dashboard with all panels.

Demonstrates building a complete dashboard with all data sources.
"""
from dcc.iac_observability.dashboard import IaCDashboard
from dcc.iac_observability.drift import DriftResult, DriftSeverity, DriftType, ResourceDrift
from dcc.iac_observability.compliance import ComplianceReport
from dcc.iac_observability.cost_anomaly import CostAnomalyReport, CostAnomalySeverity, CostAnomalyType, CostAnomaly
from dcc.iac_observability.security_alerts import (
    SecurityAlertReport, SecurityAlertSeverity, SecurityAlertType, SecurityFinding, SecurityAlert,
)

drift_result = DriftResult(
    total_desired=5, total_actual=5, total_drifted=1,
    drifts=[ResourceDrift(
        resource_type="aws_instance", resource_id="i-123", resource_name="web-1",
        drift_type=DriftType.MODIFIED, severity=DriftSeverity.HIGH,
    )],
)
compliance_report = ComplianceReport(total_checks=10, passed=8, failed=2)
cost_report = CostAnomalyReport(
    total_anomalies=1,
    anomalies=[CostAnomaly(
        anomaly_type=CostAnomalyType.SPIKE, severity=CostAnomalySeverity.MEDIUM,
        resource_id="i-123", resource_name="web-1", resource_type="aws_instance",
        description="Spike",
    )],
)
finding = SecurityFinding(
    alert_type=SecurityAlertType.OPEN_PORT, severity=SecurityAlertSeverity.HIGH,
    resource_id="i-123", resource_name="web-1", resource_type="aws_instance",
    description="Port 22 open",
)
security_report = SecurityAlertReport(
    total_alerts=1, open_alerts=1,
    alerts=[SecurityAlert(finding=finding)],
)

dashboard = IaCDashboard()
dashboard.set_drift_result(drift_result)
dashboard.set_compliance_report(compliance_report)
dashboard.set_cost_report(cost_report)
dashboard.set_security_report(security_report)
report = dashboard.build()
print(f"Overall status: {report.status.value}")
print(f"Panels: {len(report.panels)}")
for p in report.panels:
    print(f"  {p.name}: {p.status}")
