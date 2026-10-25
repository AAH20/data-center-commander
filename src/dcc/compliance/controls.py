"""Built-in compliance controls for common frameworks.

Provides a library of pre-built compliance controls for SOC 2, ISO 27001,
PCI DSS, HIPAA, and NIST 800-53. Each control is a self-contained evaluator
that measures something about the running system and returns findings.

WHAT A FINDING IS ALLOWED TO SAY
--------------------------------
Every control here answers a question by MEASURING the system: querying the
database the application is configured to use, reading the configuration the
application actually consumes, or loading files that ship with the deployment.
The measurement itself lives in :mod:`dcc.compliance.observables`.

Nothing here reads an environment variable in order to decide a verdict unless
the served application reads that same variable. The controls previously did the
opposite -- ``DCC_TLS_ENFORCED``, ``DCC_MFA_ENABLED``, ``DCC_AUDIT_TRAIL_ENABLED``
and twelve more were consulted by no code path, so an operator could set one and
turn a report green without changing the system. Fifteen of the sixteen controls
asserted a configuration the system ignores.

Where a fact genuinely cannot be measured from inside the application, the
control returns ``NOT_ASSESSED`` with the reason attached. That is a deliberate
outcome, not a failure to implement the control: an unmeasurable control is not a
satisfied one, and a fabricated pass is worse than a visible gap.

Each control keeps the historical ``control_id`` so existing reports and the
``/v2/compliance`` endpoints keep their identifiers.
"""
from __future__ import annotations

from typing import Any

from ..security.posture import auth_posture
from . import observables
from .models import (
    ComplianceStatus,
    ControlDefinition,
    Evidence,
    EvidenceType,
    Finding,
    Framework,
    Severity,
)
from .observables import Measurement


# ---------------------------------------------------------------------------
# Evidence and finding helpers
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


def _not_assessed_finding(
    control_id: str,
    message: str,
    severity: Severity = Severity.MEDIUM,
    evidence: list[Evidence] | None = None,
) -> list[Finding]:
    """Create a finding for a fact this environment cannot measure.

    Deliberately not a pass and deliberately not silent: the message must say what
    could not be measured and what evidence would settle it, so the gap is
    actionable rather than an unexplained blank in the report.
    """
    return [
        Finding(
            control_id=control_id,
            status=ComplianceStatus.NOT_ASSESSED,
            severity=severity,
            message=message,
            evidence=tuple(evidence or []),
        )
    ]


def _finding(
    control_id: str,
    measurement: Measurement,
    *,
    severity: Severity = Severity.HIGH,
) -> list[Finding]:
    """Turn a Measurement into the finding its verdict warrants.

    The three outcomes map one-to-one onto PASS / FAIL / NOT_ASSESSED, so a
    measurement that could not be taken can never be reported as a pass.
    """
    evidence = [
        _collect_evidence(
            measurement.evidence_type,
            measurement.source,
            dict(measurement.detail) or {"statement": measurement.statement},
        )
    ]
    if measurement.verdict is True:
        return _pass_finding(control_id, measurement.statement, evidence)
    if measurement.verdict is False:
        return _fail_finding(
            control_id,
            measurement.statement,
            severity,
            evidence,
            measurement.remediation,
        )
    return _not_assessed_finding(control_id, measurement.statement, severity, evidence)


# ---------------------------------------------------------------------------
# SOC 2 Controls
# ---------------------------------------------------------------------------


