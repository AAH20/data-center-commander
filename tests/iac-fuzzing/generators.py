"""
Shared fuzzing generators for IaC fuzzing suite.

Provides hypothesis strategies and atheris-compatible generators for
fuzzing Terraform variables, policy inputs, and IaC configurations.
"""

import json
import random
import string
from typing import Any, Dict, List, Optional

from hypothesis import strategies as st


# ─── Terraform Variable Generators ───────────────────────────────────────────

TERRAFORM_PRIMITIVES = st.one_of(
    st.text(min_size=0, max_size=256),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
)

TERRAFORM_STRING_VALUES = st.one_of(
    st.text(alphabet=string.ascii_letters + string.digits + "-_./:@", min_size=0, max_size=128),
    st.sampled_from([
        "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
        "production", "staging", "dev", "test",
        "true", "false", "null", "undefined",
        "", " ", "\n", "\t",
        "0", "-1", "999999999",
        "0.0.0.0/0", "::/0", "10.0.0.0/8", "172.16.0.0/12",
        "admin", "root", "user", "guest",
        "password", "secret", "api_key", "access_key",
        "AES-256", "DES", "3DES", "RC4", "MD5", "SHA-1",
        "TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3", "SSLv3",
        "ECB", "CBC", "GCM",
        "sensitive", "confidential", "restricted", "public",
        "isolated", "restricted", "public",
        "least", "admin", "read", "write", "read-write",
        "enabled", "disabled", "enable", "disable",
    ]),
)

TERRAFORM_LIST_VALUES = st.lists(
    TERRAFORM_STRING_VALUES,
    min_size=0,
    max_size=10,
)

TERRAFORM_MAP_VALUES = st.dictionaries(
    keys=st.text(alphabet=string.ascii_letters + "_-", min_size=1, max_size=32),
    values=TERRAFORM_STRING_VALUES,
    min_size=0,
    max_size=10,
)

# Common Terraform variable names
TERRAFORM_VARIABLE_NAMES = st.sampled_from([
    "region", "environment", "project", "owner", "team",
    "instance_type", "ami_id", "vpc_id", "subnet_id",
    "availability_zones", "cidr_block", "port", "protocol",
    "encrypted", "multi_az", "publicly_accessible",
    "backup_retention_period", "monitoring_enabled",
    "tags", "name", "description", "version",
    "admin_password", "db_name", "db_username",
    "storage_encrypted", "deletion_protection",
    "ssl_policy", "certificate_arn", "domain_name",
    "log_retention_days", "enable_logging",
    "waf_enabled", "ddos_protection", "cdn_enabled",
    "data_classification", "compliance_scope",
    "cost_center", "department", "billing",
    "mfa_enabled", "password_policy",
    "key_rotation", "algorithm", "hash_algorithm",
    "tls_version", "mode", "hmac_enabled",
    "certificate_type", "certificate_key_size",
    "network_segment", "public_access",
    "firewall_enabled", "ids_enabled", "nacl_enabled",
    "ssh_cidr", "rdp_cidr", "database_cidr",
    "telnet_enabled", "ftp_enabled", "snmp_version",
    "http_enabled", "https_enabled",
    "sslv3_enabled", "tls_10_enabled", "tls_11_enabled",
    "open_ports", "unused_security_groups",
    "inter_segment_traffic", "explicit_allow",
    "inbound_traffic", "outbound_traffic",
    "retention_days", "max_retention_days",
    "last_review_days", "backup_enabled",
    "logging_enabled", "monitoring_enabled",
    "certificate_expiry_days", "license_expiry_days",
    "support_expiry_days", "maintenance_window",
    "change_management", "incident_response",
    "disaster_recovery", "business_continuity",
    "security_assessment", "risk_assessment",
    "compliance_assessment", "audit_trail",
    "configuration_management", "asset_inventory",
    "vulnerability_management", "patch_management",
    "capacity_management", "performance_management",
    "availability_management", "service_level_agreement",
    "operational_level_agreement", "underpinning_contract",
    "service_catalog", "service_portfolio",
    "service_design_package", "service_transition_plan",
    "service_operation_plan", "continual_service_improvement_plan",
    "service_reporting", "service_measurement",
    "service_level_management", "service_continuity_management",
    "it_service_continuity_management",
    "information_security_management",
    "supplier_management", "relationship_management",
    "design_coordination",
    "service_asset_and_configuration_management",
    "release_and_deployment_management",
    "service_validation_and_testing",
    "knowledge_management", "incident_management",
    "problem_management", "event_management",
    "request_fulfillment", "access_management",
    "service_desk", "technical_management",
    "application_management", "it_operations_management",
    "facilities_management", "infrastructure_management",
    "network_management", "storage_management",
    "database_management", "middleware_management",
    "web_management", "identity_management",
    "entitlement_management", "role_management",
    "privilege_management", "policy_management",
    "compliance_management", "risk_management",
    "audit_management", "governance",
    "resource_id", "access_role",
    "ssl_enabled", "ssl_valid", "ssl_expiry_days",
    "ssl_strength", "ssl_version",
    "waf_enabled", "ddos_protection", "cdn_enabled",
    "load_balancer", "health_check",
    "vpc_enabled", "private_subnet", "route_table",
    "network_interface", "dns_enabled", "syslog_enabled",
    "ntp_enabled",
    "key_expiry_days", "key_age_days",
    "certificate_signature", "certificate_key_algorithm",
    "certificate_expiry_days",
    "hash_algorithm", "key_rotation_days",
    "unused_nacls", "unused_route_tables",
    "unused_network_interfaces", "unused_elastic_ips",
    "unused_vpcs", "unused_subnets",
    "unused_internet_gateways", "unused_nat_gateways",
    "unused_vpn_connections", "unused_direct_connect",
    "unused_transit_gateways", "unused_peering_connections",
    "unused_load_balancers", "unused_auto_scaling_groups",
    "unused_launch_configurations", "unused_launch_templates",
    "unused_ebs_volumes", "unused_ebs_snapshots", "unused_amis",
    "icmp_cidr",
    "gre-tunnel", "ipsec-tunnel", "vxlan", "geneve",
    "stt", "nvgre", "mpls", "sd-wan",
    "ssh", "rdp", "ftp", "sftp", "scp", "tftp",
    "telnet", "snmp", "icmp", "dns", "dhcp", "ntp",
    "syslog", "netflow", "sflow", "ipfix",
    "vpn", "api", "webhook", "callback", "redirect",
    "proxy", "tunnel",
    "service-account", "contractor", "temp",
    "vendor", "partner", "external",
    "anonymous", "public", "guest",
    "default", "custom", "read-only", "read-write",
    "full", "superuser", "owner", "root",
    "write", "read",
    "admin",
])

# ─── Terraform Variable Strategy ─────────────────────────────────────────────

