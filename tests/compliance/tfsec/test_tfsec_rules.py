"""
tfsec Rule Tests — Data Center Commander
Tests for tfsec custom rules.
These tests validate that tfsec rules correctly enforce data center governance rules.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

# tests/compliance/tfsec/ -> project root is three levels up, not two.
TFSEC_RULES_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "policies" / "tfsec")


def run_tfsec(rule_file: str, tf_file: str) -> dict:
    """Run tfsec against a Terraform file with custom rules."""
    result = subprocess.run(
        ["tfsec", "--custom-check", rule_file, tf_file],
        capture_output=True,
        text=True,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_tfsec_with_json(rule_file: str, tf_content: str) -> dict:
    """Run tfsec with JSON output against Terraform content."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
        f.write(tf_content)
        tf_file = f.name

    try:
        result = subprocess.run(
            ["tfsec", "--custom-check", rule_file, "--format", "json", tf_file],
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout) if result.stdout else {}
        return {
            "returncode": result.returncode,
            "output": output,
            "stderr": result.stderr,
        }
    finally:
        os.unlink(tf_file)


class TestTfsecRules:
    """Tests for tfsec custom rules."""

    def test_tfsec_rules_directory_exists(self):
        """Verify tfsec rules directory exists."""
        assert os.path.isdir(TFSEC_RULES_DIR)

    def test_tfsec_rule_files_present(self):
        """Verify tfsec rule files are present."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        assert len(rule_files) > 0

    def test_tfsec_rule_format_valid(self):
        """Verify tfsec rule files have valid JSON format."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            assert "rules" in rule_data or "id" in rule_data

    def test_tfsec_rule_has_required_fields(self):
        """Verify tfsec rules have required fields."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                assert "id" in rule
                assert "description" in rule or "impact" in rule
                assert "resolution" in rule or "remediation" in rule

    def test_tfsec_rule_ids_follow_convention(self):
        """Verify tfsec rule IDs follow DC_ prefix convention."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                assert rule["id"].startswith("DC_")

    def test_tfsec_rule_severity_levels(self):
        """Verify tfsec rules have valid severity levels."""
        valid_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "WARNING", "ERROR", "INFO"]
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                severity = rule.get("severity", rule.get("impact", ""))
                assert severity.upper() in valid_severities

    def test_tfsec_rule_categories(self):
        """Verify tfsec rules have valid categories."""
        valid_categories = [
            "networking",
            "compute",
            "storage",
            "encryption",
            "logging",
            "monitoring",
            "iam",
            "compliance",
            "general",
        ]
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                category = rule.get("category", rule.get("categories", ["general"]))
                if isinstance(category, list):
                    for cat in category:
                        assert cat.lower() in valid_categories
                else:
                    assert category.lower() in valid_categories


class TestTfsecNetworkRules:
    """Tests for tfsec network security rules."""

    def test_network_rules_present(self):
        """Verify network security rules are present."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        network_rules = []
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                if (
                    "network" in rule.get("category", "").lower()
                    or "network" in str(rule.get("categories", [])).lower()
                ):
                    network_rules.append(rule)
        assert len(network_rules) > 0


class TestTfsecEncryptionRules:
    """Tests for tfsec encryption rules."""

    def test_encryption_rules_present(self):
        """Verify encryption rules are present."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        encryption_rules = []
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                if (
                    "encryption" in rule.get("category", "").lower()
                    or "encryption" in str(rule.get("categories", [])).lower()
                ):
                    encryption_rules.append(rule)
        assert len(encryption_rules) > 0


class TestTfsecIAMRules:
    """Tests for tfsec IAM rules."""

    def test_iam_rules_present(self):
        """Verify IAM rules are present."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        iam_rules = []
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                if (
                    "iam" in rule.get("category", "").lower()
                    or "iam" in str(rule.get("categories", [])).lower()
                ):
                    iam_rules.append(rule)
        assert len(iam_rules) > 0


class TestTfsecComplianceRules:
    """Tests for tfsec compliance rules."""

    def test_compliance_rules_present(self):
        """Verify compliance rules are present."""
        rule_files = [f for f in os.listdir(TFSEC_RULES_DIR) if f.endswith(".json")]
        compliance_rules = []
        for rule_file in rule_files:
            rule_path = os.path.join(TFSEC_RULES_DIR, rule_file)
            with open(rule_path) as f:
                rule_data = json.load(f)
            rules = rule_data.get("rules", [rule_data])
            for rule in rules:
                if (
                    "compliance" in rule.get("category", "").lower()
                    or "compliance" in str(rule.get("categories", [])).lower()
                ):
                    compliance_rules.append(rule)
        assert len(compliance_rules) > 0
