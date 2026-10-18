"""DR testing framework for Data Center Commander.

Provides disaster recovery testing orchestration including test plan
management, test execution, results tracking, and compliance reporting.
Supports scheduled tests, on-demand tests, and automated test suites.

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


class DRTestingError(Exception):
    """Base exception for DR testing failures."""

    def __init__(self, message: str, code: str = "dr_testing_error") -> None:
        self.code = code
        super().__init__(message)


class TestPlanNotFoundError(DRTestingError):
    """Raised when a test plan cannot be found."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"test plan {plan_id!r} not found", "test_plan_not_found")


class TestExecutionError(DRTestingError):
    """Raised when a test execution fails."""

    def __init__(self, message: str, test_step: str = "") -> None:
        self.test_step = test_step
        super().__init__(message, "test_execution_error")


class TestValidationError(DRTestingError):
    """Raised when a test plan is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "test_validation_error")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestType(str, Enum):
    """Type of DR test."""

    FAILOVER = "failover"
    FAILOBACK = "failback"
    RESTORE = "restore"
    BACKUP_VERIFICATION = "backup_verification"
    NETWORK_ISOLATION = "network_isolation"
    POWER_OUTAGE = "power_outage"
    DATA_CORRUPTION = "data_corruption"
    COMPLETE_DR = "complete_dr"


class TestFrequency(str, Enum):
    """How often to run a test."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ON_DEMAND = "on_demand"


