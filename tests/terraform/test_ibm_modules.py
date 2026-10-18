"""
IBM Cloud Module Tests
======================
Tests for IBM Cloud modules: VPC, VSI, Block Storage, IAM, Object Storage.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))


class TestIBMVPCModule(unittest.TestCase):
    """Tests for the IBM VPC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "vpc")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM VPC module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_vpc_resource(self):
        """IBM VPC resource exists."""
        self.assertIn("ibm_is_vpc.this", self.parsed["resources"])

    def test_address_prefix_resource(self):
        """Address prefix resource exists."""
        self.assertIn("ibm_is_vpc_address_prefix.this", self.parsed["resources"])

    def test_subnet_resource(self):
        """Subnet resource exists."""
        self.assertIn("ibm_is_subnet.this", self.parsed["resources"])

    def test_network_acl_resource(self):
        """Network ACL resource exists."""
        self.assertIn("ibm_is_network_acl.this", self.parsed["resources"])

    def test_public_gateway_resource(self):
        """Public gateway resource exists."""
        self.assertIn("ibm_is_public_gateway.this", self.parsed["resources"])

    def test_security_group_resource(self):
        """Security group resource exists."""
        self.assertIn("ibm_is_security_group.this", self.parsed["resources"])

    def test_security_group_rule_resource(self):
        """Security group rule resource exists."""
        self.assertIn("ibm_is_security_group_rule.this", self.parsed["resources"])

    def test_flow_log_resource(self):
        """Flow log resource exists."""
        self.assertIn("ibm_is_flow_log.this", self.parsed["resources"])

    def test_address_prefix_management_validation(self):
        """Address prefix management has validation."""
        apm = self.parsed["variables"].get("address_prefix_management", {})
        self.assertIn("validation", apm)
        self.assertIn("auto", apm["validation"]["condition"])
        self.assertIn("manual", apm["validation"]["condition"])

    def test_classic_access_default(self):
        """Classic access defaults to false."""
        ca = self.parsed["variables"].get("classic_access", {})
        self.assertEqual(ca.get("default"), "false")

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vpc_id", outputs)
        self.assertIn("vpc_crn", outputs)
        self.assertIn("vpc_name", outputs)
        self.assertIn("subnet_ids", outputs)
        self.assertIn("subnet_crns", outputs)
        self.assertIn("public_gateway_ids", outputs)
        self.assertIn("security_group_id", outputs)
        self.assertIn("network_acl_id", outputs)
        self.assertIn("flow_log_id", outputs)

    def test_ibm_provider(self):
        """IBM provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("ibm", providers)
        self.assertEqual(providers["ibm"]["source"], "IBM-Cloud/ibm")

    def test_dynamic_network_acl_rules(self):
        """Dynamic network ACL rules are used."""
        resource = self.parsed["resources"]["ibm_is_network_acl.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_dynamic_security_group_rules(self):
        """Dynamic security group rules are used."""
        resource = self.parsed["resources"]["ibm_is_security_group_rule.this"]
        self.assertTrue(resource.get("dynamic"))


class TestIBMVSIModule(unittest.TestCase):
    """Tests for the IBM VSI module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "vsi")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM VSI module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """IBM instance resource exists."""
        self.assertIn("ibm_is_instance.this", self.parsed["resources"])

    def test_floating_ip_resource(self):
        """Floating IP resource exists."""
        self.assertIn("ibm_is_floating_ip.this", self.parsed["resources"])

    def test_image_data_source(self):
        """Image data source exists."""
        self.assertIn("ibm_is_image.this", self.parsed["data_sources"])

    def test_ssh_key_data_source(self):
        """SSH key data source exists."""
        self.assertIn("ibm_is_ssh_key.this", self.parsed["data_sources"])

    def test_vsi_outputs(self):
        """VSI outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_id", outputs)
        self.assertIn("instance_crn", outputs)
        self.assertIn("instance_name", outputs)
        self.assertIn("primary_ip", outputs)
        self.assertIn("floating_ip", outputs)
        self.assertIn("floating_ip_id", outputs)

    def test_enable_floating_ip_default(self):
        """Floating IP defaults to disabled."""
        fip = self.parsed["variables"].get("enable_floating_ip", {})
        self.assertEqual(fip.get("default"), "false")

    def test_boot_volume_size_default(self):
        """Boot volume size defaults to 100 GB."""
        bvs = self.parsed["variables"].get("boot_volume_size", {})
        self.assertEqual(bvs.get("default"), "100")


class TestIBMBlockStorageModule(unittest.TestCase):
    """Tests for the IBM Block Storage module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "block-storage")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM Block Storage module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_volume_resource(self):
        """IBM volume resource exists."""
        self.assertIn("ibm_is_volume.this", self.parsed["resources"])

    def test_volume_attachment_resource(self):
        """Volume attachment resource exists."""
        self.assertIn("ibm_is_instance_volume_attachment.this", self.parsed["resources"])

    def test_profile_validation(self):
        """Profile has validation."""
        prof = self.parsed["variables"].get("profile", {})
        self.assertIn("validation", prof)
        self.assertIn("10iops-tier", prof["validation"]["condition"])
        self.assertIn("5iops-tier", prof["validation"]["condition"])
        self.assertIn("general-purpose", prof["validation"]["condition"])
        self.assertIn("custom", prof["validation"]["condition"])

    def test_encryption_key_support(self):
        """Encryption key is supported."""
        self.assertIn("encryption_key_crn", self.parsed["variables"])

    def test_volume_outputs(self):
        """Volume outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("volume_id", outputs)
        self.assertIn("volume_crn", outputs)
        self.assertIn("volume_name", outputs)
        self.assertIn("volume_capacity", outputs)
        self.assertIn("attachment_id", outputs)


class TestIBMIAMModule(unittest.TestCase):
    """Tests for the IBM IAM module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "iam")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM IAM module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_access_group_resource(self):
        """Access group resource exists."""
        self.assertIn("ibm_iam_access_group.this", self.parsed["resources"])

    def test_access_group_members_resource(self):
        """Access group members resource exists."""
        self.assertIn("ibm_iam_access_group_members.this", self.parsed["resources"])

    def test_access_group_policy_resource(self):
        """Access group policy resource exists."""
        self.assertIn("ibm_iam_access_group_policy.this", self.parsed["resources"])

    def test_dynamic_rule_resource(self):
        """Dynamic rule resource exists."""
        self.assertIn("ibm_iam_access_group_dynamic_rule.this", self.parsed["resources"])

    def test_iam_outputs(self):
        """IAM outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("access_group_id", outputs)
        self.assertIn("access_group_name", outputs)
        self.assertIn("access_group_crn", outputs)
        self.assertIn("policy_ids", outputs)
        self.assertIn("dynamic_rule_ids", outputs)


class TestIBMObjectStorageModule(unittest.TestCase):
    """Tests for the IBM Object Storage module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "object-storage")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM Object Storage module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_cos_bucket_resource(self):
        """COS bucket resource exists."""
        self.assertIn("ibm_cos_bucket.this", self.parsed["resources"])

    def test_versioning_resource(self):
        """Versioning resource exists."""
        self.assertIn("ibm_cos_bucket_versioning.this", self.parsed["resources"])

    def test_lifecycle_configuration_resource(self):
        """Lifecycle configuration resource exists."""
        self.assertIn("ibm_cos_bucket_lifecycle_configuration.this", self.parsed["resources"])

    def test_storage_class_validation(self):
        """Storage class has validation."""
        sc = self.parsed["variables"].get("storage_class", {})
        self.assertIn("validation", sc)
        self.assertIn("standard", sc["validation"]["condition"])
        self.assertIn("vault", sc["validation"]["condition"])
        self.assertIn("cold", sc["validation"]["condition"])
        self.assertIn("smart", sc["validation"]["condition"])

    def test_encryption_key_support(self):
        """Encryption key is supported."""
        self.assertIn("encryption_key_crn", self.parsed["variables"])

    def test_activity_tracking_support(self):
        """Activity tracking is supported."""
        self.assertIn("enable_activity_tracking", self.parsed["variables"])

    def test_metrics_monitoring_support(self):
        """Metrics monitoring is supported."""
        self.assertIn("enable_metrics_monitoring", self.parsed["variables"])

    def test_allowed_ips_support(self):
        """Allowed IPs are supported."""
        self.assertIn("allowed_ips", self.parsed["variables"])

    def test_lifecycle_rules_support(self):
        """Lifecycle rules are supported."""
        self.assertIn("lifecycle_rules", self.parsed["variables"])

    def test_object_storage_outputs(self):
        """Object storage outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("bucket_id", outputs)
        self.assertIn("bucket_crn", outputs)
        self.assertIn("bucket_name", outputs)
        self.assertIn("bucket_location", outputs)
        self.assertIn("s3_endpoint", outputs)

    def test_dynamic_blocks(self):
        """Dynamic blocks are used for optional features."""
        resource = self.parsed["resources"]["ibm_cos_bucket.this"]
        self.assertTrue(resource.get("dynamic"))


if __name__ == "__main__":
    unittest.main()