@st.composite
def terraform_variable(draw):
    """Generate a Terraform variable definition."""
    name = draw(TERRAFORM_VARIABLE_NAMES)
    var_type = draw(st.sampled_from([
        "string", "number", "bool", "list", "map", "object", "tuple", "set",
    ]))
    default = draw(st.one_of(
        TERRAFORM_STRING_VALUES,
        TERRAFORM_LIST_VALUES,
        TERRAFORM_MAP_VALUES,
        st.dictionaries(
            keys=st.text(alphabet=string.ascii_letters + "_-", min_size=1, max_size=32),
            values=TERRAFORM_STRING_VALUES,
            min_size=0,
            max_size=5,
        ),
    ))
    return {
        "name": name,
        "type": var_type,
        "default": default,
        "description": draw(st.text(max_size=256)),
        "sensitive": draw(st.booleans()),
        "nullable": draw(st.booleans()),
    }


@st.composite
def terraform_variables(draw, min_vars=1, max_vars=20):
    """Generate a set of Terraform variables."""
    count = draw(st.integers(min_value=min_vars, max_value=max_vars))
    return draw(st.lists(terraform_variable(), min_size=count, max_size=count))


# ─── Policy Input Generators ─────────────────────────────────────────────────

POLICY_RESOURCE_IDS = st.sampled_from([
    "aws_instance.web", "aws_db_instance.primary", "aws_s3_bucket.data",
    "aws_security_group.ssh", "aws_vpc.main", "aws_subnet.private",
    "aws_iam_role.admin", "aws_iam_policy.readonly",
    "aws_kms_key.encryption", "aws_cloudtrail.audit",
    "aws_guardduty_detector.main", "aws_config_configuration_recorder.default",
    "aws_backup_vault.critical", "aws_backup_plan.daily",
    "aws_route53_record.api", "aws_cloudfront_distribution.cdn",
    "aws_shield_protection.ddos", "aws_dx_connection.backup",
    "aws_vpn_connection.primary", "aws_ec2_transit_gateway.main",
    "aws_network_acl_rule.allow_ssh", "aws_flow_log.vpc",
    "aws_cloudwatch_log_group.app", "aws_cloudwatch_metric_alarm.cpu",
    "aws_secretsmanager_secret.db_password", "aws_acm_certificate.api",
    "aws_dynamodb_table.sessions", "aws_elasticache_replication_group.cache",
    "aws_ebs_volume.data", "aws_ebs_snapshot.backup",
    "aws_s3_bucket_public_access_block.strict",
    "aws_s3_bucket_replication_configuration.dr",
    "aws_dynamodb_global_table.sessions",
    "aws_autoscaling_group.web", "aws_lb_listener.https",
    "aws_alb_listener.https", "aws_elb.classic",
    "aws_launch_template.web", "aws_launch_configuration.web",
    "aws_iam_virtual_mfa_device.user1",
    "aws_iam_account_password_policy.strict",
    "aws_iam_group_membership.admins",
    "aws_iam_user_policy_attachment.direct",
    "aws_iam_role_policy.custom", "aws_iam_group_policy.custom",
    "aws_iam_user_policy.custom",
    "aws_rds_cluster.aurora",
    "aws_s3_bucket_policy.ssl_only",
    "aws_vpc_endpoint.s3", "aws_vpc_flow_log.main",
    "aws_security_group_rule.ssh",
    "azurerm_network_security_group.main",
    "google_compute_firewall.allow_ssh",
    "aws_ec2_transit_gateway.main",
    "aws_shield_protection.ddos",
    "aws_dx_connection.backup",
    "aws_vpn_connection.primary",
    "aws_network_acl_rule.deny_all",
    "aws_subnet.public",
    "aws_vpc.main",
    "aws_flow_log.vpc",
    "aws_cloudwatch_log_group.app",
    "aws_cloudwatch_metric_alarm.cpu",
    "aws_guardduty_detector.main",
    "aws_securityhub_account.main",
    "aws_config_configuration_recorder.default",
    "aws_backup_vault.critical",
    "aws_backup_plan.daily",
    "aws_route53_record.api",
    "aws_cloudfront_distribution.cdn",
    "aws_shield_protection.ddos",
    "aws_dx_connection.backup",
    "aws_vpn_connection.primary",
    "aws_ec2_transit_gateway.main",
    "aws_network_acl_rule.allow_ssh",
    "aws_flow_log.vpc",
    "aws_cloudwatch_log_group.app",
    "aws_cloudwatch_metric_alarm.cpu",
    "aws_secretsmanager_secret.db_password",
    "aws_acm_certificate.api",
    "aws_dynamodb_table.sessions",
    "aws_elasticache_replication_group.cache",
    "aws_ebs_volume.data",
    "aws_ebs_snapshot.backup",
    "aws_s3_bucket_public_access_block.strict",
    "aws_s3_bucket_replication_configuration.dr",
    "aws_dynamodb_global_table.sessions",
    "aws_autoscaling_group.web",
    "aws_lb_listener.https",
    "aws_alb_listener.https",
    "aws_elb.classic",
    "aws_launch_template.web",
    "aws_launch_configuration.web",
    "aws_iam_virtual_mfa_device.user1",
    "aws_iam_account_password_policy.strict",
    "aws_iam_group_membership.admins",
    "aws_iam_user_policy_attachment.direct",
    "aws_iam_role_policy.custom",
    "aws_iam_group_policy.custom",
    "aws_iam_user_policy.custom",
    "aws_rds_cluster.aurora",
    "aws_s3_bucket_policy.ssl_only",
    "aws_vpc_endpoint.s3",
    "aws_vpc_flow_log.main",
    "aws_security_group_rule.ssh",
    "azurerm_network_security_group.main",
    "google_compute_firewall.allow_ssh",
])

POLICY_ENVIRONMENTS = st.sampled_from([
    "production", "staging", "dev", "test", "qa",
    "prod", "development", "stage",
    "", "unknown", "PRODUCTION", "Production",
])

POLICY_REGIONS = st.sampled_from([
    "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
    "us-east-2", "us-west-1", "eu-west-2", "eu-west-3",
    "ap-southeast-1", "ap-northeast-1",
    "us-gov-west-1", "us-gov-east-1",
    "cn-north-1", "cn-northwest-1",
    "", "invalid-region", "us-east-99",
])

