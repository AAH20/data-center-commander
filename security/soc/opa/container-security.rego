# OPA Rego Policy — Container Security Evaluation for Trivy Scan Results
# Data Center Commander SOC
# Version: 2.0.0
# Package: container-security
#
# This policy evaluates Trivy scan results and determines whether a container
# image should be allowed to deploy based on vulnerability thresholds,
# misconfiguration counts, and secret detection.

package container-security

import future.keywords.if
import future.keywords.in

# =============================================================================
# DEFAULT DECISION
# =============================================================================

default allow := false

# =============================================================================
# POLICY PARAMETERS
# =============================================================================

# Maximum allowed vulnerabilities by severity
max_critical := 0
max_high := 0
max_medium := 5
max_low := 10

# Maximum allowed misconfigurations
max_misconfigs := 0

# Maximum allowed secrets
max_secrets := 0

# Allowed registries
allowed_registries := {
    "docker.io/data-center-commander/",
    "ghcr.io/data-center-commander/",
    "registry.data-center-commander.local/"
}

# =============================================================================
# MAIN POLICY RULES
# =============================================================================

# Allow if all checks pass
allow if {
    not has_critical_vulnerabilities
    not has_high_vulnerabilities
    not has_too_many_medium_vulnerabilities
    not has_too_many_low_vulnerabilities
    not has_misconfigurations
    not has_secrets
    not has_forbidden_registry
    not has_missing_digest
    not has_missing_signature
    not has_missing_sbom
    not has_missing_provenance
    not has_expired_scan
    not has_forbidden_base_image
    not has_forbidden_capabilities
    not has_privileged_container
    not has_root_user
    not has_missing_seccomp
    not has_missing_apparmor
    not has_missing_selinux
    not has_missing_network_policy
    not has_missing_resource_limits
    not has_missing_health_checks
    not has_missing_encryption
    not has_missing_monitoring
    not has_missing_logging
    not has_missing_tracing
    not has_missing_autoscaling
    not has_missing_pdb
}

# =============================================================================
# VULNERABILITY CHECKS
# =============================================================================

# Check for critical vulnerabilities
has_critical_vulnerabilities if {
    input.vulnerabilities.critical > max_critical
}

# Check for high vulnerabilities
has_high_vulnerabilities if {
    input.vulnerabilities.high > max_high
}

# Check for too many medium vulnerabilities
has_too_many_medium_vulnerabilities if {
    input.vulnerabilities.medium > max_medium
}

# Check for too many low vulnerabilities
has_too_many_low_vulnerabilities if {
    input.vulnerabilities.low > max_low
}

# =============================================================================
# MISCONFIGURATION CHECKS
# =============================================================================

has_misconfigurations if {
    input.misconfigurations > max_misconfigs
}

# =============================================================================
# SECRET CHECKS
# =============================================================================

has_secrets if {
    input.secrets > max_secrets
}

# =============================================================================
# REGISTRY CHECKS
# =============================================================================

has_forbidden_registry if {
    not starts_with_any(input.image, allowed_registries)
}

# =============================================================================
# IMAGE INTEGRITY CHECKS
# =============================================================================

has_missing_digest if {
    not input.image_digest
}

has_missing_signature if {
    not input.image_signature
}

has_missing_sbom if {
    not input.sbom
}

has_missing_provenance if {
    not input.provenance
}

has_expired_scan if {
    input.scan_age_days > 30
}

# =============================================================================
# BASE IMAGE CHECKS
# =============================================================================

forbidden_base_images := {
    "latest",
    "alpine:3.18",
    "alpine:3.17",
    "debian:11",
    "ubuntu:20.04",
    "ubuntu:18.04"
}

has_forbidden_base_image if {
    some base_image in forbidden_base_images
    contains(input.base_image, base_image)
}

# =============================================================================
# CONTAINER RUNTIME CHECKS
# =============================================================================

forbidden_capabilities := {
    "SYS_ADMIN",
    "NET_ADMIN",
    "SYS_PTRACE",
    "SYS_MODULE",
    "DAC_READ_SEARCH",
    "SETUID",
    "SETGID",
    "NET_RAW",
    "SYS_TIME",
    "SYS_RESOURCE",
    "SYS_BOOT",
    "LINUX_IMMUTABLE",
    "NET_BROADCAST",
    "IPC_LOCK",
    "IPC_OWNER",
    "SYS_RAWIO",
    "SYS_CHROOT",
    "SYS_PACCT",
    "SYS_NICE",
    "SYS_CONFIG",
    "LEASE",
    "AUDIT_CONTROL",
    "AUDIT_WRITE",
    "SETFCAP",
    "MAC_ADMIN",
    "MAC_OVERRIDE",
    "SYSLOG",
    "WAKE_ALARM",
    "BLOCK_SUSPEND",
    "PERFMON",
    "BPF",
    "CHECKPOINT_RESTORE"
}

has_forbidden_capabilities if {
    some cap in input.capabilities
    cap in forbidden_capabilities
}

has_privileged_container if {
    input.privileged == true
}

has_root_user if {
    input.run_as_non_root == false
}

has_missing_seccomp if {
    input.seccomp_profile != "RuntimeDefault"
}

has_missing_apparmor if {
    input.apparmor_profile != "runtime/default"
}

has_missing_selinux if {
    not input.selinux_options
}

