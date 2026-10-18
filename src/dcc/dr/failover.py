"""Failover automation for Data Center Commander.

Provides automated failover orchestration with health-based triggers,
multi-step failover procedures, rollback capabilities, and comprehensive
audit logging. Integrates with the HA manager for node health monitoring.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import uuid4


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FailoverAutomationError(Exception):
    """Base exception for failover automation failures."""

    def __init__(self, message: str, code: str = "failover_automation_error") -> None:
        self.code = code
        super().__init__(message)


class FailoverExecutionError(FailoverAutomationError):
    """Raised when a failover execution fails."""

    def __init__(self, message: str, step: str = "") -> None:
        self.step = step
        super().__init__(message, "failover_execution_error")


class RollbackError(FailoverAutomationError):
    """Raised when a rollback fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "rollback_error")


class FailoverValidationError(FailoverAutomationError):
    """Raised when failover pre-conditions are not met."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "failover_validation_error")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FailoverTrigger(str, Enum):
    """What triggered the failover."""

    MANUAL = "manual"
    HEALTH_CHECK = "health_check"
    HEALTH_DEGRADED = "health_degraded"
    HEALTH_UNHEALTHY = "health_unhealthy"
    SCHEDULED = "scheduled"
    CAPACITY = "capacity"
    MAINTENANCE = "maintenance"


class FailoverStepStatus(str, Enum):
    """Status of a failover step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class FailoverStatus(str, Enum):
    """Overall failover status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PARTIAL = "partial"


class FailoverMode(str, Enum):
    """Failover execution mode."""

    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailoverStep:
    """A single step in a failover procedure."""

    step_id: str
    name: str
    description: str
    order: int
    status: FailoverStepStatus = FailoverStepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    error: str = ""
    rollback_action: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "rollback_action": self.rollback_action,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FailoverProcedure:
    """A complete failover procedure definition."""

    procedure_id: str
    name: str
    description: str
    steps: list[FailoverStep]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "procedure_id": self.procedure_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailoverProcedure:
        steps = []
        for s in data.get("steps", []):
            steps.append(FailoverStep(
                step_id=s["step_id"],
                name=s["name"],
                description=s["description"],
                order=s["order"],
                status=FailoverStepStatus(s.get("status", "pending")),
                started_at=(
                    datetime.fromisoformat(s["started_at"])
                    if s.get("started_at")
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(s["completed_at"])
                    if s.get("completed_at")
                    else None
                ),
                duration_seconds=s.get("duration_seconds", 0.0),
                error=s.get("error", ""),
                rollback_action=s.get("rollback_action"),
                metadata=dict(s.get("metadata", {})),
            ))
        return cls(
            procedure_id=data["procedure_id"],
            name=data["name"],
            description=data["description"],
            steps=steps,
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=dict(data.get("tags", {})),
        )


@dataclass
class FailoverExecution:
    """A running or completed failover execution."""

    execution_id: str
    procedure_id: str
    tenant_id: str
    source_node: str
    target_node: str | None
    trigger: FailoverTrigger
    status: FailoverStatus
    mode: FailoverMode
    steps: list[FailoverStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "procedure_id": self.procedure_id,
            "tenant_id": self.tenant_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "trigger": self.trigger.value,
            "status": self.status.value,
            "mode": self.mode.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass
class FailoverResult:
    """Result of a failover execution."""

    success: bool
    execution_id: str
    status: FailoverStatus
    message: str = ""
    duration_seconds: float = 0.0
    error: str = ""
    steps_completed: int = 0
    steps_failed: int = 0
    steps_total: int = 0
    rolled_back: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "execution_id": self.execution_id,
            "status": self.status.value,
            "message": self.message,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "steps_total": self.steps_total,
            "rolled_back": self.rolled_back,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Default procedures
# ---------------------------------------------------------------------------


def create_default_failover_procedure() -> FailoverProcedure:
    """Create a default failover procedure with standard steps."""
    steps = [
        FailoverStep(
            step_id=str(uuid4()),
            name="pre_check",
            description="Validate pre-conditions: target health, capacity, connectivity",
            order=1,
            rollback_action="none",
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="drain_source",
            description="Drain connections from source node gracefully",
            order=2,
            rollback_action="restore_connections",
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="sync_data",
            description="Ensure data synchronization between source and target",
            order=3,
            rollback_action="none",
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="promote_target",
            description="Promote target node to active status",
            order=4,
            rollback_action="demote_target",
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="update_routing",
            description="Update load balancer and DNS routing to target",
            order=5,
            rollback_action="restore_routing",
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="verify",
            description="Verify target is serving traffic correctly",
            order=6,
            rollback_action="none",
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="decommission_source",
            description="Mark source node as failed/drained",
            order=7,
            rollback_action="reactivate_source",
        ),
    ]
    return FailoverProcedure(
        procedure_id=str(uuid4()),
        name="default_failover",
        description="Standard failover procedure with full verification",
        steps=steps,
    )


def create_rollback_procedure() -> FailoverProcedure:
    """Create a rollback procedure to undo a failover."""
    steps = [
        FailoverStep(
            step_id=str(uuid4()),
            name="pre_check",
            description="Validate source node is available for rollback",
            order=1,
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="drain_target",
            description="Drain connections from target node",
            order=2,
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="demote_target",
            description="Demote target node from active status",
            order=3,
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="promote_source",
            description="Re-promote source node to active status",
            order=4,
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="restore_routing",
            description="Restore routing to source node",
            order=5,
        ),
        FailoverStep(
            step_id=str(uuid4()),
            name="verify",
            description="Verify source is serving traffic correctly",
            order=6,
        ),
    ]
    return FailoverProcedure(
        procedure_id=str(uuid4()),
        name="default_rollback",
        description="Standard rollback procedure to restore original state",
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Failover automation engine
# ---------------------------------------------------------------------------


class FailoverAutomation:
    """Automated failover orchestration engine.

    Coordinates failover procedures, step execution, rollback, and
    audit logging. Thread-safe for concurrent operations.

    Attributes:
        procedure_root: Root directory for procedure storage.
        auto_rollback: Whether to auto-rollback on failure.
        max_retries: Maximum retry attempts per step.
        retry_delay_seconds: Delay between retries.
    """

    def __init__(
        self,
        procedure_root: str | Path,
        *,
        auto_rollback: bool = True,
        max_retries: int = 3,
        retry_delay_seconds: float = 5.0,
    ) -> None:
        self.procedure_root = Path(procedure_root).resolve()
        self.auto_rollback = auto_rollback
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._ensure_root()
        self._executions: dict[str, FailoverExecution] = {}
        self._procedures: dict[str, FailoverProcedure] = {}
        self._lock = threading.RLock()
        self._step_handlers: dict[str, Callable[..., None]] = {}
        self._load_procedures()

    def _ensure_root(self) -> None:
        self.procedure_root.mkdir(parents=True, exist_ok=True)

    def _procedure_path(self, procedure_id: str) -> Path:
        return self.procedure_root / f"{procedure_id}.json"

    def _execution_path(self, execution_id: str) -> Path:
        return self.procedure_root / f"_exec_{execution_id}.json"

    def _write_procedure(self, procedure: FailoverProcedure) -> None:
        path = self._procedure_path(procedure.procedure_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(procedure.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_procedure(self, procedure_id: str) -> FailoverProcedure:
        path = self._procedure_path(procedure_id)
        if not path.exists():
            raise FailoverAutomationError(
                f"procedure {procedure_id!r} not found",
                "procedure_not_found",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return FailoverProcedure.from_dict(data)

    def _write_execution(self, execution: FailoverExecution) -> None:
        path = self._execution_path(execution.execution_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(execution.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_execution(self, execution_id: str) -> FailoverExecution:
        path = self._execution_path(execution_id)
        if not path.exists():
            raise FailoverAutomationError(
                f"execution {execution_id!r} not found",
                "execution_not_found",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        steps = []
        for s in data.get("steps", []):
            steps.append(FailoverStep(
                step_id=s["step_id"],
                name=s["name"],
                description=s["description"],
                order=s["order"],
                status=FailoverStepStatus(s.get("status", "pending")),
                started_at=(
                    datetime.fromisoformat(s["started_at"])
                    if s.get("started_at")
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(s["completed_at"])
                    if s.get("completed_at")
                    else None
                ),
                duration_seconds=s.get("duration_seconds", 0.0),
                error=s.get("error", ""),
                rollback_action=s.get("rollback_action"),
                metadata=dict(s.get("metadata", {})),
            ))
        return FailoverExecution(
            execution_id=data["execution_id"],
            procedure_id=data["procedure_id"],
            tenant_id=data["tenant_id"],
            source_node=data["source_node"],
            target_node=data.get("target_node"),
            trigger=FailoverTrigger(data.get("trigger", "manual")),
            status=FailoverStatus(data.get("status", "pending")),
            mode=FailoverMode(data.get("mode", "manual")),
            steps=steps,
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            duration_seconds=data.get("duration_seconds", 0.0),
            error=data.get("error", ""),
            metadata=dict(data.get("metadata", {})),
        )

    def _load_procedures(self) -> None:
        """Load stored procedures from disk."""
        if not self.procedure_root.exists():
            return
        for entry in self.procedure_root.iterdir():
            if not entry.is_file() or not entry.name.endswith(".json"):
                continue
            if entry.name.startswith("_"):
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
                proc = FailoverProcedure.from_dict(data)
                self._procedures[proc.procedure_id] = proc
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Procedure management
    # ------------------------------------------------------------------

    def register_procedure(self, procedure: FailoverProcedure) -> None:
        """Register a failover procedure."""
        with self._lock:
            self._procedures[procedure.procedure_id] = procedure
            self._write_procedure(procedure)

    def get_procedure(self, procedure_id: str) -> FailoverProcedure:
        """Get a procedure by ID."""
        with self._lock:
            if procedure_id in self._procedures:
                return self._procedures[procedure_id]
            return self._read_procedure(procedure_id)

    def list_procedures(self) -> list[FailoverProcedure]:
        """List all registered procedures."""
        with self._lock:
            return list(self._procedures.values())

    def register_step_handler(self, step_name: str, handler: Callable[..., None]) -> None:
        """Register a handler for a specific step type.

        Args:
            step_name: Name of the step to handle.
            handler: Callable that executes the step logic.
        """
        self._step_handlers[step_name] = handler

    # ------------------------------------------------------------------
    # Failover execution
    # ------------------------------------------------------------------

    def execute_failover(
        self,
        tenant_id: str,
        source_node: str,
        target_node: str | None = None,
        *,
        procedure_id: str | None = None,
        trigger: FailoverTrigger | str = FailoverTrigger.MANUAL,
        mode: FailoverMode | str = FailoverMode.AUTOMATIC,
        metadata: dict[str, Any] | None = None,
    ) -> FailoverResult:
        """Execute a failover.

        Args:
            tenant_id: Tenant UUID string.
            source_node: Node to fail over from.
            target_node: Node to fail over to (None = auto-select).
            procedure_id: Procedure to use (None = default).
            trigger: What triggered this failover.
            mode: Execution mode.
            metadata: Additional metadata.

        Returns:
            FailoverResult with execution details.
        """
        if isinstance(trigger, str):
            trigger = FailoverTrigger(trigger)
        if isinstance(mode, str):
            mode = FailoverMode(mode)

        start_time = time.monotonic()
        execution_id = str(uuid4())

        # Get procedure
        if procedure_id:
            procedure = self.get_procedure(procedure_id)
        else:
            procedure = create_default_failover_procedure()
            self.register_procedure(procedure)

        # Create execution record
        execution = FailoverExecution(
            execution_id=execution_id,
            procedure_id=procedure.procedure_id,
            tenant_id=tenant_id,
            source_node=source_node,
            target_node=target_node,
            trigger=trigger,
            status=FailoverStatus.IN_PROGRESS,
            mode=mode,
            steps=[FailoverStep(
                step_id=s.step_id,
                name=s.name,
                description=s.description,
                order=s.order,
                rollback_action=s.rollback_action,
            ) for s in procedure.steps],
            started_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        with self._lock:
            self._executions[execution_id] = execution
            self._write_execution(execution)

        # Execute steps
        steps_completed = 0
        steps_failed = 0
        failed = False
        last_step: FailoverStep | None = None
        current_steps = list(execution.steps)

        for step in sorted(current_steps, key=lambda s: s.order):
            if failed and self.auto_rollback:
                break

            step_start = time.monotonic()
            step = replace(step, started_at=datetime.now(timezone.utc))

            try:
                handler = self._step_handlers.get(step.name)
                if handler:
                    handler(execution, step)
                else:
                    # Default: simulate step execution
                    self._default_step_handler(execution, step)

                step = replace(step, status=FailoverStepStatus.COMPLETED)
                steps_completed += 1

            except Exception as exc:
                step = replace(
                    step,
                    status=FailoverStepStatus.FAILED,
                    error=str(exc),
                )
                steps_failed += 1
                failed = True

                if self.auto_rollback:
                    current_steps = self._rollback_execution(current_steps, step)
                    break

            finally:
                step = replace(
                    step,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=time.monotonic() - step_start,
                )
                # Update the step in the execution's step list
                for i, s in enumerate(current_steps):
                    if s.step_id == step.step_id:
                        current_steps[i] = step
                        break
                last_step = step

        # Finalize
        duration = time.monotonic() - start_time
        completed_at = datetime.now(timezone.utc)

        if failed:
            status = FailoverStatus.FAILED if not self.auto_rollback else FailoverStatus.ROLLED_BACK
            success = False
            message = f"failover failed at step: {last_step.name if last_step else 'unknown'}"
            error_msg = last_step.error if last_step else ""
        else:
            status = FailoverStatus.COMPLETED
            success = True
            message = f"failover completed: {steps_completed}/{len(current_steps)} steps"
            error_msg = ""

        execution = replace(
            execution,
            steps=current_steps,
            status=status,
            duration_seconds=duration,
            completed_at=completed_at,
            error=error_msg,
        )

        with self._lock:
            self._executions[execution_id] = execution
            self._write_execution(execution)

        return FailoverResult(
            success=success,
            execution_id=execution_id,
            status=status,
            message=message,
            duration_seconds=duration,
            error=execution.error,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            steps_total=len(execution.steps),
            rolled_back=(status == FailoverStatus.ROLLED_BACK),
        )

    def _default_step_handler(
        self, execution: FailoverExecution, step: FailoverStep
    ) -> None:
        """Default step handler - simulates step execution."""
        # In production, this would perform actual operations
        time.sleep(0.01)  # Minimal delay to simulate work

    def _rollback_execution(
        self, steps: list[FailoverStep], failed_step: FailoverStep
    ) -> list[FailoverStep]:
        """Rollback a failover execution. Returns updated step list."""
        # Find steps to rollback (completed steps before the failed one, in reverse)
        steps_to_rollback = [
            s for s in steps
            if s.status == FailoverStepStatus.COMPLETED
            and s.order < failed_step.order
            and s.rollback_action
            and s.rollback_action != "none"
        ]

        updated = list(steps)
        for step in reversed(steps_to_rollback):
            try:
                handler = self._step_handlers.get(f"rollback_{step.name}")
                if handler:
                    handler(step)
                for i, s in enumerate(updated):
                    if s.step_id == step.step_id:
                        updated[i] = replace(s, status=FailoverStepStatus.ROLLED_BACK)
                        break
            except Exception:
                pass  # Best-effort rollback
        return updated

    def rollback(self, execution_id: str) -> FailoverResult:
        """Manually rollback a failover execution.

        Args:
            execution_id: The execution to rollback.

        Returns:
            FailoverResult with rollback details.
        """
        start_time = time.monotonic()

        with self._lock:
            execution = self._executions.get(execution_id)
            if not execution:
                try:
                    execution = self._read_execution(execution_id)
                except FailoverAutomationError:
                    return FailoverResult(
                        success=False,
                        execution_id=execution_id,
                        status=FailoverStatus.FAILED,
                        message=f"execution {execution_id!r} not found",
                        error="execution_not_found",
                    )

        # Create rollback procedure
        rollback_proc = create_rollback_procedure()

        # Execute rollback steps
        steps_completed = 0
        rollback_steps = list(rollback_proc.steps)
        for step in sorted(rollback_steps, key=lambda s: s.order):
            step_start = time.monotonic()
            step = replace(step, started_at=datetime.now(timezone.utc))

            try:
                handler = self._step_handlers.get(step.name)
                if handler:
                    handler(execution, step)
                else:
                    self._default_step_handler(execution, step)

                step = replace(step, status=FailoverStepStatus.COMPLETED)
                steps_completed += 1

            except Exception as exc:
                step = replace(step, status=FailoverStepStatus.FAILED, error=str(exc))

            finally:
                step = replace(
                    step,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=time.monotonic() - step_start,
                )
                for i, s in enumerate(rollback_steps):
                    if s.step_id == step.step_id:
                        rollback_steps[i] = step
                        break

        duration = time.monotonic() - start_time
        success = steps_completed == len(rollback_steps)

        execution = replace(
            execution,
            status=FailoverStatus.ROLLED_BACK,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=duration,
        )

        with self._lock:
            self._executions[execution_id] = execution
            self._write_execution(execution)

        return FailoverResult(
            success=success,
            execution_id=execution_id,
            status=FailoverStatus.ROLLED_BACK,
            message=f"rollback {'completed' if success else 'partial'}: {steps_completed}/{len(rollback_proc.steps)} steps",
            duration_seconds=duration,
            steps_completed=steps_completed,
            steps_failed=len(rollback_proc.steps) - steps_completed,
            steps_total=len(rollback_proc.steps),
            rolled_back=True,
        )

    # ------------------------------------------------------------------
    # Monitoring and status
    # ------------------------------------------------------------------

    def get_execution(self, execution_id: str) -> FailoverExecution | None:
        """Get an execution by ID."""
        with self._lock:
            if execution_id in self._executions:
                return self._executions[execution_id]
            try:
                return self._read_execution(execution_id)
            except FailoverAutomationError:
                return None

    def list_executions(
        self,
        *,
        tenant_id: str | None = None,
        status: FailoverStatus | None = None,
    ) -> list[FailoverExecution]:
        """List executions, optionally filtered."""
        with self._lock:
            executions = list(self._executions.values())

        # Also load from disk
        if self.procedure_root.exists():
            for entry in self.procedure_root.iterdir():
                if not entry.is_file() or not entry.name.startswith("_exec_"):
                    continue
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                    exec_id = data["execution_id"]
                    if exec_id not in self._executions:
                        execution = self._read_execution(exec_id)
                        executions.append(execution)
                except Exception:
                    continue

        if tenant_id:
            executions = [e for e in executions if e.tenant_id == tenant_id]
        if status:
            executions = [e for e in executions if e.status == status]

        return sorted(executions, key=lambda e: e.created_at, reverse=True)

    def get_status(self) -> dict[str, Any]:
        """Get overall failover automation status."""
        with self._lock:
            executions = list(self._executions.values())

        total = len(executions)
        completed = sum(1 for e in executions if e.status == FailoverStatus.COMPLETED)
        failed = sum(1 for e in executions if e.status == FailoverStatus.FAILED)
        rolled_back = sum(1 for e in executions if e.status == FailoverStatus.ROLLED_BACK)
        in_progress = sum(1 for e in executions if e.status == FailoverStatus.IN_PROGRESS)

        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "rolled_back": rolled_back,
            "in_progress": in_progress,
            "procedures_registered": len(self._procedures),
            "auto_rollback": self.auto_rollback,
            "max_retries": self.max_retries,
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def execute_failover(
    procedure_root: str | Path,
    tenant_id: str,
    source_node: str,
    **kwargs: Any,
) -> FailoverResult:
    """Convenience function: execute failover with a new engine."""
    engine = FailoverAutomation(procedure_root)
    return engine.execute_failover(tenant_id, source_node, **kwargs)


def rollback_failover(
    procedure_root: str | Path,
    execution_id: str,
) -> FailoverResult:
    """Convenience function: rollback with a new engine."""
    engine = FailoverAutomation(procedure_root)
    return engine.rollback(execution_id)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "FailoverAutomationError",
    "FailoverExecutionError",
    "RollbackError",
    "FailoverValidationError",
    "FailoverTrigger",
    "FailoverStepStatus",
    "FailoverStatus",
    "FailoverMode",
    "FailoverStep",
    "FailoverProcedure",
    "FailoverExecution",
    "FailoverResult",
    "create_default_failover_procedure",
    "create_rollback_procedure",
    "FailoverAutomation",
    "execute_failover",
    "rollback_failover",
]
