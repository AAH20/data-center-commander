"""Built-in compliance controls for common frameworks.

Provides a library of pre-built compliance controls for SOC 2, ISO 27001,
PCI DSS, HIPAA, and NIST 800-53. Each control is a self-contained evaluator
that checks a specific aspect of the system and returns findings.

Controls are designed to be:
- Framework-mapped (each control maps to a specific framework requirement)
- Evidence-producing (each evaluation collects evidence)
- Remediation-ready (each finding includes a remediation hint)
- Extensible (custom controls can be added alongside built-ins)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .models import (
    ComplianceStatus,
    ControlDefinition,
    Evidence,
    EvidenceType,
    Finding,
    Framework,
    Severity,
)


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------


def _collect_evidence(
    evidence_type: EvidenceType,
    source: str,
    content: Any,
    **metadata: Any,
) -> Evidence:
    """Helper to create an Evidence instance."""
    return Evidence(
        evidence_type=evidence_type,
        source=source,
        content=content,
        metadata=metadata,
    )


def _pass_finding(
    control_id: str,
    message: str,
    evidence: list[Evidence] | None = None,
) -> list[Finding]:
    """Create a passing finding."""
    return [
        Finding(
            control_id=control_id,
            status=ComplianceStatus.PASS,
            severity=Severity.INFO,
            message=message,
            evidence=tuple(evidence or []),
        )
    ]


def _fail_finding(
    control_id: str,
    message: str,
    severity: Severity = Severity.HIGH,
    evidence: list[Evidence] | None = None,
    remediation_hint: str = "",
) -> list[Finding]:
    """Create a failing finding."""
    return [
        Finding(
            control_id=control_id,
            status=ComplianceStatus.FAIL,
            severity=severity,
            message=message,
            evidence=tuple(evidence or []),
            remediation_hint=remediation_hint,
        )
    ]


# ---------------------------------------------------------------------------
# SOC 2 Controls
# ---------------------------------------------------------------------------


def _eval_soc2_cc6_1() -> list[Finding]:
    """SOC 2 CC6.1: Logical access controls are implemented."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check if authentication is configured
    auth_enabled = os.environ.get("DCC_AUTH_ENABLED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"auth_enabled": auth_enabled},
        )
    )

    if not auth_enabled:
        findings.extend(
            _fail_finding(
                "SOC2-CC6.1",
                "Authentication is not enabled",
                Severity.CRITICAL,
                evidence,
                "Set DCC_AUTH_ENABLED=true and configure authentication providers",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "SOC2-CC6.1",
                "Authentication is enabled",
                evidence,
            )
        )

    # Check for MFA configuration
    mfa_enabled = os.environ.get("DCC_MFA_ENABLED", "false").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"mfa_enabled": mfa_enabled},
        )
    )

    if not mfa_enabled:
        findings.extend(
            _fail_finding(
                "SOC2-CC6.1",
                "MFA is not enabled for administrative access",
                Severity.HIGH,
                evidence,
                "Enable MFA for all administrative accounts",
            )
        )

    return findings


def _eval_soc2_cc6_2() -> list[Finding]:
    """SOC 2 CC6.2: Access is removed when no longer needed."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check session timeout configuration
    session_timeout = os.environ.get("DCC_SESSION_TIMEOUT_MINUTES", "60")
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"session_timeout_minutes": session_timeout},
        )
    )

    try:
        timeout_val = int(session_timeout)
        if timeout_val > 240:
            findings.extend(
                _fail_finding(
                    "SOC2-CC6.2",
                    f"Session timeout ({timeout_val} min) exceeds recommended 240 minutes",
                    Severity.MEDIUM,
                    evidence,
                    "Reduce DCC_SESSION_TIMEOUT_MINUTES to 240 or less",
                )
            )
        else:
            findings.extend(
                _pass_finding(
                    "SOC2-CC6.2",
                    f"Session timeout is configured ({timeout_val} minutes)",
                    evidence,
                )
            )
    except ValueError:
        findings.extend(
            _fail_finding(
                "SOC2-CC6.2",
                f"Invalid session timeout value: {session_timeout}",
                Severity.HIGH,
                evidence,
                "Set DCC_SESSION_TIMEOUT_MINUTES to a valid integer",
            )
        )

    return findings


def _eval_soc2_cc6_3() -> list[Finding]:
    """SOC 2 CC6.3: Access is reviewed periodically."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check if audit logging is enabled
    audit_enabled = os.environ.get("DCC_AUDIT_ENABLED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"audit_enabled": audit_enabled},
        )
    )

    if not audit_enabled:
        findings.extend(
            _fail_finding(
                "SOC2-CC6.3",
                "Audit logging is not enabled",
                Severity.CRITICAL,
                evidence,
                "Set DCC_AUDIT_ENABLED=true to enable audit logging",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "SOC2-CC6.3",
                "Audit logging is enabled",
                evidence,
            )
        )

    return findings