def _eval_soc2_cc6_1() -> list[Finding]:
    """SOC 2 CC6.1: Logical access controls are implemented.

    Two requirements, measured separately because only one of them is measurable.

    Authentication: read from ``dcc.security.posture``, the same module the
    served application uses to decide whether a request may proceed. This is the
    variable the application really consumes (``DCC_ALLOW_ANONYMOUS``) plus the
    key count it really loads.

    MFA: nothing in the product verifies a second factor, and no variable can
    stand in for one. It reports NOT_ASSESSED, which makes the control overall
    NOT_ASSESSED -- correct, because a control that asserts two things and can
    only measure one has not satisfied the other.
    """
    evidence: list[Evidence] = []
    findings: list[Finding] = []

    posture = auth_posture()
    evidence.append(
        _collect_evidence(
            EvidenceType.CONFIG,
            "dcc.security.posture",
            {
                "authentication_required": posture["authentication_required"],
                "anonymous_allowed": posture["anonymous_allowed"],
                "configured_keys": posture["configured_keys"],
                "locked_out": posture["locked_out"],
            },
        )
    )

    if posture["anonymous_allowed"]:
        findings.extend(
            _fail_finding(
                "SOC2-CC6.1",
                "Anonymous access is enabled; the API accepts unauthenticated requests, so "
                "there is no logical access control to report on",
                Severity.CRITICAL,
                evidence,
                "Unset DCC_ALLOW_ANONYMOUS and configure DCC_API_KEYS with at least one key",
            )
        )
    elif not posture["keys_available"]:
        findings.extend(
            _fail_finding(
                "SOC2-CC6.1",
                "Authentication is required but no API keys are configured, so every request "
                "is rejected (lockout rather than access control)",
                Severity.HIGH,
                evidence,
                "Mint a key with 'python -m dcc.keys_cli create' and set DCC_API_KEYS",
            )
        )
    else:
        findings.extend(
            _pass_finding(
                "SOC2-CC6.1",
                f"Authentication is required and {posture['configured_keys']} key(s) are "
                "configured, which is the posture the authentication middleware enforces",
                evidence,
            )
        )

    findings.extend(_finding("SOC2-CC6.1", observables.measure_mfa(), severity=Severity.HIGH))
    return findings


def _eval_soc2_cc6_2() -> list[Finding]:
    """SOC 2 CC6.2: Access is removed when no longer needed.

    Measured from credential lifecycle, not from a session-timeout setting: this
    deployment has no sessions, it has bearer keys, and the clock that matters is
    when a key stops being valid.
    """
    return _finding(
        "SOC2-CC6.2",
        observables.measure_credential_expiry(),
        severity=Severity.HIGH,
    )


def _eval_soc2_cc6_3() -> list[Finding]:
    """SOC 2 CC6.3: Access is reviewed periodically.

    A review is performed against records of access. The control therefore asks
    whether access, authentication and permission events are recorded at all -- a
    chain full of fixture rows cannot support a review however well it verifies.
    """
    return _finding(
        "SOC2-CC6.3",
        observables.measure_access_events(),
        severity=Severity.CRITICAL,
    )


def _eval_soc2_cc7_1() -> list[Finding]:
    """SOC 2 CC7.1: Monitoring detects anomalies.

    Alert rules count only if the metrics they reference are exported. A rule over
    a series nothing publishes is permanently silent while looking like coverage.
    """
    return _finding(
        "SOC2-CC7.1",
        observables.measure_alert_coverage(),
        severity=Severity.HIGH,
    )


def _eval_soc2_cc7_2() -> list[Finding]:
    """SOC 2 CC7.2: Incident response process is in place.

    The observable is the incident record itself: if it cannot hold detection,
    mitigation and resolution times, the process leaves no trail anyone can audit.
    """
    return _finding(
        "SOC2-CC7.2",
        observables.measure_incident_lifecycle(),
        severity=Severity.MEDIUM,
    )


# ---------------------------------------------------------------------------
# ISO 27001 Controls
# ---------------------------------------------------------------------------


def _eval_iso_a_9_4_1() -> list[Finding]:
    """ISO 27001 A.9.4.1: Information access restriction.

    Row-level security on every tenant-scoped table is the mechanism that
    restricts one tenant's data from another, and it is read from the catalogue
    the database maintains -- so disabling it on one table moves this control.
    """
    return _finding(
        "ISO27001-A.9.4.1",
        observables.measure_tenant_rls(),
        severity=Severity.CRITICAL,
    )


