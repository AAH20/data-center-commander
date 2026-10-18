"""Example: Dashboard with drift panel only.

Demonstrates building a dashboard with drift detection results.
"""
from dcc.iac_observability.dashboard import IaCDashboard
from dcc.iac_observability.drift import DriftResult, DriftSeverity, DriftType, ResourceDrift

drift_result = DriftResult(
    total_desired=5,
    total_actual=5,
    total_drifted=1,
    drifts=[ResourceDrift(
        resource_type="aws_instance",
        resource_id="i-123",
        resource_name="web-1",
        drift_type=DriftType.MODIFIED,
        severity=DriftSeverity.HIGH,
    )],
    severity_counts={"high": 1},
)

dashboard = IaCDashboard()
dashboard.set_drift_result(drift_result)
report = dashboard.build()
print(f"Status: {report.status.value}")
print(f"Panels: {len(report.panels)}")
for p in report.panels:
    print(f"  {p.name}: {p.status} - {p.summary}")