def _eval_soc2_cc7_1() -> list[Finding]:
    """SOC 2 CC7.1: Monitoring detects anomalies."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check if monitoring is configured
    monitoring_enabled = os.environ.get("DCC_MONITORING_ENABLED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"monitoring_enabled": monitoring_enabled},
        )
    )

    if not monitoring_enabled:
        findings.extend(
            _fail_finding(
                "SOC2-CC7.1",
                "Monitoring and alerting is not enabled",
                Severity.HIGH,
                evidence,
                "Enable monitoring and configure alerting rules",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "SOC2-CC7.1",
                "Monitoring and alerting is enabled",
                evidence,
            )
        )

    return findings


def _eval_soc2_cc7_2() -> list[Finding]:
    """SOC 2 CC7.2: Incident response process is in place."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for incident response documentation
    ir_plan_path = os.environ.get("DCC_IR_PLAN_PATH", "")
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"ir_plan_path": ir_plan_path},
        )
    )

    if not ir_plan_path:
        findings.extend(
            _fail_finding(
                "SOC2-CC7.2",
                "No incident response plan path configured",
                Severity.MEDIUM,
                evidence,
                "Set DCC_IR_PLAN_PATH to the location of your incident response plan",
            )
        )
    elif not Path(ir_plan_path).exists():
        findings.extend(
            _fail_finding(
                "SOC2-CC7.2",
                f"Incident response plan not found at {ir_plan_path}",
                Severity.MEDIUM,
                evidence,
                "Ensure the incident response plan exists at the configured path",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "SOC2-CC7.2",
                "Incident response plan is configured and accessible",
                evidence,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# ISO 27001 Controls
# ---------------------------------------------------------------------------


def _eval_iso_a_9_4_1() -> list[Finding]:
    """ISO 27001 A.9.4.1: Information access restriction."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for RBAC configuration
    rbac_enabled = os.environ.get("DCC_RBAC_ENABLED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"rbac_enabled": rbac_enabled},
        )
    )

    if not rbac_enabled:
        findings.extend(
            _fail_finding(
                "ISO27001-A.9.4.1",
                "Role-based access control is not enabled",
                Severity.CRITICAL,
                evidence,
                "Enable RBAC to enforce least-privilege access",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "ISO27001-A.9.4.1",
                "Role-based access control is enabled",
                evidence,
            )
        )

    return findings


def _eval_iso_a_12_4_1() -> list[Finding]:
    """ISO 27001 A.12.4.1: Event logging."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check logging configuration
    log_level = os.environ.get("DCC_LOG_LEVEL", "INFO")
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"log_level": log_level},
        )
    )

    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level.upper() not in valid_levels:
        findings.extend(
            _fail_finding(
                "ISO27001-A.12.4.1",
                f"Invalid log level: {log_level}",
                Severity.MEDIUM,
                evidence,
                f"Set DCC_LOG_LEVEL to one of: {', '.join(sorted(valid_levels))}",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "ISO27001-A.12.4.1",
                f"Event logging is configured (level: {log_level})",
                evidence,
            )
        )

    return findings


