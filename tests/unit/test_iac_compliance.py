"""Unit tests for dcc.iac_observability.compliance module."""
import unittest

from dcc.iac_observability.compliance import (
    ComplianceCheck,
    ComplianceEngine,
    ComplianceReport,
    ComplianceResult,
    ComplianceSeverity,
    ComplianceStatus,
    evaluate_compliance,
    build_compliance_dashboard,
    get_default_checks,
)


class TestComplianceStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ComplianceStatus.PASS.value, "pass")
        self.assertEqual(ComplianceStatus.FAIL.value, "fail")
        self.assertEqual(ComplianceStatus.WARNING.value, "warning")
        self.assertEqual(ComplianceStatus.NOT_APPLICABLE.value, "not_applicable")
        self.assertEqual(ComplianceStatus.UNKNOWN.value, "unknown")


class TestComplianceSeverity(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ComplianceSeverity.INFO.value, "info")
        self.assertEqual(ComplianceSeverity.LOW.value, "low")
        self.assertEqual(ComplianceSeverity.MEDIUM.value, "medium")
        self.assertEqual(ComplianceSeverity.HIGH.value, "high")
        self.assertEqual(ComplianceSeverity.CRITICAL.value, "critical")


class TestComplianceCheck(unittest.TestCase):
    def test_attribute_eq_pass(self):
        check = ComplianceCheck(
            check_id="test-1",
            name="Test Check",
            description="A test check",
            severity=ComplianceSeverity.HIGH,
            category="security",
            attribute="encrypted",
            expected_value=True,
            operator="eq",
        )
        result = check.evaluate({"id": "r1", "encrypted": True})
        self.assertEqual(result.status, ComplianceStatus.PASS)

    def test_attribute_eq_fail(self):
        check = ComplianceCheck(
            check_id="test-1",
            name="Test Check",
            description="A test check",
            severity=ComplianceSeverity.HIGH,
            category="security",
            attribute="encrypted",
            expected_value=True,
            operator="eq",
        )
        result = check.evaluate({"id": "r1", "encrypted": False})
        self.assertEqual(result.status, ComplianceStatus.FAIL)

    def test_attribute_exists(self):
        check = ComplianceCheck(
            check_id="test-2",
            name="Exists Check",
            description="Check attribute exists",
            severity=ComplianceSeverity.LOW,
            category="tagging",
            attribute="tags",
            operator="exists",
        )
        result = check.evaluate({"id": "r1", "tags": {"env": "prod"}})
        self.assertEqual(result.status, ComplianceStatus.PASS)

    def test_attribute_not_exists(self):
        check = ComplianceCheck(
            check_id="test-3",
            name="Not Exists Check",
            description="Check attribute does not exist",
            severity=ComplianceSeverity.LOW,
            category="tagging",
            attribute="tags",
            operator="not_exists",
        )
        result = check.evaluate({"id": "r1"})
        self.assertEqual(result.status, ComplianceStatus.PASS)

    def test_attribute_contains(self):
        check = ComplianceCheck(
            check_id="test-4",
            name="Contains Check",
            description="Check attribute contains value",
            severity=ComplianceSeverity.MEDIUM,
            category="security",
            attribute="name",
            expected_value="prod",
            operator="contains",
        )
        result = check.evaluate({"id": "r1", "name": "prod-server-1"})
        self.assertEqual(result.status, ComplianceStatus.PASS)

    def test_attribute_regex(self):
        check = ComplianceCheck(
            check_id="test-5",
            name="Regex Check",
            description="Check attribute matches regex",
            severity=ComplianceSeverity.MEDIUM,
            category="security",
            attribute="name",
            expected_value=r"^prod-.*",
            operator="regex",
        )
        result = check.evaluate({"id": "r1", "name": "prod-server-1"})
        self.assertEqual(result.status, ComplianceStatus.PASS)

    def test_evaluator_function(self):
        def check_func(resource):
            return resource.get("encrypted", False), "Custom check"

        check = ComplianceCheck(
            check_id="test-6",
            name="Custom Check",
            description="Custom evaluator",
            severity=ComplianceSeverity.HIGH,
            category="security",
            evaluator=check_func,
        )
        result = check.evaluate({"id": "r1", "encrypted": True})
        self.assertEqual(result.status, ComplianceStatus.PASS)
        self.assertEqual(result.detail, "Custom check")

    def test_evaluator_exception(self):
        def bad_func(resource):
            raise ValueError("bad")

        check = ComplianceCheck(
            check_id="test-7",
            name="Bad Check",
            description="Bad evaluator",
            severity=ComplianceSeverity.HIGH,
            category="security",
            evaluator=bad_func,
        )
        result = check.evaluate({"id": "r1"})
        self.assertEqual(result.status, ComplianceStatus.UNKNOWN)


class TestComplianceResult(unittest.TestCase):
    def test_to_dict(self):
        r = ComplianceResult(
            check_id="test-1",
            name="Test",
            status=ComplianceStatus.PASS,
            severity=ComplianceSeverity.HIGH,
            category="security",
            detail="All good",
            resource_id="r1",
            resource_type="aws_instance",
        )
        d = r.to_dict()
        self.assertEqual(d["check_id"], "test-1")
        self.assertEqual(d["status"], "pass")


