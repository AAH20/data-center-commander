"""Example: Dashboard with healthy overall status.

Demonstrates a healthy dashboard when all checks pass.
"""
from dcc.iac_observability.dashboard import IaCDashboard, DashboardStatus
from dcc.iac_observability.compliance import ComplianceReport

compliance_report = ComplianceReport(total_checks=10, passed=10, failed=0)

dashboard = IaCDashboard()
dashboard.set_compliance_report(compliance_report)
report = dashboard.build()
print(f"Overall status: {report.status.value}")
assert report.status == DashboardStatus.HEALTHY
