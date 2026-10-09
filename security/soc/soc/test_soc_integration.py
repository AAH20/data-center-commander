# SOC Integration Tests — Data Center Commander
# Version: 1.0.0
# pytest tests for Trivy + OPA SOC integration

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from soc_integration import (
    AlertStatus,
    Misconfiguration,
    OpaEvaluator,
    PolicyEvaluation,
    RemediationAction,
    ScanResult,
    Secret,
    SecurityAlert,
    Severity,
    SocIntegration,
    TrivyScanner,
    Vulnerability,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_vulnerability():
    return Vulnerability(
        id="CVE-2026-12345",
        severity=Severity.CRITICAL,
        package="openssl",
        installed_version="1.1.1",
        fixed_version="1.1.2",
        title="Critical vulnerability in OpenSSL",
        description="A critical vulnerability was found in OpenSSL",
        cvss_score=9.8,
        references=["https://nvd.nist.gov/vuln/detail/CVE-2026-12345"]
    )


@pytest.fixture
def sample_scan_result(sample_vulnerability):
    return ScanResult(
        image="registry.data-center-commander.local/test:latest",
        artifact_type="container_image",
        vulnerabilities=[sample_vulnerability],
        misconfigurations=[],
        secrets=[],
        scan_time=datetime.utcnow()
    )


@pytest.fixture
def sample_misconfiguration():
    return Misconfiguration(
        id="DOCKER-001",
        severity=Severity.HIGH,
        title="Container runs as root",
        description="Container should not run as root",
        message="Container runs as root user",
        resolution="Set USER instruction in Dockerfile"
    )


@pytest.fixture
def sample_secret():
    return Secret(
        id="SECRET-001",
        severity=Severity.CRITICAL,
        category="AWS",
        title="AWS Access Key",
        match="AKIAIOSFODNN7EXAMPLE"
    )


@pytest.fixture
def trivy_scanner():
    return TrivyScanner(config_path="/test/trivy-config.yaml")


@pytest.fixture
def opa_evaluator():
    return OpaEvaluator(opa_url="http://localhost:8181")


@pytest.fixture
def soc_integration():
    return SocIntegration(config_path="/test/soc-integration.yaml")


# =============================================================================
# VULNERABILITY TESTS
# =============================================================================

class TestVulnerability:
    def test_vulnerability_creation(self, sample_vulnerability):
        assert sample_vulnerability.id == "CVE-2026-12345"
        assert sample_vulnerability.severity == Severity.CRITICAL
        assert sample_vulnerability.package == "openssl"
        assert sample_vulnerability.cvss_score == 9.8

    def test_vulnerability_severity_levels(self):
        for severity in Severity:
            vuln = Vulnerability(
                id="TEST-001",
                severity=severity,
                package="test",
                installed_version="1.0",
                fixed_version="1.1",
                title="Test",
                description="Test"
            )
            assert vuln.severity == severity


# =============================================================================
# SCAN RESULT TESTS
# =============================================================================

class TestScanResult:
    def test_scan_result_creation(self, sample_scan_result):
        assert sample_scan_result.image == "registry.data-center-commander.local/test:latest"
        assert sample_scan_result.total_count == 1
        assert sample_scan_result.critical_count == 1
        assert sample_scan_result.high_count == 0

    def test_scan_result_counts(self, sample_vulnerability):
        scan_result = ScanResult(
            image="test:latest",
            artifact_type="container_image",
            vulnerabilities=[
                sample_vulnerability,
                Vulnerability(
                    id="CVE-2026-00002",
                    severity=Severity.HIGH,
                    package="test",
                    installed_version="1.0",
                    fixed_version="1.1",
                    title="Test",
                    description="Test"
                ),
                Vulnerability(
                    id="CVE-2026-00003",
                    severity=Severity.MEDIUM,
                    package="test",
                    installed_version="1.0",
                    fixed_version="1.1",
                    title="Test",
                    description="Test"
                ),
            ]
        )

        assert scan_result.critical_count == 1
        assert scan_result.high_count == 1
        assert scan_result.medium_count == 1
        assert scan_result.low_count == 0
        assert scan_result.total_count == 3


# =============================================================================
# TRIVY SCANNER TESTS
# =============================================================================

class TestTrivyScanner:
    @patch("subprocess.run")
    def test_scan_image(self, mock_run, trivy_scanner):
        # Mock Trivy output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )

        # Create mock report file
        report_data = {
            "ArtifactName": "test:latest",
            "ArtifactType": "container_image",
            "Results": [
                {
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-12345",
                            "Severity": "CRITICAL",
                            "PkgName": "openssl",
                            "InstalledVersion": "1.1.1",
                            "FixedVersion": "1.1.2",
                            "Title": "Test",
                            "Description": "Test"
                        }
                    ]
                }
            ]
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value=report_data):
                    result = trivy_scanner.scan_image("test:latest")
                    assert result.image == "test:latest"
                    assert result.total_count == 1

    def test_parse_report(self, trivy_scanner, tmp_path):
        report_data = {
            "ArtifactName": "test:latest",
            "ArtifactType": "container_image",
            "Results": [
                {
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-12345",
                            "Severity": "CRITICAL",
                            "PkgName": "openssl",
                            "InstalledVersion": "1.1.1",
                            "FixedVersion": "1.1.2",
                            "Title": "Test",
                            "Description": "Test"
                        }
                    ],
                    "Misconfigurations": [
                        {
                            "ID": "DOCKER-001",
                            "Severity": "HIGH",
                            "Title": "Test",
                            "Description": "Test",
                            "Message": "Test",
                            "Resolution": "Test"
                        }
                    ],
                    "Secrets": [
                        {
                            "RuleID": "SECRET-001",
                            "Severity": "CRITICAL",
                            "Category": "AWS",
                            "Title": "Test",
                            "Match": "AKIAIOSFODNN7EXAMPLE"
                        }
                    ]
                }
            ]
        }

        report_file = tmp_path / "report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        result = trivy_scanner._parse_report(report_file, "test:latest")

        assert result.image == "test:latest"
        assert result.total_count == 1
        assert result.critical_count == 1
        assert len(result.misconfigurations) == 1
        assert len(result.secrets) == 1


