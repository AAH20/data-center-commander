"""Unit tests for dcc.iac_observability.dashboard module."""
import unittest

from dcc.iac_observability.dashboard import (
    DashboardPanel,
    DashboardReport,
    DashboardStatus,
    IaCDashboard,
    build_dashboard,
)
from dcc.iac_observability.drift import DriftResult, DriftSeverity, DriftType, ResourceDrift
from dcc.iac_observability.compliance import ComplianceReport, ComplianceStatus, ComplianceSeverity
from dcc.iac_observability.cost_anomaly import CostAnomalyReport, CostAnomalySeverity, CostAnomalyType, CostAnomaly
from dcc.iac_observability.security_alerts import SecurityAlertReport, SecurityAlertSeverity, SecurityAlertType, SecurityFinding, SecurityAlert


class TestDashboardStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DashboardStatus.HEALTHY.value, "healthy")
        self.assertEqual(DashboardStatus.DEGRADED.value, "degraded")
        self.assertEqual(DashboardStatus.UNHEALTHY.value, "unhealthy")
        self.assertEqual(DashboardStatus.CRITICAL.value, "critical")


class TestDashboardPanel(unittest.TestCase):
    def test_creation(self):
        p = DashboardPanel(
            name="test",
            title="Test Panel",
            status="healthy",
            summary={"key": "value"},
        )
        self.assertEqual(p.name, "test")
        self.assertTrue(p.to_dict())


class TestDashboardReport(unittest.TestCase):
    def test_creation(self):
        r = DashboardReport(status=DashboardStatus.HEALTHY)
        self.assertEqual(r.status, DashboardStatus.HEALTHY)
        self.assertTrue(r.to_dict())


class TestIaCDashboard(unittest.TestCase):
    def test_empty_dashboard(self):
        dashboard = IaCDashboard()
        report = dashboard.build()
        self.assertEqual(report.status, DashboardStatus.HEALTHY)
        self.assertEqual(len(report.panels), 0)

    def test_drift_panel(self):
        d = ResourceDrift(
            resource_type="aws_instance",
            resource_id="i-123",
            resource_name="web-1",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.HIGH,
        )
        drift_result = DriftResult(
            total_desired=5,
            total_actual=5,
            total_drifted=1,
            drifts=[d],
            severity_counts={"high": 1},
        )
        dashboard = IaCDashboard()
        dashboard.set_drift_result(drift_result)
        report = dashboard.build()
        self.assertEqual(len(report.panels), 1)
        self.assertEqual(report.panels[0].name, "drift")

    def test_compliance_panel(self):
        compliance_report = ComplianceReport(
            total_checks=10,
            passed=8,
            failed=2,
            severity_summary={"high": 2},
        )
        dashboard = IaCDashboard()
        dashboard.set_compliance_report(compliance_report)
        report = dashboard.build()
        self.assertEqual(len(report.panels), 1)
        self.assertEqual(report.panels[0].name, "compliance")

    def test_cost_panel(self):
        a = CostAnomaly(
            anomaly_type=CostAnomalyType.SPIKE,
            severity=CostAnomalySeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Spike",
        )
        cost_report = CostAnomalyReport(
            total_anomalies=1,
            anomalies=[a],
            severity_counts={"high": 1},
        )
        dashboard = IaCDashboard()
        dashboard.set_cost_report(cost_report)
        report = dashboard.build()
        self.assertEqual(len(report.panels), 1)
        self.assertEqual(report.panels[0].name, "cost")

    def test_security_panel(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.CRITICAL,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Port 22 open",
        )
        a = SecurityAlert(finding=f)
        security_report = SecurityAlertReport(
            total_alerts=1,
            open_alerts=1,
            alerts=[a],
            severity_counts={"critical": 1},
        )
        dashboard = IaCDashboard()
        dashboard.set_security_report(security_report)
        report = dashboard.build()
        self.assertEqual(len(report.panels), 1)
        self.assertEqual(report.panels[0].name, "security")

    def test_all_panels(self):
        d = ResourceDrift(
            resource_type="aws_instance",
            resource_id="i-123",
            resource_name="web-1",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.HIGH,
        )
        drift_result = DriftResult(
            total_desired=5,
            total_actual=5,
            total_drifted=1,
            drifts=[d],
        )
        compliance_report = ComplianceReport(
            total_checks=10,
            passed=8,
            failed=2,
        )
        a = CostAnomaly(
            anomaly_type=CostAnomalyType.SPIKE,
            severity=CostAnomalySeverity.MEDIUM,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Spike",
        )
        cost_report = CostAnomalyReport(
            total_anomalies=1,
            anomalies=[a],
        )
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Port 22 open",
        )
        sec_alert = SecurityAlert(finding=f)
        security_report = SecurityAlertReport(
            total_alerts=1,
            open_alerts=1,
            alerts=[sec_alert],
        )

        dashboard = IaCDashboard()
        dashboard.set_drift_result(drift_result)
        dashboard.set_compliance_report(compliance_report)
        dashboard.set_cost_report(cost_report)
        dashboard.set_security_report(security_report)
        report = dashboard.build()
        self.assertEqual(len(report.panels), 4)

    def test_overall_status_critical(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.CRITICAL,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Port 22 open",
        )
        a = SecurityAlert(finding=f)
        security_report = SecurityAlertReport(
            total_alerts=1,
            open_alerts=1,
            alerts=[a],
            severity_counts={"critical": 1},
        )
        dashboard = IaCDashboard()
        dashboard.set_security_report(security_report)
        report = dashboard.build()
        self.assertEqual(report.status, DashboardStatus.CRITICAL)

    def test_overall_status_healthy(self):
        compliance_report = ComplianceReport(
            total_checks=10,
            passed=10,
            failed=0,
        )
        dashboard = IaCDashboard()
        dashboard.set_compliance_report(compliance_report)
        report = dashboard.build()
        self.assertEqual(report.status, DashboardStatus.HEALTHY)


class TestBuildDashboard(unittest.TestCase):
    def test_convenience_function_empty(self):
        report = build_dashboard()
        self.assertIsInstance(report, DashboardReport)
        self.assertEqual(report.status, DashboardStatus.HEALTHY)

    def test_convenience_function_with_data(self):
        d = ResourceDrift(
            resource_type="aws_instance",
            resource_id="i-123",
            resource_name="web-1",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.LOW,
        )
        drift_result = DriftResult(
            total_desired=5,
            total_actual=5,
            total_drifted=1,
            drifts=[d],
        )
        report = build_dashboard(drift_result=drift_result)
        self.assertEqual(len(report.panels), 1)


if __name__ == "__main__":
    unittest.main()
