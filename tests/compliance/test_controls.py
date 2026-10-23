"""Tests for built-in compliance controls."""
from __future__ import annotations

import os
from unittest.mock import patch

from dcc.compliance.controls import get_builtin_controls, get_controls_by_framework
from dcc.compliance.models import ComplianceStatus, Framework


class TestBuiltinControls:
    def test_get_all_controls(self) -> None:
        controls = get_builtin_controls()
        assert len(controls) > 0
        ids = {c.control_id for c in controls}
        assert "SOC2-CC6.1" in ids
        assert "PCI-3.4" in ids
        assert "HIPAA-164.312(a)(1)" in ids

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


class TestControlEvaluation:
    #: The two knobs the SOC 2 access control actually reads.
    #:
    #: It used to read DCC_AUTH_ENABLED, which the served application never consults,
    #: so this test could pass while the API was open to anonymous callers. The real
    #: posture is derived from DCC_ALLOW_ANONYMOUS plus the number of DCC_API_KEYS
    #: entries (see dcc.security.posture.auth_posture). Enforced auth with zero keys
    #: is a lockout, not a control, so a PASS needs at least one key configured.
    #: tests/conftest.py sets DCC_ALLOW_ANONYMOUS=1 suite-wide, which is why both
    #: cases below state it explicitly instead of relying on the ambient value.

    def _api_keys_env(self) -> dict[str, str]:
        """One real tenant:hash entry, minted the same way the CLI mints one."""
        from dcc.security.api_keys import generate_api_key, hash_api_key

        tenant = "11111111-1111-1111-1111-111111111111"
        return {"DCC_API_KEYS": f"{tenant}:{hash_api_key(generate_api_key())}"}

    def test_soc2_cc6_1_pass(self) -> None:
        env = {"DCC_ALLOW_ANONYMOUS": "0", "DCC_MFA_ENABLED": "true", **self._api_keys_env()}
        with patch.dict(os.environ, env):
            controls = {c.control_id: c for c in get_builtin_controls()}
            findings = controls["SOC2-CC6.1"].evaluator()
            assert all(f.status == ComplianceStatus.PASS for f in findings), [
                f.message for f in findings
            ]

    def test_soc2_cc6_1_fail_no_auth(self) -> None:
        env = {"DCC_ALLOW_ANONYMOUS": "1", "DCC_MFA_ENABLED": "true", **self._api_keys_env()}
        with patch.dict(os.environ, env):
            controls = {c.control_id: c for c in get_builtin_controls()}
            findings = controls["SOC2-CC6.1"].evaluator()
            assert any(f.status == ComplianceStatus.FAIL for f in findings)

    def test_pci_3_4_pass(self) -> None:
        with patch.dict(os.environ, {"DCC_ENCRYPTION_AT_REST": "true"}):
            controls = {c.control_id: c for c in get_builtin_controls()}
            findings = controls["PCI-3.4"].evaluator()
            assert all(f.status == ComplianceStatus.PASS for f in findings)

    def test_pci_3_4_fail(self) -> None:
        with patch.dict(os.environ, {"DCC_ENCRYPTION_AT_REST": "false"}):
            controls = {c.control_id: c for c in get_builtin_controls()}
            findings = controls["PCI-3.4"].evaluator()
            assert any(f.status == ComplianceStatus.FAIL for f in findings)

    def test_hipaa_pass(self) -> None:
        with patch.dict(os.environ, {"DCC_UNIQUE_USER_IDS": "true", "DCC_TLS_ENFORCED": "true"}):
            controls = {c.control_id: c for c in get_builtin_controls()}
            findings = controls["HIPAA-164.312(a)(1)"].evaluator()
            assert all(f.status == ComplianceStatus.PASS for f in findings)

    def test_nist_ac_2_pass(self) -> None:
        with patch.dict(os.environ, {"DCC_ACCOUNT_MANAGEMENT": "true"}):
            controls = {c.control_id: c for c in get_builtin_controls()}
            findings = controls["NIST-AC-2"].evaluator()
            assert all(f.status == ComplianceStatus.PASS for f in findings)