def _eval_iso_a_14_1_1() -> list[Finding]:
    """ISO 27001 A.14.1.1: Information security requirements analysis."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for security policy documentation
    policy_path = os.environ.get("DCC_SECURITY_POLICY_PATH", "")
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"security_policy_path": policy_path},
        )
    )

    if not policy_path:
        findings.extend(
            _fail_finding(
                "ISO27001-A.14.1.1",
                "No security policy path configured",
                Severity.MEDIUM,
                evidence,
                "Set DCC_SECURITY_POLICY_PATH to your security policy document",
            )
        )
    elif not Path(policy_path).exists():
        findings.extend(
            _fail_finding(
                "ISO27001-A.14.1.1",
                f"Security policy not found at {policy_path}",
                Severity.MEDIUM,
                evidence,
                "Ensure the security policy document exists",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "ISO27001-A.14.1.1",
                "Security policy is documented and accessible",
                evidence,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# PCI DSS Controls
# ---------------------------------------------------------------------------


def _eval_pci_1_1() -> list[Finding]:
    """PCI DSS 1.1: Firewall configuration standards."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for network segmentation
    network_segmented = os.environ.get("DCC_NETWORK_SEGMENTED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"network_segmented": network_segmented},
        )
    )

    if not network_segmented:
        findings.extend(
            _fail_finding(
                "PCI-1.1",
                "Network segmentation is not enabled",
                Severity.CRITICAL,
                evidence,
                "Enable network segmentation to isolate cardholder data environment",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "PCI-1.1",
                "Network segmentation is enabled",
                evidence,
            )
        )

    return findings


def _eval_pci_3_4() -> list[Finding]:
    """PCI DSS 3.4: Render PAN unreadable."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check encryption at rest
    encryption_enabled = os.environ.get("DCC_ENCRYPTION_AT_REST", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"encryption_at_rest": encryption_enabled},
        )
    )

    if not encryption_enabled:
        findings.extend(
            _fail_finding(
                "PCI-3.4",
                "Encryption at rest is not enabled",
                Severity.CRITICAL,
                evidence,
                "Enable encryption for all stored cardholder data",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "PCI-3.4",
                "Encryption at rest is enabled",
                evidence,
            )
        )

    return findings


def _eval_pci_8_2() -> list[Finding]:
    """PCI DSS 8.2: User authentication."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check password policy
    min_password_length = os.environ.get("DCC_MIN_PASSWORD_LENGTH", "12")
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"min_password_length": min_password_length},
        )
    )

    try:
        pwd_len = int(min_password_length)
        if pwd_len < 8:
            findings.extend(
                _fail_finding(
                    "PCI-8.2",
                    f"Minimum password length ({pwd_len}) is below PCI requirement of 8",
                    Severity.HIGH,
                    evidence,
                    "Set DCC_MIN_PASSWORD_LENGTH to at least 8",
                )
            )
        else:
            findings.extend(
                _pass_finding(
                    "PCI-8.2",
                    f"Password policy meets requirements (min length: {pwd_len})",
                    evidence,
                )
            )
    except ValueError:
        findings.extend(
            _fail_finding(
                "PCI-8.2",
                f"Invalid minimum password length: {min_password_length}",
                Severity.HIGH,
                evidence,
                "Set DCC_MIN_PASSWORD_LENGTH to a valid integer",
            )
        )

    return findings


def _eval_pci_10_1() -> list[Finding]:
    """PCI DSS 10.1: Audit trail implementation."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check audit trail configuration
    audit_trail_enabled = os.environ.get("DCC_AUDIT_TRAIL_ENABLED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"audit_trail_enabled": audit_trail_enabled},
        )
    )

    if not audit_trail_enabled:
        findings.extend(
            _fail_finding(
                "PCI-10.1",
                "Audit trail is not enabled",
                Severity.CRITICAL,
                evidence,
                "Enable audit trails for all system components",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "PCI-10.1",
                "Audit trail is enabled",
                evidence,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# HIPAA Controls
# ---------------------------------------------------------------------------


def _eval_hipaa_164_312_a_1() -> list[Finding]:
    """HIPAA 164.312(a)(1): Access control."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for unique user identification
    unique_user_ids = os.environ.get("DCC_UNIQUE_USER_IDS", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"unique_user_ids": unique_user_ids},
        )
    )

    if not unique_user_ids:
        findings.extend(
            _fail_finding(
                "HIPAA-164.312(a)(1)",
                "Unique user identification is not enforced",
                Severity.CRITICAL,
                evidence,
                "Implement unique user identification for all users",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "HIPAA-164.312(a)(1)",
                "Unique user identification is enforced",
                evidence,
            )
        )

    return findings