class TestComplianceEngine(unittest.TestCase):
    def test_evaluate_all_pass(self):
        checks = [
            ComplianceCheck(
                check_id="c1",
                name="Check 1",
                description="Test",
                severity=ComplianceSeverity.HIGH,
                category="security",
                attribute="encrypted",
                expected_value=True,
                operator="eq",
            ),
        ]
        resources = [
            {"id": "r1", "encrypted": True},
            {"id": "r2", "encrypted": True},
        ]
        engine = ComplianceEngine(checks)
        report = engine.evaluate(resources)
        self.assertEqual(report.total_checks, 2)
        self.assertEqual(report.passed, 2)
        self.assertEqual(report.failed, 0)

    def test_evaluate_mixed(self):
        checks = [
            ComplianceCheck(
                check_id="c1",
                name="Check 1",
                description="Test",
                severity=ComplianceSeverity.HIGH,
                category="security",
                attribute="encrypted",
                expected_value=True,
                operator="eq",
            ),
        ]
        resources = [
            {"id": "r1", "encrypted": True},
            {"id": "r2", "encrypted": False},
        ]
        engine = ComplianceEngine(checks)
        report = engine.evaluate(resources)
        self.assertEqual(report.passed, 1)
        self.assertEqual(report.failed, 1)

    def test_compliance_rate(self):
        checks = [
            ComplianceCheck(
                check_id="c1",
                name="Check 1",
                description="Test",
                severity=ComplianceSeverity.HIGH,
                category="security",
                attribute="encrypted",
                expected_value=True,
                operator="eq",
            ),
        ]
        resources = [
            {"id": "r1", "encrypted": True},
            {"id": "r2", "encrypted": False},
            {"id": "r3", "encrypted": False},
            {"id": "r4", "encrypted": False},
        ]
        engine = ComplianceEngine(checks)
        report = engine.evaluate(resources)
        self.assertAlmostEqual(report.compliance_rate, 0.25)

    def test_add_check(self):
        engine = ComplianceEngine()
        engine.add_check(ComplianceCheck(
            check_id="c1",
            name="Check 1",
            description="Test",
            severity=ComplianceSeverity.LOW,
            category="tagging",
            attribute="tags",
            operator="exists",
        ))
        self.assertEqual(len(engine.checks), 1)


class TestComplianceReport(unittest.TestCase):
    def test_overall_status_pass(self):
        report = ComplianceReport(
            total_checks=2,
            passed=2,
            failed=0,
        )
        self.assertEqual(report.overall_status, ComplianceStatus.PASS)

    def test_overall_status_fail(self):
        report = ComplianceReport(
            total_checks=2,
            passed=1,
            failed=1,
        )
        self.assertEqual(report.overall_status, ComplianceStatus.FAIL)

    def test_to_dict(self):
        report = ComplianceReport(
            total_checks=10,
            passed=8,
            failed=2,
        )
        d = report.to_dict()
        self.assertEqual(d["total_checks"], 10)
        self.assertEqual(d["compliance_rate"], 0.8)


class TestEvaluateCompliance(unittest.TestCase):
    def test_convenience_function(self):
        checks = [
            ComplianceCheck(
                check_id="c1",
                name="Check 1",
                description="Test",
                severity=ComplianceSeverity.HIGH,
                category="security",
                attribute="encrypted",
                expected_value=True,
                operator="eq",
            ),
        ]
        resources = [{"id": "r1", "encrypted": True}]
        report = evaluate_compliance(resources, checks)
        self.assertIsInstance(report, ComplianceReport)
        self.assertEqual(report.passed, 1)


class TestBuildComplianceDashboard(unittest.TestCase):
    def test_dashboard(self):
        report = ComplianceReport(
            total_checks=10,
            passed=7,
            failed=2,
            warnings=1,
            category_summary={"security": {"pass": 5, "fail": 2}},
            severity_summary={"high": 2, "medium": 1},
        )
        dashboard = build_compliance_dashboard(report)
        self.assertIn("compliance_rate", dashboard)
        self.assertIn("overall_status", dashboard)
        self.assertIn("by_category", dashboard)
        self.assertIn("top_failures", dashboard)


class TestGetDefaultChecks(unittest.TestCase):
    def test_default_checks(self):
        checks = get_default_checks()
        self.assertGreater(len(checks), 0)
        check_ids = [c.check_id for c in checks]
        self.assertIn("CIS-1.1", check_ids)
        self.assertIn("CIS-1.2", check_ids)
        self.assertIn("ORG-1.1", check_ids)

    def test_default_checks_evaluate(self):
        checks = get_default_checks()
        resources = [
            {
                "id": "r1",
                "resource_type": "aws_s3_bucket",
                "encrypted": True,
                "publicly_accessible": False,
                "tags": {"environment": "prod", "cost_center": "cc1", "owner": "team-a"},
                "logging_enabled": True,
                "versioning_enabled": True,
            },
        ]
        engine = ComplianceEngine(checks)
        report = engine.evaluate(resources)
        self.assertGreater(report.total_checks, 0)


if __name__ == "__main__":
    unittest.main()
