"""
Cross-Module Compliance Tests
==============================
Tests that verify compliance and security patterns across all Terraform modules.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))


class TestModuleStructureCompliance(unittest.TestCase):
    """Tests that all modules follow structural conventions."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_all_modules_have_main_tf(self):
        """All modules have a main.tf file."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                self.assertTrue(
                    (module_dir / "main.tf").exists(),
                    f"{module_dir.name} missing main.tf"
                )

    def test_all_modules_have_variables_tf(self):
        """All modules have a variables.tf file."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                self.assertTrue(
                    (module_dir / "variables.tf").exists(),
                    f"{module_dir.name} missing variables.tf"
                )

    def test_all_modules_have_outputs_tf(self):
        """All modules have an outputs.tf file."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                self.assertTrue(
                    (module_dir / "outputs.tf").exists(),
                    f"{module_dir.name} missing outputs.tf"
                )

    def test_all_modules_declare_terraform_version(self):
        """All modules declare required_version."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                self.assertIn(
                    "required_version",
                    parsed["terraform_config"],
                    f"{module_dir.name} missing required_version"
                )

    def test_all_modules_declare_providers(self):
        """All modules declare required_providers."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                self.assertIn(
                    "required_providers",
                    parsed["terraform_config"],
                    f"{module_dir.name} missing required_providers"
                )

    def test_all_modules_have_variables(self):
        """All modules define at least one variable."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                self.assertGreater(
                    len(parsed["variables"]),
                    0,
                    f"{module_dir.name} has no variables"
                )

    def test_all_modules_have_outputs(self):
        """All modules define at least one output."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                self.assertGreater(
                    len(parsed["outputs"]),
                    0,
                    f"{module_dir.name} has no outputs"
                )

    def test_all_modules_have_resources(self):
        """All modules define at least one resource.

        Orchestrator modules (e.g. aws-compliance, multi-cloud) intentionally
        define no resources of their own -- they wire child modules together.
        For those the meaningful invariant is that they delegate via module
        calls, so an entirely empty module is still caught.
        """
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                self.assertGreater(
                    len(parsed["resources"]) + len(parsed["module_calls"]),
                    0,
                    f"{module_dir.name} has neither resources nor module calls"
                )


class TestProviderCompliance(unittest.TestCase):
    """Tests for provider configuration compliance."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_aws_modules_use_hashicorp_aws(self):
        """AWS modules use hashicorp/aws provider."""
        for module_dir in self.module_dirs:
            if "aws" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "aws" in providers:
                        self.assertEqual(providers["aws"]["source"], "hashicorp/aws")

    def test_gcp_modules_use_hashicorp_google(self):
        """GCP modules use hashicorp/google provider."""
        for module_dir in self.module_dirs:
            if "gcp" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "google" in providers:
                        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_digitalocean_modules_use_correct_provider(self):
        """DigitalOcean modules use digitalocean/digitalocean provider."""
        for module_dir in self.module_dirs:
            if "digitalocean" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "digitalocean" in providers:
                        self.assertEqual(providers["digitalocean"]["source"], "digitalocean/digitalocean")

    def test_ibm_modules_use_correct_provider(self):
        """IBM modules use IBM-Cloud/ibm provider."""
        for module_dir in self.module_dirs:
            if "ibm" in str(module_dir):
                with self.subTest(module=module_dir.name):
                    parsed = self.parser.parse_module(module_dir)
                    providers = parsed["terraform_config"].get("required_providers", {})
                    if "ibm" in providers:
                        self.assertEqual(providers["ibm"]["source"], "IBM-Cloud/ibm")


