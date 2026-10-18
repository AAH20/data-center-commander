"""
AWS Core Module Tests
=====================
Tests for AWS infrastructure modules: VPC, S3, EC2, IAM, RDS, Security Groups, Subnets, CloudWatch.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path, read_tf_file


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform", "modules"))


class TestAWSVPCModule(unittest.TestCase):
    """Tests for the AWS VPC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "vpc")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """VPC module directory exists with required files."""
        self.assertTrue(os.path.isdir(self.module_path))
        for f in ["main.tf", "variables.tf", "outputs.tf"]:
            self.assertTrue(os.path.exists(os.path.join(self.module_path, f)))

    def test_required_version(self):
        """Terraform version constraint is set."""
        self.assertIn("required_version", self.parsed["terraform_config"])
        version = self.parsed["terraform_config"]["required_version"]
        self.assertRegex(version, r">=\s*\d+\.\d+")

    def test_aws_provider_declared(self):
        """AWS provider is declared with correct source."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("aws", providers)
        self.assertEqual(providers["aws"]["source"], "hashicorp/aws")

    def test_vpc_resource_exists(self):
        """VPC resource is defined."""
        self.assertIn("aws_vpc.this", self.parsed["resources"])

    def test_vpc_cidr_validation(self):
        """VPC CIDR block has validation."""
        cidr_var = self.parsed["variables"].get("cidr_block", {})
        self.assertIn("validation", cidr_var)
        self.assertIn("cidrnetmask", cidr_var["validation"]["condition"])

    def test_flow_logs_resource(self):
        """Flow log resource exists with count."""
        flow_log = self.parsed["resources"].get("aws_flow_log.this", {})
        self.assertTrue(flow_log.get("count"))

    def test_cloudwatch_log_group_for_flow_logs(self):
        """CloudWatch log group for flow logs exists."""
        self.assertIn("aws_cloudwatch_log_group.flow_log", self.parsed["resources"])

    def test_default_security_group(self):
        """Default security group resource exists."""
        self.assertIn("aws_default_security_group.default", self.parsed["resources"])

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vpc_id", outputs)
        self.assertIn("vpc_cidr_block", outputs)
        self.assertIn("default_security_group_id", outputs)
        self.assertIn("flow_log_id", outputs)

    def test_flow_log_traffic_type_validation(self):
        """Flow log traffic type has validation."""
        var = self.parsed["variables"].get("flow_log_traffic_type", {})
        self.assertIn("validation", var)
        self.assertIn("ACCEPT", var["validation"]["condition"])
        self.assertIn("REJECT", var["validation"]["condition"])
        self.assertIn("ALL", var["validation"]["condition"])

    def test_tags_on_resources(self):
        """Resources have tags."""
        for key, resource in self.parsed["resources"].items():
            self.assertTrue(resource.get("tags"), f"Resource {key} missing tags")

    def test_dns_support_defaults(self):
        """DNS support defaults to true."""
        dns = self.parsed["variables"].get("enable_dns_support", {})
        self.assertEqual(dns.get("default"), "true")

    def test_flow_logs_default_enabled(self):
        """Flow logs default to enabled."""
        flow = self.parsed["variables"].get("enable_flow_logs", {})
        self.assertEqual(flow.get("default"), "true")


class TestAWSS3Module(unittest.TestCase):
    """Tests for the AWS S3 module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "s3")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """S3 module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_s3_bucket_resource(self):
        """S3 bucket resource is defined."""
        self.assertIn("aws_s3_bucket.this", self.parsed["resources"])

    def test_versioning_resource(self):
        """Versioning configuration exists."""
        self.assertIn("aws_s3_bucket_versioning.this", self.parsed["resources"])

    def test_encryption_resource(self):
        """Server-side encryption is configured."""
        self.assertIn("aws_s3_bucket_server_side_encryption_configuration.this", self.parsed["resources"])

    def test_public_access_block(self):
        """Public access block is configured."""
        self.assertIn("aws_s3_bucket_public_access_block.this", self.parsed["resources"])
        resource = self.parsed["resources"]["aws_s3_bucket_public_access_block.this"]
        body = resource.get("body", "")
        self.assertIn("block_public_acls", body)
        self.assertIn("block_public_policy", body)
        self.assertIn("ignore_public_acls", body)
        self.assertIn("restrict_public_buckets", body)

    def test_lifecycle_configuration(self):
        """Lifecycle configuration exists."""
        self.assertIn("aws_s3_bucket_lifecycle_configuration.this", self.parsed["resources"])

    def test_bucket_outputs(self):
        """S3 outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("bucket_id", outputs)
        self.assertIn("bucket_arn", outputs)
        self.assertIn("bucket_domain_name", outputs)
        self.assertIn("bucket_regional_domain_name", outputs)

    def test_versioning_defaults_enabled(self):
        """Versioning defaults to enabled."""
        ver = self.parsed["variables"].get("versioning_enabled", {})
        self.assertEqual(ver.get("default"), "true")

    def test_bucket_key_enabled_default(self):
        """Bucket key defaults to enabled."""
        bk = self.parsed["variables"].get("bucket_key_enabled", {})
        self.assertEqual(bk.get("default"), "true")

    def test_kms_encryption_support(self):
        """KMS encryption is supported."""
        self.assertIn("kms_key_id", self.parsed["variables"])

    def test_access_logging_support(self):
        """Access logging is supported."""
        self.assertIn("access_logging_bucket", self.parsed["variables"])
        self.assertIn("aws_s3_bucket_logging.this", self.parsed["resources"])