POLICY_TAGS = st.dictionaries(
    keys=st.sampled_from([
        "owner", "cost_center", "data_classification", "compliance_scope",
        "environment", "project", "team", "service", "version",
        "created_date", "last_reviewed", "backup_policy", "retention_policy",
        "disaster_recovery", "business_continuity", "security_assessment",
        "risk_assessment", "compliance_assessment", "audit_trail",
        "configuration_management", "asset_inventory",
        "vulnerability_management", "patch_management",
        "capacity_management", "performance_management",
        "availability_management", "service_level_agreement",
        "operational_level_agreement", "underpinning_contract",
        "service_catalog", "service_portfolio",
        "service_design_package", "service_transition_plan",
        "service_operation_plan", "continual_service_improvement_plan",
        "service_reporting", "service_measurement",
        "service_level_management", "service_continuity_management",
        "it_service_continuity_management",
        "information_security_management",
        "supplier_management", "relationship_management",
        "design_coordination",
        "service_asset_and_configuration_management",
        "release_and_deployment_management",
        "service_validation_and_testing",
        "change_management", "knowledge_management",
        "incident_management", "problem_management",
        "event_management", "request_fulfillment",
        "access_management", "service_desk",
        "technical_management", "application_management",
        "it_operations_management", "facilities_management",
        "infrastructure_management", "network_management",
        "storage_management", "database_management",
        "middleware_management", "web_management",
        "identity_management", "entitlement_management",
        "role_management", "privilege_management",
        "policy_management", "compliance_management",
        "risk_management", "audit_management", "governance",
        "Environment", "Owner", "Project", "Name",
        "CostCenter", "Billing", "Department",
    ]),
    values=st.one_of(
        st.text(max_size=64),
        st.integers(),
        st.booleans(),
    ),
    min_size=0,
    max_size=20,
)

POLICY_ENCRYPTION = st.fixed_dictionaries({
    "at_rest": st.booleans(),
    "in_transit": st.booleans(),
    "algorithm": st.sampled_from([
        "AES-256", "AES-128", "DES", "3DES", "RC4",
        "RSA", "RSA-2048", "RSA-4096", "ECC",
        "ChaCha20-Poly1305",
    ]),
    "tls_version": st.sampled_from([
        "TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3", "SSLv3",
    ]),
    "hash_algorithm": st.sampled_from([
        "MD5", "SHA-1", "SHA-256", "SHA-384", "SHA-512",
    ]),
    "mode": st.sampled_from(["ECB", "CBC", "GCM", "CTR"]),
    "hmac_enabled": st.booleans(),
    "key_rotation": st.booleans(),
    "key_rotation_days": st.integers(min_value=0, max_value=365),
    "key_expiry_days": st.integers(min_value=-30, max_value=365),
    "key_age_days": st.integers(min_value=0, max_value=730),
    "certificate_type": st.sampled_from([
        "self-signed", "wildcard", "SAN", "EV", "OV", "DV",
    ]),
    "certificate_expiry_days": st.integers(min_value=-30, max_value=365),
    "certificate_key_size": st.integers(min_value=0, max_value=8192),
    "certificate_signature": st.sampled_from([
        "SHA-1", "SHA-256", "SHA-384", "SHA-512", "MD5",
    ]),
    "certificate_key_algorithm": st.sampled_from([
        "RSA", "ECC", "DSA", "DH", "Ed25519",
    ]),
})

POLICY_NETWORK = st.fixed_dictionaries({
    "segment": st.sampled_from(["isolated", "restricted", "public"]),
    "public_access": st.booleans(),
    "waf_enabled": st.booleans(),
    "ddos_protection": st.booleans(),
    "cdn_enabled": st.booleans(),
    "load_balancer": st.booleans(),
    "health_check": st.booleans(),
    "ssl_enabled": st.booleans(),
    "ssl_valid": st.booleans(),
    "ssl_expiry_days": st.integers(min_value=-30, max_value=365),
    "ssl_strength": st.sampled_from(["weak", "medium", "strong"]),
    "ssl_version": st.sampled_from([
        "TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3", "SSLv3",
    ]),
    "firewall_enabled": st.booleans(),
    "ids_enabled": st.booleans(),
    "nacl_enabled": st.booleans(),
    "security_group": st.booleans(),
    "vpc_enabled": st.booleans(),
    "private_subnet": st.booleans(),
    "route_table": st.booleans(),
    "network_interface": st.booleans(),
    "dns_enabled": st.booleans(),
    "syslog_enabled": st.booleans(),
    "ntp_enabled": st.booleans(),
    "inter_segment_traffic": st.booleans(),
    "explicit_allow": st.booleans(),
    "inbound_traffic": st.sampled_from(["all", "restricted", "none"]),
    "outbound_traffic": st.sampled_from(["all", "restricted", "none"]),
    "ssh_cidr": st.sampled_from(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]),
    "rdp_cidr": st.sampled_from(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]),
    "database_cidr": st.sampled_from(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]),
    "icmp_cidr": st.sampled_from(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]),
    "telnet_enabled": st.booleans(),
    "ftp_enabled": st.booleans(),
    "snmp_version": st.sampled_from(["v1", "v2c", "v3"]),
    "http_enabled": st.booleans(),
    "https_enabled": st.booleans(),
    "sslv3_enabled": st.booleans(),
    "tls_10_enabled": st.booleans(),
    "tls_11_enabled": st.booleans(),
    "open_ports": st.lists(st.integers(min_value=0, max_value=65535), min_size=0, max_size=20),
    "unused_security_groups": st.integers(min_value=0, max_value=100),
    "unused_nacls": st.integers(min_value=0, max_value=100),
    "unused_route_tables": st.integers(min_value=0, max_value=100),
    "unused_network_interfaces": st.integers(min_value=0, max_value=100),
    "unused_elastic_ips": st.integers(min_value=0, max_value=100),
    "unused_vpcs": st.integers(min_value=0, max_value=100),
    "unused_subnets": st.integers(min_value=0, max_value=100),
    "unused_internet_gateways": st.integers(min_value=0, max_value=100),
    "unused_nat_gateways": st.integers(min_value=0, max_value=100),
    "unused_vpn_connections": st.integers(min_value=0, max_value=100),
    "unused_direct_connect": st.integers(min_value=0, max_value=100),
    "unused_transit_gateways": st.integers(min_value=0, max_value=100),
    "unused_peering_connections": st.integers(min_value=0, max_value=100),
    "unused_load_balancers": st.integers(min_value=0, max_value=100),
    "unused_auto_scaling_groups": st.integers(min_value=0, max_value=100),
    "unused_launch_configurations": st.integers(min_value=0, max_value=100),
    "unused_launch_templates": st.integers(min_value=0, max_value=100),
    "unused_ebs_volumes": st.integers(min_value=0, max_value=100),
    "unused_ebs_snapshots": st.integers(min_value=0, max_value=100),
    "unused_amis": st.integers(min_value=0, max_value=100),
})

