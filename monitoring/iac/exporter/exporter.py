#!/usr/bin/env python3
"""
IaC Monitoring Exporter for Prometheus.

Scans Checkov JSON output and Terraform plan files to expose
security and compliance metrics on /metrics.
"""

import json
import os
import time
import glob
import logging
from pathlib import Path
from prometheus_client import start_http_server, Gauge, Counter, Info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("iac-exporter")

# Prometheus metrics
CHECKOV_PASSED = Gauge("iac_checkov_passed", "Total passed checks")
CHECKOV_FAILED = Gauge("iac_checkov_failed", "Total failed checks")
CHECKOV_FAILED_CRITICAL = Gauge("iac_checkov_failed_critical", "Critical severity failures")
CHECKOV_FAILED_HIGH = Gauge("iac_checkov_failed_high", "High severity failures")
CHECKOV_FAILED_MEDIUM = Gauge("iac_checkov_failed_medium", "Medium severity failures")
CHECKOV_FAILED_LOW = Gauge("iac_checkov_failed_low", "Low severity failures")
COMPLIANCE_SCORE = Gauge("iac_compliance_score", "Overall compliance score (0-100)")
POLICY_CATEGORY_FAILURES = Gauge(
    "iac_policy_category_failures",
    "Failures by policy category",
    ["category"]
)
TERRAFORM_DRIFT = Gauge("iac_terraform_drift_detected", "Terraform drift detected count")
UNENCRYPTED_RESOURCES = Gauge("iac_unencrypted_resources", "Unencrypted resources count")
PUBLIC_EXPOSURE = Gauge("iac_public_exposure", "Publicly exposed resources count")
SCAN_TIMESTAMP = Gauge("iac_last_scan_timestamp", "Unix timestamp of last scan")
EXPORTER_INFO = Info("iac_exporter", "IaC exporter metadata")

CHECKOV_OUTPUT_DIR = os.environ.get("CHECKOV_OUTPUT_DIR", "/data/checkov")
TERRAFORM_PLAN_DIR = os.environ.get("TERRAFORM_PLAN_DIR", "/data/terraform")
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "300"))
PORT = int(os.environ.get("PROMETHEUS_PORT", "9091"))


def parse_checkov_results(checkov_dir: str) -> dict:
    """Parse all Checkov JSON result files in directory."""
    results = {
        "passed": 0,
        "failed": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "categories": {},
    }

    for json_file in glob.glob(os.path.join(checkov_dir, "**", "*.json"), recursive=True):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            if isinstance(data, list):
                for result_set in data:
                    _process_checkov_result(result_set, results)
            elif isinstance(data, dict):
                _process_checkov_result(data, results)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse {json_file}: {e}")

    return results


def _process_checkov_result(result_set: dict, results: dict):
    """Process a single Checkov result set."""
    if "results" not in result_set:
        return

    check_results = result_set["results"].get("passed_checks", [])
    failed_results = result_set["results"].get("failed_checks", [])

    results["passed"] += len(check_results)
    results["failed"] += len(failed_results)

    for check in failed_results:
        severity = (check.get("severity") or "MEDIUM").upper()
        check_id = check.get("check_id", "UNKNOWN")

        if severity == "CRITICAL":
            results["critical"] += 1
        elif severity == "HIGH":
            results["high"] += 1
        elif severity == "LOW":
            results["low"] += 1
        else:
            results["medium"] += 1

        # Extract category from check_id (e.g., DC_NET_001 -> NET)
        category = _extract_category(check_id)
        results["categories"][category] = results["categories"].get(category, 0) + 1


def _extract_category(check_id: str) -> str:
    """Extract category from check ID like DC_NET_001 -> NET."""
    parts = check_id.split("_")
    if len(parts) >= 3 and parts[0] == "DC":
        return parts[1]
    return "OTHER"


def parse_terraform_plan(plan_dir: str) -> dict:
    """Parse Terraform plan JSON for drift detection."""
    drift_count = 0

    for json_file in glob.glob(os.path.join(plan_dir, "**", "*.json"), recursive=True):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            if isinstance(data, dict) and "resource_changes" in data:
                for change in data["resource_changes"]:
                    actions = change.get("change", {}).get("actions", [])
                    if "create" in actions or "update" in actions or "delete" in actions:
                        drift_count += 1
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse Terraform plan {json_file}: {e}")

    return {"drift": drift_count}


def detect_unencrypted_resources(checkov_results: dict) -> int:
    """Count unencrypted resources from Checkov results."""
    unencrypted = 0
    for category, count in checkov_results.get("categories", {}).items():
        if category in ("STORAGE", "CRYPTO"):
            unencrypted += count
    return unencrypted


def detect_public_exposure(checkov_results: dict) -> int:
    """Count publicly exposed resources from Checkov results."""
    exposure = 0
    for category, count in checkov_results.get("categories", {}).items():
        if category == "NET":
            exposure += count
    return exposure


def update_metrics():
    """Scan all data sources and update Prometheus metrics."""
    logger.info("Starting metrics collection...")

    # Parse Checkov results
    checkov_results = parse_checkov_results(CHECKOV_OUTPUT_DIR)
    logger.info(
        f"Checkov: {checkov_results['passed']} passed, "
        f"{checkov_results['failed']} failed"
    )

    # Parse Terraform plans
    tf_results = parse_terraform_plan(TERRAFORM_PLAN_DIR)
    logger.info(f"Terraform drift: {tf_results['drift']} resources")

    # Calculate compliance score
    total = checkov_results["passed"] + checkov_results["failed"]
    compliance = (checkov_results["passed"] / total * 100) if total > 0 else 100.0

    # Update gauges
    CHECKOV_PASSED.set(checkov_results["passed"])
    CHECKOV_FAILED.set(checkov_results["failed"])
    CHECKOV_FAILED_CRITICAL.set(checkov_results["critical"])
    CHECKOV_FAILED_HIGH.set(checkov_results["high"])
    CHECKOV_FAILED_MEDIUM.set(checkov_results["medium"])
    CHECKOV_FAILED_LOW.set(checkov_results["low"])
    COMPLIANCE_SCORE.set(round(compliance, 2))
    TERRAFORM_DRIFT.set(tf_results["drift"])
    UNENCRYPTED_RESOURCES.set(detect_unencrypted_resources(checkov_results))
    PUBLIC_EXPOSURE.set(detect_public_exposure(checkov_results))
    SCAN_TIMESTAMP.set(time.time())

    # Update per-category metrics
    for category, count in checkov_results["categories"].items():
        POLICY_CATEGORY_FAILURES.labels(category=category).set(count)

    logger.info(f"Metrics updated. Compliance: {compliance:.1f}%")


def main():
    """Main entry point."""
    EXPORTER_INFO.info({
        "version": "1.0.0",
        "checkov_dir": CHECKOV_OUTPUT_DIR,
        "terraform_dir": TERRAFORM_PLAN_DIR,
        "scrape_interval": str(SCRAPE_INTERVAL),
    })

    logger.info(f"Starting IaC exporter on port {PORT}")
    logger.info(f"Checkov output dir: {CHECKOV_OUTPUT_DIR}")
    logger.info(f"Terraform plan dir: {TERRAFORM_PLAN_DIR}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")

    start_http_server(PORT)
    logger.info(f"Metrics available at http://0.0.0.0:{PORT}/metrics")

    while True:
        try:
            update_metrics()
        except Exception as e:
            logger.error(f"Error updating metrics: {e}", exc_info=True)
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
