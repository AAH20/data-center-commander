"""Example: Empty dashboard.

Demonstrates building a dashboard with no data.
"""
from dcc.iac_observability.dashboard import IaCDashboard

dashboard = IaCDashboard()
report = dashboard.build()
print(f"Status: {report.status.value}")
print(f"Panels: {len(report.panels)}")
