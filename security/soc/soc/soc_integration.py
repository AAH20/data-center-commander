# SOC Integration Module — Data Center Commander
# Version: 2.0.0
# Python module for Trivy + OPA integration with SOC

"""
SOC Integration Module for Data Center Commander

This module provides integration between Trivy container security scanner,
OPA policy engine, and the Security Operations Center (SOC).

Features:
- Trivy scan result parsing and evaluation
- OPA policy evaluation
- Alert generation and routing
- Auto-remediation
- Compliance reporting
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import requests
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dcc-soc")


# =============================================================================
# ENUMS
# =============================================================================


class Severity(Enum):
    """Security alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(Enum):
    """Alert status."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RemediationAction(Enum):
    """Auto-remediation actions."""

    ROLLBACK = "rollback"
    RESCHEDULE = "reschedule"
    PATCH = "patch"
    QUARANTINE = "quarantine"
    SCALE_DOWN = "scale_down"
    NONE = "none"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Vulnerability:
    """Represents a security vulnerability."""

    id: str
    severity: Severity
    package: str
    installed_version: str
    fixed_version: str | None
    title: str
    description: str
    cvss_score: float | None = None
    references: list[str] = field(default_factory=list)


@dataclass
class Misconfiguration:
    """Represents a security misconfiguration."""

    id: str
    severity: Severity
    title: str
    description: str
    message: str
    resolution: str


@dataclass
class Secret:
    """Represents a detected secret."""

    id: str
    severity: Severity
    category: str
    title: str
    match: str


@dataclass
class ScanResult:
    """Represents a Trivy scan result."""

    image: str
    artifact_type: str
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    misconfigurations: list[Misconfiguration] = field(default_factory=list)
    secrets: list[Secret] = field(default_factory=list)
    scan_time: datetime = field(default_factory=datetime.utcnow)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.LOW)

    @property
    def total_count(self) -> int:
        return len(self.vulnerabilities)


@dataclass
class PolicyEvaluation:
    """Represents an OPA policy evaluation result."""

    allowed: bool
    violations: list[str] = field(default_factory=list)
    policy: str = ""
    evaluation_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SecurityAlert:
    """Represents a security alert."""

    id: str
    severity: Severity
    title: str
    description: str
    source: str
    status: AlertStatus = AlertStatus.NEW
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    assigned_to: str | None = None
    remediation_action: RemediationAction | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# TRIVY SCANNER
# =============================================================================


class TrivyScanner:
    """Trivy container security scanner integration."""

    def __init__(self, config_path: str = "/etc/trivy/trivy-config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.report_dir = Path("/var/log/trivy")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> dict[str, Any]:
        """Load Trivy configuration."""
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            return {}

    def scan_image(self, image: str, scan_type: str = "full") -> ScanResult:
        """Scan a container image with Trivy."""
        logger.info(f"Starting Trivy scan for image: {image}")

        report_file = self.report_dir / f"trivy-report-{int(time.time())}.json"

        cmd = [
            "trivy",
            "image",
            "--severity",
            "CRITICAL,HIGH,MEDIUM,LOW",
            "--scanners",
            "vuln,secret,config,license",
            "--format",
            "json",
            "--output",
            str(report_file),
            "--timeout",
            "10m",
            "--cache-dir",
            "/tmp/trivy-cache",
            image,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                logger.error(f"Trivy scan failed: {result.stderr}")
                raise Exception(f"Trivy scan failed: {result.stderr}")

            return self._parse_report(report_file, image)

        except subprocess.TimeoutExpired:
            logger.error("Trivy scan timed out")
            raise
        except FileNotFoundError:
            logger.error("Trivy not found. Please install Trivy.")
            raise

    def scan_kubernetes(self, namespace: str = "data-center-commander") -> list[ScanResult]:
        """Scan Kubernetes cluster with Trivy."""
        logger.info(f"Starting Trivy Kubernetes scan for namespace: {namespace}")

        report_file = self.report_dir / f"trivy-k8s-report-{int(time.time())}.json"

        cmd = [
            "trivy",
            "k8s",
            "--severity",
            "CRITICAL,HIGH,MEDIUM,LOW",
            "--scanners",
            "vuln,secret,config",
            "--format",
            "json",
            "--output",
            str(report_file),
            "--timeout",
            "10m",
            "--cache-dir",
            "/tmp/trivy-cache",
            "--namespace",
            namespace,
            "--report",
            "summary",
            "cluster",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                logger.error(f"Trivy K8s scan failed: {result.stderr}")
                raise Exception(f"Trivy K8s scan failed: {result.stderr}")

            return self._parse_k8s_report(report_file)

        except subprocess.TimeoutExpired:
            logger.error("Trivy K8s scan timed out")
            raise

    def _parse_report(self, report_file: Path, image: str) -> ScanResult:
        """Parse Trivy JSON report."""
        with open(report_file) as f:
            data = json.load(f)

        scan_result = ScanResult(
            image=image, artifact_type=data.get("ArtifactType", "container_image")
        )

        for result in data.get("Results", []):
            # Parse vulnerabilities
            for vuln in result.get("Vulnerabilities", []):
                severity = Severity(vuln.get("Severity", "LOW").lower())
                scan_result.vulnerabilities.append(
                    Vulnerability(
                        id=vuln.get("VulnerabilityID", ""),
                        severity=severity,
                        package=vuln.get("PkgName", ""),
                        installed_version=vuln.get("InstalledVersion", ""),
                        fixed_version=vuln.get("FixedVersion"),
                        title=vuln.get("Title", ""),
                        description=vuln.get("Description", ""),
                        cvss_score=vuln.get("CVSS", {}).get("nvd", {}).get("V3Score"),
                        references=vuln.get("References", []),
                    )
                )

            # Parse misconfigurations
            for misconfig in result.get("Misconfigurations", []):
                severity = Severity(misconfig.get("Severity", "LOW").lower())
                scan_result.misconfigurations.append(
                    Misconfiguration(
                        id=misconfig.get("ID", ""),
                        severity=severity,
                        title=misconfig.get("Title", ""),
                        description=misconfig.get("Description", ""),
                        message=misconfig.get("Message", ""),
                        resolution=misconfig.get("Resolution", ""),
                    )
                )

            # Parse secrets
            for secret in result.get("Secrets", []):
                severity = Severity(secret.get("Severity", "LOW").lower())
                scan_result.secrets.append(
                    Secret(
                        id=secret.get("RuleID", ""),
                        severity=severity,
                        category=secret.get("Category", ""),
                        title=secret.get("Title", ""),
                        match=secret.get("Match", ""),
                    )
                )

        logger.info(
            f"Parsed scan result: {scan_result.total_count} vulnerabilities, "
            f"{len(scan_result.misconfigurations)} misconfigurations, "
            f"{len(scan_result.secrets)} secrets"
        )

        return scan_result

    def _parse_k8s_report(self, report_file: Path) -> list[ScanResult]:
        """Parse Trivy Kubernetes JSON report."""
        with open(report_file) as f:
            data = json.load(f)

        results = []
        for result in data.get("Results", []):
            scan_result = ScanResult(
                image=result.get("Target", "unknown"), artifact_type="kubernetes"
            )

            for vuln in result.get("Vulnerabilities", []):
                severity = Severity(vuln.get("Severity", "LOW").lower())
                scan_result.vulnerabilities.append(
                    Vulnerability(
                        id=vuln.get("VulnerabilityID", ""),
                        severity=severity,
                        package=vuln.get("PkgName", ""),
                        installed_version=vuln.get("InstalledVersion", ""),
                        fixed_version=vuln.get("FixedVersion"),
                        title=vuln.get("Title", ""),
                        description=vuln.get("Description", ""),
                    )
                )

            results.append(scan_result)

        return results


# =============================================================================
# OPA POLICY EVALUATOR
# =============================================================================


class OpaEvaluator:
    """OPA policy evaluation integration."""

    def __init__(self, opa_url: str = "http://opa.opa.svc.cluster.local:8181"):
        self.opa_url = opa_url
        self.timeout = 30

    def evaluate_container_security(self, scan_result: ScanResult) -> PolicyEvaluation:
        """Evaluate container security policy."""
        logger.info("Evaluating container security policy...")

        input_data = {
            "image": scan_result.image,
            "vulnerabilities": {
                "critical": scan_result.critical_count,
                "high": scan_result.high_count,
                "medium": scan_result.medium_count,
                "low": scan_result.low_count,
            },
            "misconfigurations": len(scan_result.misconfigurations),
            "secrets": len(scan_result.secrets),
            "timestamp": scan_result.scan_time.isoformat(),
        }

        return self._evaluate("container-security", input_data)

    def evaluate_autoscaling(self, autoscaling_config: dict[str, Any]) -> PolicyEvaluation:
        """Evaluate autoscaling policy."""
        logger.info("Evaluating autoscaling policy...")

        return self._evaluate("autoscaling", autoscaling_config)

    def evaluate_soc(self, alert_data: dict[str, Any]) -> PolicyEvaluation:
        """Evaluate SOC policy."""
        logger.info("Evaluating SOC policy...")

        return self._evaluate("soc", alert_data)

    def _evaluate(self, policy: str, input_data: dict[str, Any]) -> PolicyEvaluation:
        """Evaluate policy with OPA."""
        url = f"{self.opa_url}/v1/data/{policy}"

        try:
            response = requests.post(url, json={"input": input_data}, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()
            allowed = result.get("result", {}).get("allow", False)
            violations = result.get("result", {}).get("violations", [])

            logger.info(f"OPA evaluation result: allowed={allowed}, violations={len(violations)}")

            return PolicyEvaluation(allowed=allowed, violations=violations, policy=policy)

        except requests.exceptions.RequestException as e:
            logger.error(f"OPA evaluation failed: {e}")
            return PolicyEvaluation(
                allowed=False, violations=[f"OPA evaluation failed: {str(e)}"], policy=policy
            )


# =============================================================================
# SOC INTEGRATION
# =============================================================================


class SocIntegration:
    """Security Operations Center integration."""

    def __init__(self, config_path: str = "/etc/soc/soc-integration.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.opa_evaluator = OpaEvaluator()
        self.trivy_scanner = TrivyScanner()

    def _load_config(self) -> dict[str, Any]:
        """Load SOC configuration."""
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            return {}

    def process_scan_result(self, scan_result: ScanResult) -> SecurityAlert:
        """Process Trivy scan result and generate alert."""
        logger.info(f"Processing scan result for {scan_result.image}")

        # Evaluate with OPA
        evaluation = self.opa_evaluator.evaluate_container_security(scan_result)

        if evaluation.allowed:
            logger.info("Scan result passed policy evaluation")
            return None

        # Determine severity
        severity = Severity.LOW
        if scan_result.critical_count > 0:
            severity = Severity.CRITICAL
        elif scan_result.high_count > 0:
            severity = Severity.HIGH
        elif scan_result.medium_count > 0:
            severity = Severity.MEDIUM

        # Create alert
        alert = SecurityAlert(
            id=f"alert-{int(time.time())}",
            severity=severity,
            title=f"Security issues detected in {scan_result.image}",
            description=f"Found {scan_result.critical_count} critical, "
            f"{scan_result.high_count} high, "
            f"{scan_result.medium_count} medium, "
            f"{scan_result.low_count} low vulnerabilities",
            source="trivy",
            metadata={
                "image": scan_result.image,
                "vulnerabilities": {
                    "critical": scan_result.critical_count,
                    "high": scan_result.high_count,
                    "medium": scan_result.medium_count,
                    "low": scan_result.low_count,
                },
                "misconfigurations": len(scan_result.misconfigurations),
                "secrets": len(scan_result.secrets),
                "violations": evaluation.violations,
            },
        )

        # Route alert
        self._route_alert(alert)

        return alert

    def _route_alert(self, alert: SecurityAlert):
        """Route alert to appropriate channels."""
        logger.info(f"Routing alert {alert.id} with severity {alert.severity.value}")

        # Send to Slack
        self._send_slack_notification(alert)

        # Send to PagerDuty for critical/high
        if alert.severity in (Severity.CRITICAL, Severity.HIGH):
            self._send_pagerduty_notification(alert)

        # Send email
        self._send_email_notification(alert)

    def _send_slack_notification(self, alert: SecurityAlert):
        """Send Slack notification."""
        slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
        if not slack_webhook:
            return

        color = {
            Severity.CRITICAL: "danger",
            Severity.HIGH: "warning",
            Severity.MEDIUM: "#439FE0",
            Severity.LOW: "good",
        }.get(alert.severity, "good")

        message = {
            "text": "DCC SOC Alert",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Title", "value": alert.title, "short": False},
                        {"title": "Description", "value": alert.description, "short": False},
                        {"title": "Source", "value": alert.source, "short": True},
                    ],
                }
            ],
        }

        try:
            requests.post(slack_webhook, json=message, timeout=10)
            logger.info("Slack notification sent")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")

    def _send_pagerduty_notification(self, alert: SecurityAlert):
        """Send PagerDuty notification."""
        pagerduty_key = os.environ.get("PAGERDUTY_KEY")
        if not pagerduty_key:
            return

        severity_map = {
            Severity.CRITICAL: "critical",
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "info",
        }

        message = {
            "routing_key": pagerduty_key,
            "event_action": "trigger",
            "dedup_key": alert.id,
            "payload": {
                "summary": alert.title,
                "severity": severity_map.get(alert.severity, "info"),
                "source": "DCC SOC",
                "component": alert.source,
                "group": "Security",
                "class": "Security Alert",
            },
        }

        try:
            requests.post("https://events.pagerduty.com/v2/enqueue", json=message, timeout=10)
            logger.info("PagerDuty notification sent")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send PagerDuty notification: {e}")

    def _send_email_notification(self, alert: SecurityAlert):
        """Send email notification."""
        # Implementation depends on email service
        logger.info("Email notification queued")

    def auto_remediate(self, alert: SecurityAlert) -> bool:
        """Attempt auto-remediation."""
        logger.info(f"Attempting auto-remediation for alert {alert.id}")

        if alert.severity == Severity.CRITICAL:
            # Rollback or quarantine
            alert.remediation_action = RemediationAction.QUARANTINE
            return self._quarantine_pod(alert)
        elif alert.severity == Severity.HIGH:
            # Scale down
            alert.remediation_action = RemediationAction.SCALE_DOWN
            return self._scale_down_deployment(alert)

        return False

    def _quarantine_pod(self, alert: SecurityAlert) -> bool:
        """Quarantine affected pods."""
        logger.info(f"Quarantining pods for image {alert.metadata.get('image')}")
        # Implementation would use Kubernetes API
        return True

    def _scale_down_deployment(self, alert: SecurityAlert) -> bool:
        """Scale down deployment."""
        logger.info(f"Scaling down deployment for image {alert.metadata.get('image')}")
        # Implementation would use Kubernetes API
        return True


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="DCC SOC Integration")
    parser.add_argument("command", choices=["scan", "evaluate", "alert"])
    parser.add_argument("--image", help="Container image to scan")
    parser.add_argument("--report", help="Trivy report file")
    parser.add_argument("--opa-url", default="http://opa.opa.svc.cluster.local:8181")

    args = parser.parse_args()

    soc = SocIntegration()

    if args.command == "scan":
        if not args.image:
            print("Error: --image required for scan command")
            return 1

        scan_result = soc.trivy_scanner.scan_image(args.image)
        alert = soc.process_scan_result(scan_result)

        if alert:
            print(f"Alert generated: {alert.id}")
            print(f"Severity: {alert.severity.value}")
            print(f"Title: {alert.title}")
        else:
            print("No alert generated - image passed policy evaluation")

    elif args.command == "evaluate":
        if not args.report:
            print("Error: --report required for evaluate command")
            return 1

        scan_result = soc.trivy_scanner._parse_report(Path(args.report), "unknown")
        evaluation = soc.opa_evaluator.evaluate_container_security(scan_result)

        print(f"Allowed: {evaluation.allowed}")
        print(f"Violations: {evaluation.violations}")

    return 0


if __name__ == "__main__":
    exit(main())