# =============================================================================
# OPA EVALUATOR TESTS
# =============================================================================

class TestOpaEvaluator:
    @patch("requests.post")
    def test_evaluate_container_security_allowed(self, mock_post, opa_evaluator, sample_scan_result):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "result": {
                    "allow": True,
                    "violations": []
                }
            }
        )

        result = opa_evaluator.evaluate_container_security(sample_scan_result)

        assert result.allowed is True
        assert len(result.violations) == 0

    @patch("requests.post")
    def test_evaluate_container_security_denied(self, mock_post, opa_evaluator, sample_scan_result):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "result": {
                    "allow": False,
                    "violations": ["CRITICAL: Image has 1 critical vulnerabilities"]
                }
            }
        )

        result = opa_evaluator.evaluate_container_security(sample_scan_result)

        assert result.allowed is False
        assert len(result.violations) == 1

    @patch("requests.post")
    def test_evaluate_container_security_timeout(self, mock_post, opa_evaluator, sample_scan_result):
        mock_post.side_effect = requests.exceptions.Timeout()

        result = opa_evaluator.evaluate_container_security(sample_scan_result)

        assert result.allowed is False
        assert "OPA evaluation failed" in result.violations[0]


# =============================================================================
# SOC INTEGRATION TESTS
# =============================================================================

class TestSocIntegration:
    def test_process_scan_result_allowed(self, soc_integration, sample_scan_result):
        with patch.object(OpaEvaluator, "evaluate_container_security") as mock_eval:
            mock_eval.return_value = PolicyEvaluation(
                allowed=True,
                violations=[],
                policy="container-security"
            )

            alert = soc_integration.process_scan_result(sample_scan_result)

            assert alert is None

    def test_process_scan_result_denied(self, soc_integration, sample_scan_result):
        with patch.object(OpaEvaluator, "evaluate_container_security") as mock_eval:
            mock_eval.return_value = PolicyEvaluation(
                allowed=False,
                violations=["CRITICAL: Image has 1 critical vulnerabilities"],
                policy="container-security"
            )

            with patch.object(SocIntegration, "_route_alert"):
                alert = soc_integration.process_scan_result(sample_scan_result)

                assert alert is not None
                assert alert.severity == Severity.CRITICAL
                assert alert.source == "trivy"

    def test_route_alert_slack(self, soc_integration):
        alert = SecurityAlert(
            id="test-alert",
            severity=Severity.HIGH,
            title="Test Alert",
            description="Test Description",
            source="test"
        )

        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            with patch("requests.post") as mock_post:
                soc_integration._send_slack_notification(alert)
                mock_post.assert_called_once()

    def test_route_alert_pagerduty(self, soc_integration):
        alert = SecurityAlert(
            id="test-alert",
            severity=Severity.CRITICAL,
            title="Test Alert",
            description="Test Description",
            source="test"
        )

        with patch.dict(os.environ, {"PAGERDUTY_KEY": "test-key"}):
            with patch("requests.post") as mock_post:
                soc_integration._send_pagerduty_notification(alert)
                mock_post.assert_called_once()

    def test_auto_remediate_critical(self, soc_integration):
        alert = SecurityAlert(
            id="test-alert",
            severity=Severity.CRITICAL,
            title="Test Alert",
            description="Test Description",
            source="test",
            metadata={"image": "test:latest"}
        )

        with patch.object(SocIntegration, "_quarantine_pod", return_value=True):
            result = soc_integration.auto_remediate(alert)

            assert result is True
            assert alert.remediation_action == RemediationAction.QUARANTINE

    def test_auto_remediate_high(self, soc_integration):
        alert = SecurityAlert(
            id="test-alert",
            severity=Severity.HIGH,
            title="Test Alert",
            description="Test Description",
            source="test",
            metadata={"image": "test:latest"}
        )

        with patch.object(SocIntegration, "_scale_down_deployment", return_value=True):
            result = soc_integration.auto_remediate(alert)

            assert result is True
            assert alert.remediation_action == RemediationAction.SCALE_DOWN


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    @patch("subprocess.run")
    @patch("requests.post")
    def test_full_scan_workflow(self, mock_post, mock_run, tmp_path):
        # Mock Trivy scan
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Create mock report
        report_data = {
            "ArtifactName": "test:latest",
            "ArtifactType": "container_image",
            "Results": [
                {
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-12345",
                            "Severity": "CRITICAL",
                            "PkgName": "openssl",
                            "InstalledVersion": "1.1.1",
                            "FixedVersion": "1.1.2",
                            "Title": "Test",
                            "Description": "Test"
                        }
                    ]
                }
            ]
        }

        report_file = tmp_path / "report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        # Mock OPA response
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "result": {
                    "allow": False,
                    "violations": ["CRITICAL: Image has 1 critical vulnerabilities"]
                }
            }
        )

        # Run workflow
        scanner = TrivyScanner()
        scan_result = scanner._parse_report(report_file, "test:latest")

        evaluator = OpaEvaluator()
        evaluation = evaluator.evaluate_container_security(scan_result)

        assert scan_result.critical_count == 1
        assert evaluation.allowed is False
        assert len(evaluation.violations) == 1


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