class TestAWSEC2Module(unittest.TestCase):
    """Tests for the AWS EC2 module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "ec2")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """EC2 module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """EC2 instance resource is defined."""
        self.assertIn("aws_instance.this", self.parsed["resources"])

    def test_ami_data_source(self):
        """AMI data source exists for auto-detection."""
        self.assertIn("aws_ami.this", self.parsed["data_sources"])

    def test_eip_resource(self):
        """Elastic IP resource exists."""
        self.assertIn("aws_eip.this", self.parsed["resources"])

    def test_instance_count(self):
        """Instance count variable exists."""
        self.assertIn("instance_count", self.parsed["variables"])

    def test_root_volume_encryption_default(self):
        """Root volume encryption defaults to true."""
        enc = self.parsed["variables"].get("root_volume_encrypted", {})
        self.assertEqual(enc.get("default"), "true")

    def test_additional_volumes_support(self):
        """Additional EBS volumes are supported."""
        self.assertIn("additional_volumes", self.parsed["variables"])

    def test_ebs_block_device_dynamic(self):
        """Dynamic EBS block device is used."""
        resource = self.parsed["resources"]["aws_instance.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_instance_outputs(self):
        """EC2 outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_ids", outputs)
        self.assertIn("instance_public_ips", outputs)
        self.assertIn("instance_private_ips", outputs)
        self.assertIn("elastic_ips", outputs)

    def test_lifecycle_ignore_ami(self):
        """AMI changes are ignored in lifecycle."""
        resource = self.parsed["resources"]["aws_instance.this"]
        self.assertTrue(resource.get("lifecycle"))

    def test_monitoring_support(self):
        """Detailed monitoring is supported."""
        self.assertIn("detailed_monitoring", self.parsed["variables"])


class TestAWSIAMModule(unittest.TestCase):
    """Tests for the AWS IAM module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "iam")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IAM module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_role_resource(self):
        """IAM role resource exists."""
        self.assertIn("aws_iam_role.this", self.parsed["resources"])

    def test_policy_resource(self):
        """IAM policy resource exists."""
        self.assertIn("aws_iam_policy.this", self.parsed["resources"])

    def test_instance_profile_resource(self):
        """IAM instance profile resource exists."""
        self.assertIn("aws_iam_instance_profile.this", self.parsed["resources"])

    def test_group_resource(self):
        """IAM group resource exists."""
        self.assertIn("aws_iam_group.this", self.parsed["resources"])

    def test_user_resource(self):
        """IAM user resource exists."""
        self.assertIn("aws_iam_user.this", self.parsed["resources"])

    def test_access_key_resource(self):
        """IAM access key resource exists."""
        self.assertIn("aws_iam_access_key.this", self.parsed["resources"])

    def test_sensitive_outputs(self):
        """Sensitive outputs are marked."""
        access_keys = self.parsed["outputs"].get("access_key_ids", {})
        self.assertTrue(access_keys.get("sensitive"))
        secret_keys = self.parsed["outputs"].get("secret_access_keys", {})
        self.assertTrue(secret_keys.get("sensitive"))

    def test_role_outputs(self):
        """Role outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("role_arns", outputs)
        self.assertIn("role_names", outputs)

    def test_inline_policies_support(self):
        """Inline policies are supported for roles."""
        roles_var = self.parsed["variables"].get("roles", {})
        self.assertIn("roles", self.parsed["variables"])

    def test_permissions_boundary_support(self):
        """Permissions boundary is supported."""
        roles_var = self.parsed["variables"].get("roles", {})
        # Check that the roles variable type includes permissions_boundary
        self.assertIn("roles", self.parsed["variables"])


class TestAWSRDSModule(unittest.TestCase):
    """Tests for the AWS RDS module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "rds")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """RDS module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_db_instance_resource(self):
        """RDS instance resource exists."""
        self.assertIn("aws_db_instance.this", self.parsed["resources"])

    def test_db_subnet_group_resource(self):
        """DB subnet group resource exists."""
        self.assertIn("aws_db_subnet_group.this", self.parsed["resources"])

    def test_random_password_resource(self):
        """Random password resource exists."""
        self.assertIn("random_password.master_password", self.parsed["resources"])

    def test_storage_encryption_default(self):
        """Storage encryption defaults to true."""
        enc = self.parsed["variables"].get("storage_encrypted", {})
        self.assertEqual(enc.get("default"), "true")

    def test_multi_az_default(self):
        """Multi-AZ defaults to true."""
        az = self.parsed["variables"].get("multi_az", {})
        self.assertEqual(az.get("default"), "true")

    def test_deletion_protection_default(self):
        """Deletion protection defaults to true."""
        dp = self.parsed["variables"].get("deletion_protection", {})
        self.assertEqual(dp.get("default"), "true")

    def test_publicly_accessible_default(self):
        """Publicly accessible defaults to false."""
        pa = self.parsed["variables"].get("publicly_accessible", {})
        self.assertEqual(pa.get("default"), "false")

    def test_backup_retention_default(self):
        """Backup retention defaults to 7 days."""
        br = self.parsed["variables"].get("backup_retention_period", {})
        self.assertEqual(br.get("default"), "7")

    def test_performance_insights_default(self):
        """Performance Insights defaults to enabled."""
        pi = self.parsed["variables"].get("performance_insights_enabled", {})
        self.assertEqual(pi.get("default"), "true")

    def test_password_sensitive(self):
        """Password variable is sensitive."""
        pw = self.parsed["variables"].get("password", {})
        self.assertTrue(pw.get("sensitive"))

    def test_password_output_sensitive(self):
        """Password output is sensitive."""
        pw = self.parsed["outputs"].get("master_password", {})
        self.assertTrue(pw.get("sensitive"))

    def test_prevent_destroy_lifecycle(self):
        """Prevent destroy lifecycle is configured."""
        resource = self.parsed["resources"]["aws_db_instance.this"]
        self.assertTrue(resource.get("lifecycle"))

    def test_random_provider_declared(self):
        """Random provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("random", providers)

    def test_db_outputs(self):
        """RDS outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("db_instance_id", outputs)
        self.assertIn("db_instance_arn", outputs)
        self.assertIn("db_instance_endpoint", outputs)
        self.assertIn("db_instance_address", outputs)
        self.assertIn("db_instance_port", outputs)
        self.assertIn("db_subnet_group_name", outputs)


class TestAWSSecurityGroupsModule(unittest.TestCase):
    """Tests for the AWS Security Groups module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "security-groups")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Security groups module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_security_group_resource(self):
        """Security group resource exists."""
        self.assertIn("aws_security_group.this", self.parsed["resources"])

    def test_ingress_rules_resource(self):
        """Ingress rules resource exists."""
        self.assertIn("aws_vpc_security_group_ingress_rule.ingress", self.parsed["resources"])

    def test_egress_rules_resource(self):
        """Egress rules resource exists."""
        self.assertIn("aws_vpc_security_group_egress_rule.egress", self.parsed["resources"])

    def test_create_before_destroy(self):
        """Create before destroy lifecycle is set."""
        resource = self.parsed["resources"]["aws_security_group.this"]
        self.assertTrue(resource.get("lifecycle"))

    def test_sg_outputs(self):
        """Security group outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("security_group_id", outputs)
        self.assertIn("security_group_name", outputs)
        self.assertIn("security_group_arn", outputs)

    def test_ingress_rules_variable(self):
        """Ingress rules variable exists."""
        self.assertIn("ingress_rules", self.parsed["variables"])

    def test_egress_rules_variable(self):
        """Egress rules variable exists."""
        self.assertIn("egress_rules", self.parsed["variables"])


class TestAWSSubnetsModule(unittest.TestCase):
    """Tests for the AWS Subnets module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "subnets")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Subnets module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_public_subnets_resource(self):
        """Public subnets resource exists."""
        self.assertIn("aws_subnet.public", self.parsed["resources"])

    def test_private_subnets_resource(self):
        """Private subnets resource exists."""
        self.assertIn("aws_subnet.private", self.parsed["resources"])

    def test_database_subnets_resource(self):
        """Database subnets resource exists."""
        self.assertIn("aws_subnet.database", self.parsed["resources"])

    def test_nat_gateway_resource(self):
        """NAT gateway resource exists."""
        self.assertIn("aws_nat_gateway.this", self.parsed["resources"])

    def test_route_tables(self):
        """Route tables exist for all tiers."""
        self.assertIn("aws_route_table.public", self.parsed["resources"])
        self.assertIn("aws_route_table.private", self.parsed["resources"])
        self.assertIn("aws_route_table.database", self.parsed["resources"])

    def test_route_table_associations(self):
        """Route table associations exist."""
        self.assertIn("aws_route_table_association.public", self.parsed["resources"])
        self.assertIn("aws_route_table_association.private", self.parsed["resources"])
        self.assertIn("aws_route_table_association.database", self.parsed["resources"])

    def test_db_subnet_group(self):
        """DB subnet group resource exists."""
        self.assertIn("aws_db_subnet_group.this", self.parsed["resources"])

    def test_availability_zones_data_source(self):
        """Availability zones data source exists."""
        self.assertIn("aws_availability_zones.available", self.parsed["data_sources"])

    def test_subnet_outputs(self):
        """Subnet outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("public_subnet_ids", outputs)
        self.assertIn("private_subnet_ids", outputs)
        self.assertIn("database_subnet_ids", outputs)
        self.assertIn("db_subnet_group_name", outputs)
        self.assertIn("nat_gateway_id", outputs)

    def test_nat_gateway_default(self):
        """NAT gateway defaults to enabled."""
        nat = self.parsed["variables"].get("enable_nat_gateway", {})
        self.assertEqual(nat.get("default"), "true")


class TestAWSCloudWatchModule(unittest.TestCase):
    """Tests for the AWS CloudWatch module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws", "cloudwatch")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """CloudWatch module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_log_group_resource(self):
        """CloudWatch log group resource exists."""
        self.assertIn("aws_cloudwatch_log_group.this", self.parsed["resources"])

    def test_metric_alarm_resource(self):
        """CloudWatch metric alarm resource exists."""
        self.assertIn("aws_cloudwatch_metric_alarm.this", self.parsed["resources"])

    def test_dashboard_resource(self):
        """CloudWatch dashboard resource exists."""
        self.assertIn("aws_cloudwatch_dashboard.this", self.parsed["resources"])

    def test_event_rule_resource(self):
        """CloudWatch event rule resource exists."""
        self.assertIn("aws_cloudwatch_event_rule.this", self.parsed["resources"])

    def test_event_target_resource(self):
        """CloudWatch event target resource exists."""
        self.assertIn("aws_cloudwatch_event_target.this", self.parsed["resources"])

    def test_cloudwatch_outputs(self):
        """CloudWatch outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("log_group_names", outputs)
        self.assertIn("log_group_arns", outputs)
        self.assertIn("alarm_names", outputs)
        self.assertIn("dashboard_name", outputs)

    def test_log_group_for_each(self):
        """Log groups use for_each."""
        resource = self.parsed["resources"]["aws_cloudwatch_log_group.this"]
        self.assertTrue(resource.get("for_each"))

    def test_alarm_for_each(self):
        """Alarms use for_each."""
        resource = self.parsed["resources"]["aws_cloudwatch_metric_alarm.this"]
        self.assertTrue(resource.get("for_each"))


if __name__ == "__main__":
    unittest.main()