POLICY_ACCESS = st.fixed_dictionaries({
    "mfa": st.booleans(),
    "privilege": st.sampled_from(["least", "admin", "read", "write", "read-write"]),
    "role": st.sampled_from([
        "admin", "root", "superuser", "owner", "full",
        "write", "read-write", "read-only", "read",
        "custom", "default", "guest", "anonymous", "public",
        "external", "partner", "vendor", "contractor", "temp",
        "service-account", "api", "webhook", "callback", "redirect",
        "proxy", "tunnel", "vpn", "ssh", "rdp", "ftp", "sftp",
        "scp", "tftp", "telnet", "snmp", "icmp", "dns", "dhcp",
        "ntp", "syslog", "netflow", "sflow", "ipfix",
        "gre-tunnel", "ipsec-tunnel", "vxlan", "geneve",
        "stt", "nvgre", "mpls", "sd-wan",
    ]),
})

POLICY_RETENTION = st.fixed_dictionaries({
    "retention_days": st.integers(min_value=0, max_value=365),
    "max_retention_days": st.integers(min_value=0, max_value=365),
    "last_review_days": st.integers(min_value=0, max_value=365),
})

POLICY_BACKUP = st.fixed_dictionaries({
    "enabled": st.booleans(),
})

POLICY_MONITORING = st.fixed_dictionaries({
    "enabled": st.booleans(),
})

POLICY_LOGGING = st.fixed_dictionaries({
    "enabled": st.booleans(),
})

POLICY_CERTIFICATE = st.fixed_dictionaries({
    "expiry_days": st.integers(min_value=-30, max_value=365),
})

POLICY_LICENSE = st.fixed_dictionaries({
    "expiry_days": st.integers(min_value=-30, max_value=365),
})

POLICY_SUPPORT = st.fixed_dictionaries({
    "expiry_days": st.integers(min_value=-30, max_value=365),
})

# Management field strategies (plain dict of strategies, not wrapped in fixed_dictionaries)
POLICY_MANAGEMENT = {
    "maintenance_window": st.text(max_size=64),
    "change_management": st.text(max_size=64),
    "incident_response": st.text(max_size=64),
    "disaster_recovery": st.text(max_size=64),
    "business_continuity": st.text(max_size=64),
    "security_assessment": st.text(max_size=64),
    "risk_assessment": st.text(max_size=64),
    "compliance_assessment": st.text(max_size=64),
    "audit_trail": st.text(max_size=64),
    "configuration_management": st.text(max_size=64),
    "asset_inventory": st.text(max_size=64),
    "vulnerability_management": st.text(max_size=64),
    "patch_management": st.text(max_size=64),
    "capacity_management": st.text(max_size=64),
    "performance_management": st.text(max_size=64),
    "availability_management": st.text(max_size=64),
    "service_level_agreement": st.text(max_size=64),
    "operational_level_agreement": st.text(max_size=64),
    "underpinning_contract": st.text(max_size=64),
    "service_catalog": st.text(max_size=64),
    "service_portfolio": st.text(max_size=64),
    "service_design_package": st.text(max_size=64),
    "service_transition_plan": st.text(max_size=64),
    "service_operation_plan": st.text(max_size=64),
    "continual_service_improvement_plan": st.text(max_size=64),
    "service_reporting": st.text(max_size=64),
    "service_measurement": st.text(max_size=64),
    "service_level_management": st.text(max_size=64),
    "service_continuity_management": st.text(max_size=64),
    "it_service_continuity_management": st.text(max_size=64),
    "information_security_management": st.text(max_size=64),
    "supplier_management": st.text(max_size=64),
    "relationship_management": st.text(max_size=64),
    "design_coordination": st.text(max_size=64),
    "service_asset_and_configuration_management": st.text(max_size=64),
    "release_and_deployment_management": st.text(max_size=64),
    "service_validation_and_testing": st.text(max_size=64),
    "knowledge_management": st.text(max_size=64),
    "incident_management": st.text(max_size=64),
    "problem_management": st.text(max_size=64),
    "event_management": st.text(max_size=64),
    "request_fulfillment": st.text(max_size=64),
    "access_management": st.text(max_size=64),
    "service_desk": st.text(max_size=64),
    "technical_management": st.text(max_size=64),
    "application_management": st.text(max_size=64),
    "it_operations_management": st.text(max_size=64),
    "facilities_management": st.text(max_size=64),
    "infrastructure_management": st.text(max_size=64),
    "network_management": st.text(max_size=64),
    "storage_management": st.text(max_size=64),
    "database_management": st.text(max_size=64),
    "middleware_management": st.text(max_size=64),
    "web_management": st.text(max_size=64),
    "identity_management": st.text(max_size=64),
    "entitlement_management": st.text(max_size=64),
    "role_management": st.text(max_size=64),
    "privilege_management": st.text(max_size=64),
    "policy_management": st.text(max_size=64),
    "compliance_management": st.text(max_size=64),
    "risk_management": st.text(max_size=64),
    "audit_management": st.text(max_size=64),
    "governance": st.text(max_size=64),
}


