"""OSSEC active response — automated incident response actions."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .models import OSSECAlert, Severity


class ResponseActionType(str, Enum):
    """Types of active response actions."""

    BLOCK_IP = "block_ip"
    UNBLOCK_IP = "unblock_ip"
    FIREWALL_DROP = "firewall_drop"
    FIREWALL_REJECT = "firewall_reject"
    HOST_DENY = "host_deny"
    ADD_HOST = "add_host"
    RESTART_OSSEC = "restart_ossec"
    CUSTOM = "custom"


class ResponseStatus(str, Enum):
    """Status of an active response action."""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ActiveResponse:
    """An active response action definition."""

    response_id: str
    name: str
    description: str
    action_type: ResponseActionType
    command: str
    severity_threshold: Severity
    groups: list[str] = field(default_factory=list)
    rules: list[int] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    timeout: int = 30
    enabled: bool = True
    require_approval: bool = False
    max_executions_per_hour: int = 10
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ResponseExecution:
    """Record of an active response execution."""

    execution_id: str
    response_id: str
    alert_id: str
    action_type: ResponseActionType
    command: str
    status: ResponseStatus
    started_at: str = ""
    completed_at: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    triggered_by: str = ""
    approved_by: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()


# Pre-built active response definitions
DEFAULT_RESPONSES: list[ActiveResponse] = [
    ActiveResponse(
        response_id="AR-001",
        name="Block Brute Force IP",
        description="Block IP address after repeated failed authentication",
        action_type=ResponseActionType.BLOCK_IP,
        command="firewall-drop {src_ip}",
        severity_threshold=Severity.HIGH,
        groups=["authentication", "sshd"],
        timeout=30,
        require_approval=False,
        max_executions_per_hour=20,
    ),
    ActiveResponse(
        response_id="AR-002",
        name="Block Malware C2",
        description="Block known malware command and control IP",
        action_type=ResponseActionType.BLOCK_IP,
        command="firewall-drop {dst_ip}",
        severity_threshold=Severity.CRITICAL,
        groups=["syscheck", "malware"],
        timeout=30,
        require_approval=False,
        max_executions_per_hour=50,
    ),
    ActiveResponse(
        response_id="AR-003",
        name="Isolate Compromised Host",
        description="Isolate host from network on critical alert",
        action_type=ResponseActionType.FIREWALL_REJECT,
        command="firewall-reject {agent_ip}",
        severity_threshold=Severity.EMERGENCY,
        groups=["rootcheck"],
        timeout=60,
        require_approval=True,
        max_executions_per_hour=5,
    ),
    ActiveResponse(
        response_id="AR-004",
        name="Add Host to Deny List",
        description="Add malicious host to /etc/hosts.deny",
        action_type=ResponseActionType.HOST_DENY,
        command="echo '{src_ip}' >> /etc/hosts.deny",
        severity_threshold=Severity.HIGH,
        groups=["authentication"],
        timeout=10,
        require_approval=False,
        max_executions_per_hour=15,
    ),
    ActiveResponse(
        response_id="AR-005",
        name="Restart OSSEC Agent",
        description="Restart OSSEC agent on configuration change",
        action_type=ResponseActionType.RESTART_OSSEC,
        command="/var/ossec/bin/ossec-control restart",
        severity_threshold=Severity.MEDIUM,
        groups=["general"],
        timeout=60,
        require_approval=True,
        max_executions_per_hour=3,
    ),
]


class ActiveResponseEngine:
    """Engine for executing OSSEC active responses."""

    def __init__(self) -> None:
        self.responses: list[ActiveResponse] = list(DEFAULT_RESPONSES)
        self.executions: list[ResponseExecution] = []
        self._execution_counts: dict[str, int] = {}

    def load_responses(self, responses: list[ActiveResponse]) -> None:
        """Load active response definitions."""
        self.responses = responses

    def evaluate_alert(self, alert: OSSECAlert) -> list[ActiveResponse]:
        """Evaluate an alert against active response rules."""
        triggered: list[ActiveResponse] = []

        for response in self.responses:
            if not response.enabled:
                continue

            if alert.severity.value < response.severity_threshold.value:
                continue

            if response.groups:
                if alert.rule.group.value not in response.groups:
                    continue

            if response.rules:
                if alert.rule.rule_id not in response.rules:
                    continue

            if response.agents:
                if alert.agent_id not in response.agents:
                    continue

            if not self._check_rate_limit(response):
                continue

            triggered.append(response)

        return triggered

    def execute_response(
        self,
        response: ActiveResponse,
        alert: OSSECAlert,
        dry_run: bool = False,
    ) -> ResponseExecution:
        """Execute an active response action."""
        execution = ResponseExecution(
            execution_id=f"exec-{datetime.now(timezone.utc).timestamp()}",
            response_id=response.response_id,
            alert_id=alert.alert_id,
            action_type=response.action_type,
            command=self._render_command(response.command, alert),
            status=ResponseStatus.PENDING,
            triggered_by="auto",
        )

        if dry_run:
            execution.status = ResponseStatus.SKIPPED
            execution.notes = "Dry run - not executed"
            self.executions.append(execution)
            return execution

        if response.require_approval:
            execution.status = ResponseStatus.PENDING
            execution.notes = "Requires approval"
            self.executions.append(execution)
            return execution

        execution.status = ResponseStatus.EXECUTING

        try:
            result = subprocess.run(
                execution.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=response.timeout,
            )

            execution.stdout = result.stdout
            execution.stderr = result.stderr
            execution.exit_code = result.returncode
            execution.completed_at = datetime.now(timezone.utc).isoformat()

            if result.returncode == 0:
                execution.status = ResponseStatus.SUCCESS
            else:
                execution.status = ResponseStatus.FAILED

        except subprocess.TimeoutExpired:
            execution.status = ResponseStatus.TIMEOUT
            execution.completed_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            execution.status = ResponseStatus.FAILED
            execution.stderr = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()

        self.executions.append(execution)
        self._increment_execution_count(response.response_id)

        return execution

    def _render_command(self, template: str, alert: OSSECAlert) -> str:
        """Render command template with alert data."""
        return template.format(
            src_ip=alert.src_ip or alert.agent_ip,
            dst_ip=alert.dst_ip,
            agent_ip=alert.agent_ip,
            agent_name=alert.agent_name,
            user=alert.user,
            file_path=alert.file_path,
        )

    def _check_rate_limit(self, response: ActiveResponse) -> bool:
        """Check if response is within rate limits."""
        count = self._execution_counts.get(response.response_id, 0)
        return count < response.max_executions_per_hour

    def _increment_execution_count(self, response_id: str) -> None:
        """Increment execution counter for rate limiting."""
        self._execution_counts[response_id] = (
            self._execution_counts.get(response_id, 0) + 1
        )

    def get_execution_history(
        self,
        response_id: str = "",
        status: Optional[ResponseStatus] = None,
    ) -> list[ResponseExecution]:
        """Get execution history with optional filtering."""
        results = self.executions

        if response_id:
            results = [e for e in results if e.response_id == response_id]

        if status:
            results = [e for e in results if e.status == status]

        return results

    def approve_execution(self, execution_id: str, approved_by: str) -> bool:
        """Approve a pending execution."""
        for execution in self.executions:
            if execution.execution_id == execution_id:
                if execution.status == ResponseStatus.PENDING:
                    execution.approved_by = approved_by
                    execution.status = ResponseStatus.EXECUTING
                    return True
        return False
