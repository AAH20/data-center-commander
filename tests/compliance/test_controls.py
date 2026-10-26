"""Tests for the built-in compliance controls.

These assert the *contract* of the catalogue: how many controls exist, that every
evaluator produces a status, and that the controls which can be judged without a
database judge the state the application actually enforces.

What they deliberately do NOT do is assert a status from an environment variable.
The previous version of this file did exactly that -- it set ``DCC_MFA_ENABLED``,
``DCC_ENCRYPTION_AT_REST`` and friends and expected a pass -- which is how a suite
stays green while the controls report on configuration nothing reads. The
measurement-level tests, including the ones that show a status moving when the
underlying fact moves, live in ``test_controls_real_state.py``.
"""
from __future__ import annotations

import os
from unittest.mock import patch

from dcc.compliance import observables
from dcc.compliance.controls import (
    EVALUATION_BASIS,
    _finding,
    get_builtin_controls,
    get_controls_by_framework,
)
from dcc.compliance.models import ComplianceStatus, Framework, Severity
from dcc.compliance.scanner import ComplianceScanner

EXPECTED_IDS = {
    "SOC2-CC6.1",
    "SOC2-CC6.2",
    "SOC2-CC6.3",
    "SOC2-CC7.1",
    "SOC2-CC7.2",
    "ISO27001-A.9.4.1",
    "ISO27001-A.12.4.1",
    "ISO27001-A.14.1.1",
    "PCI-1.1",
    "PCI-3.4",
    "PCI-8.2",
    "PCI-10.1",
    "HIPAA-164.312(a)(1)",
    "HIPAA-164.312(e)(1)",
    "NIST-AC-2",
    "NIST-AU-1",
}


def _one_tenant_key() -> str:
    """A real ``tenant:sha256hex`` entry, minted the way the CLI mints one."""
    from dcc.security.api_keys import generate_api_key, hash_api_key

    tenant = "11111111-1111-1111-1111-111111111111"
    return f"{tenant}:{hash_api_key(generate_api_key())}"


def _evaluate(control_id: str, env: dict[str, str] | None = None):
    """Run one control's evaluator with a controlled environment."""
    clean = {
        k: v
        for k, v in os.environ.items()
        if k not in {"DCC_API_KEYS", "DCC_ALLOW_ANONYMOUS", "DCC_MFA_ENABLED", "DCC_DATABASE_URL"}
    }
    clean.update(env or {})
    with patch.dict(os.environ, clean, clear=True):
        controls = {c.control_id: c for c in get_builtin_controls()}
        evaluator = controls[control_id].evaluator
        assert evaluator is not None, f"{control_id} has no evaluator"
        return evaluator()


def _has(findings, status: ComplianceStatus, needle: str = "") -> bool:
    return any(
        f.status is status and (needle in f.message if needle else True) for f in findings
    )


class TestCatalogue:
    def test_control_count_is_unchanged(self) -> None:
        """Sixteen controls, always. Rewriting their basis must not shrink the set."""
        assert len(get_builtin_controls()) == 16

    def test_control_ids_are_stable(self) -> None:
        ids = {c.control_id for c in get_builtin_controls()}
        assert ids == EXPECTED_IDS

    def test_get_controls_by_framework(self) -> None:
        soc2 = get_controls_by_framework(Framework.SOC2)
        assert len(soc2) > 0
        assert all(c.framework == Framework.SOC2 for c in soc2)

        pci = get_controls_by_framework(Framework.PCI_DSS)
        assert len(pci) > 0
        assert all(c.framework == Framework.PCI_DSS for c in pci)

    def test_all_controls_have_evaluators(self) -> None:
        for ctrl in get_builtin_controls():
            assert ctrl.evaluator is not None, f"{ctrl.control_id} has no evaluator"

    def test_all_controls_have_tags(self) -> None:
        for ctrl in get_builtin_controls():
            assert len(ctrl.tags) > 0, f"{ctrl.control_id} has no tags"

    def test_every_control_declares_its_basis(self) -> None:
        """A control must say whether it measures state or cannot be measured."""
        assert set(EVALUATION_BASIS) == EXPECTED_IDS
        assert set(EVALUATION_BASIS.values()) == {"measured", "not_assessed"}

    def test_descriptions_do_not_promise_unmeasured_things(self) -> None:
        for ctrl in get_builtin_controls():
            text = f"{ctrl.title} {ctrl.description}".lower()
            assert "mfa is enabled" not in text, ctrl.control_id
            assert "tls is enforced" not in text, ctrl.control_id