@st.composite
def policy_input(draw):
    """Generate a policy input document for Rego/Checkov evaluation."""
    return {
        "resource_id": draw(POLICY_RESOURCE_IDS),
        "environment": draw(POLICY_ENVIRONMENTS),
        "region": draw(POLICY_REGIONS),
        "tags": draw(POLICY_TAGS),
        "encryption": draw(POLICY_ENCRYPTION),
        "network": draw(POLICY_NETWORK),
        "access": draw(POLICY_ACCESS),
        "retention": draw(POLICY_RETENTION),
        "backup": draw(POLICY_BACKUP),
        "monitoring": draw(POLICY_MONITORING),
        "logging": draw(POLICY_LOGGING),
        "certificate": draw(POLICY_CERTIFICATE),
        "license": draw(POLICY_LICENSE),
        "support": draw(POLICY_SUPPORT),
        "maintenance_window": draw(POLICY_MANAGEMENT["maintenance_window"]),
        "change_management": draw(POLICY_MANAGEMENT["change_management"]),
        "incident_response": draw(POLICY_MANAGEMENT["incident_response"]),
        "disaster_recovery": draw(POLICY_MANAGEMENT["disaster_recovery"]),
        "business_continuity": draw(POLICY_MANAGEMENT["business_continuity"]),
        "security_assessment": draw(POLICY_MANAGEMENT["security_assessment"]),
        "risk_assessment": draw(POLICY_MANAGEMENT["risk_assessment"]),
        "compliance_assessment": draw(POLICY_MANAGEMENT["compliance_assessment"]),
        "audit_trail": draw(POLICY_MANAGEMENT["audit_trail"]),
        "configuration_management": draw(POLICY_MANAGEMENT["configuration_management"]),
        "asset_inventory": draw(POLICY_MANAGEMENT["asset_inventory"]),
        "vulnerability_management": draw(POLICY_MANAGEMENT["vulnerability_management"]),
        "patch_management": draw(POLICY_MANAGEMENT["patch_management"]),
        "capacity_management": draw(POLICY_MANAGEMENT["capacity_management"]),
        "performance_management": draw(POLICY_MANAGEMENT["performance_management"]),
        "availability_management": draw(POLICY_MANAGEMENT["availability_management"]),
        "service_level_agreement": draw(POLICY_MANAGEMENT["service_level_agreement"]),
        "operational_level_agreement": draw(POLICY_MANAGEMENT["operational_level_agreement"]),
        "underpinning_contract": draw(POLICY_MANAGEMENT["underpinning_contract"]),
        "service_catalog": draw(POLICY_MANAGEMENT["service_catalog"]),
        "service_portfolio": draw(POLICY_MANAGEMENT["service_portfolio"]),
        "service_design_package": draw(POLICY_MANAGEMENT["service_design_package"]),
        "service_transition_plan": draw(POLICY_MANAGEMENT["service_transition_plan"]),
        "service_operation_plan": draw(POLICY_MANAGEMENT["service_operation_plan"]),
        "continual_service_improvement_plan": draw(POLICY_MANAGEMENT["continual_service_improvement_plan"]),
        "service_reporting": draw(POLICY_MANAGEMENT["service_reporting"]),
        "service_measurement": draw(POLICY_MANAGEMENT["service_measurement"]),
        "service_level_management": draw(POLICY_MANAGEMENT["service_level_management"]),
        "service_continuity_management": draw(POLICY_MANAGEMENT["service_continuity_management"]),
        "it_service_continuity_management": draw(POLICY_MANAGEMENT["it_service_continuity_management"]),
        "information_security_management": draw(POLICY_MANAGEMENT["information_security_management"]),
        "supplier_management": draw(POLICY_MANAGEMENT["supplier_management"]),
        "relationship_management": draw(POLICY_MANAGEMENT["relationship_management"]),
        "design_coordination": draw(POLICY_MANAGEMENT["design_coordination"]),
        "service_asset_and_configuration_management": draw(POLICY_MANAGEMENT["service_asset_and_configuration_management"]),
        "release_and_deployment_management": draw(POLICY_MANAGEMENT["release_and_deployment_management"]),
        "service_validation_and_testing": draw(POLICY_MANAGEMENT["service_validation_and_testing"]),
        "knowledge_management": draw(POLICY_MANAGEMENT["knowledge_management"]),
        "incident_management": draw(POLICY_MANAGEMENT["incident_management"]),
        "problem_management": draw(POLICY_MANAGEMENT["problem_management"]),
        "event_management": draw(POLICY_MANAGEMENT["event_management"]),
        "request_fulfillment": draw(POLICY_MANAGEMENT["request_fulfillment"]),
        "access_management": draw(POLICY_MANAGEMENT["access_management"]),
        "service_desk": draw(POLICY_MANAGEMENT["service_desk"]),
        "technical_management": draw(POLICY_MANAGEMENT["technical_management"]),
        "application_management": draw(POLICY_MANAGEMENT["application_management"]),
        "it_operations_management": draw(POLICY_MANAGEMENT["it_operations_management"]),
        "facilities_management": draw(POLICY_MANAGEMENT["facilities_management"]),
        "infrastructure_management": draw(POLICY_MANAGEMENT["infrastructure_management"]),
        "network_management": draw(POLICY_MANAGEMENT["network_management"]),
        "storage_management": draw(POLICY_MANAGEMENT["storage_management"]),
        "database_management": draw(POLICY_MANAGEMENT["database_management"]),
        "middleware_management": draw(POLICY_MANAGEMENT["middleware_management"]),
        "web_management": draw(POLICY_MANAGEMENT["web_management"]),
        "identity_management": draw(POLICY_MANAGEMENT["identity_management"]),
        "entitlement_management": draw(POLICY_MANAGEMENT["entitlement_management"]),
        "role_management": draw(POLICY_MANAGEMENT["role_management"]),
        "privilege_management": draw(POLICY_MANAGEMENT["privilege_management"]),
        "policy_management": draw(POLICY_MANAGEMENT["policy_management"]),
        "compliance_management": draw(POLICY_MANAGEMENT["compliance_management"]),
        "risk_management": draw(POLICY_MANAGEMENT["risk_management"]),
        "audit_management": draw(POLICY_MANAGEMENT["audit_management"]),
        "governance": draw(POLICY_MANAGEMENT["governance"]),
    }


# ─── Terraform Configuration Generators ──────────────────────────────────────

TERRAFORM_RESOURCE_TYPES = st.sampled_from([
    "aws_instance", "aws_ebs_volume", "aws_ebs_snapshot",
    "aws_security_group", "aws_security_group_rule",
    "aws_vpc", "aws_subnet", "aws_vpc_flow_log", "aws_flow_log",
    "aws_db_instance", "aws_rds_cluster",
    "aws_s3_bucket", "aws_s3_bucket_policy",
    "aws_s3_bucket_public_access_block",
    "aws_s3_bucket_replication_configuration",
    "aws_iam_role", "aws_iam_policy",
    "aws_iam_role_policy", "aws_iam_group_policy", "aws_iam_user_policy",
    "aws_iam_group_membership", "aws_iam_user_policy_attachment",
    "aws_iam_virtual_mfa_device", "aws_iam_account_password_policy",
    "aws_kms_key", "aws_cloudtrail",
    "aws_guardduty_detector", "aws_securityhub_account",
    "aws_config_configuration_recorder",
    "aws_backup_vault", "aws_backup_plan",
    "aws_route53_record", "aws_cloudfront_distribution",
    "aws_shield_protection", "aws_dx_connection",
    "aws_vpn_connection", "aws_ec2_transit_gateway",
    "aws_network_acl_rule",
    "aws_cloudwatch_log_group", "aws_cloudwatch_metric_alarm",
    "aws_secretsmanager_secret", "aws_acm_certificate",
    "aws_dynamodb_table", "aws_dynamodb_global_table",
    "aws_elasticache_replication_group",
    "aws_autoscaling_group", "aws_lb_listener", "aws_alb_listener",
    "aws_elb", "aws_launch_template", "aws_launch_configuration",
    "aws_vpc_endpoint",
    "azurerm_network_security_group",
    "google_compute_firewall",
])

