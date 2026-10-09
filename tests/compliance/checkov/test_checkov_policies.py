"""
Checkov Policy Tests — Data Center Commander
Tests for Checkov custom policies.
These tests validate that Checkov policies correctly enforce data center governance rules.
"""

import os
import sys
import pytest
import importlib.util

# Add the checkov policies directory to the path for direct module loading
CHECKOV_POLICY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "policies", "checkov")

# Ensure the installed checkov package takes precedence over the local directory
# Remove any path entries that point to the local checkov policies directory
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != os.path.abspath(CHECKOV_POLICY_DIR)]

from checkov.common.models.enums import CheckResult, CheckCategories
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


def load_checkov_module(module_name: str):
    """Load a checkov policy module directly from file."""
    module_path = os.path.join(CHECKOV_POLICY_DIR, "terraform", f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCheckovNetworkSecurity:
    """Tests for Checkov network security policies."""

    def test_rdp_port_not_publicly_accessible(self):
        """Test DC_NET_001: RDP port 3389 not publicly accessible."""
        mod = load_checkov_module("network_security")
        check = mod.RDPPortNotPubliclyAccessible()

        # Should pass - no public RDP
        conf = {
            "ingress": [{
                "from_port": 443,
                "to_port": 443,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - public RDP
        conf = {
            "ingress": [{
                "from_port": 3389,
                "to_port": 3389,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ssh_port_not_publicly_accessible(self):
        """Test DC_NET_002: SSH port 22 not publicly accessible."""
        mod = load_checkov_module("network_security")
        check = mod.SSHPortNotPubliclyAccessible()

        # Should pass - no public SSH
        conf = {
            "ingress": [{
                "from_port": 443,
                "to_port": 443,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - public SSH
        conf = {
            "ingress": [{
                "from_port": 22,
                "to_port": 22,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_database_port_not_publicly_accessible(self):
        """Test DC_NET_003: Database ports not publicly accessible."""
        mod = load_checkov_module("network_security")
        check = mod.DatabasePortNotPubliclyAccessible()

        # Should pass - no public database ports
        conf = {
            "ingress": [{
                "from_port": 443,
                "to_port": 443,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - public MySQL port
        conf = {
            "ingress": [{
                "from_port": 3306,
                "to_port": 3306,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_vpc_flow_logs_enabled(self):
        """Test DC_NET_004: VPC flow logs enabled."""
        mod = load_checkov_module("network_security")
        check = mod.VPCFlowLogsEnabled()

        # Should pass - flow log resource exists
        conf = {"traffic_type": "ALL"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - VPC without flow logs
        conf = {"tags": {}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_network_acl_restricted(self):
        """Test DC_NET_005: NACLs do not allow unrestricted traffic."""
        mod = load_checkov_module("network_security")
        check = mod.NetworkACLRestricted()

        # Should pass - restricted CIDR
        conf = {"cidr_block": "10.0.0.0/8", "rule_action": "allow"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - unrestricted CIDR
        conf = {"cidr_block": "0.0.0.0/0", "rule_action": "allow"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_subnet_has_private_ip(self):
        """Test DC_NET_006: Subnets do not auto-assign public IPs."""
        mod = load_checkov_module("network_security")
        check = mod.SubnetHasPrivateIP()

        # Should pass - no public IP
        conf = {"map_public_ip_on_launch": False}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - public IP
        conf = {"map_public_ip_on_launch": True}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_vpc_endpoint_enabled(self):
        """Test DC_NET_007: VPC endpoints configured."""
        mod = load_checkov_module("network_security")
        check = mod.VPCEndpointEnabled()

        # Should pass - endpoint exists
        conf = {"service_name": "com.amazonaws.us-east-1.s3"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no service name
        conf = {"service_name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_security_group_has_description(self):
        """Test DC_NET_008: Security groups have descriptions."""
        mod = load_checkov_module("network_security")
        check = mod.SecurityGroupHasDescription()

        # Should pass - has description
        conf = {"description": "Allow HTTPS traffic"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no description
        conf = {"description": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_no_wildcard_cidr(self):
        """Test DC_NET_009: No wildcard CIDR for non-web ports."""
        mod = load_checkov_module("network_security")
        check = mod.NoWildcardCIDR()

        # Should pass - web port with wildcard
        conf = {
            "ingress": [{
                "from_port": 443,
                "to_port": 443,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - non-web port with wildcard
        conf = {
            "ingress": [{
                "from_port": 8081,
                "to_port": 8081,
                "cidr_blocks": ["0.0.0.0/0"],
            }]
        }
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_transit_gateway_auto_accept_disabled(self):
        """Test DC_NET_010: Transit gateway does not auto-accept shared attachments."""
        mod = load_checkov_module("network_security")
        check = mod.TransitGatewayHasAutoAcceptDisabled()

        # Should pass - auto accept disabled
        conf = {"auto_accept_shared_attachments": "disable"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - auto accept enabled
        conf = {"auto_accept_shared_attachments": "enable"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovComputeSecurity:
    """Tests for Checkov compute security policies."""

    def test_ec2_instance_metadata_options(self):
        """Test DC_COMPUTE_001: EC2 instances require IMDSv2."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceMetadataOptions()

        # Should pass - IMDSv2 required
        conf = {"metadata_options": {"http_tokens": "required"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - IMDSv1
        conf = {"metadata_options": {"http_tokens": "optional"}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ec2_instance_detailed_monitoring(self):
        """Test DC_COMPUTE_002: EC2 detailed monitoring enabled."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceDetailedMonitoring()

        # Should pass - monitoring enabled
        conf = {"monitoring": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - monitoring disabled
        conf = {"monitoring": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ec2_instance_no_public_ip(self):
        """Test DC_COMPUTE_003: EC2 instances do not have public IPs."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceNoPublicIP()

        # Should pass - no public IP
        conf = {"associate_public_ip_address": False}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - public IP
        conf = {"associate_public_ip_address": True}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ec2_instance_encrypted_root_volume(self):
        """Test DC_COMPUTE_004: EC2 root EBS volumes encrypted."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceEncryptedRootVolume()

        # Should pass - encrypted
        conf = {"root_block_device": {"encrypted": True}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - not encrypted
        conf = {"root_block_device": {"encrypted": False}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ec2_instance_no_hardcoded_credentials(self):
        """Test DC_COMPUTE_005: No hardcoded credentials in user data."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceNoHardcodedCredentials()

        # Should pass - no credentials
        conf = {"user_data": "#!/bin/bash\necho hello"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - contains password
        conf = {"user_data": "#!/bin/bash\npassword=secret123"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_auto_scaling_group_health_check(self):
        """Test DC_COMPUTE_006: Auto Scaling health checks enabled."""
        mod = load_checkov_module("compute_security")
        check = mod.AutoScalingGroupHealthCheck()

        # Should pass - health check configured
        conf = {"health_check_type": "ELB"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no health check
        conf = {"health_check_type": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_auto_scaling_group_tags(self):
        """Test DC_COMPUTE_007: Auto Scaling groups tagged."""
        mod = load_checkov_module("compute_security")
        check = mod.AutoScalingGroupTags()

        # Should pass - has tags
        conf = {"tag": [{"key": "Name", "value": "test"}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no tags
        conf = {"tag": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_launch_template_has_security_groups(self):
        """Test DC_COMPUTE_008: Launch templates specify security groups."""
        mod = load_checkov_module("compute_security")
        check = mod.LaunchTemplateHasSecurityGroups()

        # Should pass - has security groups
        conf = {"vpc_security_group_ids": ["sg-12345"]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no security groups
        conf = {"vpc_security_group_ids": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ec2_instance_tenancy(self):
        """Test DC_COMPUTE_009: EC2 dedicated tenancy."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceTenancy()

        # Should pass - dedicated tenancy
        conf = {"tenancy": "dedicated"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - default tenancy
        conf = {"tenancy": "default"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ec2_instance_no_burstable(self):
        """Test DC_COMPUTE_010: No burstable instances for production."""
        mod = load_checkov_module("compute_security")
        check = mod.EC2InstanceNoInstanceTypeT2Micro()

        # Should pass - non-burstable instance
        conf = {"instance_type": "m5.large"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - burstable instance
        conf = {"instance_type": "t2.micro"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovStorageSecurity:
    """Tests for Checkov storage security policies."""

    def test_ebs_encryption_enabled(self):
        """Test DC_STORAGE_001: EBS volumes encrypted."""
        mod = load_checkov_module("storage_security")
        check = mod.EBSEncryptionEnabled()

        # Should pass - encrypted
        conf = {"encrypted": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - not encrypted
        conf = {"encrypted": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_ebs_snapshot_encrypted(self):
        """Test DC_STORAGE_002: EBS snapshots encrypted."""
        mod = load_checkov_module("storage_security")
        check = mod.EBSSnapshotEncrypted()

        # Should pass - encrypted
        conf = {"encrypted": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - not encrypted
        conf = {"encrypted": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_encryption_enabled(self):
        """Test DC_STORAGE_003: S3 default encryption enabled."""
        mod = load_checkov_module("storage_security")
        check = mod.S3BucketEncryptionEnabled()

        # Should pass - encryption configured
        conf = {"server_side_encryption_configuration": [{"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no encryption
        conf = {"server_side_encryption_configuration": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_public_access_block(self):
        """Test DC_STORAGE_004: S3 public access blocked."""
        mod = load_checkov_module("storage_security")
        check = mod.S3BucketPublicAccessBlock()

        # Should pass - all blocks enabled
        conf = {
            "block_public_acls": True,
            "block_public_policy": True,
            "ignore_public_acls": True,
            "restrict_public_buckets": True,
        }
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - missing blocks
        conf = {
            "block_public_acls": True,
            "block_public_policy": False,
            "ignore_public_acls": True,
            "restrict_public_buckets": True,
        }
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_versioning_enabled(self):
        """Test DC_STORAGE_005: S3 versioning enabled."""
        mod = load_checkov_module("storage_security")
        check = mod.S3BucketVersioningEnabled()

        # Should pass - versioning enabled
        conf = {"versioning": {"enabled": True}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - versioning disabled
        conf = {"versioning": {"enabled": False}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_logging_enabled(self):
        """Test DC_STORAGE_006: S3 logging enabled."""
        mod = load_checkov_module("storage_security")
        check = mod.S3BucketLoggingEnabled()

        # Should pass - logging configured
        conf = {"logging": {"target_bucket": "log-bucket"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no logging
        conf = {"logging": {}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_rds_encryption_enabled(self):
        """Test DC_STORAGE_007: RDS storage encryption enabled."""
        mod = load_checkov_module("storage_security")
        check = mod.RDSEncryptionEnabled()

        # Should pass - encrypted
        conf = {"storage_encrypted": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - not encrypted
        conf = {"storage_encrypted": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_rds_backup_retention_enabled(self):
        """Test DC_STORAGE_008: RDS backup retention configured."""
        mod = load_checkov_module("storage_security")
        check = mod.RDSBackupRetentionEnabled()

        # Should pass - retention >= 7 days
        conf = {"backup_retention_period": 7}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - retention < 7 days
        conf = {"backup_retention_period": 3}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_rds_not_publicly_accessible(self):
        """Test DC_STORAGE_009: RDS not publicly accessible."""
        mod = load_checkov_module("storage_security")
        check = mod.RDSPubliclyAccessible()

        # Should pass - not publicly accessible
        conf = {"publicly_accessible": False}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - publicly accessible
        conf = {"publicly_accessible": True}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_object_lock_enabled(self):
        """Test DC_STORAGE_010: S3 object lock enabled."""
        mod = load_checkov_module("storage_security")
        check = mod.S3BucketObjectLockEnabled()

        # Should pass - object lock enabled
        conf = {"object_lock_enabled": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - object lock disabled
        conf = {"object_lock_enabled": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovEncryption:
    """Tests for Checkov encryption policies."""

    def test_kms_key_rotation_enabled(self):
        """Test DC_CRYPTO_001: KMS key rotation enabled."""
        mod = load_checkov_module("encryption")
        check = mod.KMSKeyRotationEnabled()

        # Should pass - rotation enabled
        conf = {"enable_key_rotation": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - rotation disabled
        conf = {"enable_key_rotation": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_kms_key_has_description(self):
        """Test DC_CRYPTO_002: KMS keys have descriptions."""
        mod = load_checkov_module("encryption")
        check = mod.KMSKeyHasDescription()

        # Should pass - has description
        conf = {"description": "My KMS key"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no description
        conf = {"description": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_kms_key_policy_not_wildcard(self):
        """Test DC_CRYPTO_003: KMS key policies no wildcard principals."""
        mod = load_checkov_module("encryption")
        check = mod.KMSKeyPolicyNotWildcard()

        # Should pass - no wildcard
        conf = {"policy": '{"Principal": {"AWS": "arn:aws:iam::123456789012:user/test"}}'}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - wildcard principal
        conf = {"policy": '{"Principal": "*"}'}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_alb_listener_https(self):
        """Test DC_CRYPTO_004: ALB/ELB listeners use HTTPS."""
        mod = load_checkov_module("encryption")
        check = mod.ALBListenerHTTPS()

        # Should pass - HTTPS with SSL policy
        conf = {"protocol": "HTTPS", "ssl_policy": "ELBSecurityPolicy-2016-08"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - HTTP
        conf = {"protocol": "HTTP", "ssl_policy": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cloudfront_tls_version(self):
        """Test DC_CRYPTO_005: CloudFront TLS 1.2+."""
        mod = load_checkov_module("encryption")
        check = mod.CloudFrontTLSVersion()

        # Should pass - TLS 1.2
        conf = {"viewer_certificate": {"minimum_protocol_version": "TLSv1.2"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - TLS 1.0
        conf = {"viewer_certificate": {"minimum_protocol_version": "TLSv1"}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_ssl_only(self):
        """Test DC_CRYPTO_006: S3 buckets enforce SSL/TLS."""
        mod = load_checkov_module("encryption")
        check = mod.S3BucketSSLOnly()

        # Should pass - SSL enforced
        conf = {"policy": '{"Condition": {"Bool": {"aws:SecureTransport": "false"}}}'}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no SSL enforcement
        conf = {"policy": '{"Condition": {}}'}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_secrets_manager_rotation_enabled(self):
        """Test DC_CRYPTO_007: Secrets Manager rotation enabled."""
        mod = load_checkov_module("encryption")
        check = mod.SecretsManagerRotationEnabled()

        # Should pass - rotation configured
        conf = {"rotation_rules": [{"automatically_after_days": 30}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no rotation
        conf = {"rotation_rules": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_acm_certificate_has_key(self):
        """Test DC_CRYPTO_008: ACM certificates configured."""
        mod = load_checkov_module("encryption")
        check = mod.ACMCertificateHasKey()

        # Should pass - has domain name
        conf = {"domain_name": "example.com"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no domain name
        conf = {"domain_name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_dynamodb_encryption_enabled(self):
        """Test DC_CRYPTO_009: DynamoDB encryption enabled."""
        mod = load_checkov_module("encryption")
        check = mod.DynamoDBEncryptionEnabled()

        # Should pass - encryption configured
        conf = {"server_side_encryption": [{"enabled": True}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no encryption
        conf = {"server_side_encryption": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_elasticache_encryption_enabled(self):
        """Test DC_CRYPTO_010: ElastiCache encryption enabled."""
        mod = load_checkov_module("encryption")
        check = mod.ElasticacheEncryptionEnabled()

        # Should pass - both encryptions enabled
        conf = {"at_rest_encryption_enabled": True, "transit_encryption_enabled": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - missing encryption
        conf = {"at_rest_encryption_enabled": False, "transit_encryption_enabled": True}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovIAM:
    """Tests for Checkov IAM policies."""

    def test_iam_policy_not_wildcard(self):
        """Test DC_IAM_001: No wildcard actions in IAM policies."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMPolicyNotWildcard()

        # Should pass - no wildcard
        conf = {"policy": '{"Action": "s3:GetObject"}'}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - wildcard action
        conf = {"policy": '{"Action": "*"}'}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_role_trust_policy_not_wildcard(self):
        """Test DC_IAM_002: No wildcard principals in trust policies."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMRoleTrustPolicyNotWildcard()

        # Should pass - no wildcard
        conf = {"assume_role_policy": '{"Principal": {"Service": "ec2.amazonaws.com"}}'}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - wildcard principal
        conf = {"assume_role_policy": '{"Principal": "*"}'}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_user_has_mfa(self):
        """Test DC_IAM_003: IAM users have MFA."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMUserHasMFA()

        # Should pass - MFA device exists
        conf = {"user_name": "test-user"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no user
        conf = {"user_name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_password_policy_strong(self):
        """Test DC_IAM_004: Strong IAM password policy."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMPasswordPolicyStrong()

        # Should pass - strong policy
        conf = {
            "minimum_password_length": 14,
            "require_symbols": True,
            "require_numbers": True,
            "require_uppercase_characters": True,
            "require_lowercase_characters": True,
        }
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - weak policy
        conf = {
            "minimum_password_length": 8,
            "require_symbols": False,
            "require_numbers": False,
            "require_uppercase_characters": False,
            "require_lowercase_characters": False,
        }
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_role_has_description(self):
        """Test DC_IAM_005: IAM roles have descriptions."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMRoleHasDescription()

        # Should pass - has description
        conf = {"description": "My role"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no description
        conf = {"description": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_group_has_users(self):
        """Test DC_IAM_006: IAM groups have users."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMGroupHasUsers()

        # Should pass - has users
        conf = {"users": ["user1", "user2"]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no users
        conf = {"users": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_policy_attached_to_group_or_role(self):
        """Test DC_IAM_007: Policies attached to groups/roles."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMPolicyAttachedToGroupOrRole()

        # Should fail - direct user attachment
        conf = {"user_name": "test-user"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_no_admin_access_policy(self):
        """Test DC_IAM_008: No AdministratorAccess policies."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMNoAdminAccessPolicy()

        # Should pass - no admin access
        conf = {"policy": '{"Action": "s3:GetObject"}'}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - admin access
        conf = {"policy": "AdministratorAccess"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_role_max_session_duration(self):
        """Test DC_IAM_009: IAM role max session duration."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMRoleMaxSessionDuration()

        # Should pass - session duration <= 3600
        conf = {"max_session_duration": 3600}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - session duration > 3600
        conf = {"max_session_duration": 7200}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_iam_policy_no_full_access(self):
        """Test DC_IAM_010: No full-access service policies."""
        mod = load_checkov_module("iam_access_control")
        check = mod.IAMPolicyNoFullAccess()

        # Should pass - no full access
        conf = {"policy": '{"Action": "s3:GetObject"}'}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - full access
        conf = {"policy": '{"Action": "s3:*"}'}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovLoggingMonitoring:
    """Tests for Checkov logging and monitoring policies."""

    def test_cloudtrail_enabled(self):
        """Test DC_MONITOR_001: CloudTrail enabled in all regions."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.CloudTrailEnabled()

        # Should pass - multi-region trail
        conf = {"is_multi_region_trail": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - single region
        conf = {"is_multi_region_trail": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cloudtrail_log_file_validation(self):
        """Test DC_MONITOR_002: CloudTrail log file validation."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.CloudTrailLogFileValidation()

        # Should pass - validation enabled
        conf = {"enable_log_file_validation": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - validation disabled
        conf = {"enable_log_file_validation": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cloudtrail_s3_bucket_logging(self):
        """Test DC_MONITOR_003: CloudTrail S3 bucket logging."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.CloudTrailS3BucketLogging()

        # Should pass - bucket configured
        conf = {"s3_bucket_name": "my-cloudtrail-bucket"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no bucket
        conf = {"s3_bucket_name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cloudwatch_log_group_retention(self):
        """Test DC_MONITOR_004: CloudWatch log retention policy."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.CloudWatchLogGroupRetention()

        # Should pass - retention >= 30 days
        conf = {"retention_in_days": 30}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - retention < 30 days
        conf = {"retention_in_days": 7}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cloudwatch_alarm_actions(self):
        """Test DC_MONITOR_005: CloudWatch alarm actions configured."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.CloudWatchAlarmActions()

        # Should pass - actions configured
        conf = {"alarm_actions": ["arn:aws:sns:us-east-1:123456789012:my-topic"]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no actions
        conf = {"alarm_actions": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_guardduty_enabled(self):
        """Test DC_MONITOR_006: GuardDuty enabled."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.GuardDutyEnabled()

        # Should pass - enabled
        conf = {"enable": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - disabled
        conf = {"enable": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_security_hub_enabled(self):
        """Test DC_MONITOR_007: Security Hub enabled."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.SecurityHubEnabled()

        # Should pass - resource exists
        conf = {}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

    def test_config_recorder_enabled(self):
        """Test DC_MONITOR_008: AWS Config recorder enabled."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.ConfigRecorderEnabled()

        # Should pass - all supported
        conf = {"recording_group": {"all_supported": True}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - not all supported
        conf = {"recording_group": {"all_supported": False}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_vpc_flow_log_traffic_type(self):
        """Test DC_MONITOR_009: VPC flow logs capture all traffic."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.VPCFlowLogTrafficType()

        # Should pass - ALL traffic
        conf = {"traffic_type": "ALL"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - ACCEPT only
        conf = {"traffic_type": "ACCEPT"}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_cloudtrail_validation(self):
        """Test DC_MONITOR_010: S3 buckets used for CloudTrail have validation."""
        mod = load_checkov_module("logging_monitoring")
        check = mod.S3BucketCloudTrailValidation()

        # Should pass - bucket exists
        conf = {"bucket": "my-cloudtrail-bucket"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no bucket
        conf = {"bucket": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovComplianceGovernance:
    """Tests for Checkov compliance and governance policies."""

    def test_resource_has_tags(self):
        """Test DC_GOV_001: Required tags present."""
        mod = load_checkov_module("compliance_governance")
        check = mod.ResourceHasTags()

        # Should pass - all required tags
        conf = {"tags": {"Environment": "prod", "Owner": "team-a", "Project": "project-x"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - missing tags
        conf = {"tags": {"Environment": "prod"}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_backup_vault_exists(self):
        """Test DC_GOV_002: AWS Backup vault exists."""
        mod = load_checkov_module("compliance_governance")
        check = mod.BackupVaultExists()

        # Should pass - vault exists
        conf = {"name": "my-backup-vault"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no vault
        conf = {"name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_backup_plan_exists(self):
        """Test DC_GOV_003: AWS Backup plan exists."""
        mod = load_checkov_module("compliance_governance")
        check = mod.BackupPlanExists()

        # Should pass - plan exists
        conf = {"rule": [{"rule_name": "daily"}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no plan
        conf = {"rule": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_environment_tag_separation(self):
        """Test DC_GOV_004: Valid environment tags."""
        mod = load_checkov_module("compliance_governance")
        check = mod.EnvironmentTagSeparation()

        # Should pass - valid environment
        conf = {"tags": {"Environment": "production"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - invalid environment
        conf = {"tags": {"Environment": "invalid"}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cost_allocation_tags(self):
        """Test DC_GOV_005: Cost allocation tags."""
        mod = load_checkov_module("compliance_governance")
        check = mod.CostAllocationTags()

        # Should pass - has cost tag
        conf = {"tags": {"CostCenter": "cc-12345"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no cost tag
        conf = {"tags": {"Name": "test"}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_lifecycle_policy(self):
        """Test DC_GOV_006: S3 lifecycle policies."""
        mod = load_checkov_module("compliance_governance")
        check = mod.S3BucketLifecyclePolicy()

        # Should pass - lifecycle rule exists
        conf = {"lifecycle_rule": [{"id": "rule1", "status": "Enabled"}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no lifecycle rule
        conf = {"lifecycle_rule": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_rds_snapshot_retention(self):
        """Test DC_GOV_007: RDS snapshot retention."""
        mod = load_checkov_module("compliance_governance")
        check = mod.RDSSnapshotRetention()

        # Should pass - retention >= 7 days
        conf = {"backup_retention_period": 7}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - retention < 7 days
        conf = {"backup_retention_period": 3}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_vpc_has_dhcp_options(self):
        """Test DC_GOV_008: VPCs have DHCP options set."""
        mod = load_checkov_module("compliance_governance")
        check = mod.VPCHasDHCPOptions()

        # Should pass - best effort check
        conf = {}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

    def test_resource_has_name(self):
        """Test DC_GOV_009: Resources have name tags."""
        mod = load_checkov_module("compliance_governance")
        check = mod.ResourceHasName()

        # Should pass - has name
        conf = {"tags": {"Name": "my-resource"}}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no name
        conf = {"tags": {"Environment": "prod"}}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_replication_enabled(self):
        """Test DC_GOV_010: S3 cross-region replication."""
        mod = load_checkov_module("compliance_governance")
        check = mod.S3BucketReplicationEnabled()

        # Should pass - replication configured
        conf = {"role": "arn:aws:iam::123456789012:role/replication"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no replication
        conf = {"role": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED


class TestCheckovDataCenterSpecific:
    """Tests for Checkov data center specific policies."""

    def test_rds_multi_az_enabled(self):
        """Test DC_DC_001: RDS Multi-AZ enabled."""
        mod = load_checkov_module("data_center_specific")
        check = mod.RDSMultiAZEnabled()

        # Should pass - Multi-AZ
        conf = {"multi_az": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - single AZ
        conf = {"multi_az": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_auto_scaling_group_multi_az(self):
        """Test DC_DC_002: Auto Scaling multi-AZ."""
        mod = load_checkov_module("data_center_specific")
        check = mod.AutoScalingGroupMultiAZ()

        # Should pass - multiple AZs
        conf = {"availability_zones": ["us-east-1a", "us-east-1b"]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - single AZ
        conf = {"availability_zones": ["us-east-1a"]}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_elb_cross_zone_load_balancing(self):
        """Test DC_DC_003: Cross-zone load balancing."""
        mod = load_checkov_module("data_center_specific")
        check = mod.ELBCrossZoneLoadBalancing()

        # Should pass - cross-zone enabled
        conf = {"cross_zone_load_balancing": True}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - cross-zone disabled
        conf = {"cross_zone_load_balancing": False}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_s3_bucket_cross_region_replication(self):
        """Test DC_DC_004: S3 cross-region replication."""
        mod = load_checkov_module("data_center_specific")
        check = mod.S3BucketCrossRegionReplication()

        # Should pass - replication rule exists
        conf = {"rule": [{"id": "rule1", "status": "Enabled"}]}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no replication rule
        conf = {"rule": []}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_dynamodb_global_tables(self):
        """Test DC_DC_005: DynamoDB global tables."""
        mod = load_checkov_module("data_center_specific")
        check = mod.DynamoDBGlobalTables()

        # Should pass - global table exists
        conf = {"name": "my-global-table"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no global table
        conf = {"name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_route53_health_check_enabled(self):
        """Test DC_DC_006: Route 53 health checks."""
        mod = load_checkov_module("data_center_specific")
        check = mod.Route53HealthCheckEnabled()

        # Should pass - health check configured
        conf = {"health_check_id": "hc-12345"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no health check
        conf = {"health_check_id": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_cloudfront_waf_enabled(self):
        """Test DC_DC_007: CloudFront WAF enabled."""
        mod = load_checkov_module("data_center_specific")
        check = mod.CloudFrontWAFEnabled()

        # Should pass - WAF configured
        conf = {"web_acl_id": "waf-12345"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no WAF
        conf = {"web_acl_id": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_shield_advanced_enabled(self):
        """Test DC_DC_008: AWS Shield Advanced."""
        mod = load_checkov_module("data_center_specific")
        check = mod.ShieldAdvancedEnabled()

        # Should pass - Shield protection exists
        conf = {"name": "my-protection"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no Shield protection
        conf = {"name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_direct_connect_has_backup(self):
        """Test DC_DC_009: Direct Connect backup."""
        mod = load_checkov_module("data_center_specific")
        check = mod.DirectConnectHasBackup()

        # Should pass - DX connection exists
        conf = {"name": "my-dx-connection"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no DX connection
        conf = {"name": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED

    def test_vpn_connection_has_redundancy(self):
        """Test DC_DC_010: VPN redundant tunnels."""
        mod = load_checkov_module("data_center_specific")
        check = mod.VPNConnectionHasRedundancy()

        # Should pass - VPN connection exists
        conf = {"customer_gateway_id": "cgw-12345"}
        assert check.scan_resource_conf(conf) == CheckResult.PASSED

        # Should fail - no VPN connection
        conf = {"customer_gateway_id": ""}
        assert check.scan_resource_conf(conf) == CheckResult.FAILED
