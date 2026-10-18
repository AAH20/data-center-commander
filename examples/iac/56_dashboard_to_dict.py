"""Example: Dashboard report serialization.

Demonstrates converting dashboard report to dictionary.
"""
from dcc.iac_observability.dashboard import IaCDashboard
from dcc.iac_observability.compliance import ComplianceReport

compliance_report = ComplianceReport(total_checks=10, passed=8, failed=2)

dashboard = IaCDashboard()
dashboard.set_compliance_report(compliance_report)
report = dashboard.build()
d = report.to_dict()
print(f"Status: {d['status']}")
print(f"Generated at: {d['generated_at']}")
print(f"Metadata: {d['metadata']}")
print(f"Panels: {len(d['panels'])}"))
for p in d['panels']:
    print(f"  {p['name']}: {p['status']}")