def _eval_hipaa_164_312_e_1() -> list[Finding]:
    """HIPAA 164.312(e)(1): Transmission security."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for TLS enforcement
    tls_enforced = os.environ.get("DCC_TLS_ENFORCED", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"tls_enforced": tls_enforced},
        )
    )

    if not tls_enforced:
        findings.extend(
            _fail_finding(
                "HIPAA-164.312(e)(1)",
                "TLS is not enforced for data transmission",
                Severity.CRITICAL,
                evidence,
                "Enforce TLS 1.2+ for all data transmission",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "HIPAA-164.312(e)(1)",
                "TLS is enforced for data transmission",
                evidence,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# NIST 800-53 Controls
# ---------------------------------------------------------------------------


def _eval_nist_ac_2() -> list[Finding]:
    """NIST 800-53 AC-2: Account management."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for account management process
    account_mgmt_enabled = os.environ.get("DCC_ACCOUNT_MANAGEMENT", "true").lower() == "true"
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"account_management": account_mgmt_enabled},
        )
    )

    if not account_mgmt_enabled:
        findings.extend(
            _fail_finding(
                "NIST-AC-2",
                "Account management process is not enabled",
                Severity.HIGH,
                evidence,
                "Implement account management procedures",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "NIST-AC-2",
                "Account management process is enabled",
                evidence,
            )
        )

    return findings