def _eval_iso_a_12_4_1() -> list[Finding]:
    """ISO 27001 A.12.4.1: Event logging.

    Logging is demonstrated by recorded events that name an actor. The old check
    read ``DCC_LOG_LEVEL``, which the logging setup does consume -- but a valid
    level name proves a level was set, not that any event was recorded.
    """
    return _finding(
        "ISO27001-A.12.4.1",
        observables.measure_event_attribution(),
        severity=Severity.MEDIUM,
    )


def _eval_iso_a_14_1_1() -> list[Finding]:
    """ISO 27001 A.14.1.1: Information security requirements analysis.

    Whether requirements were analysed is a document-review judgement. The
    measurement reports which governance documents exist and refuses to call that
    a pass.
    """
    return _finding(
        "ISO27001-A.14.1.1",
        observables.measure_policy_document(
            "Whether information security requirements were analysed"
        ),
        severity=Severity.MEDIUM,
    )


# ---------------------------------------------------------------------------
# PCI DSS Controls
# ---------------------------------------------------------------------------


def _eval_pci_1_1() -> list[Finding]:
    """PCI DSS 1.1: Firewall configuration standards.

    Segmentation is enforced by network devices this process cannot query. It is
    reported as not assessed with the reason, rather than green on the strength of
    a variable or a manifest file.
    """
    return _finding(
        "PCI-1.1",
        observables.measure_network_segmentation(),
        severity=Severity.CRITICAL,
    )


def _eval_pci_3_4() -> list[Finding]:
    """PCI DSS 3.4: Render PAN unreadable.

    At-rest encryption is a property of the storage volume; nothing in SQL reports
    it. The measurement says so explicitly instead of asserting a pass.
    """
    return _finding(
        "PCI-3.4",
        observables.measure_at_rest_encryption(),
        severity=Severity.CRITICAL,
    )


def _eval_pci_8_2() -> list[Finding]:
    """PCI DSS 8.2: User authentication.

    This deployment has no password authentication: users present bearer keys.
    The measurable requirement is therefore that each credential is a strong,
    hashed secret -- not that a password-length setting exists.
    """
    return _finding(
        "PCI-8.2",
        observables.measure_credential_strength(),
        severity=Severity.HIGH,
    )


def _eval_pci_10_1() -> list[Finding]:
    """PCI DSS 10.1: Audit trail implementation.

    An audit trail that can be edited in place is not an audit trail. The chain is
    recomputed from the stored rows with the same code the writer uses, so a
    modified, inserted or removed event fails this control.
    """
    return _finding(
        "PCI-10.1",
        observables.measure_evidence_chain(),
        severity=Severity.CRITICAL,
    )


# ---------------------------------------------------------------------------
# HIPAA Controls
# ---------------------------------------------------------------------------


def _eval_hipaa_164_312_a_1() -> list[Finding]:
    """HIPAA 164.312(a)(1): Access control.

    Unique user identification: each credential must resolve to exactly one
    existing principal. A shared hash or a credential pointing at a tenant that no
    longer exists fails, because neither identifies a user.
    """
    return _finding(
        "HIPAA-164.312(a)(1)",
        observables.measure_identity_uniqueness(),
        severity=Severity.CRITICAL,
    )


def _eval_hipaa_164_312_e_1() -> list[Finding]:
    """HIPAA 164.312(e)(1): Transmission security.

    Measured on both halves of the database link: whether the configured DSN
    refuses plaintext, and whether the live sessions actually carry TLS
    (``pg_stat_ssl``). The browser-to-API leg terminates outside this process and
    is not claimed here.
    """
    return _finding(
        "HIPAA-164.312(e)(1)",
        observables.measure_db_tls(),
        severity=Severity.CRITICAL,
    )


# ---------------------------------------------------------------------------
# NIST 800-53 Controls
# ---------------------------------------------------------------------------