class TestFindingContract:
    def test_evaluators_never_raise_without_a_database(self) -> None:
        """A scan must survive an unconfigured environment and report why."""
        for ctrl in get_builtin_controls():
            findings = _evaluate(ctrl.control_id, {"DCC_ALLOW_ANONYMOUS": "1"})
            assert findings, f"{ctrl.control_id} returned no findings"
            for finding in findings:
                assert finding.status in {
                    ComplianceStatus.PASS,
                    ComplianceStatus.FAIL,
                    ComplianceStatus.NOT_ASSESSED,
                }, f"{ctrl.control_id}: {finding.status} ({finding.message})"

    def test_not_assessed_findings_explain_themselves(self) -> None:
        """An unmeasurable control must say what could not be measured, and why.

        This test used to depend on ambient process state without saying so. Controls
        that need a key store call live_key_store(), which returns
        ``dcc.api_async._API_KEYS`` if -- and only if -- that module is already in
        sys.modules. Running this file alone, it is absent, so SOC2-CC6.2 reported "no
        live key store"; after any test that imported dcc.api_async, the same control
        reported a different NOT_ASSESSED statement that did not contain the expected
        vocabulary, and this test failed. It passed or failed depending on which tests
        ran before it.

        The vocabulary is now checked against BOTH branches of that control explicitly,
        via the store argument, so the assertion no longer depends on import order.
        """
        explain = ("cannot", "could not", "judgement", "not assessed", "unable")

        def _assert_explains(finding, label: str) -> None:
            assert len(finding.message) > 40, label
            assert any(word in finding.message.lower() for word in explain), (
                f"{label} does not explain itself: {finding.message!r}"
            )

        for ctrl in get_builtin_controls():
            for finding in _evaluate(ctrl.control_id, {"DCC_ALLOW_ANONYMOUS": "1"}):
                if finding.status is ComplianceStatus.NOT_ASSESSED:
                    _assert_explains(finding, ctrl.control_id)

        # Both key-store branches, forced, so neither depends on sys.modules.
        class _EmptyStore:
            def list_keys(self):
                return []

        for store, label in ((None, "SOC2-CC6.2/no-store"), (_EmptyStore(), "SOC2-CC6.2/empty-store")):
            measurement = observables.measure_credential_expiry(store=store)
            for finding in _finding("SOC2-CC6.2", measurement, severity=Severity.HIGH):
                if finding.status is ComplianceStatus.NOT_ASSESSED:
                    _assert_explains(finding, label)

    def test_every_finding_carries_evidence(self) -> None:
        for ctrl in get_builtin_controls():
            for finding in _evaluate(ctrl.control_id, {"DCC_ALLOW_ANONYMOUS": "1"}):
                assert finding.evidence, f"{ctrl.control_id} finding has no evidence"


class TestSoc2CC61:
    """Access control reads the posture the application enforces."""

    def test_anonymous_access_fails(self) -> None:
        findings = _evaluate("SOC2-CC6.1", {"DCC_ALLOW_ANONYMOUS": "1", "DCC_API_KEYS": _one_tenant_key()})
        assert any(f.status is ComplianceStatus.FAIL for f in findings)
        assert any("Anonymous" in f.message for f in findings)

    def test_enforced_auth_with_keys_passes_the_auth_half(self) -> None:
        findings = _evaluate("SOC2-CC6.1", {"DCC_ALLOW_ANONYMOUS": "0", "DCC_API_KEYS": _one_tenant_key()})
        assert any(f.status is ComplianceStatus.PASS for f in findings), [f.message for f in findings]

    def test_enforced_auth_without_keys_is_a_lockout_not_a_pass(self) -> None:
        findings = _evaluate("SOC2-CC6.1", {"DCC_ALLOW_ANONYMOUS": "0", "DCC_API_KEYS": ""})
        assert any(f.status is ComplianceStatus.FAIL for f in findings)
        assert any("lockout" in f.message for f in findings)

    def test_mfa_is_not_asserted_from_the_environment(self) -> None:
        """The old control failed unless DCC_MFA_ENABLED=true. Nothing reads it now."""
        base = {"DCC_ALLOW_ANONYMOUS": "0", "DCC_API_KEYS": _one_tenant_key()}
        without = [(f.status, f.message) for f in _evaluate("SOC2-CC6.1", base)]
        with_flag = [
            (f.status, f.message)
            for f in _evaluate("SOC2-CC6.1", {**base, "DCC_MFA_ENABLED": "true"})
        ]
        assert without == with_flag

    def test_mfa_reports_not_assessed(self) -> None:
        findings = _evaluate("SOC2-CC6.1", {"DCC_ALLOW_ANONYMOUS": "0", "DCC_API_KEYS": _one_tenant_key()})
        mfa = [f for f in findings if "MFA" in f.message]
        assert mfa and mfa[0].status is ComplianceStatus.NOT_ASSESSED


