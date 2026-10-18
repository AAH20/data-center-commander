"""Unit tests for dcc.iac_observability.security_alerts module."""
import unittest

from dcc.iac_observability.security_alerts import (
    SecurityAlert,
    SecurityAlertEngine,
    SecurityAlertReport,
    SecurityAlertSeverity,
    SecurityAlertType,
    SecurityFinding,
    evaluate_security,
    build_security_dashboard,
)


class TestSecurityAlertType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SecurityAlertType.OPEN_PORT.value, "open_port")
        self.assertEqual(SecurityAlertType.PUBLIC_EXPOSURE.value, "public_exposure")
        self.assertEqual(SecurityAlertType.WEAK_ENCRYPTION.value, "weak_encryption")
        self.assertEqual(SecurityAlertType.MISSING_MFA.value, "missing_mfa")
        self.assertEqual(SecurityAlertType.OVER_PRIVILEGED.value, "over_privileged")
        self.assertEqual(SecurityAlertType.SECRET_EXPOSURE.value, "secret_exposure")
        self.assertEqual(SecurityAlertType.MISSING_LOGGING.value, "missing_logging")
        self.assertEqual(SecurityAlertType.DEFAULT_SECURITY_GROUP.value, "default_security_group")
        self.assertEqual(SecurityAlertType.UNRESTRICTED_EGRESS.value, "unrestricted_egress")
        self.assertEqual(SecurityAlertType.OUTDATED_TLS.value, "outdated_tls")


class TestSecurityAlertSeverity(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SecurityAlertSeverity.INFO.value, "info")
        self.assertEqual(SecurityAlertSeverity.LOW.value, "low")
        self.assertEqual(SecurityAlertSeverity.MEDIUM.value, "medium")
        self.assertEqual(SecurityAlertSeverity.HIGH.value, "high")
        self.assertEqual(SecurityAlertSeverity.CRITICAL.value, "critical")


class TestSecurityFinding(unittest.TestCase):
    def test_creation(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.CRITICAL,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Port 22 open to world",
            remediation="Restrict to specific IPs",
        )
        self.assertEqual(f.resource_id, "i-123")
        self.assertTrue(f.to_dict())


class TestSecurityAlert(unittest.TestCase):
    def test_creation(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Test",
        )
        a = SecurityAlert(finding=f)
        self.assertEqual(a.status, "open")
        self.assertTrue(a.alert_id)

    def test_acknowledge(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Test",
        )
        a = SecurityAlert(finding=f)
        a.acknowledge("admin")
        self.assertEqual(a.status, "acknowledged")
        self.assertEqual(a.acknowledged_by, "admin")

    def test_resolve(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Test",
        )
        a = SecurityAlert(finding=f)
        a.resolve()
        self.assertEqual(a.status, "resolved")

    def test_dismiss(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Test",
        )
        a = SecurityAlert(finding=f)
        a.dismiss()
        self.assertEqual(a.status, "dismissed")


class TestSecurityAlertReport(unittest.TestCase):
    def test_empty(self):
        r = SecurityAlertReport()
        self.assertFalse(r.has_critical)
        self.assertEqual(r.critical_count, 0)

    def test_with_critical(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.CRITICAL,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Test",
        )
        a = SecurityAlert(finding=f)
        r = SecurityAlertReport(
            total_alerts=1,
            open_alerts=1,
            alerts=[a],
            severity_counts={"critical": 1},
        )
        self.assertTrue(r.has_critical)
        self.assertEqual(r.critical_count, 1)