TERRAFORM_PROPERTY_NAMES = st.sampled_from([
    "name", "description", "tags", "region", "environment",
    "instance_type", "ami_id", "vpc_id", "subnet_id",
    "availability_zones", "cidr_block", "port", "protocol",
    "from_port", "to_port", "cidr_blocks", "source_ranges",
    "encrypted", "storage_encrypted", "multi_az",
    "publicly_accessible", "map_public_ip_on_launch",
    "backup_retention_period", "monitoring_enabled",
    "ingress", "egress", "security_rule", "allow", "deny",
    "policy", "assume_role_policy",
    "enable_key_rotation", "enable_log_file_validation",
    "is_multi_region_trail", "s3_bucket_name",
    "retention_in_days", "alarm_actions", "ok_actions",
    "insufficient_data_actions", "enable",
    "recording_group", "all_supported",
    "traffic_type", "rule", "role",
    "block_public_acls", "block_public_policy",
    "ignore_public_acls", "restrict_public_buckets",
    "versioning", "enabled", "logging",
    "object_lock_enabled", "lifecycle_rule",
    "server_side_encryption_configuration",
    "minimum_protocol_version", "ssl_policy",
    "protocol", "domain_name",
    "server_side_encryption",
    "at_rest_encryption_enabled", "transit_encryption_enabled",
    "rotation_rules",
    "health_check_type", "tag",
    "vpc_security_group_ids",
    "tenancy", "metadata_options", "http_tokens",
    "root_block_device", "user_data",
    "auto_accept_shared_attachments",
    "cross_zone_load_balancing",
    "web_acl_id", "health_check_id",
    "customer_gateway_id",
    "user_name", "minimum_password_length",
    "require_symbols", "require_numbers",
    "require_uppercase_characters", "require_lowercase_characters",
    "max_session_duration",
    "users",
    "destination_port_range", "destination_port_ranges",
    "source_address_prefix",
    "rule_action",
    "service_name",
    "bucket",
    "block_public_acls",
    "block_public_policy",
    "ignore_public_acls",
    "restrict_public_buckets",
    "versioning",
    "logging",
    "object_lock_enabled",
    "lifecycle_rule",
    "server_side_encryption_configuration",
    "minimum_protocol_version",
    "ssl_policy",
    "protocol",
    "domain_name",
    "server_side_encryption",
    "at_rest_encryption_enabled",
    "transit_encryption_enabled",
    "rotation_rules",
    "health_check_type",
    "tag",
    "vpc_security_group_ids",
    "tenancy",
    "metadata_options",
    "http_tokens",
    "root_block_device",
    "user_data",
    "auto_accept_shared_attachments",
    "cross_zone_load_balancing",
    "web_acl_id",
    "health_check_id",
    "customer_gateway_id",
    "user_name",
    "minimum_password_length",
    "require_symbols",
    "require_numbers",
    "require_uppercase_characters",
    "require_lowercase_characters",
    "max_session_duration",
    "users",
    "destination_port_range",
    "destination_port_ranges",
    "source_address_prefix",
    "rule_action",
    "service_name",
    "bucket",
])


@st.composite
def terraform_resource(draw):
    """Generate a Terraform resource configuration."""
    resource_type = draw(TERRAFORM_RESOURCE_TYPES)
    resource_name = draw(st.text(alphabet=string.ascii_letters + "_-", min_size=1, max_size=32))

    # Generate properties based on resource type
    properties = {}
    num_props = draw(st.integers(min_value=0, max_value=15))
    for _ in range(num_props):
        prop_name = draw(TERRAFORM_PROPERTY_NAMES)
        prop_value = draw(st.one_of(
            TERRAFORM_STRING_VALUES,
            TERRAFORM_LIST_VALUES,
            TERRAFORM_MAP_VALUES,
            st.dictionaries(
                keys=st.text(alphabet=string.ascii_letters + "_-", min_size=1, max_size=32),
                values=TERRAFORM_STRING_VALUES,
                min_size=0,
                max_size=5,
            ),
            st.integers(min_value=-(2**31), max_value=2**31 - 1),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.none(),
        ))
        properties[prop_name] = prop_value

    return {
        "type": resource_type,
        "name": resource_name,
        "properties": properties,
    }


@st.composite
def terraform_configuration(draw, min_resources=1, max_resources=30):
    """Generate a complete Terraform configuration."""
    count = draw(st.integers(min_value=min_resources, max_value=max_resources))
    resources = draw(st.lists(terraform_resource(), min_size=count, max_size=count))

    # Generate variables
    variables = draw(terraform_variables(min_vars=0, max_vars=10))

    # Generate outputs
    outputs = {}
    num_outputs = draw(st.integers(min_value=0, max_value=5))
    for _ in range(num_outputs):
        output_name = draw(st.text(alphabet=string.ascii_letters + "_-", min_size=1, max_size=32))
        outputs[output_name] = {
            "value": draw(st.one_of(
                TERRAFORM_STRING_VALUES,
                TERRAFORM_LIST_VALUES,
                TERRAFORM_MAP_VALUES,
            )),
            "description": draw(st.text(max_size=256)),
            "sensitive": draw(st.booleans()),
        }

    return {
        "resources": resources,
        "variables": variables,
        "outputs": outputs,
        "provider": draw(st.sampled_from(["aws", "azurerm", "google"])),
        "terraform_version": draw(st.sampled_from([">= 0.12", ">= 0.13", ">= 0.14", ">= 0.15", ">= 1.0", ">= 1.1", ">= 1.2", ">= 1.3", ">= 1.4", ">= 1.5"])),
    }


# ─── Azure Policy Generators ──────────────────────────────────────────────────

AZURE_POLICY_EFFECTS = st.sampled_from(["Deny", "Audit", "Disabled", "Append", "DeployIfNotExists", "Modify", "AuditIfNotExists"])

AZURE_POLICY_LOCATIONS = st.sampled_from([
    "eastus", "westus2", "westeurope", "northeurope",
    "eastus2", "westus", "centralus", "southcentralus",
    "northcentralus", "westcentralus", "canadacentral",
    "brazilsouth", "australiaeast", "australiasoutheast",
    "southeastasia", "northeurope", "uksouth", "ukwest",
    "francecentral", "germanynorth", "norwayeast",
    "switzerlandnorth", "uaenorth", "southafricanorth",
    "centralindia", "southindia", "westindia",
    "japaneast", "japanwest", "koreacentral",
    "koreasouth", "canadacentral", "canadaeast",
    "australiacentral", "australiacentral2",
    "australiaeast", "australiasoutheast",
    "brazilsouth", "brazilsoutheast",
    "chilecentral", "mexicocentral",
    "usgovarizona", "usgoviowa", "usgovtexas", "usgovvirginia",
    "ussecwest", "usseceast",
    "usnatwest", "usnateast",
    "usdodeast", "usdodcentral",
])


@st.composite
def azure_policy_parameter(draw):
    """Generate an Azure Policy parameter."""
    return {
        "type": draw(st.sampled_from(["String", "Array", "Object", "Boolean", "Integer", "Float", "DateTime"])),
        "metadata": {
            "displayName": draw(st.text(max_size=128)),
            "description": draw(st.text(max_size=256)),
        },
        "allowedValues": draw(st.lists(
            st.one_of(st.text(max_size=64), st.integers(), st.booleans()),
            min_size=0,
            max_size=10,
        )),
        "defaultValue": draw(st.one_of(
            st.text(max_size=64),
            st.integers(),
            st.booleans(),
            st.lists(st.text(max_size=64), min_size=0, max_size=5),
            st.dictionaries(
                keys=st.text(max_size=32),
                values=st.text(max_size=64),
                min_size=0,
                max_size=5,
            ),
        )),
    }


