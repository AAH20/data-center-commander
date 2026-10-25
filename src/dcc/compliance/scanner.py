"""Compliance scanner engine.

The scanner orchestrates control evaluation, evidence collection, and
report generation. It supports:

- Registering controls from multiple frameworks
- Running full or filtered scans
- Collecting evidence during evaluation
- Generating serialisable compliance reports
- Tenant-scoped scanning
- Scan hooks (pre/post scan callbacks)

Usage
-----

.. code-block:: python

    from dcc.compliance.scanner import ComplianceScanner
    from dcc.compliance.controls import get_builtin_controls

    scanner = ComplianceScanner()
    for ctrl in get_builtin_controls():
        scanner.register(ctrl)

    report = scanner.scan(framework=Framework.SOC2)
    print(f"Score: {report.compliance_score:.1f}%")
    report.save("compliance-report.json")
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

from .models import (
    ComplianceReport,
    ComplianceStatus,
    ControlDefinition,
    ControlResult,
    Finding,
    Framework,
    Severity,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ScannerError(RuntimeError):
    """Base exception for scanner errors."""


class ControlNotFoundError(ScannerError):
    """Raised when a requested control is not registered."""

    def __init__(self, control_id: str) -> None:
        super().__init__(f"control {control_id!r} is not registered")
        self.control_id = control_id


class DuplicateControlError(ScannerError):
    """Raised when registering a control with an ID that already exists."""

    def __init__(self, control_id: str) -> None:
        super().__init__(f"control {control_id!r} is already registered")
        self.control_id = control_id


# ---------------------------------------------------------------------------
# Scan hooks
# ---------------------------------------------------------------------------


@dataclass
class ScanContext:
    """Context passed to scan hooks.

    Attributes
    ----------
    framework:
        The framework being scanned.
    tenant_id:
        Optional tenant scope.
    metadata:
        Arbitrary scan metadata.
    """

    framework: Framework
    tenant_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


ScanHook = Callable[[ScanContext], None]


def _status_from_findings(findings: Sequence[Finding]) -> ComplianceStatus:
    """Collapse a control's findings into one status, worst first.

    Order is FAIL, ERROR, NOT_ASSESSED, PASS. ``NOT_ASSESSED`` sits below ERROR
    because an error is a control that broke, and above PASS because a partially
    measured control has not satisfied its requirement in full. Reporting such a
    control as a pass is the specific false assurance this ordering prevents: a
    control that measured one of two halves must not present as complete.
    """
    statuses = {f.status for f in findings}
    if ComplianceStatus.FAIL in statuses:
        return ComplianceStatus.FAIL
    if ComplianceStatus.ERROR in statuses:
        return ComplianceStatus.ERROR
    if ComplianceStatus.NOT_ASSESSED in statuses:
        return ComplianceStatus.NOT_ASSESSED
    return ComplianceStatus.PASS


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class ComplianceScanner:
    """Main compliance scanner engine.

    Manages a registry of compliance controls and runs scans to produce
    compliance reports.

    Parameters
    ----------
    controls:
        Initial set of controls to register.
    fail_fast:
        If True, stop the scan on the first control error.
    collect_evidence:
        If True, collect evidence during control evaluation.
    """

    def __init__(
        self,
        controls: Iterable[ControlDefinition] | None = None,
        *,
        fail_fast: bool = False,
        collect_evidence: bool = True,
    ) -> None:
        self._controls: dict[str, ControlDefinition] = {}
        self._fail_fast = fail_fast
        self._collect_evidence = collect_evidence
        self._pre_scan_hooks: list[ScanHook] = []
        self._post_scan_hooks: list[ScanHook] = []

        if controls:
            for ctrl in controls:
                self.register(ctrl)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, control: ControlDefinition) -> None:
        """Register a compliance control.

        Raises
        ------
        DuplicateControlError
            If a control with the same ID is already registered.
        """
        if control.control_id in self._controls:
            raise DuplicateControlError(control.control_id)
        self._controls[control.control_id] = control

    def unregister(self, control_id: str) -> None:
        """Remove a control from the registry."""
        if control_id not in self._controls:
            raise ControlNotFoundError(control_id)
        del self._controls[control_id]

    @property
    def controls(self) -> dict[str, ControlDefinition]:
        """Return a read-only view of registered controls."""
        return dict(self._controls)

    def get_control(self, control_id: str) -> ControlDefinition:
        """Get a control by ID.

        Raises
        ------
        ControlNotFoundError
            If the control is not registered.
        """
        if control_id not in self._controls:
            raise ControlNotFoundError(control_id)
        return self._controls[control_id]

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def add_pre_scan_hook(self, hook: ScanHook) -> None:
        """Add a hook that runs before the scan starts."""
        self._pre_scan_hooks.append(hook)

    def add_post_scan_hook(self, hook: ScanHook) -> None:
        """Add a hook that runs after the scan completes."""
        self._post_scan_hooks.append(hook)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan(
        self,
        *,
        framework: Framework | None = None,
        control_ids: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ComplianceReport:
        """Run a compliance scan.

        Parameters
        ----------
        framework:
            Only scan controls for this framework. If None, scan all.
        control_ids:
            Only scan these specific controls. If None, scan all matching.
        tags:
            Only scan controls that have at least one of these tags.
        tenant_id:
            Tenant scope for the scan.
        metadata:
            Additional metadata to include in the report.

        Returns
        -------
        ComplianceReport
            The complete scan report.
        """
        ctx = ScanContext(
            framework=framework or Framework.CUSTOM,
            tenant_id=tenant_id,
            metadata=metadata or {},
        )

        # Run pre-scan hooks
        for hook in self._pre_scan_hooks:
            hook(ctx)

        # Select controls to evaluate
        selected = self._select_controls(
            framework=framework,
            control_ids=control_ids,
            tags=tags,
        )

        # Evaluate each control
        results: list[ControlResult] = []
        for ctrl in selected:
            result = self._evaluate_control(ctrl, tenant_id=tenant_id)
            results.append(result)

            if self._fail_fast and result.status == ComplianceStatus.ERROR:
                break

        # Build report
        report = ComplianceReport(
            framework=framework or Framework.CUSTOM,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            results=results,
            tenant_id=tenant_id,
            metadata=metadata or {},
        )

        # Run post-scan hooks
        for hook in self._post_scan_hooks:
            hook(ctx)

        return report

    def scan_single(
        self,
        control_id: str,
        *,
        tenant_id: str | None = None,
    ) -> ControlResult:
        """Evaluate a single control.

        Raises
        ------
        ControlNotFoundError
            If the control is not registered.
        """
        ctrl = self.get_control(control_id)
        return self._evaluate_control(ctrl, tenant_id=tenant_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _select_controls(
        self,
        *,
        framework: Framework | None,
        control_ids: Sequence[str] | None,
        tags: Sequence[str] | None,
    ) -> list[ControlDefinition]:
        """Select controls matching the given filters."""
        selected: list[ControlDefinition] = []

        for ctrl in self._controls.values():
            # Filter by framework
            if framework is not None and ctrl.framework != framework:
                continue

            # Filter by control IDs
            if control_ids is not None and ctrl.control_id not in control_ids:
                continue

            # Filter by tags
            if tags is not None:
                tag_set = set(tags)
                if not tag_set.intersection(ctrl.tags):
                    continue

            selected.append(ctrl)

        return selected

    def _evaluate_control(
        self,
        control: ControlDefinition,
        *,
        tenant_id: str | None = None,
    ) -> ControlResult:
        """Evaluate a single control and return the result."""
        start = time.monotonic()
        findings: list[Finding] = []
        status = ComplianceStatus.PASS

        if control.evaluator is None:
            status = ComplianceStatus.SKIP
        else:
            try:
                raw_findings = control.evaluator()
                findings = list(raw_findings or [])
                status = _status_from_findings(findings)
            except Exception as exc:
                status = ComplianceStatus.ERROR
                findings = [
                    Finding(
                        control_id=control.control_id,
                        status=ComplianceStatus.ERROR,
                        severity=Severity.HIGH,
                        message=f"Control evaluation failed: {exc}",
                        remediation_hint="Check control implementation and system state.",
                    )
                ]

        duration_ms = (time.monotonic() - start) * 1000.0

        return ControlResult(
            control_id=control.control_id,
            framework=control.framework,
            title=control.title,
            description=control.description,
            status=status,
            findings=findings,
            duration_ms=duration_ms,
            evaluated_at=datetime.now(timezone.utc),
            tags=control.tags,
        )