# =============================================================================
# NETWORK CHECKS
# =============================================================================

has_missing_network_policy if {
    not input.network_policy
}

# =============================================================================
# RESOURCE CHECKS
# =============================================================================

has_missing_resource_limits if {
    not input.resource_limits
}

# =============================================================================
# HEALTH CHECKS
# =============================================================================

has_missing_health_checks if {
    not input.liveness_probe
}

has_missing_health_checks if {
    not input.readiness_probe
}

# =============================================================================
# ENCRYPTION CHECKS
# =============================================================================

has_missing_encryption if {
    not input.encryption_at_rest
}

has_missing_encryption if {
    not input.encryption_in_transit
}

# =============================================================================
# MONITORING CHECKS
# =============================================================================

has_missing_monitoring if {
    not input.monitoring
}

has_missing_logging if {
    not input.logging
}

has_missing_tracing if {
    not input.tracing
}

# =============================================================================
# AUTOSCALING CHECKS
# =============================================================================

has_missing_autoscaling if {
    not input.hpa_configured
}

has_missing_autoscaling if {
    not input.vpa_configured
}

has_missing_pdb if {
    not input.pdb_configured
}

# =============================================================================
# VIOLATION MESSAGES
# =============================================================================

violations contains msg if {
    has_critical_vulnerabilities
    msg := sprintf("CRITICAL: Image has %d critical vulnerabilities (max: %d)", [input.vulnerabilities.critical, max_critical])
}

violations contains msg if {
    has_high_vulnerabilities
    msg := sprintf("HIGH: Image has %d high vulnerabilities (max: %d)", [input.vulnerabilities.high, max_high])
}

violations contains msg if {
    has_too_many_medium_vulnerabilities
    msg := sprintf("MEDIUM: Image has %d medium vulnerabilities (max: %d)", [input.vulnerabilities.medium, max_medium])
}

violations contains msg if {
    has_too_many_low_vulnerabilities
    msg := sprintf("LOW: Image has %d low vulnerabilities (max: %d)", [input.vulnerabilities.low, max_low])
}

violations contains msg if {
    has_misconfigurations
    msg := sprintf("HIGH: Image has %d misconfigurations (max: %d)", [input.misconfigurations, max_misconfigs])
}

violations contains msg if {
    has_secrets
    msg := sprintf("CRITICAL: Image has %d secrets (max: %d)", [input.secrets, max_secrets])
}

violations contains msg if {
    has_forbidden_registry
    msg := sprintf("CRITICAL: Image '%s' is from a forbidden registry", [input.image])
}

violations contains msg if {
    has_missing_digest
    msg := "HIGH: Image does not have a digest"
}

violations contains msg if {
    has_missing_signature
    msg := "CRITICAL: Image does not have a signature"
}

violations contains msg if {
    has_missing_sbom
    msg := "HIGH: Image does not have an SBOM"
}

violations contains msg if {
    has_missing_provenance
    msg := "HIGH: Image does not have provenance"
}

violations contains msg if {
    has_expired_scan
    msg := sprintf("MEDIUM: Scan is %d days old (max: 30)", [input.scan_age_days])
}

violations contains msg if {
    has_forbidden_base_image
    msg := sprintf("HIGH: Image uses forbidden base image '%s'", [input.base_image])
}

violations contains msg if {
    has_forbidden_capabilities
    msg := sprintf("CRITICAL: Image has forbidden capabilities: %s", [concat(", ", input.capabilities)])
}

violations contains msg if {
    has_privileged_container
    msg := "CRITICAL: Container runs in privileged mode"
}

violations contains msg if {
    has_root_user
    msg := "HIGH: Container runs as root"
}

violations contains msg if {
    has_missing_seccomp
    msg := "HIGH: Container does not have seccomp profile"
}

violations contains msg if {
    has_missing_apparmor
    msg := "MEDIUM: Container does not have AppArmor profile"
}

violations contains msg if {
    has_missing_selinux
    msg := "MEDIUM: Container does not have SELinux options"
}

violations contains msg if {
    has_missing_network_policy
    msg := "HIGH: Pod does not have network policy"
}

violations contains msg if {
    has_missing_resource_limits
    msg := "MEDIUM: Container does not have resource limits"
}

violations contains msg if {
    has_missing_health_checks
    msg := "MEDIUM: Container does not have health checks"
}

violations contains msg if {
    has_missing_encryption
    msg := "HIGH: Encryption is not configured"
}

violations contains msg if {
    has_missing_monitoring
    msg := "MEDIUM: Monitoring is not configured"
}

violations contains msg if {
    has_missing_logging
    msg := "MEDIUM: Logging is not configured"
}

violations contains msg if {
    has_missing_tracing
    msg := "LOW: Tracing is not configured"
}

violations contains msg if {
    has_missing_autoscaling
    msg := "LOW: Autoscaling is not configured"
}

violations contains msg if {
    has_missing_pdb
    msg := "LOW: Pod Disruption Budget is not configured"
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

starts_with_any(str, prefixes) if {
    some prefix in prefixes
    startswith(str, prefix)
}

# =============================================================================
# METADATA
# =============================================================================

metadata := {
    "policy": "container-security",
    "version": "2.0.0",
    "description": "Container security policy for Data Center Commander",
    "author": "Security Team",
    "created": "2026-09-29"
}
