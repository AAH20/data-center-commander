"""
OPA/Rego Policy Tests — Shared Helpers
Common utilities for OPA policy tests.
"""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

POLICY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "policies", "rego")

OPA_BIN = "opa"


def _policy_files() -> list[str]:
    """The .rego sources to load as policy data.

    `--data <dir>` walks the WHOLE directory, so it also ingests
    `testdata/tfplan_governance/*.json` as policy documents. Those are Terraform
    plan fixtures, not policy data, and OPA cannot merge them (opa exits rc=2
    with "<fixture>: merge error"), which failed every Rego evaluation in this
    suite regardless of the input. policies/rego/selftest.sh -- the repo's own
    canonical invocation -- loads a single named .rego file for exactly this
    reason. Enumerate the policies explicitly and leave the fixtures alone.
    """
    return sorted(
        os.path.join(POLICY_DIR, name)
        for name in os.listdir(POLICY_DIR)
        if name.endswith(".rego")
    )


def run_opa(input_data: dict, package: str = "datacenter.resource_tagging") -> dict:
    """Run OPA eval against the given input and return the result.

    The `opa` CLI is an external dependency (CI installs it; a dev machine may
    not have it). Skip rather than error so the suite degrades honestly instead
    of reporting a FileNotFoundError as a policy failure.
    """
    if shutil.which(OPA_BIN) is None:
        pytest.skip("opa CLI not installed; skipping Rego policy evaluation")

    input_json = json.dumps(input_data)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(input_json)
        input_file = f.name

    try:
        argv = [OPA_BIN, "eval", "--format", "json"]
        for policy in _policy_files():
            argv += ["--data", policy]
        argv += ["--input", input_file, f"data.{package}.deny"]
        result = subprocess.run(argv, capture_output=True, text=True)
        if result.returncode != 0:
            # OPA reports parse/eval errors as JSON on stdout, so stderr alone
            # reads as empty and hides the real cause.
            detail = (result.stderr or "").strip() or (result.stdout or "").strip()
            raise RuntimeError(f"OPA eval failed (rc={result.returncode}): {detail}")
        return json.loads(result.stdout)
    finally:
        os.unlink(input_file)


