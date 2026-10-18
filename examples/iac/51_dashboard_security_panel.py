"""Example: Dashboard with security panel only.

Demonstrates building a dashboard with security alert results.
"""
from dcc.iac_observability.dashboard import IaCDashboard
from dcc.iac_observability.security_alerts import (
    SecurityAlertReport, SecurityAlertSeverity, SecurityAlertType, SecurityFinding, SecurityAlert,
)

finding = SecurityFinding(
    alert_type=SecurityAlertType.OPEN_PORT,
    severity=SecurityAlertSeverity.CRITICAL,
    resource_id="i-123",
    resource_name="web-1",
    resource_type="aws_instance",
    description="Port 22 open",
)
security_report = SecurityAlertReport(
    total_alerts=1,
    open_alerts=1,
    alerts=[SecurityAlert(finding=finding)],
    severity_counts={"critical": 1},
)

dashboard = IaCDashboard()
dashboard.set_security_report(security_report)
report = dashboard.build()
print(f"Status: {report.status.value}")
print(f"Panels: {len(report.panels)}")
for p in report.panels:
    print(f"  {p.name}: {p.status} - {p.summary}")