class TestSecurityAlertEngine(unittest.TestCase):
    def test_no_findings(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_instance",
                "encrypted": True,
                "publicly_accessible": False,
                "logging_enabled": True,
                "mfa_enabled": True,
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        self.assertEqual(report.total_alerts, 0)

    def test_open_port_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_instance",
                "open_ports": [{"port": 22, "cidr": "0.0.0.0/0"}],
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        self.assertGreater(report.total_alerts, 0)
        port_found = any(
            a.finding.alert_type == SecurityAlertType.OPEN_PORT
            for a in report.alerts
        )
        self.assertTrue(port_found)

    def test_public_exposure_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_s3_bucket",
                "publicly_accessible": True,
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        exposure_found = any(
            a.finding.alert_type == SecurityAlertType.PUBLIC_EXPOSURE
            for a in report.alerts
        )
        self.assertTrue(exposure_found)

    def test_encryption_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_ebs_volume",
                "encrypted": False,
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        enc_found = any(
            a.finding.alert_type == SecurityAlertType.WEAK_ENCRYPTION
            for a in report.alerts
        )
        self.assertTrue(enc_found)

    def test_mfa_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_iam_user",
                "mfa_enabled": False,
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        mfa_found = any(
            a.finding.alert_type == SecurityAlertType.MISSING_MFA
            for a in report.alerts
        )
        self.assertTrue(mfa_found)

    def test_over_privileged_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_iam_role",
                "policy": '{"Effect": "Allow", "Action": "*", "Resource": "*"}',
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        priv_found = any(
            a.finding.alert_type == SecurityAlertType.OVER_PRIVILEGED
            for a in report.alerts
        )
        self.assertTrue(priv_found)

    def test_secret_exposure_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_instance",
                "user_data": "password=secret123",
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        secret_found = any(
            a.finding.alert_type == SecurityAlertType.SECRET_EXPOSURE
            for a in report.alerts
        )
        self.assertTrue(secret_found)

    def test_logging_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_s3_bucket",
                "logging_enabled": False,
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        log_found = any(
            a.finding.alert_type == SecurityAlertType.MISSING_LOGGING
            for a in report.alerts
        )
        self.assertTrue(log_found)

    def test_default_sg_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_instance",
                "security_group": "default",
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        sg_found = any(
            a.finding.alert_type == SecurityAlertType.DEFAULT_SECURITY_GROUP
            for a in report.alerts
        )
        self.assertTrue(sg_found)

    def test_unrestricted_egress_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_security_group",
                "egress_rules": [{"cidr": "0.0.0.0/0", "port": 0}],
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        egress_found = any(
            a.finding.alert_type == SecurityAlertType.UNRESTRICTED_EGRESS
            for a in report.alerts
        )
        self.assertTrue(egress_found)

    def test_outdated_tls_finding(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_lb",
                "tls_version": "TLSv1.0",
            },
        ]
        engine = SecurityAlertEngine()
        report = engine.evaluate(resources)
        tls_found = any(
            a.finding.alert_type == SecurityAlertType.OUTDATED_TLS
            for a in report.alerts
        )
        self.assertTrue(tls_found)

    def test_add_custom_check(self):
        def custom_check(resource):
            if resource.get("custom_flag"):
                return [SecurityFinding(
                    alert_type=SecurityAlertType.MISSING_LOGGING,
                    severity=SecurityAlertSeverity.LOW,
                    resource_id=resource.get("id", "unknown"),
                    resource_name=resource.get("name", "unknown"),
                    resource_type=resource.get("resource_type", "unknown"),
                    description="Custom finding",
                )]
            return []

        engine = SecurityAlertEngine()
        engine.add_check(custom_check)
        resources = [{"id": "r1", "custom_flag": True}]
        report = engine.evaluate(resources)
        self.assertGreater(report.total_alerts, 0)


class TestEvaluateSecurity(unittest.TestCase):
    def test_convenience_function(self):
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_instance",
                "open_ports": [{"port": 22, "cidr": "0.0.0.0/0"}],
            },
        ]
        report = evaluate_security(resources)
        self.assertIsInstance(report, SecurityAlertReport)
        self.assertGreater(report.total_alerts, 0)


class TestBuildSecurityDashboard(unittest.TestCase):
    def test_dashboard(self):
        f = SecurityFinding(
            alert_type=SecurityAlertType.OPEN_PORT,
            severity=SecurityAlertSeverity.CRITICAL,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Port 22 open",
            remediation="Restrict access",
        )
        a = SecurityAlert(finding=f)
        report = SecurityAlertReport(
            total_alerts=1,
            open_alerts=1,
            alerts=[a],
            severity_counts={"critical": 1},
        )
        dashboard = build_security_dashboard(report)
        self.assertIn("total_alerts", dashboard)
        self.assertIn("has_critical", dashboard)
        self.assertIn("top_alerts", dashboard)
        self.assertTrue(dashboard["has_critical"])


if __name__ == "__main__":
    unittest.main()