@st.composite
def azure_policy_definition(draw):
    """Generate an Azure Policy definition."""
    return {
        "properties": {
            "displayName": draw(st.text(max_size=128)),
            "description": draw(st.text(max_size=512)),
            "metadata": {
                "category": draw(st.sampled_from(["Security", "Networking", "Compute", "Storage", "Monitoring", "Governance"])),
                "version": draw(st.sampled_from(["1.0.0", "1.1.0", "2.0.0", "3.0.0"])),
            },
            "parameters": draw(st.dictionaries(
                keys=st.text(alphabet=string.ascii_letters + "_", min_size=1, max_size=32),
                values=azure_policy_parameter(),
                min_size=0,
                max_size=5,
            )),
            "policyType": draw(st.sampled_from(["BuiltIn", "Custom", "Static"])),
            "mode": draw(st.sampled_from(["Indexed", "All", "Microsoft.DataPlane", "Microsoft.Kubernetes.DataPlane"])),
            "policyRule": {
                "if": {
                    "field": draw(st.sampled_from([
                        "type", "location", "name", "tags", "kind",
                        "Microsoft.Storage/storageAccounts/minimumTlsVersion",
                        "Microsoft.Compute/virtualMachines/imageReference",
                    ])),
                    "equals": draw(st.text(max_size=128)),
                },
                "then": {
                    "effect": draw(AZURE_POLICY_EFFECTS),
                    "details": draw(st.one_of(
                        st.dictionaries(
                            keys=st.text(max_size=64),
                            values=st.text(max_size=128),
                            min_size=0,
                            max_size=5,
                        ),
                        st.none(),
                    )),
                },
            },
        },
    }


# ─── Atheris-compatible random generators ─────────────────────────────────────

def random_terraform_variable_dict() -> Dict[str, Any]:
    """Generate a random Terraform variable dict for atheris fuzzing."""
    return {
        "name": "".join(random.choices(string.ascii_lowercase + "_-", k=random.randint(1, 32))),
        "type": random.choice(["string", "number", "bool", "list", "map", "object"]),
        "default": random.choice([
            "".join(random.choices(string.ascii_letters + string.digits + "-_./:@", k=random.randint(0, 128))),
            random.randint(-2**31, 2**31 - 1),
            random.random() * 1000,
            random.choice([True, False, None]),
            [random.choice(["a", "b", "c", "us-east-1", "production"]) for _ in range(random.randint(0, 5))],
            {random.choice(["key", "name", "value"]): random.choice(["val1", "val2", "val3"]) for _ in range(random.randint(0, 5))},
        ]),
        "description": "".join(random.choices(string.ascii_letters + " ", k=random.randint(0, 256))),
        "sensitive": random.choice([True, False]),
        "nullable": random.choice([True, False]),
    }


