"""
Data Center Commander — SOC Scanner

Performs vulnerability scanning, compliance checks, and security audits
on containers and IaC configurations.
"""

import os
import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional

import yaml
from prometheus_client import Gauge, start_http_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("soc-scanner")

# Prometheus metrics
vulnerabilities = Gauge(
    "trivy_vulnerabilities",
    "Number of vulnerabilities by severity",
    ["severity", "image"],
)
scan_duration = Gauge(
    "soc_scan_duration_seconds",
    "Duration of the last scan in seconds",
)
scan_status = Gauge(
    "soc_scan_status",
    "Status of the last scan (1=success, 0=failure)",
)


class SOCScanner:
    """Security Operations Center scanner."""

    def __init__(self):
        self.reports_dir = os.environ.get("REPORTS_DIR", "/reports")
        self.trivy_cache = os.environ.get("TRIVY_CACHE_DIR", "/data/trivy-cache")
        self.iac_dir = os.environ.get("IAC_DIR", "/iac")
        self.policies_dir = os.environ.get("POLICIES_DIR", "/app/policies")

        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.trivy_cache, exist_ok=True)

        logger.info(f"SOC Scanner initialized: reports={self.reports_dir}")

    def scan_image(self, image: str) -> Dict:
        """Scan a container image with Trivy."""
        logger.info(f"Scanning image: {image}")
        try:
            result = subprocess.run(
                [
                    "trivy", "image",
                    "--format", "json",
                    "--cache-dir", self.trivy_cache,
                    "--severity", "CRITICAL,HIGH,MEDIUM,LOW",
                    image,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error(f"Trivy scan failed: {result.stderr}")
                return {}

            return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error(f"Trivy scan timed out for {image}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Trivy output: {e}")
            return {}

    def scan_iac(self) -> Dict:
        """Scan IaC configurations with Checkov."""
        logger.info(f"Scanning IaC directory: {self.iac_dir}")
        try:
            result = subprocess.run(
                [
                    "checkov",
                    "-d", self.iac_dir,
                    "--external-checks-dir", f"{self.policies_dir}/checkov/terraform/",
                    "--check", "DC_",
                    "--output", "json",
                    "--soft-fail",
                    "--compact",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode not in (0, 1):
                logger.error(f"Checkov scan failed: {result.stderr}")
                return {}

            return json.loads(result.stdout) if result.stdout else {}
        except subprocess.TimeoutExpired:
            logger.error("Checkov scan timed out")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Checkov output: {e}")
            return {}

    def update_metrics(self, trivy_results: Dict, checkov_results: Dict):
        """Update Prometheus metrics with scan results."""
        # Update vulnerability metrics
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

        if trivy_results and "Results" in trivy_results:
            for result in trivy_results["Results"]:
                image = result.get("Target", "unknown")
                for vuln in result.get("Vulnerabilities", []):
                    severity = vuln.get("Severity", "UNKNOWN")
                    if severity in severity_counts:
                        severity_counts[severity] += 1
                        vulnerabilities.labels(severity=severity, image=image).inc()

        for severity, count in severity_counts.items():
            vulnerabilities.labels(severity=severity, image="total").set(count)

        # Update scan status
        scan_status.set(1)

    def generate_report(self, trivy_results: Dict, checkov_results: Dict) -> str:
        """Generate a consolidated security report."""
        report = {
            "scan_time": datetime.now(timezone.utc).isoformat(),
            "tool": "Data Center Commander SOC Scanner",
            "version": "1.0.0",
            "trivy": trivy_results,
            "checkov": checkov_results,
            "summary": {
                "total_vulnerabilities": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "iac_findings": 0,
            },
        }

        # Summarize vulnerabilities
        if trivy_results and "Results" in trivy_results:
            for result in trivy_results["Results"]:
                for vuln in result.get("Vulnerabilities", []):
                    severity = vuln.get("Severity", "UNKNOWN")
                    report["summary"]["total_vulnerabilities"] += 1
                    if severity in report["summary"]:
                        report["summary"][severity.lower()] += 1

        # Summarize IaC findings
        if checkov_results and "results" in checkov_results:
            results = checkov_results["results"]
            report["summary"]["iac_findings"] = (
                len(results.get("passed_checks", []))
                + len(results.get("failed_checks", []))
                + len(results.get("skipped_checks", []))
            )

        report_path = os.path.join(self.reports_dir, "soc-report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report written to {report_path}")
        return report_path

    def run(self):
        """Run the full SOC scan."""
        start_time = datetime.now(timezone.utc)
        logger.info("Starting SOC scan...")

        # Scan IaC
        checkov_results = self.scan_iac()

        # Scan images (if any are specified)
        trivy_results = {}
        images = os.environ.get("SCAN_IMAGES", "").split(",")
        for image in images:
            image = image.strip()
            if image:
                result = self.scan_image(image)
                if result:
                    trivy_results = result

        # Update metrics
        self.update_metrics(trivy_results, checkov_results)

        # Generate report
        report_path = self.generate_report(trivy_results, checkov_results)

        # Record duration
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        scan_duration.set(duration)

        logger.info(f"SOC scan completed in {duration:.1f}s")
        return report_path


def main():
    """Entry point for the SOC scanner."""
    scanner = SOCScanner()

    # Start Prometheus metrics server
    port = int(os.environ.get("PROMETHEUS_PORT", 9102))
    start_http_server(port)
    logger.info(f"Prometheus metrics server started on port {port}")

    scanner.run()


if __name__ == "__main__":
    main()