def _eval_nist_audit_1() -> list[Finding]:
    """NIST 800-53 AU-1: Audit policy."""
    findings: list[Finding] = []
    evidence: list[Evidence] = []

    # Check for audit policy
    audit_policy_path = os.environ.get("DCC_AUDIT_POLICY_PATH", "")
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "environment",
            {"audit_policy_path": audit_policy_path},
        )
    )

    if not audit_policy_path:
        findings.extend(
            _fail_finding(
                "NIST-AU-1",
                "No audit policy path configured",
                Severity.MEDIUM,
                evidence,
                "Set DCC_AUDIT_POLICY_PATH to your audit policy document",
            )
        )
    elif not Path(audit_policy_path).exists():
        findings.extend(
            _fail_finding(
                "NIST-AU-1",
                f"Audit policy not found at {audit_policy_path}",
                Severity.MEDIUM,
                evidence,
                "Ensure the audit policy document exists",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "NIST-AU-1",
                "Audit policy is documented and accessible",
                evidence,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Control registry
# ---------------------------------------------------------------------------


def get_builtin_controls() -> list[ControlDefinition]:
    """Return all built-in compliance controls.

    Returns
    -------
    list[ControlDefinition]
        All built-in controls for all supported frameworks.
    """
    return [
        # SOC 2
        ControlDefinition(
            control_id="SOC2-CC6.1",
            framework=Framework.SOC2,
            title="Logical Access Controls",
            description="Verifies that logical access controls are implemented and MFA is enabled",
            severity=Severity.CRITICAL,
            evaluator=_eval_soc2_cc6_1,
            tags=["access-control", "authentication", "mfa"],
        ),
        ControlDefinition(
            control_id="SOC2-CC6.2",
            framework=Framework.SOC2,
            title="Access Removal",
            description="Verifies that access is removed when no longer needed",
            severity=Severity.HIGH,
            evaluator=_eval_soc2_cc6_2,
            tags=["access-control", "session-management"],
        ),
        ControlDefinition(
            control_id="SOC2-CC6.3",
            framework=Framework.SOC2,
            title="Access Review",
            description="Verifies that access is reviewed periodically via audit logging",
            severity=Severity.CRITICAL,
            evaluator=_eval_soc2_cc6_3,
            tags=["access-control", "audit"],
        ),
        ControlDefinition(
            control_id="SOC2-CC7.1",
            framework=Framework.SOC2,
            title="Anomaly Detection",
            description="Verifies that monitoring detects anomalies",
            severity=Severity.HIGH,
            evaluator=_eval_soc2_cc7_1,
            tags=["monitoring", "alerting"],
        ),
        ControlDefinition(
            control_id="SOC2-CC7.2",
            framework=Framework.SOC2,
            title="Incident Response",
            description="Verifies that an incident response process is in place",
            severity=Severity.MEDIUM,
            evaluator=_eval_soc2_cc7_2,
            tags=["incident-response"],
        ),
        # ISO 27001
        ControlDefinition(
            control_id="ISO27001-A.9.4.1",
            framework=Framework.ISO27001,
            title="Information Access Restriction",
            description="Verifies that information access is restricted per policy",
            severity=Severity.CRITICAL,
            evaluator=_eval_iso_a_9_4_1,
            tags=["access-control", "rbac"],
        ),
        ControlDefinition(
            control_id="ISO27001-A.12.4.1",
            framework=Framework.ISO27001,
            title="Event Logging",
            description="Verifies that event logging is configured",
            severity=Severity.MEDIUM,
            evaluator=_eval_iso_a_12_4_1,
            tags=["logging", "audit"],
        ),
        ControlDefinition(
            control_id="ISO27001-A.14.1.1",
            framework=Framework.ISO27001,
            title="Security Requirements Analysis",
            description="Verifies that security requirements are documented",
            severity=Severity.MEDIUM,
            evaluator=_eval_iso_a_14_1_1,
            tags=["documentation", "policy"],
        ),
        # PCI DSS
        ControlDefinition(
            control_id="PCI-1.1",
            framework=Framework.PCI_DSS,
            title="Firewall Configuration",
            description="Verifies that firewall configuration standards are maintained",
            severity=Severity.CRITICAL,
            evaluator=_eval_pci_1_1,
            tags=["network", "firewall"],
        ),
        ControlDefinition(
            control_id="PCI-3.4",
            framework=Framework.PCI_DSS,
            title="PAN Protection",
            description="Verifies that PAN is rendered unreadable",
            severity=Severity.CRITICAL,
            evaluator=_eval_pci_3_4,
            tags=["encryption", "data-protection"],
        ),
        ControlDefinition(
            control_id="PCI-8.2",
            framework=Framework.PCI_DSS,
            title="User Authentication",
            description="Verifies that user authentication meets requirements",
            severity=Severity.HIGH,
            evaluator=_eval_pci_8_2,
            tags=["authentication", "password-policy"],
        ),
        ControlDefinition(
            control_id="PCI-10.1",
            framework=Framework.PCI_DSS,
            title="Audit Trail",
            description="Verifies that audit trails are implemented",
            severity=Severity.CRITICAL,
            evaluator=_eval_pci_10_1,
            tags=["audit", "logging"],
        ),
        # HIPAA
        ControlDefinition(
            control_id="HIPAA-164.312(a)(1)",
            framework=Framework.HIPAA,
            title="Access Control",
            description="Verifies that access controls are implemented",
            severity=Severity.CRITICAL,
            evaluator=_eval_hipaa_164_312_a_1,
            tags=["access-control", "phi"],
        ),
        ControlDefinition(
            control_id="HIPAA-164.312(e)(1)",
            framework=Framework.HIPAA,
            title="Transmission Security",
            description="Verifies that transmission security is enforced",
            severity=Severity.CRITICAL,
            evaluator=_eval_hipaa_164_312_e_1,
            tags=["encryption", "tls", "phi"],
        ),
        # NIST 800-53
        ControlDefinition(
            control_id="NIST-AC-2",
            framework=Framework.NIST_800_53,
            title="Account Management",
            description="Verifies that account management is implemented",
            severity=Severity.HIGH,
            evaluator=_eval_nist_ac_2,
            tags=["account-management", "access-control"],
        ),
        ControlDefinition(
            control_id="NIST-AU-1",
            framework=Framework.NIST_800_53,
            title="Audit Policy",
            description="Verifies that audit policy is documented",
            severity=Severity.MEDIUM,
            evaluator=_eval_nist_audit_1,
            tags=["audit", "policy"],
        ),
    ]


def get_controls_by_framework(framework: Framework) -> list[ControlDefinition]:
    """Get all built-in controls for a specific framework."""
    return [c for c in get_builtin_controls() if c.framework == framework]