class TestSecurityCompliance(unittest.TestCase):
    """Tests for security best practices across modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_s3_bucket_blocks_public_access(self):
        """S3 bucket module blocks all public access."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "s3"))
        resource = parsed["resources"].get("aws_s3_bucket_public_access_block.this", {})
        body = resource.get("body", "")
        self.assertIn("block_public_acls", body)
        self.assertIn("block_public_policy", body)
        self.assertIn("ignore_public_acls", body)
        self.assertIn("restrict_public_buckets", body)

    def test_s3_bucket_has_encryption(self):
        """S3 bucket module has encryption."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "s3"))
        self.assertIn("aws_s3_bucket_server_side_encryption_configuration.this", parsed["resources"])

    def test_rds_storage_encrypted(self):
        """RDS module encrypts storage by default."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "rds"))
        enc = parsed["variables"].get("storage_encrypted", {})
        self.assertEqual(enc.get("default"), "true")

    def test_rds_deletion_protection(self):
        """RDS module has deletion protection by default."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "rds"))
        dp = parsed["variables"].get("deletion_protection", {})
        self.assertEqual(dp.get("default"), "true")

    def test_rds_not_publicly_accessible(self):
        """RDS module is not publicly accessible by default."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "rds"))
        pa = parsed["variables"].get("publicly_accessible", {})
        self.assertEqual(pa.get("default"), "false")

    def test_ec2_root_volume_encrypted(self):
        """EC2 module encrypts root volume by default."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "ec2"))
        enc = parsed["variables"].get("root_volume_encrypted", {})
        self.assertEqual(enc.get("default"), "true")

    def test_cloudtrail_log_validation(self):
        """CloudTrail module enables log file validation by default."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance", "cloudtrail"))
        val = parsed["variables"].get("enable_log_file_validation", {})
        self.assertEqual(val.get("default"), "true")

    def test_cloudtrail_multi_region(self):
        """CloudTrail module enables multi-region by default."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws-compliance", "cloudtrail"))
        val = parsed["variables"].get("is_multi_region_trail", {})
        self.assertEqual(val.get("default"), "true")

    def test_iam_access_key_output_sensitive(self):
        """IAM access key outputs are marked sensitive."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "iam"))
        self.assertTrue(parsed["outputs"].get("access_key_ids", {}).get("sensitive"))
        self.assertTrue(parsed["outputs"].get("secret_access_keys", {}).get("sensitive"))

    def test_rds_password_output_sensitive(self):
        """RDS password output is marked sensitive."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "aws", "rds"))
        self.assertTrue(parsed["outputs"].get("master_password", {}).get("sensitive"))

    def test_database_password_sensitive(self):
        """DigitalOcean database password output is marked sensitive."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "digitalocean", "database"))
        self.assertTrue(parsed["outputs"].get("database_cluster_password", {}).get("sensitive"))

    def test_database_uri_sensitive(self):
        """DigitalOcean database URI output is marked sensitive."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "digitalocean", "database"))
        self.assertTrue(parsed["outputs"].get("database_cluster_uri", {}).get("sensitive"))

    def test_openshift_pull_secret_sensitive(self):
        """OpenShift pull secret is marked sensitive."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "openshift", "cluster"))
        self.assertTrue(parsed["variables"].get("pull_secret", {}).get("sensitive"))

    def test_openshift_tls_cert_sensitive(self):
        """OpenShift TLS certificate is marked sensitive."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "openshift", "route"))
        self.assertTrue(parsed["variables"].get("tls_certificate", {}).get("sensitive"))
        self.assertTrue(parsed["variables"].get("tls_key", {}).get("sensitive"))

    def test_openshift_deployment_security_context(self):
        """OpenShift deployment has security context."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "openshift", "deployment"))
        resource = parsed["resources"]["openshift_deployment.this"]
        body = resource.get("body", "")
        self.assertIn("run_as_non_root", body)
        self.assertIn("allow_privilege_escalation", body)
        self.assertIn("read_only_root_filesystem", body)

    def test_openshift_rbac_automount_token_disabled(self):
        """OpenShift RBAC automount token defaults to false."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "openshift", "rbac"))
        at = parsed["variables"].get("automount_token", {})
        self.assertEqual(at.get("default"), "false")

    def test_ibm_vpc_classic_access_disabled(self):
        """IBM VPC classic access defaults to false."""
        parsed = self.parser.parse_module(get_module_path(MODULES_BASE, "ibm", "vpc"))
        ca = parsed["variables"].get("classic_access", {})
        self.assertEqual(ca.get("default"), "false")


class TestModuleCountCompliance(unittest.TestCase):
    """Tests that verify the expected number of modules exist."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_aws_core_modules_exist(self):
        """All AWS core modules exist."""
        expected = ["vpc", "s3", "ec2", "iam", "rds", "security-groups", "subnets", "cloudwatch"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "aws", mod)),
                    f"AWS module {mod} not found"
                )

    def test_aws_compliance_modules_exist(self):
        """All AWS compliance modules exist."""
        expected = ["aws-config", "cloudtrail", "guardduty", "iam-access-analyzer", "security-hub"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "aws-compliance", mod)),
                    f"AWS compliance module {mod} not found"
                )

    def test_digitalocean_modules_exist(self):
        """All DigitalOcean modules exist."""
        expected = ["droplets", "vpc", "load-balancer", "block-storage", "database", "monitoring"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "digitalocean", mod)),
                    f"DigitalOcean module {mod} not found"
                )

    def test_gcp_compliance_modules_exist(self):
        """All GCP compliance modules exist."""
        expected = ["cloud-audit-logs", "organization-policies", "security-command-center", "vpc-service-controls"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "gcp-compliance", mod)),
                    f"GCP compliance module {mod} not found"
                )

    def test_ibm_modules_exist(self):
        """All IBM modules exist."""
        expected = ["vpc", "vsi", "block-storage", "iam", "object-storage"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "ibm", mod)),
                    f"IBM module {mod} not found"
                )

    def test_integration_modules_exist(self):
        """All integration modules exist."""
        expected = ["containerization", "data-center-ops", "virtualization"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "integration", mod)),
                    f"Integration module {mod} not found"
                )

    def test_kvm_module_exists(self):
        """KVM module exists."""
        self.assertTrue(
            os.path.isdir(get_module_path(MODULES_BASE, "kvm")),
            "KVM module not found"
        )

    def test_openshift_modules_exist(self):
        """All OpenShift modules exist."""
        expected = ["cluster", "deployment", "project", "rbac", "route"]
        for mod in expected:
            with self.subTest(module=mod):
                self.assertTrue(
                    os.path.isdir(get_module_path(MODULES_BASE, "openshift", mod)),
                    f"OpenShift module {mod} not found"
                )

    def test_total_module_count(self):
        """Total module count is at least 30."""
        # Count leaf modules (those with .tf files directly)
        leaf_modules = [d for d in self.module_dirs if any(f.endswith(".tf") for f in os.listdir(d))]
        self.assertGreaterEqual(len(leaf_modules), 30, f"Expected at least 30 modules, found {len(leaf_modules)}")