def _eval_nist_ac_2() -> list[Finding]:
    """NIST 800-53 AC-2: Account management.

    ``dcc.tenants`` is the account register: it holds a lifecycle status. A
    credential belonging to a suspended account, or to no account at all, means
    account management is not operating -- and both are queryable.
    """
    return _finding(
        "NIST-AC-2",
        observables.measure_account_register(),
        severity=Severity.HIGH,
    )


def _eval_nist_audit_1() -> list[Finding]:
    """NIST 800-53 AU-1: Audit policy.

    A policy is a document and its adequacy is a review judgement. Presence of the
    governance documents is reported; a pass is not asserted from a file existing.
    """
    return _finding(
        "NIST-AU-1",
        observables.measure_policy_document(
            "Whether an audit and accountability policy exists and is followed"
        ),
        severity=Severity.MEDIUM,
    )


# ---------------------------------------------------------------------------
# Control registry
# ---------------------------------------------------------------------------

#: How each control reaches its verdict, for documentation and tests.
#: ``"measured"``    -- derived from observable system state (can pass and fail)
#: ``"not_assessed"`` -- no observable exists from inside the application
EVALUATION_BASIS: dict[str, str] = {
    "SOC2-CC6.1": "measured",  # partial: authentication measured, MFA not assessable
    "SOC2-CC6.2": "measured",
    "SOC2-CC6.3": "measured",
    "SOC2-CC7.1": "measured",
    "SOC2-CC7.2": "measured",
    "ISO27001-A.9.4.1": "measured",
    "ISO27001-A.12.4.1": "measured",
    "ISO27001-A.14.1.1": "not_assessed",
    "PCI-1.1": "not_assessed",
    "PCI-3.4": "not_assessed",
    "PCI-8.2": "measured",
    "PCI-10.1": "measured",
    "HIPAA-164.312(a)(1)": "measured",
    "HIPAA-164.312(e)(1)": "measured",
    "NIST-AC-2": "measured",
    "NIST-AU-1": "not_assessed",
}


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
            description=(
                "Measures the authentication posture the application enforces "
                "(DCC_ALLOW_ANONYMOUS plus configured keys); MFA has no observable state "
                "and is reported not assessed"
            ),
            severity=Severity.CRITICAL,
            evaluator=_eval_soc2_cc6_1,
            tags=["access-control", "authentication"],
        ),
        ControlDefinition(
            control_id="SOC2-CC6.2",
            framework=Framework.SOC2,
            title="Access Removal",
            description="Measures whether credentials expire, so access can be removed on a schedule",
            severity=Severity.HIGH,
            evaluator=_eval_soc2_cc6_2,
            tags=["access-control", "credential-lifecycle"],
        ),
        ControlDefinition(
            control_id="SOC2-CC6.3",
            framework=Framework.SOC2,
            title="Access Review",
            description="Measures whether access, authentication and permission events are recorded for review",
            severity=Severity.CRITICAL,
            evaluator=_eval_soc2_cc6_3,
            tags=["access-control", "audit"],
        ),
        ControlDefinition(
            control_id="SOC2-CC7.1",
            framework=Framework.SOC2,
            title="Anomaly Detection",
            description="Measures whether alert rules reference metrics the system actually exports",
            severity=Severity.HIGH,
            evaluator=_eval_soc2_cc7_1,
            tags=["monitoring", "alerting"],
        ),
        ControlDefinition(
            control_id="SOC2-CC7.2",
            framework=Framework.SOC2,
            title="Incident Response",
            description="Measures whether incident records can hold a detection-to-resolution timeline",
            severity=Severity.MEDIUM,
            evaluator=_eval_soc2_cc7_2,
            tags=["incident-response"],
        ),
        # ISO 27001
        ControlDefinition(
            control_id="ISO27001-A.9.4.1",
            framework=Framework.ISO27001,
            title="Information Access Restriction",
            description="Measures row-level security (ENABLE + FORCE + policy) on every tenant-scoped table",
            severity=Severity.CRITICAL,
            evaluator=_eval_iso_a_9_4_1,
            tags=["access-control", "row-level-security"],
        ),
        ControlDefinition(
            control_id="ISO27001-A.12.4.1",
            framework=Framework.ISO27001,
            title="Event Logging",
            description="Measures whether recorded events exist and name the actor who caused them",
            severity=Severity.MEDIUM,
            evaluator=_eval_iso_a_12_4_1,
            tags=["logging", "audit"],
        ),
        ControlDefinition(
            control_id="ISO27001-A.14.1.1",
            framework=Framework.ISO27001,
            title="Security Requirements Analysis",
            description=(
                "Reports which governance documents exist; whether requirements were analysed "
                "is a review judgement and is not assessed"
            ),
            severity=Severity.MEDIUM,
            evaluator=_eval_iso_a_14_1_1,
            tags=["documentation", "policy"],
        ),
        # PCI DSS
        ControlDefinition(
            control_id="PCI-1.1",
            framework=Framework.PCI_DSS,
            title="Firewall Configuration",
            description=(
                "Network segmentation is enforced outside this process and cannot be observed "
                "from it; reported not assessed with the reason"
            ),
            severity=Severity.CRITICAL,
            evaluator=_eval_pci_1_1,
            tags=["network", "firewall"],
        ),
        ControlDefinition(
            control_id="PCI-3.4",
            framework=Framework.PCI_DSS,
            title="PAN Protection",
            description=(
                "Encryption at rest is a property of the storage volume and is not observable "
                "from SQL or the process; reported not assessed with the reason"
            ),
            severity=Severity.CRITICAL,
            evaluator=_eval_pci_3_4,
            tags=["encryption", "data-protection"],
        ),
        ControlDefinition(
            control_id="PCI-8.2",
            framework=Framework.PCI_DSS,
            title="User Authentication",
            description="Measures that each configured credential is a hashed 256-bit key, not a weak or plaintext secret",
            severity=Severity.HIGH,
            evaluator=_eval_pci_8_2,
            tags=["authentication", "credential-strength"],
        ),
        ControlDefinition(
            control_id="PCI-10.1",
            framework=Framework.PCI_DSS,
            title="Audit Trail",
            description="Recomputes the evidence hash chain and fails if any row was edited, inserted or removed",
            severity=Severity.CRITICAL,
            evaluator=_eval_pci_10_1,
            tags=["audit", "integrity"],
        ),
        # HIPAA
        ControlDefinition(
            control_id="HIPAA-164.312(a)(1)",
            framework=Framework.HIPAA,
            title="Access Control",
            description="Measures that every credential identifies exactly one existing principal, with no shared hashes",
            severity=Severity.CRITICAL,
            evaluator=_eval_hipaa_164_312_a_1,
            tags=["access-control", "identity"],
        ),
        ControlDefinition(
            control_id="HIPAA-164.312(e)(1)",
            framework=Framework.HIPAA,
            title="Transmission Security",
            description="Measures the DSN's sslmode and the TLS state of live database sessions (pg_stat_ssl)",
            severity=Severity.CRITICAL,
            evaluator=_eval_hipaa_164_312_e_1,
            tags=["encryption", "tls"],
        ),
        # NIST 800-53
        ControlDefinition(
            control_id="NIST-AC-2",
            framework=Framework.NIST_800_53,
            title="Account Management",
            description="Measures that credentialed principals exist in dcc.tenants with an active lifecycle status",
            severity=Severity.HIGH,
            evaluator=_eval_nist_ac_2,
            tags=["account-management", "access-control"],
        ),
        ControlDefinition(
            control_id="NIST-AU-1",
            framework=Framework.NIST_800_53,
            title="Audit Policy",
            description=(
                "Reports which governance documents exist; policy adequacy is a review "
                "judgement and is not assessed"
            ),
            severity=Severity.MEDIUM,
            evaluator=_eval_nist_audit_1,
            tags=["audit", "policy"],
        ),
    ]


def get_controls_by_framework(framework: Framework) -> list[ControlDefinition]:
    """Get all built-in controls for a specific framework."""
    return [c for c in get_builtin_controls() if c.framework == framework]
