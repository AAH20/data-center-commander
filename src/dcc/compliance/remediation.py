"""Remediation workflow engine.

Provides automated and manual remediation workflows for compliance findings.
Supports:

- Creating remediation actions from findings
- Executing automated remediations
- Tracking remediation status
- Generating remediation reports
- Remediation playbooks (predefined fix procedures)

Usage
-----

.. code-block:: python

    from dcc.compliance.remediation import RemediationEngine
    from dcc.compliance.models import RemediationAction

    engine = RemediationEngine()
    actions = engine.create_from_report(report)
    results = engine.execute_all()
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .models import (
    ComplianceReport,
    ComplianceStatus,
    Finding,
    RemediationAction,
    RemediationStatus,
)


# ---------------------------------------------------------------------------
# Cloud Provider Remediation
# ---------------------------------------------------------------------------


class CloudRemediationError(RuntimeError):
    """Base exception for cloud remediation errors."""


class CloudRemediationExecutionError(CloudRemediationError):
    """Raised when a cloud remediation action fails."""

    def __init__(self, action_id: str, message: str) -> None:
        super().__init__(f"remediation {action_id!r} failed: {message}")
        self.action_id = action_id


@dataclass
class CloudRemediationAction:
    """A remediation action for a cloud provider compliance finding."""

    action_id: str = ""
    provider: str = ""
    check_id: str = ""
    title: str = ""
    description: str = ""
    status: RemediationStatus = RemediationStatus.PENDING
    automated: bool = False
    command: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "provider": self.provider,
            "check_id": self.check_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "automated": self.automated,
            "command": self.command,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
        }


class CloudRemediationEngine:
    """Engine for managing and executing cloud provider remediation actions."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self._dry_run = dry_run
        self._actions: dict[str, CloudRemediationAction] = {}
        self._playbooks = self._build_playbooks()

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def create_from_results(self, results) -> list[CloudRemediationAction]:
        """Create remediation actions from provider compliance results."""
        from .providers.base import ProviderComplianceResult, ProviderComplianceStatus
        actions: list[CloudRemediationAction] = []
        for result in results:
            if result.status != ProviderComplianceStatus.FAIL:
                continue
            action = self._create_action_from_result(result)
            if action:
                actions.append(action)
                self._actions[action.action_id] = action
        return actions

    def create_from_report(self, report: ComplianceReport) -> list[CloudRemediationAction]:
        """Create remediation actions from a compliance report."""
        actions: list[CloudRemediationAction] = []
        for result in report.results:
            if result.status != ComplianceStatus.FAIL:
                continue
            for finding in result.findings:
                if finding.status != ComplianceStatus.FAIL:
                    continue
                action = self._create_action_from_finding(finding)
                if action:
                    actions.append(action)
                    self._actions[action.action_id] = action
        return actions

    def execute(self, action_id: str) -> CloudRemediationAction:
        """Execute a single remediation action."""
        if action_id not in self._actions:
            raise CloudRemediationError(f"action {action_id!r} not found")
        action = self._actions[action_id]
        action.status = RemediationStatus.IN_PROGRESS
        if not action.automated or not action.command:
            action.status = RemediationStatus.PENDING
            action.result = "Manual remediation required"
            return action
        if self._dry_run:
            action.status = RemediationStatus.COMPLETED
            action.result = f"[DRY RUN] Would execute: {action.command}"
            action.completed_at = datetime.now(timezone.utc)
            return action
        try:
            result = subprocess.run(action.command, shell=True, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                action.status = RemediationStatus.COMPLETED
                action.result = result.stdout.strip() or "Success"
            else:
                action.status = RemediationStatus.FAILED
                action.result = result.stderr.strip() or f"Exit code: {result.returncode}"
        except subprocess.TimeoutExpired:
            action.status = RemediationStatus.FAILED
            action.result = "Execution timed out after 120 seconds"
        except Exception as exc:
            action.status = RemediationStatus.FAILED
            action.result = str(exc)
        action.completed_at = datetime.now(timezone.utc)
        return action

    def execute_all(self) -> list[CloudRemediationAction]:
        """Execute all pending automated actions."""
        results: list[CloudRemediationAction] = []
        for action in self._actions.values():
            if action.status == RemediationStatus.PENDING and action.automated:
                results.append(self.execute(action.action_id))
        return results

    def get_actions(self) -> list[CloudRemediationAction]:
        return list(self._actions.values())

    def get_pending(self) -> list[CloudRemediationAction]:
        return [a for a in self._actions.values() if a.status == RemediationStatus.PENDING]

    def get_completed(self) -> list[CloudRemediationAction]:
        return [a for a in self._actions.values() if a.status == RemediationStatus.COMPLETED]

    def get_failed(self) -> list[CloudRemediationAction]:
        return [a for a in self._actions.values() if a.status == RemediationStatus.FAILED]

    def to_report(self) -> dict[str, Any]:
        actions = self.get_actions()
        return {
            "total": len(actions),
            "pending": len(self.get_pending()),
            "completed": len(self.get_completed()),
            "failed": len(self.get_failed()),
            "actions": [a.to_dict() for a in actions],
        }

    def save_report(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_report(), indent=2), encoding="utf-8")
        return path

    def _create_action_from_result(self, result) -> CloudRemediationAction | None:
        playbook = self._find_playbook(result.check_id)
        if playbook is None:
            return CloudRemediationAction(
                action_id=f"{result.provider}-{result.check_id}",
                provider=result.provider,
                check_id=result.check_id,
                title=f"Remediate {result.name}",
                description=result.detail,
                automated=False,
            )
        return CloudRemediationAction(
            action_id=f"{result.provider}-{result.check_id}",
            provider=result.provider,
            check_id=result.check_id,
            title=playbook["title"],
            description=playbook["description"],
            automated=playbook.get("automated", False),
            command=playbook.get("command", ""),
        )

    def _create_action_from_finding(self, finding: Finding) -> CloudRemediationAction | None:
        return CloudRemediationAction(
            action_id=finding.control_id,
            check_id=finding.control_id,
            title=f"Remediate {finding.control_id}",
            description=finding.message,
            automated=False,
        )

    def _find_playbook(self, check_id: str) -> dict[str, Any] | None:
        import re
        for pattern, playbook in self._playbooks.items():
            if re.search(pattern, check_id):
                return playbook
        return None

    def _build_playbooks(self) -> dict[str, dict[str, Any]]:
        return {
            r"AWS-S3-001": {"title": "Enable S3 Bucket Encryption", "description": "Enable server-side encryption on S3 bucket", "automated": False, "command": ""},
            r"AWS-S3-002": {"title": "Block S3 Bucket Public Access", "description": "Block public access on S3 bucket", "automated": False, "command": ""},
            r"AWS-EC2-002": {"title": "Enable IMDSv2 on EC2 Instance", "description": "Set HttpTokens to required on EC2 instance", "automated": False, "command": ""},
            r"AWS-VPC-001": {"title": "Enable VPC Flow Logs", "description": "Enable flow logs on VPC", "automated": False, "command": ""},
            r"AWS-RDS-001": {"title": "Enable RDS Encryption", "description": "Enable storage encryption on RDS instance", "automated": False, "command": ""},
            r"AWS-CT-001": {"title": "Enable CloudTrail", "description": "Enable CloudTrail for all regions", "automated": False, "command": ""},
            r"AZURE-STORAGE-001": {"title": "Enable Storage Account Encryption", "description": "Enable encryption on storage account", "automated": False, "command": ""},
            r"AZURE-STORAGE-002": {"title": "Enforce HTTPS-Only on Storage Account", "description": "Enable HTTPS-only traffic on storage account", "automated": False, "command": ""},
            r"AZURE-SQL-001": {"title": "Enable SQL Database TDE", "description": "Enable TDE on SQL database", "automated": False, "command": ""},
            r"GCP-GCS-001": {"title": "Enable GCS Uniform Bucket Access", "description": "Enable uniform bucket-level access on GCS bucket", "automated": False, "command": ""},
            r"GCP-GCS-002": {"title": "Enable GCS Public Access Prevention", "description": "Enable public access prevention on GCS bucket", "automated": False, "command": ""},
            r"GCP-GKE-001": {"title": "Enable GKE Private Endpoint", "description": "Enable private endpoint on GKE cluster", "automated": False, "command": ""},
            r"GCP-GKE-002": {"title": "Enable GKE Network Policy", "description": "Enable network policy on GKE cluster", "automated": False, "command": ""},
            r"DO-SPACES-001": {"title": "Set Spaces Bucket ACL to Private", "description": "Set Spaces bucket ACL to private", "automated": False, "command": ""},
            r"IBM-COS-001": {"title": "Enable COS Bucket Encryption", "description": "Enable encryption on COS bucket", "automated": False, "command": ""},
        }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RemediationError(RuntimeError):
    """Base exception for remediation errors."""