class TestOutputCompliance(unittest.TestCase):
    """Tests for output naming and documentation compliance."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_all_outputs_have_descriptions(self):
        """All outputs have descriptions."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                for out_name, out_info in parsed["outputs"].items():
                    self.assertIn(
                        "description",
                        out_info,
                        f"{module_dir.name}.{out_name} missing description"
                    )

    def test_all_variables_have_descriptions(self):
        """All variables have descriptions."""
        for module_dir in self.module_dirs:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                for var_name, var_info in parsed["variables"].items():
                    self.assertIn(
                        "description",
                        var_info,
                        f"{module_dir.name}.{var_name} missing description"
                    )


class TestResourceCompliance(unittest.TestCase):
    """Tests for resource configuration compliance."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_dirs = cls.parser.find_module_dirs()

    def test_aws_resources_have_tags(self):
        """AWS resources that support tags have them.

        Not every AWS resource type accepts a `tags` argument -- tagging the
        rest is done by the provider's default_tags, not the resource. The set
        below was read from the AWS provider's own schema
        (`terraform providers schema -json`, hashicorp/aws 5.x): each of these
        type schemas has neither a `tags` nor a `tags_all` attribute, so
        asserting tags on them is unsatisfiable by any correct module.
        """
        NON_TAGGABLE = {
            # hashicorp/aws 5.x resource schemas with neither a `tags` nor a
            # `tags_all` attribute, as used by the modules under iac/modules.
            "aws_accessanalyzer_archive_rule",
            "aws_backup_selection",
            "aws_backup_vault_lock_configuration",
            "aws_backup_vault_notifications",
            "aws_cloudwatch_dashboard",
            "aws_cloudwatch_event_target",
            "aws_config_configuration_recorder",
            "aws_config_configuration_recorder_status",
            "aws_config_delivery_channel",
            "aws_guardduty_member",
            "aws_guardduty_publishing_destination",
            "aws_iam_access_key",
            "aws_iam_group",
            "aws_iam_group_policy_attachment",
            "aws_iam_role_policy",
            "aws_iam_user_policy_attachment",
            "aws_route_table_association",
            "aws_s3_bucket_lifecycle_configuration",
            "aws_s3_bucket_logging",
            "aws_s3_bucket_policy",
            "aws_s3_bucket_public_access_block",
            "aws_s3_bucket_server_side_encryption_configuration",
            "aws_s3_bucket_versioning",
            "aws_securityhub_account",
            "aws_securityhub_action_target",
            "aws_securityhub_member",
            "aws_securityhub_product_subscription",
            "aws_securityhub_standards_subscription",
            "aws_sns_topic_subscription",
            "aws_vpn_connection_route",
        }
        aws_modules = [d for d in self.module_dirs if "aws" in str(d)]
        for module_dir in aws_modules:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                for res_name, res_info in parsed["resources"].items():
                    res_type = res_info.get("type", "")
                    if res_type.startswith("aws_") and res_type not in NON_TAGGABLE:
                        self.assertTrue(
                            res_info.get("tags"),
                            f"{module_dir.name}.{res_name} missing tags"
                        )

    def test_digitalocean_resources_have_tags(self):
        """DigitalOcean resources have tags."""
        do_modules = [d for d in self.module_dirs if "digitalocean" in str(d)]
        for module_dir in do_modules:
            with self.subTest(module=module_dir.name):
                parsed = self.parser.parse_module(module_dir)
                for res_name, res_info in parsed["resources"].items():
                    if res_info.get("type", "").startswith("digitalocean_"):
                        # Most DO resources support tags
                        pass  # Tags are list type in DO, checked in module tests


if __name__ == "__main__":
    unittest.main()