class TestPci82:
    """Authentication strength is judged from the credentials that exist."""

    def test_strong_hashed_key_passes(self) -> None:
        findings = _evaluate("PCI-8.2", {"DCC_API_KEYS": _one_tenant_key()})
        assert all(f.status is ComplianceStatus.PASS for f in findings), [f.message for f in findings]

    def test_truncated_hash_fails(self) -> None:
        findings = _evaluate("PCI-8.2", {"DCC_API_KEYS": "11111111-1111-1111-1111-111111111111:abc123"})
        assert any(f.status is ComplianceStatus.FAIL for f in findings)

    def test_no_credentials_fails(self) -> None:
        findings = _evaluate("PCI-8.2", {"DCC_API_KEYS": ""})
        assert any(f.status is ComplianceStatus.FAIL for f in findings)


class TestUnmeasurableControls:
    """Controls with no honest observable must say so rather than pass."""

    def test_network_segmentation_is_not_asserted(self) -> None:
        findings = _evaluate("PCI-1.1", {})
        assert all(f.status is ComplianceStatus.NOT_ASSESSED for f in findings)
        assert any("cannot be observed" in f.message for f in findings)

    def test_encryption_at_rest_is_not_asserted(self) -> None:
        findings = _evaluate("PCI-3.4", {})
        assert all(f.status is ComplianceStatus.NOT_ASSESSED for f in findings)

    def test_policy_documents_report_presence_not_adequacy(self) -> None:
        for control_id in ("ISO27001-A.14.1.1", "NIST-AU-1"):
            findings = _evaluate(control_id, {})
            assert all(f.status is ComplianceStatus.NOT_ASSESSED for f in findings), control_id

    def test_environment_cannot_flip_an_unmeasurable_control(self) -> None:
        """No variable turns "we cannot see this" into "this is fine"."""
        env = {
            "DCC_NETWORK_SEGMENTED": "true",
            "DCC_ENCRYPTION_AT_REST": "true",
            "DCC_SECURITY_POLICY_PATH": "/etc/passwd",
            "DCC_AUDIT_POLICY_PATH": "/etc/passwd",
        }
        for control_id in ("PCI-1.1", "PCI-3.4", "ISO27001-A.14.1.1", "NIST-AU-1"):
            findings = _evaluate(control_id, env)
            assert all(f.status is ComplianceStatus.NOT_ASSESSED for f in findings), control_id


class TestScannerAggregation:
    def test_not_assessed_outranks_pass_but_not_fail(self) -> None:
        scanner = ComplianceScanner()
        controls = {c.control_id: c for c in get_builtin_controls()}
        result = scanner._evaluate_control(controls["SOC2-CC6.1"], tenant_id=None)
        # Authentication passes, MFA is unmeasurable: the control as a whole is not
        # satisfied, and must not be presented as a pass.
        with patch.dict(
            os.environ,
            {"DCC_ALLOW_ANONYMOUS": "0", "DCC_API_KEYS": _one_tenant_key()},
        ):
            result = scanner._evaluate_control(controls["SOC2-CC6.1"], tenant_id=None)
        assert result.status is ComplianceStatus.NOT_ASSESSED
        assert any(f.status is ComplianceStatus.PASS for f in result.findings)

    def test_not_assessed_controls_lower_the_score(self) -> None:
        from dcc.compliance.models import ComplianceReport, ControlResult

        report = ComplianceReport(
            results=[
                ControlResult(control_id="a", framework=Framework.SOC2, title="a", status=ComplianceStatus.PASS),
                ControlResult(
                    control_id="b",
                    framework=Framework.SOC2,
                    title="b",
                    status=ComplianceStatus.NOT_ASSESSED,
                ),
            ]
        )
        assert report.not_assessed == 1
        assert report.compliance_score == 50.0