def random_policy_input_dict() -> Dict[str, Any]:
    """Generate a random policy input dict for atheris fuzzing."""
    return {
        "resource_id": random.choice([
            "aws_instance.web", "aws_db_instance.primary", "aws_s3_bucket.data",
            "aws_security_group.ssh", "aws_vpc.main", "aws_subnet.private",
            "aws_iam_role.admin", "aws_kms_key.encryption",
        ]),
        "environment": random.choice(["production", "staging", "dev", "test", "prod", "development", "stage", "", "unknown"]),
        "region": random.choice(["us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "", "invalid-region"]),
        "tags": {random.choice(["owner", "cost_center", "data_classification", "environment", "project"]): random.choice(["val1", "val2", "val3"]) for _ in range(random.randint(0, 10))},
        "encryption": {
            "at_rest": random.choice([True, False]),
            "in_transit": random.choice([True, False]),
            "algorithm": random.choice(["AES-256", "DES", "3DES", "RC4", "RSA"]),
            "tls_version": random.choice(["TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3", "SSLv3"]),
            "hash_algorithm": random.choice(["MD5", "SHA-1", "SHA-256", "SHA-384"]),
            "mode": random.choice(["ECB", "CBC", "GCM", "CTR"]),
            "hmac_enabled": random.choice([True, False]),
            "key_rotation": random.choice([True, False]),
            "key_rotation_days": random.randint(0, 365),
            "key_expiry_days": random.randint(-30, 365),
            "key_age_days": random.randint(0, 730),
            "certificate_type": random.choice(["self-signed", "wildcard", "SAN", "EV", "OV", "DV"]),
            "certificate_expiry_days": random.randint(-30, 365),
            "certificate_key_size": random.randint(0, 8192),
            "certificate_signature": random.choice(["SHA-1", "SHA-256", "SHA-384", "MD5"]),
            "certificate_key_algorithm": random.choice(["RSA", "ECC", "DSA", "DH", "Ed25519"]),
        },
        "network": {
            "segment": random.choice(["isolated", "restricted", "public"]),
            "public_access": random.choice([True, False]),
            "waf_enabled": random.choice([True, False]),
            "ddos_protection": random.choice([True, False]),
            "cdn_enabled": random.choice([True, False]),
            "load_balancer": random.choice([True, False]),
            "health_check": random.choice([True, False]),
            "ssl_enabled": random.choice([True, False]),
            "ssl_valid": random.choice([True, False]),
            "ssl_expiry_days": random.randint(-30, 365),
            "ssl_strength": random.choice(["weak", "medium", "strong"]),
            "ssl_version": random.choice(["TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3", "SSLv3"]),
            "firewall_enabled": random.choice([True, False]),
            "ids_enabled": random.choice([True, False]),
            "nacl_enabled": random.choice([True, False]),
            "security_group": random.choice([True, False]),
            "vpc_enabled": random.choice([True, False]),
            "private_subnet": random.choice([True, False]),
            "route_table": random.choice([True, False]),
            "network_interface": random.choice([True, False]),
            "dns_enabled": random.choice([True, False]),
            "syslog_enabled": random.choice([True, False]),
            "ntp_enabled": random.choice([True, False]),
            "inter_segment_traffic": random.choice([True, False]),
            "explicit_allow": random.choice([True, False]),
            "inbound_traffic": random.choice(["all", "restricted", "none"]),
            "outbound_traffic": random.choice(["all", "restricted", "none"]),
            "ssh_cidr": random.choice(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12"]),
            "rdp_cidr": random.choice(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12"]),
            "database_cidr": random.choice(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12"]),
            "icmp_cidr": random.choice(["0.0.0.0/0", "10.0.0.0/8", "172.16.0.0/12"]),
            "telnet_enabled": random.choice([True, False]),
            "ftp_enabled": random.choice([True, False]),
            "snmp_version": random.choice(["v1", "v2c", "v3"]),
            "http_enabled": random.choice([True, False]),
            "https_enabled": random.choice([True, False]),
            "sslv3_enabled": random.choice([True, False]),
            "tls_10_enabled": random.choice([True, False]),
            "tls_11_enabled": random.choice([True, False]),
            "open_ports": [random.randint(0, 65535) for _ in range(random.randint(0, 10))],
            "unused_security_groups": random.randint(0, 100),
            "unused_nacls": random.randint(0, 100),
            "unused_route_tables": random.randint(0, 100),
            "unused_network_interfaces": random.randint(0, 100),
            "unused_elastic_ips": random.randint(0, 100),
            "unused_vpcs": random.randint(0, 100),
            "unused_subnets": random.randint(0, 100),
            "unused_internet_gateways": random.randint(0, 100),
            "unused_nat_gateways": random.randint(0, 100),
            "unused_vpn_connections": random.randint(0, 100),
            "unused_direct_connect": random.randint(0, 100),
            "unused_transit_gateways": random.randint(0, 100),
            "unused_peering_connections": random.randint(0, 100),
            "unused_load_balancers": random.randint(0, 100),
            "unused_auto_scaling_groups": random.randint(0, 100),
            "unused_launch_configurations": random.randint(0, 100),
            "unused_launch_templates": random.randint(0, 100),
            "unused_ebs_volumes": random.randint(0, 100),
            "unused_ebs_snapshots": random.randint(0, 100),
            "unused_amis": random.randint(0, 100),
        },
        "access": {
            "mfa": random.choice([True, False]),
            "privilege": random.choice(["least", "admin", "read", "write", "read-write"]),
            "role": random.choice(["admin", "root", "superuser", "owner", "full", "write", "read-write", "read-only", "read", "custom", "default", "guest", "anonymous", "public", "external", "partner", "vendor", "contractor", "temp", "service-account", "api", "webhook", "callback", "redirect", "proxy", "tunnel", "vpn", "ssh", "rdp", "ftp", "sftp", "scp", "tftp", "telnet", "snmp", "icmp", "dns", "dhcp", "ntp", "syslog", "netflow", "sflow", "ipfix", "gre-tunnel", "ipsec-tunnel", "vxlan", "geneve", "stt", "nvgre", "mpls", "sd-wan"]),
        },
        "retention": {
            "retention_days": random.randint(0, 365),
            "max_retention_days": random.randint(0, 365),
            "last_review_days": random.randint(0, 365),
        },
        "backup": {"enabled": random.choice([True, False])},
        "monitoring": {"enabled": random.choice([True, False])},
        "logging": {"enabled": random.choice([True, False])},
        "certificate": {"expiry_days": random.randint(-30, 365)},
        "license": {"expiry_days": random.randint(-30, 365)},
        "support": {"expiry_days": random.randint(-30, 365)},
    }


def random_terraform_resource_dict() -> Dict[str, Any]:
    """Generate a random Terraform resource dict for atheris fuzzing."""
    resource_type = random.choice([
        "aws_instance", "aws_ebs_volume", "aws_security_group", "aws_vpc",
        "aws_db_instance", "aws_s3_bucket", "aws_iam_role", "aws_kms_key",
        "aws_cloudtrail", "aws_guardduty_detector", "aws_backup_vault",
        "aws_route53_record", "aws_cloudfront_distribution", "aws_shield_protection",
        "aws_dx_connection", "aws_vpn_connection", "aws_ec2_transit_gateway",
        "aws_network_acl_rule", "aws_flow_log", "aws_cloudwatch_log_group",
        "aws_cloudwatch_metric_alarm", "aws_secretsmanager_secret",
        "aws_acm_certificate", "aws_dynamodb_table", "aws_elasticache_replication_group",
        "aws_autoscaling_group", "aws_lb_listener", "aws_launch_template",
        "aws_vpc_endpoint", "azurerm_network_security_group", "google_compute_firewall",
    ])
    properties = {}
    for _ in range(random.randint(0, 15)):
        prop_name = random.choice([
            "name", "description", "tags", "region", "environment",
            "instance_type", "ami_id", "vpc_id", "subnet_id",
            "availability_zones", "cidr_block", "port", "protocol",
            "from_port", "to_port", "cidr_blocks", "source_ranges",
            "encrypted", "storage_encrypted", "multi_az",
            "publicly_accessible", "map_public_ip_on_launch",
            "backup_retention_period", "monitoring_enabled",
            "ingress", "egress", "security_rule", "allow", "deny",
            "policy", "assume_role_policy",
            "enable_key_rotation", "enable_log_file_validation",
            "is_multi_region_trail", "s3_bucket_name",
            "retention_in_days", "alarm_actions", "ok_actions",
            "insufficient_data_actions", "enable",
            "recording_group", "all_supported",
            "traffic_type", "rule", "role",
            "block_public_acls", "block_public_policy",
            "ignore_public_acls", "restrict_public_buckets",
            "versioning", "enabled", "logging",
            "object_lock_enabled", "lifecycle_rule",
            "server_side_encryption_configuration",
            "minimum_protocol_version", "ssl_policy",
            "protocol", "domain_name",
            "server_side_encryption",
            "at_rest_encryption_enabled", "transit_encryption_enabled",
            "rotation_rules",
            "health_check_type", "tag",
            "vpc_security_group_ids",
            "tenancy", "metadata_options", "http_tokens",
            "root_block_device", "user_data",
            "auto_accept_shared_attachments",
            "cross_zone_load_balancing",
            "web_acl_id", "health_check_id",
            "customer_gateway_id",
            "user_name", "minimum_password_length",
            "require_symbols", "require_numbers",
            "require_uppercase_characters", "require_lowercase_characters",
            "max_session_duration",
            "users",
            "destination_port_range", "destination_port_ranges",
            "source_address_prefix",
            "rule_action",
            "service_name",
            "bucket",
        ])
        properties[prop_name] = random.choice([
            "".join(random.choices(string.ascii_letters + string.digits + "-_./:@", k=random.randint(0, 128))),
            random.randint(-2**31, 2**31 - 1),
            random.random() * 1000,
            random.choice([True, False, None]),
            [random.choice(["a", "b", "c", "us-east-1", "production"]) for _ in range(random.randint(0, 5))],
            {random.choice(["key", "name", "value"]): random.choice(["val1", "val2", "val3"]) for _ in range(random.randint(0, 5))},
        ])
    return {
        "type": resource_type,
        "name": "".join(random.choices(string.ascii_lowercase + "_-", k=random.randint(1, 32))),
        "properties": properties,
    }
