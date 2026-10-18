"""Example: Dashboard with compliance panel only.

Demonstrates building a dashboard with compliance results.
"""
from dcc.iac_observability.dashboard import IaCDashboard
from dcc.iac_observability.compliance import ComplianceReport

compliance_report = ComplianceReport(
    total_checks=10,
    passed=8,
    failed=2,
    severity_summary={"high": 2},
)

dashboard = IaCDashboard()
dashboard.set_compliance_report(compliance_report)
report = dashboard.build()
print(f"Status: {report.status.value}")
print(f"Panels: {len(report.panels)}")
for p in report.panels:
    print(f"  {p.name}: {p.status} - {p.summary}")
