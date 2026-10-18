"""Example: Dashboard with degraded overall status.

Demonstrates degraded status when there are non-critical issues.
"""
from dcc.iac_observability.dashboard import IaCDashboard, DashboardStatus
from dcc.iac_observability.compliance import ComplianceReport

compliance_report = ComplianceReport(
    total_checks=10, passed=7, failed=3,
    severity_summary={"medium": 3},
)

dashboard = IaCDashboard()
dashboard.set_compliance_report(compliance_report)
report = dashboard.build()
print(f"Overall status: {report.status.value}")
assert report.status == DashboardStatus.DEGRADED
