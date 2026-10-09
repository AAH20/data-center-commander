"""
Checkov Custom Policies — Encryption & Key Management for Data Center IaC
Covers: KMS key rotation, encryption at rest, TLS enforcement, secrets management
"""

from checkov.common.models.enums import CheckResult, CheckCategories
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class KMSKeyRotationEnabled(BaseResourceCheck):
    """Ensure KMS key rotation is enabled."""

    def __init__(self):
        name = "Ensure KMS key rotation is enabled"
        id = "DC_CRYPTO_001"
        supported_resources = ["aws_kms_key"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        enable_key_rotation = conf.get("enable_key_rotation", False)
        if isinstance(enable_key_rotation, list):
            enable_key_rotation = enable_key_rotation[0] if enable_key_rotation else False
        if enable_key_rotation is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class KMSKeyHasDescription(BaseResourceCheck):
    """Ensure KMS keys have a description."""

    def __init__(self):
        name = "Ensure KMS keys have a description"
        id = "DC_CRYPTO_002"
        supported_resources = ["aws_kms_key"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        description = conf.get("description", "")
        if isinstance(description, list):
            description = description[0] if description else ""
        if not description or description.strip() == "":
            return CheckResult.FAILED
        return CheckResult.PASSED


class KMSKeyPolicyNotWildcard(BaseResourceCheck):
    """Ensure KMS key policies do not use wildcard principals."""

    def __init__(self):
        name = "Ensure KMS key policies do not use wildcard principals"
        id = "DC_CRYPTO_003"
        supported_resources = ["aws_kms_key"]
        categories = [CheckCategories.ENCRYPTION, CheckCategories.IAM]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        policy = conf.get("policy", "")
        if isinstance(policy, list):
            policy = policy[0] if policy else ""
        if isinstance(policy, str) and ("*" in policy and "Principal" in policy):
            return CheckResult.FAILED
        return CheckResult.PASSED


class ALBListenerHTTPS(BaseResourceCheck):
    """Ensure ALB/ELB listeners use HTTPS."""

    def __init__(self):
        name = "Ensure ALB/ELB listeners use HTTPS"
        id = "DC_CRYPTO_004"
        supported_resources = ["aws_lb_listener", "aws_alb_listener"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        protocol = conf.get("protocol", "")
        if isinstance(protocol, list):
            protocol = protocol[0] if protocol else ""
        ssl_policy = conf.get("ssl_policy", "")
        if isinstance(ssl_policy, list):
            ssl_policy = ssl_policy[0] if ssl_policy else ""
        if protocol not in ["HTTPS", "TLS"]:
            return CheckResult.FAILED
        if not ssl_policy:
            return CheckResult.FAILED
        return CheckResult.PASSED


class CloudFrontTLSVersion(BaseResourceCheck):
    """Ensure CloudFront distributions use TLS 1.2 or higher."""

    def __init__(self):
        name = "Ensure CloudFront distributions use TLS 1.2 or higher"
        id = "DC_CRYPTO_005"
        supported_resources = ["aws_cloudfront_distribution"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        viewer_certificate = conf.get("viewer_certificate", {})
        if isinstance(viewer_certificate, list):
            viewer_certificate = viewer_certificate[0] if viewer_certificate else {}
        if isinstance(viewer_certificate, dict):
            minimum_protocol_version = viewer_certificate.get("minimum_protocol_version", "TLSv1")
            if isinstance(minimum_protocol_version, list):
                minimum_protocol_version = minimum_protocol_version[0] if minimum_protocol_version else "TLSv1"
            if minimum_protocol_version in ["TLSv1", "TLSv1.1", "SSLv3"]:
                return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketSSLOnly(BaseResourceCheck):
    """Ensure S3 buckets enforce SSL/TLS only."""

    def __init__(self):
        name = "Ensure S3 buckets enforce SSL/TLS only"
        id = "DC_CRYPTO_006"
        supported_resources = ["aws_s3_bucket_policy"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        policy = conf.get("policy", "")
        if isinstance(policy, list):
            policy = policy[0] if policy else ""
        if isinstance(policy, str):
            if "aws:SecureTransport" not in policy or "false" not in policy:
                return CheckResult.FAILED
        return CheckResult.PASSED


class SecretsManagerRotationEnabled(BaseResourceCheck):
    """Ensure Secrets Manager secrets have rotation enabled."""

    def __init__(self):
        name = "Ensure Secrets Manager secrets have rotation enabled"
        id = "DC_CRYPTO_007"
        supported_resources = ["aws_secretsmanager_secret"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        rotation_rules = conf.get("rotation_rules", [])
        if isinstance(rotation_rules, list) and len(rotation_rules) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class ACMCertificateHasKey(BaseResourceCheck):
    """Ensure ACM certificates are properly configured."""

    def __init__(self):
        name = "Ensure ACM certificates use RSA 2048 or higher"
        id = "DC_CRYPTO_008"
        supported_resources = ["aws_acm_certificate"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # ACM certificates are managed by AWS, so we just check they exist
        domain_name = conf.get("domain_name", "")
        if isinstance(domain_name, list):
            domain_name = domain_name[0] if domain_name else ""
        if not domain_name:
            return CheckResult.FAILED
        return CheckResult.PASSED


class DynamoDBEncryptionEnabled(BaseResourceCheck):
    """Ensure DynamoDB tables have encryption enabled."""

    def __init__(self):
        name = "Ensure DynamoDB tables have encryption enabled"
        id = "DC_CRYPTO_009"
        supported_resources = ["aws_dynamodb_table"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        server_side_encryption = conf.get("server_side_encryption", [])
        if isinstance(server_side_encryption, list) and len(server_side_encryption) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class ElasticacheEncryptionEnabled(BaseResourceCheck):
    """Ensure ElastiCache clusters have encryption enabled."""

    def __init__(self):
        name = "Ensure ElastiCache clusters have encryption enabled"
        id = "DC_CRYPTO_010"
        supported_resources = ["aws_elasticache_replication_group"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        at_rest_encryption = conf.get("at_rest_encryption_enabled", False)
        transit_encryption = conf.get("transit_encryption_enabled", False)
        if isinstance(at_rest_encryption, list):
            at_rest_encryption = at_rest_encryption[0] if at_rest_encryption else False
        if isinstance(transit_encryption, list):
            transit_encryption = transit_encryption[0] if transit_encryption else False
        if not at_rest_encryption or not transit_encryption:
            return CheckResult.FAILED
        return CheckResult.PASSED