def make_resource(**kwargs) -> dict:
    """Create a minimal valid resource input with overrides."""
    base = {
        "resource_id": "test-resource-001",
        "environment": "production",
        "region": "us-east-1",
        "tags": {
            "owner": "team-a",
            "cost_center": "cc-12345",
            "data_classification": "internal",
            "compliance_scope": "sox",
            "environment": "production",
            "project": "project-x",
            "team": "team-a",
            "service": "service-a",
            "version": "1.0.0",
            "created_date": "2024-01-01",
            "last_reviewed": "2024-06-01",
            "backup_policy": "daily",
            "retention_policy": "7-years",
            "disaster_recovery": "enabled",
            "business_continuity": "enabled",
            "security_assessment": "passed",
            "risk_assessment": "passed",
            "compliance_assessment": "passed",
            "audit_trail": "enabled",
            "configuration_management": "enabled",
            "asset_inventory": "tracked",
            "vulnerability_management": "enabled",
            "patch_management": "enabled",
            "capacity_management": "enabled",
            "performance_management": "enabled",
            "availability_management": "enabled",
            "service_level_agreement": "99.9%",
            "operational_level_agreement": "99.5%",
            "underpinning_contract": "signed",
            "service_catalog": "registered",
            "service_portfolio": "registered",
            "service_design_package": "approved",
            "service_transition_plan": "approved",
            "service_operation_plan": "approved",
            "continual_service_improvement_plan": "active",
            "service_reporting": "enabled",
            "service_measurement": "enabled",
            "service_level_management": "enabled",
            "service_continuity_management": "enabled",
            "it_service_continuity_management": "enabled",
            "information_security_management": "enabled",
            "supplier_management": "enabled",
            "relationship_management": "enabled",
            "design_coordination": "enabled",
            "service_asset_and_configuration_management": "enabled",
            "release_and_deployment_management": "enabled",
            "service_validation_and_testing": "enabled",
            "change_management": "enabled",
            "knowledge_management": "enabled",
            "incident_management": "enabled",
            "problem_management": "enabled",
            "event_management": "enabled",
            "request_fulfillment": "enabled",
            "access_management": "enabled",
            "service_desk": "enabled",
            "technical_management": "enabled",
            "application_management": "enabled",
            "it_operations_management": "enabled",
            "facilities_management": "enabled",
            "infrastructure_management": "enabled",
            "network_management": "enabled",
            "storage_management": "enabled",
            "database_management": "enabled",
            "middleware_management": "enabled",
            "web_management": "enabled",
            "identity_management": "enabled",
            "entitlement_management": "enabled",
            "role_management": "enabled",
            "privilege_management": "enabled",
            "policy_management": "enabled",
            "compliance_management": "enabled",
            "risk_management": "enabled",
            "audit_management": "enabled",
            "governance": "enabled",
        },
        "encryption": {
            "at_rest": True,
            "in_transit": True,
            "algorithm": "AES-256",
            "tls_version": "TLSv1.3",
            "hash_algorithm": "SHA-256",
            "mode": "GCM",
            "hmac_enabled": True,
            "key_rotation": True,
            "key_rotation_days": 90,
            "key_expiry_days": 365,
            "key_age_days": 30,
            "certificate_type": "standard",
            "certificate_expiry_days": 365,
            "certificate_key_size": 2048,
            "certificate_signature": "SHA-256",
            "certificate_key_algorithm": "RSA",
        },
        "network": {
            "segment": "isolated",
            "public_access": False,
            "waf_enabled": True,
            "ddos_protection": True,
            "cdn_enabled": True,
            "load_balancer": True,
            "health_check": True,
            "ssl_enabled": True,
            "ssl_valid": True,
            "ssl_expiry_days": 365,
            "ssl_strength": "strong",
            "ssl_version": "TLSv1.3",
            "firewall_enabled": True,
            "ids_enabled": True,
            "nacl_enabled": True,
            "security_group": True,
            "vpc_enabled": True,
            "private_subnet": True,
            "route_table": True,
            "network_interface": True,
            "dns_enabled": True,
            "syslog_enabled": True,
            "ntp_enabled": True,
            "inter_segment_traffic": False,
            "explicit_allow": True,
            "inbound_traffic": "restricted",
            "outbound_traffic": "restricted",
            "ssh_cidr": "10.0.0.0/8",
            "rdp_cidr": "10.0.0.0/8",
            "database_cidr": "10.0.0.0/8",
            "icmp_cidr": "10.0.0.0/8",
            "telnet_enabled": False,
            "ftp_enabled": False,
            "snmp_version": "v3",
            "http_enabled": False,
            "https_enabled": True,
            "sslv3_enabled": False,
            "tls_10_enabled": False,
            "tls_11_enabled": False,
            "open_ports": [],
            "unused_security_groups": 0,
            "unused_nacls": 0,
            "unused_route_tables": 0,
            "unused_network_interfaces": 0,
            "unused_elastic_ips": 0,
            "unused_vpcs": 0,
            "unused_subnets": 0,
            "unused_internet_gateways": 0,
            "unused_nat_gateways": 0,
            "unused_vpn_connections": 0,
            "unused_direct_connect": 0,
            "unused_transit_gateways": 0,
            "unused_peering_connections": 0,
            "unused_load_balancers": 0,
            "unused_auto_scaling_groups": 0,
            "unused_launch_configurations": 0,
            "unused_launch_templates": 0,
            "unused_ebs_volumes": 0,
            "unused_ebs_snapshots": 0,
            "unused_amis": 0,
        },
        "access": {
            "mfa": True,
            "privilege": "least",
            "role": "none",
        },
        "certificate": {"expiry_days": 365},
        "license": {"expiry_days": 365},
        "support": {"expiry_days": 365},
        "maintenance_window": "sun-02:00-04:00",
        "change_management": "approved",
        "incident_response": "documented",
        "disaster_recovery": "documented",
        "business_continuity": "documented",
        "security_assessment": "completed",
        "risk_assessment": "completed",
        "compliance_assessment": "completed",
        "audit_trail": "enabled",
        "configuration_management": "tracked",
        "asset_inventory": "tracked",
        "vulnerability_management": "enabled",
        "patch_management": "enabled",
        "capacity_management": "enabled",
        "performance_management": "enabled",
        "availability_management": "enabled",
        "service_level_agreement": "99.9%",
        "operational_level_agreement": "99.5%",
        "underpinning_contract": "signed",
        "service_catalog": "registered",
        "service_portfolio": "registered",
        "service_design_package": "approved",
        "service_transition_plan": "approved",
        "service_operation_plan": "approved",
        "continual_service_improvement_plan": "active",
        "service_reporting": "enabled",
        "service_measurement": "enabled",
        "service_level_management": "enabled",
        "service_continuity_management": "enabled",
        "it_service_continuity_management": "enabled",
        "information_security_management": "enabled",
        "supplier_management": "enabled",
        "relationship_management": "enabled",
        "design_coordination": "enabled",
        "service_asset_and_configuration_management": "enabled",
        "release_and_deployment_management": "enabled",
        "service_validation_and_testing": "enabled",
        "knowledge_management": "enabled",
        "incident_management": "enabled",
        "problem_management": "enabled",
        "event_management": "enabled",
        "request_fulfillment": "enabled",
        "access_management": "enabled",
        "service_desk": "enabled",
        "technical_management": "enabled",
        "application_management": "enabled",
        "it_operations_management": "enabled",
        "facilities_management": "enabled",
        "infrastructure_management": "enabled",
        "network_management": "enabled",
        "storage_management": "enabled",
        "database_management": "enabled",
        "middleware_management": "enabled",
        "web_management": "enabled",
        "identity_management": "enabled",
        "entitlement_management": "enabled",
        "role_management": "enabled",
        "privilege_management": "enabled",
        "policy_management": "enabled",
        "compliance_management": "enabled",
        "risk_management": "enabled",
        "audit_management": "enabled",
        "governance": "enabled",
    }
    base.update(kwargs)
    return base
