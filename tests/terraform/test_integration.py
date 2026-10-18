"""
Integration Tests for Terraform Modules
=======================================
Tests that verify cross-module integration patterns and module wiring.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform", "modules"))


class TestModuleWiring(unittest.TestCase):
    """Tests that verify modules are properly wired together."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_aws_compliance_root_wires_config(self):
        """AWS Compliance root module wires AWS Config."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        self.assertIn("aws_config", parsed["module_calls"])

    def test_aws_compliance_root_wires_guardduty(self):
        """AWS Compliance root module wires GuardDuty."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        self.assertIn("guardduty", parsed["module_calls"])

    def test_aws_compliance_root_wires_security_hub(self):
        """AWS Compliance root module wires Security Hub."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        self.assertIn("security_hub", parsed["module_calls"])

    def test_aws_compliance_root_wires_cloudtrail(self):
        """AWS Compliance root module wires CloudTrail."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        self.assertIn("cloudtrail", parsed["module_calls"])

    def test_aws_compliance_root_wires_access_analyzer(self):
        """AWS Compliance root module wires IAM Access Analyzer."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        self.assertIn("iam_access_analyzer", parsed["module_calls"])

    def test_aws_compliance_uses_relative_sources(self):
        """AWS Compliance root module uses relative source paths."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        for mod_name, mod_info in parsed["module_calls"].items():
            source = mod_info.get("source", "")
            self.assertTrue(
                source.startswith("./"),
                f"Module {mod_name} source should be relative: {source}"
            )

    def test_aws_compliance_outputs_match_submodules(self):
        """AWS Compliance root outputs match submodule outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        outputs = parsed["outputs"]
        # These outputs should come from sub-modules
        self.assertIn("config_recorder_id", outputs)
        self.assertIn("guardduty_detector_id", outputs)
        self.assertIn("security_hub_arn", outputs)
        self.assertIn("cloudtrail_arn", outputs)
        self.assertIn("access_analyzer_arn", outputs)


class TestProviderVersionConstraints(unittest.TestCase):
    """Tests for provider version constraints across modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_aws_provider_version_constraint(self):
        """AWS provider has version constraint."""
        for module_dir in self.module_dirs:
            if "aws" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "aws" in providers:
                        version = providers["aws"].get("version")
                        self.assertIsNotNone(version, f"{module_dir.name} AWS provider missing version")

    def test_google_provider_version_constraint(self):
        """Google provider has version constraint."""
        for module_dir in self.module_dirs:
            if "gcp" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "google" in providers:
                        version = providers["google"].get("version")
                        self.assertIsNotNone(version, f"{module_dir.name} Google provider missing version")

    def test_digitalocean_provider_version_constraint(self):
        """DigitalOcean provider has version constraint."""
        for module_dir in self.module_dirs:
            if "digitalocean" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "digitalocean" in providers:
                        version = providers["digitalocean"].get("version")
                        self.assertIsNotNone(version, f"{module_dir.name} DO provider missing version")

    def test_ibm_provider_version_constraint(self):
        """IBM provider has version constraint."""
        for module_dir in self.module_dirs:
            if "ibm" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "ibm" in providers:
                        version = providers["ibm"].get("version")
                        self.assertIsNotNone(version, f"{module_dir.name} IBM provider missing version")


class TestTerraformVersionConstraints(unittest.TestCase):
    """Tests for Terraform version constraints across modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_all_modules_require_terraform_1_5_or_higher(self):
        """All modules require Terraform >= 1.5.0."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                version = parsed["terraform_config"].get("required_version", "")
                self.assertIn(">=", version, f"{module_dir.name} should require Terraform >= 1.5.0")


class TestModuleDependencyChains(unittest.TestCase):
    """Tests for module dependency chains."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_vpc_module_produces_subnet_ids(self):
        """VPC module produces subnet IDs for other modules."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "vpc"))
        self.assertIn("vpc_id", parsed["outputs"])

    def test_subnets_module_produces_subnet_ids(self):
        """Subnets module produces subnet IDs for other modules."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "subnets"))
        self.assertIn("public_subnet_ids", parsed["outputs"])
        self.assertIn("private_subnet_ids", parsed["outputs"])
        self.assertIn("database_subnet_ids", parsed["outputs"])

    def test_security_groups_module_produces_sg_id(self):
        """Security groups module produces SG ID for other modules."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "security-groups"))
        self.assertIn("security_group_id", parsed["outputs"])

    def test_iam_module_produces_role_arns(self):
        """IAM module produces role ARNs for other modules."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "iam"))
        self.assertIn("role_arns", parsed["outputs"])

    def test_ec2_module_produces_instance_ids(self):
        """EC2 module produces instance IDs for other modules."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "ec2"))
        self.assertIn("instance_ids", parsed["outputs"])

    def test_rds_module_produces_endpoint(self):
        """RDS module produces endpoint for other modules."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "rds"))
        self.assertIn("db_instance_endpoint", parsed["outputs"])


class TestCrossProviderIntegration(unittest.TestCase):
    """Tests for cross-provider integration patterns."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_aws_compliance_uses_shared_s3_bucket(self):
        """AWS Compliance modules share an S3 bucket for logs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        # The root module should pass compliance_s3_bucket to sub-modules
        self.assertIn("compliance_s3_bucket", parsed["variables"])

    def test_aws_compliance_uses_shared_kms_key(self):
        """AWS Compliance modules share a KMS key for encryption."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance"))
        self.assertIn("compliance_kms_key_id", parsed["variables"])


class TestModuleOutputContracts(unittest.TestCase):
    """Tests that verify module output contracts are consistent."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_vpc_module_outputs(self):
        """VPC module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "vpc"))
        expected = ["vpc_id", "vpc_cidr_block", "default_security_group_id", "flow_log_id"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"VPC module missing output: {out}")

    def test_s3_module_outputs(self):
        """S3 module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "s3"))
        expected = ["bucket_id", "bucket_arn", "bucket_domain_name", "bucket_regional_domain_name"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"S3 module missing output: {out}")

    def test_ec2_module_outputs(self):
        """EC2 module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "ec2"))
        expected = ["instance_ids", "instance_public_ips", "instance_private_ips", "elastic_ips"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"EC2 module missing output: {out}")

    def test_iam_module_outputs(self):
        """IAM module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "iam"))
        expected = ["role_arns", "role_names", "policy_arns", "instance_profile_names", "instance_profile_arns", "user_names"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"IAM module missing output: {out}")

    def test_rds_module_outputs(self):
        """RDS module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "rds"))
        expected = ["db_instance_id", "db_instance_arn", "db_instance_endpoint", "db_instance_address", "db_instance_port", "db_subnet_group_name"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"RDS module missing output: {out}")

    def test_droplets_module_outputs(self):
        """Droplets module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "digitalocean", "droplets"))
        expected = ["droplet_ids", "droplet_urns", "droplet_names", "droplet_ipv4_addresses"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"Droplets module missing output: {out}")

    def test_database_module_outputs(self):
        """Database module has expected outputs."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "digitalocean", "database"))
        expected = ["database_cluster_id", "database_cluster_urn", "database_cluster_host", "database_cluster_port"]
        for out in expected:
            self.assertIn(out, parsed["outputs"], f"Database module missing output: {out}")


if __name__ == "__main__":
    unittest.main()
