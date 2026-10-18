"""Example: Dashboard with cost panel only.

Demonstrates building a dashboard with cost anomaly results.
"""
from dcc.iac_observability.dashboard import IaCDashboard
from dcc.iac_observability.cost_anomaly import CostAnomalyReport, CostAnomalySeverity, CostAnomalyType, CostAnomaly

cost_report = CostAnomalyReport(
    total_anomalies=1,
    anomalies=[CostAnomaly(
        anomaly_type=CostAnomalyType.SPIKE,
        severity=CostAnomalySeverity.HIGH,
        resource_id="i-123",
        resource_name="web-1",
        resource_type="aws_instance",
        description="Spike detected",
    )],
    severity_counts={"high": 1},
)

dashboard = IaCDashboard()
dashboard.set_cost_report(cost_report)
report = dashboard.build()
print(f"Status: {report.status.value}")
print(f"Panels: {len(report.panels)}")
for p in report.panels:
    print(f"  {p.name}: {p.status} - {p.summary}")