class TestStatus(str, Enum):
    """Status of a test execution."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TestStepStatus(str, Enum):
    """Status of a test step."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TestResult(str, Enum):
    """Overall test result."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestStep:
    """A single step in a DR test."""

    step_id: str
    name: str
    description: str
    order: int
    expected_result: str = ""
    actual_result: str = ""
    status: TestStepStatus = TestStepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    error: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestStep:
        return cls(
            step_id=data["step_id"],
            name=data["name"],
            description=data["description"],
            order=data["order"],
            expected_result=data.get("expected_result", ""),
            actual_result=data.get("actual_result", ""),
            status=TestStepStatus(data.get("status", "pending")),
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
            evidence=list(data.get("evidence", [])),
        )


@dataclass(frozen=True)
class TestPlan:
    """A DR test plan definition."""

    plan_id: str
    tenant_id: str
    name: str
    description: str
    test_type: TestType
    frequency: TestFrequency
    steps: list[TestStep]
    rto_target_seconds: float = 3600.0
    rpo_target_seconds: float = 300.0
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.steps:
            raise TestValidationError("test plan must have at least one step")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type.value,
            "frequency": self.frequency.value,
            "steps": [s.to_dict() for s in self.steps],
            "rto_target_seconds": self.rto_target_seconds,
            "rpo_target_seconds": self.rpo_target_seconds,
            "enabled": self.enabled,
            "tags": dict(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestPlan:
        steps = [TestStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            plan_id=data["plan_id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            description=data["description"],
            test_type=TestType(data.get("test_type", "failover")),
            frequency=TestFrequency(data.get("frequency", "monthly")),
            steps=steps,
            rto_target_seconds=float(data.get("rto_target_seconds", 3600.0)),
            rpo_target_seconds=float(data.get("rpo_target_seconds", 300.0)),
            enabled=bool(data.get("enabled", True)),
            tags=dict(data.get("tags", {})),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_run_at=(
                datetime.fromisoformat(data["last_run_at"])
                if data.get("last_run_at")
                else None
            ),
            next_run_at=(
                datetime.fromisoformat(data["next_run_at"])
                if data.get("next_run_at")
                else None
            ),
        )


@dataclass
class TestExecution:
    """A running or completed test execution."""

    execution_id: str
    plan_id: str
    tenant_id: str
    test_type: TestType
    status: TestStatus
    steps: list[TestStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    rto_actual_seconds: float = 0.0
    rpo_actual_seconds: float = 0.0
    result: TestResult = TestResult.INCONCLUSIVE
    error: str = ""
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "tenant_id": self.tenant_id,
            "test_type": self.test_type.value,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "rto_actual_seconds": round(self.rto_actual_seconds, 3),
            "rpo_actual_seconds": round(self.rpo_actual_seconds, 3),
            "result": self.result.value,
            "error": self.error,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata),
        }


@dataclass
class TestResultSummary:
    """Summary of a test execution result."""

    execution_id: str
    plan_id: str
    tenant_id: str
    test_type: TestType
    result: TestResult
    status: TestStatus
    duration_seconds: float
    rto_actual_seconds: float
    rpo_actual_seconds: float
    rto_target_seconds: float
    rpo_target_seconds: float
    rto_compliant: bool
    rpo_compliant: bool
    steps_passed: int
    steps_failed: int
    steps_total: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "tenant_id": self.tenant_id,
            "test_type": self.test_type.value,
            "result": self.result.value,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 3),
            "rto_actual_seconds": round(self.rto_actual_seconds, 3),
            "rpo_actual_seconds": round(self.rpo_actual_seconds, 3),
            "rto_target_seconds": self.rto_target_seconds,
            "rpo_target_seconds": self.rpo_target_seconds,
            "rto_compliant": self.rto_compliant,
            "rpo_compliant": self.rpo_compliant,
            "steps_passed": self.steps_passed,
            "steps_failed": self.steps_failed,
            "steps_total": self.steps_total,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Default test plans
# ---------------------------------------------------------------------------


def create_failover_test_plan(tenant_id: str) -> TestPlan:
    """Create a default failover test plan."""
    steps = [
        TestStep(
            step_id=str(uuid4()),
            name="pre_test_check",
            description="Verify all systems are healthy before test",
            order=1,
            expected_result="All systems healthy",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="initiate_failover",
            description="Trigger failover to secondary site",
            order=2,
            expected_result="Failover initiated successfully",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="verify_secondary",
            description="Verify secondary site is serving traffic",
            order=3,
            expected_result="Secondary site operational",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="test_data_integrity",
            description="Verify data integrity on secondary",
            order=4,
            expected_result="Data integrity verified",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="measure_rto",
            description="Measure actual RTO",
            order=5,
            expected_result="RTO within target",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="failback",
            description="Fail back to primary site",
            order=6,
            expected_result="Failback completed successfully",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="post_test_verification",
            description="Verify all systems restored",
            order=7,
            expected_result="All systems restored",
        ),
    ]
    return TestPlan(
        plan_id=str(uuid4()),
        tenant_id=tenant_id,
        name="Failover Test",
        description="Tests failover to secondary site and back",
        test_type=TestType.FAILOVER,
        frequency=TestFrequency.MONTHLY,
        steps=steps,
    )


def create_restore_test_plan(tenant_id: str) -> TestPlan:
    """Create a default restore test plan."""
    steps = [
        TestStep(
            step_id=str(uuid4()),
            name="select_backup",
            description="Select a backup to restore",
            order=1,
            expected_result="Backup selected",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="verify_backup",
            description="Verify backup integrity",
            order=2,
            expected_result="Backup verified",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="execute_restore",
            description="Execute restore operation",
            order=3,
            expected_result="Restore completed",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="verify_data",
            description="Verify restored data integrity",
            order=4,
            expected_result="Data verified",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="measure_rto_rpo",
            description="Measure actual RTO and RPO",
            order=5,
            expected_result="RTO/RPO within targets",
        ),
    ]
    return TestPlan(
        plan_id=str(uuid4()),
        tenant_id=tenant_id,
        name="Restore Test",
        description="Tests backup restore and data integrity",
        test_type=TestType.RESTORE,
        frequency=TestFrequency.WEEKLY,
        steps=steps,
    )


def create_complete_dr_test_plan(tenant_id: str) -> TestPlan:
    """Create a comprehensive DR test plan."""
    steps = [
        TestStep(
            step_id=str(uuid4()),
            name="pre_test_audit",
            description="Complete pre-test system audit",
            order=1,
            expected_result="Audit complete",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="backup_verification",
            description="Verify all recent backups",
            order=2,
            expected_result="Backups verified",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="failover_test",
            description="Execute full failover",
            order=3,
            expected_result="Failover successful",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="secondary_operations",
            description="Run operations on secondary",
            order=4,
            expected_result="Operations successful",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="data_integrity_check",
            description="Comprehensive data integrity check",
            order=5,
            expected_result="Data integrity confirmed",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="failback_test",
            description="Execute failback",
            order=6,
            expected_result="Failback successful",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="post_test_audit",
            description="Complete post-test system audit",
            order=7,
            expected_result="Audit complete",
        ),
        TestStep(
            step_id=str(uuid4()),
            name="rto_rpo_assessment",
            description="Assess RTO/RPO compliance",
            order=8,
            expected_result="RTO/RPO within targets",
        ),
    ]
    return TestPlan(
        plan_id=str(uuid4()),
        tenant_id=tenant_id,
        name="Complete DR Test",
        description="Comprehensive disaster recovery test",
        test_type=TestType.COMPLETE_DR,
        frequency=TestFrequency.QUARTERLY,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# DR testing engine
# ---------------------------------------------------------------------------


class DRTestEngine:
    """DR testing orchestration engine.

    Manages test plans, executes tests, tracks results, and generates
    compliance reports. Thread-safe for concurrent operations.

    Attributes:
        test_root: Root directory for test storage.
        step_handlers: Custom handlers for test steps.
    """

    def __init__(self, test_root: str | Path) -> None:
        self.test_root = Path(test_root).resolve()
        self._ensure_root()
        self._lock = threading.RLock()
        self._plans: dict[str, TestPlan] = {}
        self._executions: dict[str, TestExecution] = {}
        self._step_handlers: dict[str, Callable[..., None]] = {}
        self._load_plans()

    def _ensure_root(self) -> None:
        self.test_root.mkdir(parents=True, exist_ok=True)

    def _plan_path(self, plan_id: str) -> Path:
        return self.test_root / f"{plan_id}.json"

    def _execution_path(self, execution_id: str) -> Path:
        return self.test_root / f"_exec_{execution_id}.json"

    def _write_plan(self, plan: TestPlan) -> None:
        path = self._plan_path(plan.plan_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(plan.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_plan(self, plan_id: str) -> TestPlan:
        path = self._plan_path(plan_id)
        if not path.exists():
            raise TestPlanNotFoundError(plan_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return TestPlan.from_dict(data)

    def _write_execution(self, execution: TestExecution) -> None:
        path = self._execution_path(execution.execution_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(execution.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_execution(self, execution_id: str) -> TestExecution:
        path = self._execution_path(execution_id)
        if not path.exists():
            raise DRTestingError(
                f"execution {execution_id!r} not found",
                "execution_not_found",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        steps = [TestStep.from_dict(s) for s in data.get("steps", [])]
        return TestExecution(
            execution_id=data["execution_id"],
            plan_id=data["plan_id"],
            tenant_id=data["tenant_id"],
            test_type=TestType(data.get("test_type", "failover")),
            status=TestStatus(data.get("status", "pending")),
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
            rto_actual_seconds=data.get("rto_actual_seconds", 0.0),
            rpo_actual_seconds=data.get("rpo_actual_seconds", 0.0),
            result=TestResult(data.get("result", "inconclusive")),
            error=data.get("error", ""),
            evidence=list(data.get("evidence", [])),
            metadata=dict(data.get("metadata", {})),
        )

    def _load_plans(self) -> None:
        """Load stored plans from disk."""
        if not self.test_root.exists():
            return
        for entry in self.test_root.iterdir():
            if not entry.is_file() or not entry.name.endswith(".json"):
                continue
            if entry.name.startswith("_"):
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
                plan = TestPlan.from_dict(data)
                self._plans[plan.plan_id] = plan
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def create_plan(
        self,
        tenant_id: str,
        name: str,
        *,
        test_type: TestType = TestType.FAILOVER,
        frequency: TestFrequency = TestFrequency.MONTHLY,
        description: str = "",
        rto_target_seconds: float = 3600.0,
        rpo_target_seconds: float = 300.0,
        tags: dict[str, str] | None = None,
    ) -> TestPlan:
        """Create a new test plan with default steps.

        Args:
            tenant_id: Tenant UUID string.
            name: Plan name.
            test_type: Type of test.
            frequency: How often to run.
            description: Plan description.
            rto_target_seconds: RTO target in seconds.
            rpo_target_seconds: RPO target in seconds.
            tags: Arbitrary metadata.

        Returns:
            The created TestPlan.
        """
        # Get default steps based on test type
        if test_type == TestType.FAILOVER:
            default_plan = create_failover_test_plan(tenant_id)
        elif test_type == TestType.RESTORE:
            default_plan = create_restore_test_plan(tenant_id)
        elif test_type == TestType.COMPLETE_DR:
            default_plan = create_complete_dr_test_plan(tenant_id)
        else:
            default_plan = create_failover_test_plan(tenant_id)

        plan = TestPlan(
            plan_id=str(uuid4()),
            tenant_id=tenant_id,
            name=name,
            description=description or default_plan.description,
            test_type=test_type,
            frequency=frequency,
            steps=default_plan.steps,
            rto_target_seconds=rto_target_seconds,
            rpo_target_seconds=rpo_target_seconds,
            tags=tags or {},
        )
        self._write_plan(plan)
        with self._lock:
            self._plans[plan.plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> TestPlan:
        """Get a test plan by ID."""
        with self._lock:
            if plan_id in self._plans:
                return self._plans[plan_id]
            return self._read_plan(plan_id)

    def list_plans(
        self,
        *,
        tenant_id: str | None = None,
        test_type: TestType | None = None,
        enabled_only: bool = False,
    ) -> list[TestPlan]:
        """List test plans, optionally filtered."""
        with self._lock:
            plans = list(self._plans.values())

        # Also load from disk
        if self.test_root.exists():
            for entry in self.test_root.iterdir():
                if not entry.is_file() or not entry.name.endswith(".json"):
                    continue
                if entry.name.startswith("_"):
                    continue
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                    plan = TestPlan.from_dict(data)
                    if plan.plan_id not in self._plans:
                        plans.append(plan)
                except Exception:
                    continue

        if tenant_id:
            plans = [p for p in plans if p.tenant_id == tenant_id]
        if test_type:
            plans = [p for p in plans if p.test_type == test_type]
        if enabled_only:
            plans = [p for p in plans if p.enabled]

        return sorted(plans, key=lambda p: p.created_at, reverse=True)

    def update_plan(self, plan_id: str, **updates: Any) -> TestPlan:
        """Update a test plan."""
        plan = self._read_plan(plan_id)
        data = plan.to_dict()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        for key, value in updates.items():
            if key in data and key not in ("plan_id", "tenant_id", "created_at"):
                data[key] = value

        updated = TestPlan.from_dict(data)
        self._write_plan(updated)
        with self._lock:
            self._plans[plan_id] = updated
        return updated

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a test plan."""
        path = self._plan_path(plan_id)
        if not path.exists():
            return False
        path.unlink()
        with self._lock:
            self._plans.pop(plan_id, None)
        return True

    def register_step_handler(self, step_name: str, handler: Callable[..., None]) -> None:
        """Register a handler for a specific test step."""
        self._step_handlers[step_name] = handler

    # ------------------------------------------------------------------
    # Test execution
    # ------------------------------------------------------------------

    def execute_test(
        self,
        plan_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> TestResultSummary:
        """Execute a test plan.

        Args:
            plan_id: The test plan to execute.
            metadata: Additional metadata for this execution.

        Returns:
            TestResultSummary with execution results.
        """
        start_time = time.monotonic()
        execution_id = str(uuid4())

        plan = self.get_plan(plan_id)

        execution = TestExecution(
            execution_id=execution_id,
            plan_id=plan_id,
            tenant_id=plan.tenant_id,
            test_type=plan.test_type,
            status=TestStatus.RUNNING,
            steps=[TestStep(
                step_id=s.step_id,
                name=s.name,
                description=s.description,
                order=s.order,
                expected_result=s.expected_result,
            ) for s in plan.steps],
            started_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        with self._lock:
            self._executions[execution_id] = execution
            self._write_execution(execution)

        # Execute steps
        steps_passed = 0
        steps_failed = 0
        current_steps = list(execution.steps)

        for step in sorted(current_steps, key=lambda s: s.order):
            step_start = time.monotonic()
            step = replace(step, started_at=datetime.now(timezone.utc))

            try:
                handler = self._step_handlers.get(step.name)
                if handler:
                    handler(execution, step)
                else:
                    self._default_step_handler(execution, step)

                step = replace(step, status=TestStepStatus.PASSED)
                steps_passed += 1

            except Exception as exc:
                step = replace(step, status=TestStepStatus.FAILED, error=str(exc))
                steps_failed += 1

            finally:
                step = replace(
                    step,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=time.monotonic() - step_start,
                )
                for i, s in enumerate(current_steps):
                    if s.step_id == step.step_id:
                        current_steps[i] = step
                        break

        # Calculate results
        duration = time.monotonic() - start_time
        completed_at = datetime.now(timezone.utc)

        # RTO/RPO actuals (from step durations as proxy)
        rto_actual = duration
        rpo_actual = duration * 0.1  # Simplified: assume 10% of RTO

        rto_compliant = rto_actual <= plan.rto_target_seconds
        rpo_compliant = rpo_actual <= plan.rpo_target_seconds

        if steps_failed == 0 and rto_compliant and rpo_compliant:
            result = TestResult.PASS
            status = TestStatus.PASSED
        elif steps_passed > 0:
            result = TestResult.PARTIAL
            status = TestStatus.PARTIAL
        else:
            result = TestResult.FAIL
            status = TestStatus.FAILED

        execution = replace(
            execution,
            steps=current_steps,
            status=status,
            duration_seconds=duration,
            rto_actual_seconds=rto_actual,
            rpo_actual_seconds=rpo_actual,
            result=result,
            completed_at=completed_at,
        )

        with self._lock:
            self._executions[execution_id] = execution
            self._write_execution(execution)

        return TestResultSummary(
            execution_id=execution_id,
            plan_id=plan_id,
            tenant_id=plan.tenant_id,
            test_type=plan.test_type,
            result=result,
            status=status,
            duration_seconds=duration,
            rto_actual_seconds=rto_actual,
            rpo_actual_seconds=rpo_actual,
            rto_target_seconds=plan.rto_target_seconds,
            rpo_target_seconds=plan.rpo_target_seconds,
            rto_compliant=rto_compliant,
            rpo_compliant=rpo_compliant,
            steps_passed=steps_passed,
            steps_failed=steps_failed,
            steps_total=len(current_steps),
        )

    def _default_step_handler(
        self, execution: TestExecution, step: TestStep
    ) -> None:
        """Default step handler - simulates step execution."""
        time.sleep(0.01)  # Minimal delay to simulate work

    # ------------------------------------------------------------------
    # Monitoring and reporting
    # ------------------------------------------------------------------

    def get_execution(self, execution_id: str) -> TestExecution | None:
        """Get an execution by ID."""
        with self._lock:
            if execution_id in self._executions:
                return self._executions[execution_id]
            try:
                return self._read_execution(execution_id)
            except DRTestingError:
                return None

    def list_executions(
        self,
        *,
        tenant_id: str | None = None,
        plan_id: str | None = None,
        status: TestStatus | None = None,
    ) -> list[TestExecution]:
        """List executions, optionally filtered."""
        with self._lock:
            executions = list(self._executions.values())

        # Also load from disk
        if self.test_root.exists():
            for entry in self.test_root.iterdir():
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
        if plan_id:
            executions = [e for e in executions if e.plan_id == plan_id]
        if status:
            executions = [e for e in executions if e.status == status]

        return sorted(executions, key=lambda e: e.created_at, reverse=True)

    def get_test_summary(self, tenant_id: str) -> dict[str, Any]:
        """Get a summary of all tests for a tenant."""
        plans = self.list_plans(tenant_id=tenant_id)
        executions = self.list_executions(tenant_id=tenant_id)

        passed = sum(1 for e in executions if e.status == TestStatus.PASSED)
        failed = sum(1 for e in executions if e.status == TestStatus.FAILED)
        partial = sum(1 for e in executions if e.status == TestStatus.PARTIAL)

        return {
            "tenant_id": tenant_id,
            "total_plans": len(plans),
            "total_executions": len(executions),
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "plans": [p.to_dict() for p in plans],
            "recent_executions": [e.to_dict() for e in executions[:10]],
        }

    def get_status(self) -> dict[str, Any]:
        """Get overall DR testing status."""
        with self._lock:
            plans = list(self._plans.values())
            executions = list(self._executions.values())

        total_plans = len(plans)
        total_executions = len(executions)
        passed = sum(1 for e in executions if e.status == TestStatus.PASSED)
        failed = sum(1 for e in executions if e.status == TestStatus.FAILED)
        partial = sum(1 for e in executions if e.status == TestStatus.PARTIAL)

        return {
            "total_plans": total_plans,
            "total_executions": total_executions,
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "pass_rate": round(passed / total_executions * 100, 2) if total_executions > 0 else 0.0,
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_test_plan(
    test_root: str | Path,
    tenant_id: str,
    name: str,
    **kwargs: Any,
) -> TestPlan:
    """Convenience function: create a test plan with a new engine."""
    engine = DRTestEngine(test_root)
    return engine.create_plan(tenant_id, name, **kwargs)


def execute_test(
    test_root: str | Path,
    plan_id: str,
    **kwargs: Any,
) -> TestResultSummary:
    """Convenience function: execute a test with a new engine."""
    engine = DRTestEngine(test_root)
    return engine.execute_test(plan_id, **kwargs)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "DRTestingError",
    "TestPlanNotFoundError",
    "TestExecutionError",
    "TestValidationError",
    "TestType",
    "TestFrequency",
    "TestStatus",
    "TestStepStatus",
    "TestResult",
    "TestStep",
    "TestPlan",
    "TestExecution",
    "TestResultSummary",
    "create_failover_test_plan",
    "create_restore_test_plan",
    "create_complete_dr_test_plan",
    "DRTestEngine",
    "create_test_plan",
    "execute_test",
]