class RemediationExecutionError(RemediationError):
    """Raised when a remediation action fails to execute."""

    def __init__(self, action_id: str, message: str) -> None:
        super().__init__(f"remediation {action_id!r} failed: {message}")
        self.action_id = action_id


# ---------------------------------------------------------------------------
# Playbook
# ---------------------------------------------------------------------------


@dataclass
class RemediationPlaybook:
    """A predefined remediation procedure.

    Attributes
    ----------
    name:
        Unique playbook name.
    description:
        What this playbook does.
    control_pattern:
        Regex pattern to match control IDs this playbook applies to.
    steps:
        Ordered list of remediation steps.
    automated:
        Whether this playbook can be executed automatically.
    command:
        Optional shell command to execute for automated remediation.
    """

    name: str
    description: str = ""
    control_pattern: str = ""
    steps: list[str] = field(default_factory=list)
    automated: bool = False
    command: str = ""

    def matches(self, control_id: str) -> bool:
        """Check if this playbook applies to the given control ID."""
        import re
        return bool(re.search(self.control_pattern, control_id))


# ---------------------------------------------------------------------------
# Built-in playbooks
# ---------------------------------------------------------------------------


def get_builtin_playbooks() -> list[RemediationPlaybook]:
    """Return all built-in remediation playbooks."""
    return [
        RemediationPlaybook(
            name="enable-authentication",
            description="Enable authentication for the system",
            control_pattern=r"SOC2-CC6\.1|ISO27001-A\.9\.4\.1",
            steps=[
                "Set DCC_AUTH_ENABLED=true in environment configuration",
                "Configure authentication providers (OAuth2, SAML, etc.)",
                "Verify authentication is enforced on all endpoints",
                "Test login with valid and invalid credentials",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="enable-mfa",
            description="Enable multi-factor authentication",
            control_pattern=r"SOC2-CC6\.1",
            steps=[
                "Set DCC_MFA_ENABLED=true in environment configuration",
                "Configure MFA provider (TOTP, WebAuthn, etc.)",
                "Enforce MFA for all administrative accounts",
                "Test MFA flow with test accounts",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="reduce-session-timeout",
            description="Reduce session timeout to recommended value",
            control_pattern=r"SOC2-CC6\.2",
            steps=[
                "Set DCC_SESSION_TIMEOUT_MINUTES=240 or less",
                "Verify session timeout is enforced",
                "Test that sessions expire after the configured timeout",
            ],
            automated=True,
            command="mkdir -p ~/.dcc && echo 'export DCC_SESSION_TIMEOUT_MINUTES=240' >> ~/.dcc/env",
        ),
        RemediationPlaybook(
            name="enable-audit-logging",
            description="Enable audit logging",
            control_pattern=r"SOC2-CC6\.3|PCI-10\.1|ISO27001-A\.12\.4\.1",
            steps=[
                "Set DCC_AUDIT_ENABLED=true in environment configuration",
                "Configure audit log storage backend",
                "Verify audit logs are being written",
                "Test audit log search and retrieval",
            ],
            automated=True,
            command="mkdir -p ~/.dcc && echo 'export DCC_AUDIT_ENABLED=true' >> ~/.dcc/env",
        ),
        RemediationPlaybook(
            name="enable-monitoring",
            description="Enable monitoring and alerting",
            control_pattern=r"SOC2-CC7\.1",
            steps=[
                "Set DCC_MONITORING_ENABLED=true in environment configuration",
                "Configure monitoring backend (Prometheus, etc.)",
                "Set up alerting rules and notification channels",
                "Verify alerts are firing correctly",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="configure-ir-plan",
            description="Configure incident response plan",
            control_pattern=r"SOC2-CC7\.2",
            steps=[
                "Create incident response plan document",
                "Set DCC_IR_PLAN_PATH to the plan location",
                "Verify the plan is accessible",
                "Conduct incident response drill",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="enable-rbac",
            description="Enable role-based access control",
            control_pattern=r"ISO27001-A\.9\.4\.1",
            steps=[
                "Set DCC_RBAC_ENABLED=true in environment configuration",
                "Define roles and permissions",
                "Assign roles to users",
                "Verify access restrictions are enforced",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="enable-network-segmentation",
            description="Enable network segmentation",
            control_pattern=r"PCI-1\.1",
            steps=[
                "Set DCC_NETWORK_SEGMENTED=true in environment configuration",
                "Configure network policies",
                "Verify segmentation is enforced",
                "Test cross-segment access is blocked",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="enable-encryption-at-rest",
            description="Enable encryption at rest",
            control_pattern=r"PCI-3\.4",
            steps=[
                "Set DCC_ENCRYPTION_AT_REST=true in environment configuration",
                "Configure encryption keys and key management",
                "Verify data is encrypted at rest",
                "Test encryption and decryption flow",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="strengthen-password-policy",
            description="Strengthen password policy",
            control_pattern=r"PCI-8\.2",
            steps=[
                "Set DCC_MIN_PASSWORD_LENGTH=12 or greater",
                "Configure password complexity requirements",
                "Enable password history and rotation",
                "Test password policy enforcement",
            ],
            automated=True,
            command="mkdir -p ~/.dcc && echo 'export DCC_MIN_PASSWORD_LENGTH=12' >> ~/.dcc/env",
        ),
        RemediationPlaybook(
            name="enforce-tls",
            description="Enforce TLS for all connections",
            control_pattern=r"HIPAA-164\.312\(e\)\(1\)",
            steps=[
                "Set DCC_TLS_ENFORCED=true in environment configuration",
                "Configure TLS certificates",
                "Disable insecure protocols (TLS 1.0, 1.1)",
                "Verify TLS is enforced on all endpoints",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="enable-unique-user-ids",
            description="Enable unique user identification",
            control_pattern=r"HIPAA-164\.312\(a\)\(1\)",
            steps=[
                "Set DCC_UNIQUE_USER_IDS=true in environment configuration",
                "Verify all users have unique identifiers",
                "Test that duplicate user IDs are rejected",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="enable-account-management",
            description="Enable account management process",
            control_pattern=r"NIST-AC-2",
            steps=[
                "Set DCC_ACCOUNT_MANAGEMENT=true in environment configuration",
                "Define account lifecycle procedures",
                "Implement account provisioning and deprovisioning",
                "Test account management workflow",
            ],
            automated=False,
        ),
        RemediationPlaybook(
            name="configure-audit-policy",
            description="Configure audit policy",
            control_pattern=r"NIST-AU-1",
            steps=[
                "Create audit policy document",
                "Set DCC_AUDIT_POLICY_PATH to the policy location",
                "Verify the policy is accessible",
                "Review and update policy annually",
            ],
            automated=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Remediation engine
# ---------------------------------------------------------------------------


class RemediationEngine:
    """Engine for managing and executing remediation actions.

    Parameters
    ----------
    playbooks:
        Custom playbooks to use in addition to built-in ones.
    dry_run:
        If True, simulate execution without making changes.
    """

    def __init__(
        self,
        playbooks: Iterable[RemediationPlaybook] | None = None,
        *,
        dry_run: bool = False,
    ) -> None:
        self._playbooks: list[RemediationPlaybook] = list(get_builtin_playbooks())
        if playbooks:
            self._playbooks.extend(playbooks)
        self._dry_run = dry_run
        self._actions: dict[str, RemediationAction] = {}
        self._execution_hooks: list[Callable[[RemediationAction], None]] = []

    # ------------------------------------------------------------------
    # Action creation
    # ------------------------------------------------------------------

    def create_from_report(self, report: ComplianceReport) -> list[RemediationAction]:
        """Create remediation actions from a compliance report.

        Only creates actions for failed controls.
        """
        actions: list[RemediationAction] = []

        for result in report.results:
            if result.status != ComplianceStatus.FAIL:
                continue

            for finding in result.findings:
                if finding.status != ComplianceStatus.FAIL:
                    continue

                action = self._create_action_from_finding(finding)
                if action:
                    actions.append(action)
                    self._actions[str(action.action_id)] = action

        return actions

    def create_from_finding(self, finding: Finding) -> RemediationAction | None:
        """Create a single remediation action from a finding."""
        action = self._create_action_from_finding(finding)
        if action:
            self._actions[str(action.action_id)] = action
        return action

    def _create_action_from_finding(self, finding: Finding) -> RemediationAction | None:
        """Create a remediation action from a finding using playbooks."""
        # Find matching playbook
        playbook = None
        for pb in self._playbooks:
            if pb.matches(finding.control_id):
                playbook = pb
                break

        if playbook is None:
            # Create a generic action
            return RemediationAction(
                control_id=finding.control_id,
                title=f"Remediate {finding.control_id}",
                description=finding.message,
                automated=False,
            )

        return RemediationAction(
            control_id=finding.control_id,
            title=playbook.name,
            description=playbook.description,
            automated=playbook.automated,
            command=playbook.command if playbook.automated else "",
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, action_id: str) -> RemediationAction:
        """Execute a single remediation action.

        Raises
        ------
        RemediationExecutionError
            If the action fails to execute.
        """
        if action_id not in self._actions:
            raise RemediationError(f"action {action_id!r} not found")

        action = self._actions[action_id]
        action.status = RemediationStatus.IN_PROGRESS

        if not action.automated or not action.command:
            action.status = RemediationStatus.PENDING
            action.result = "Manual remediation required"
            return action

        if self._dry_run:
            action.status = RemediationStatus.COMPLETED
            action.result = f"[DRY RUN] Would execute: {action.command}"
            action.completed_at = datetime.now(timezone.utc)
            return action

        try:
            result = subprocess.run(
                action.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                action.status = RemediationStatus.COMPLETED
                action.result = result.stdout.strip() or "Success"
            else:
                action.status = RemediationStatus.FAILED
                action.result = result.stderr.strip() or f"Exit code: {result.returncode}"
        except subprocess.TimeoutExpired:
            action.status = RemediationStatus.FAILED
            action.result = "Execution timed out after 60 seconds"
        except Exception as exc:
            action.status = RemediationStatus.FAILED
            action.result = str(exc)

        action.completed_at = datetime.now(timezone.utc)

        # Run execution hooks
        for hook in self._execution_hooks:
            hook(action)

        return action

    def execute_all(self) -> list[RemediationAction]:
        """Execute all pending automated actions."""
        results: list[RemediationAction] = []
        for action in self._actions.values():
            if action.status == RemediationStatus.PENDING and action.automated:
                results.append(self.execute(str(action.action_id)))
        return results

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def add_execution_hook(self, hook: Callable[[RemediationAction], None]) -> None:
        """Add a hook that runs after each action execution."""
        self._execution_hooks.append(hook)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_actions(self) -> list[RemediationAction]:
        """Return all tracked actions."""
        return list(self._actions.values())

    def get_pending(self) -> list[RemediationAction]:
        """Return all pending actions."""
        return [a for a in self._actions.values() if a.status == RemediationStatus.PENDING]

    def get_completed(self) -> list[RemediationAction]:
        """Return all completed actions."""
        return [a for a in self._actions.values() if a.status == RemediationStatus.COMPLETED]

    def get_failed(self) -> list[RemediationAction]:
        """Return all failed actions."""
        return [a for a in self._actions.values() if a.status == RemediationStatus.FAILED]

    def to_report(self) -> dict[str, Any]:
        """Generate a remediation report."""
        actions = self.get_actions()
        return {
            "total": len(actions),
            "pending": len(self.get_pending()),
            "completed": len(self.get_completed()),
            "failed": len(self.get_failed()),
            "actions": [a.to_dict() for a in actions],
        }

    def save_report(self, path: str | Path) -> Path:
        """Save the remediation report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_report(), indent=2), encoding="utf-8")
        return path
