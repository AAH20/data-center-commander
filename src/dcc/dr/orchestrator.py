"""Top-level disaster recovery orchestrator for Data Center Commander.

Coordinates backup policies, failover automation, RTO/RPO tracking,
and DR testing into a unified management interface.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

from .policies import (
    BackupPolicy,
    PolicyEngine,
    PolicyRunResult,
    PolicySchedule,
    PolicyStatus,
    PolicyType,
    PolicyValidationError,
)
from .failover import (
    FailoverAutomation,
    FailoverMode,
    FailoverResult,
    FailoverStatus,
    FailoverTrigger,
)
from .rto_rpo import (
    ComplianceReport,
    MeasurementSource,
    MetricStatus,
    MetricType,
    RTOTracker,
    RTOTarget,
)
from .testing import (
    DRTestEngine,
    TestResult,
    TestResultSummary,
    TestStatus,
    TestType,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DROrchestratorStatus(str, Enum):
    """Overall DR orchestrator status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DROrchestratorConfig:
    """Configuration for the DR orchestrator.

    Attributes:
        backup_root: Root directory for backups.
        policy_root: Root directory for policies.
        procedure_root: Root directory for failover procedures.
        tracker_root: Root directory for RTO/RPO tracking.
        test_root: Root directory for DR tests.
        auto_failover: Whether to enable automatic failover.
        auto_rollback: Whether to enable automatic rollback on failure.
        default_rto_target_seconds: Default RTO target.
        default_rpo_target_seconds: Default RPO target.
    """

    backup_root: str = "dcc_backups"
    policy_root: str = "dcc_policies"
    procedure_root: str = "dcc_procedures"
    tracker_root: str = "dcc_rto_tracking"
    test_root: str = "dcc_dr_tests"
    auto_failover: bool = True
    auto_rollback: bool = True
    default_rto_target_seconds: float = 3600.0
    default_rpo_target_seconds: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_root": self.backup_root,
            "policy_root": self.policy_root,
            "procedure_root": self.procedure_root,
            "tracker_root": self.tracker_root,
            "test_root": self.test_root,
            "auto_failover": self.auto_failover,
            "auto_rollback": self.auto_rollback,
            "default_rto_target_seconds": self.default_rto_target_seconds,
            "default_rpo_target_seconds": self.default_rpo_target_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DROrchestratorConfig:
        return cls(
            backup_root=data.get("backup_root", "dcc_backups"),
            policy_root=data.get("policy_root", "dcc_policies"),
            procedure_root=data.get("procedure_root", "dcc_procedures"),
            tracker_root=data.get("tracker_root", "dcc_rto_tracking"),
            test_root=data.get("test_root", "dcc_dr_tests"),
            auto_failover=bool(data.get("auto_failover", True)),
            auto_rollback=bool(data.get("auto_rollback", True)),
            default_rto_target_seconds=float(data.get("default_rto_target_seconds", 3600.0)),
            default_rpo_target_seconds=float(data.get("default_rpo_target_seconds", 300.0)),
        )


@dataclass
class DRSummary:
    """Summary of DR readiness for a tenant."""

    tenant_id: str
    generated_at: datetime
    status: DROrchestratorStatus
    policy_count: int = 0
    active_policy_count: int = 0
    due_policy_count: int = 0
    failover_procedure_count: int = 0
    failover_execution_count: int = 0
    rto_compliant: bool = True
    rpo_compliant: bool = True
    rto_avg_seconds: float = 0.0
    rpo_avg_seconds: float = 0.0
    test_plan_count: int = 0
    test_execution_count: int = 0
    test_pass_rate: float = 0.0
    last_test_result: TestResult | None = None
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "generated_at": self.generated_at.isoformat(),
            "status": self.status.value,
            "policy_count": self.policy_count,
            "active_policy_count": self.active_policy_count,
            "due_policy_count": self.due_policy_count,
            "failover_procedure_count": self.failover_procedure_count,
            "failover_execution_count": self.failover_execution_count,
            "rto_compliant": self.rto_compliant,
            "rpo_compliant": self.rpo_compliant,
            "rto_avg_seconds": round(self.rto_avg_seconds, 3),
            "rpo_avg_seconds": round(self.rpo_avg_seconds, 3),
            "test_plan_count": self.test_plan_count,
            "test_execution_count": self.test_execution_count,
            "test_pass_rate": round(self.test_pass_rate, 2),
            "last_test_result": self.last_test_result.value if self.last_test_result else None,
            "recommendations": list(self.recommendations),
        }


# ---------------------------------------------------------------------------
# DR Orchestrator
# ---------------------------------------------------------------------------


class DROrchestrator:
    """Top-level disaster recovery orchestrator.

    Coordinates all DR subsystems (policies, failover, RTO/RPO, testing)
    into a unified management interface.

    State: this class keeps no run state of its own. Everything it reports is
    read from the subsystem roots it was constructed with -- policies and
    procedures as JSON files, failover executions as ``_exec_*.json``, RTO/RPO
    measurements and DR test runs as their own files, policy run outcomes as an
    append-only ``_runs.jsonl`` ledger. Constructing a new orchestrator over the
    same roots therefore recovers the same history; it is not memory-only, and a
    restart does not erase the incident record.

    The exception is the failover step-handler registry: handlers are code, so a
    fresh process must register them again before it can act on a procedure.
    See :class:`~dcc.dr.failover.FailoverAutomation`.

    Usage::

        orchestrator = DROrchestrator("/path/to/dr/data")
        summary = orchestrator.get_tenant_summary("tenant-uuid")
    """

    #: Factory for the engine that executes backup policies, registered from
    #: outside this package by
    #: :func:`dcc.operations.backup.install_dr_backup_execution`. None means no
    #: execution layer is available, and policy runs refuse rather than claim a
    #: backup they did not take.
    _backup_engine_factory: ClassVar[Any | None] = None

    def __init__(
        self,
        config: DROrchestratorConfig | None = None,
        *,
        backup_root: str | None = None,
        policy_root: str | None = None,
        procedure_root: str | None = None,
        tracker_root: str | None = None,
        test_root: str | None = None,
        backup_engine: Any | None = None,
    ) -> None:
        """Initialize the DR orchestrator.

        Args:
            config: Configuration object (optional).
            backup_root: Override backup root directory.
            policy_root: Override policy root directory.
            procedure_root: Override procedure root directory.
            tracker_root: Override tracker root directory.
            test_root: Override test root directory.
            backup_engine: Engine used to execute backups (optional). When
                omitted, a :class:`dcc.operations.backup.BackupEngine` is built
                lazily over ``config.backup_root`` the first time a policy has
                to run.
        """
        self.config = config or DROrchestratorConfig()
        self._lock = threading.RLock()
        self._backup_engine = backup_engine

        # Apply overrides
        if backup_root:
            self.config.backup_root = backup_root
        if policy_root:
            self.config.policy_root = policy_root
        if procedure_root:
            self.config.procedure_root = procedure_root
        if tracker_root:
            self.config.tracker_root = tracker_root
        if test_root:
            self.config.test_root = test_root

        # Initialize subsystems
        self._policy_engine = PolicyEngine(self.config.policy_root)
        self._failover_automation = FailoverAutomation(
            self.config.procedure_root,
            auto_rollback=self.config.auto_rollback,
        )
        self._rto_tracker = RTOTracker(self.config.tracker_root)
        self._test_engine = DRTestEngine(self.config.test_root)

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy_engine

    @property
    def failover_automation(self) -> FailoverAutomation:
        return self._failover_automation

    @property
    def rto_tracker(self) -> RTOTracker:
        return self._rto_tracker

    @property
    def test_engine(self) -> DRTestEngine:
        return self._test_engine

    # ------------------------------------------------------------------
    # Tenant setup
    # ------------------------------------------------------------------

    def setup_tenant(
        self,
        tenant_id: str,
        *,
        rto_target_seconds: float | None = None,
        rpo_target_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Set up DR for a tenant with default configuration.

        Args:
            tenant_id: Tenant UUID string.
            rto_target_seconds: RTO target (uses config default if None).
            rpo_target_seconds: RPO target (uses config default if None).

        Returns:
            Setup summary.
        """
        rto = rto_target_seconds or self.config.default_rto_target_seconds
        rpo = rpo_target_seconds or self.config.default_rpo_target_seconds

        # Set RTO/RPO targets
        targets = RTOTarget(
            rto_target_seconds=rto,
            rpo_target_seconds=rpo,
        )
        self._rto_tracker.set_targets(tenant_id, targets)

        # Create default policies
        policies = self._policy_engine.list_policies(tenant_id)
        if not policies:
            self._policy_engine.create_policy(
                tenant_id,
                "Daily Full Backup",
                policy_type=PolicyType.FULL,
                schedule=PolicySchedule.DAILY,
                retention_days=30,
            )
            self._policy_engine.create_policy(
                tenant_id,
                "Hourly Incremental",
                policy_type=PolicyType.INCREMENTAL,
                schedule=PolicySchedule.HOURLY,
                retention_days=7,
            )

        # Create default test plans
        test_plans = self._test_engine.list_plans(tenant_id=tenant_id)
        if not test_plans:
            self._test_engine.create_plan(
                tenant_id,
                "Monthly Failover Test",
                test_type=TestType.FAILOVER,
            )
            self._test_engine.create_plan(
                tenant_id,
                "Weekly Restore Test",
                test_type=TestType.RESTORE,
            )

        return {
            "tenant_id": tenant_id,
            "rto_target_seconds": rto,
            "rpo_target_seconds": rpo,
            "policies_created": 2,
            "test_plans_created": 2,
        }

    # ------------------------------------------------------------------
    # Backup operations
    # ------------------------------------------------------------------

    def create_backup_policy(
        self,
        tenant_id: str,
        name: str,
        **kwargs: Any,
    ) -> BackupPolicy:
        """Create a backup policy for a tenant."""
        return self._policy_engine.create_policy(tenant_id, name, **kwargs)

    def get_due_policies(self, tenant_id: str) -> list[BackupPolicy]:
        """Get all policies due to run for a tenant."""
        return self._policy_engine.get_due_policies(tenant_id)

    @property
    def backup_engine(self) -> Any | None:
        """The engine that executes backups, or None when none is configured.

        ``dcc.dr`` may not import ``dcc.operations``: the DR package has to stay
        importable without ``pg_dump`` or a database, and a test enforces that
        boundary over the source. So the engine is *handed* to this class instead
        of imported by it -- pass ``backup_engine=`` to the constructor, or
        install a default factory once at the composition root with
        ``dcc.operations.backup.install_dr_backup_execution()``.

        Returns:
            The configured engine, or None when nothing was installed and no
            factory has been registered.
        """
        with self._lock:
            if self._backup_engine is None:
                factory = type(self)._backup_engine_factory
                if factory is None:
                    return None
                self._backup_engine = factory(self.config.backup_root)
            return self._backup_engine

    @classmethod
    def use_backup_engine_factory(cls, factory: Any | None) -> None:
        """Register (or clear) the default engine factory for new orchestrators.

        Args:
            factory: Callable taking the backup root and returning an engine
                exposing ``create_backup`` and ``verify_backup``, or None to
                clear it so that runs refuse instead of guessing.
        """
        cls._backup_engine_factory = factory

    def run_due_policies(
        self,
        tenant_id: str,
        *,
        dsn: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run every due policy for a tenant, for real, and record what happened.

        Each due policy is translated by
        :meth:`~dcc.dr.policies.BackupPolicy.to_engine_params` into a
        ``BackupEngine.create_backup`` call, which shells out to ``pg_dump`` and
        writes a dump file. ``success`` is only recorded when that dump exists
        *and* re-verifies: the checksum stored in the backup metadata is
        recomputed from the file on disk, and the size is compared with the
        artifact. A run that produced no file, an empty file, or a file whose
        checksum does not match is recorded as a failure with the reason attached
        -- never as a success.

        Verification happens regardless of ``BackupPolicy.verify_after``. An
        unverified run is not a successful one, and this record exists to be
        trusted; the flag describes a preference, the record states a fact.

        Failures do not raise. No configured engine, a policy the engine cannot
        express (CONTINUOUS, SNAPSHOT), an unreachable database, a ``pg_dump``
        that exits non-zero, or an artifact that fails verification all produce a
        result row with ``success=False`` and a populated ``error``, so the
        attempt is recorded rather than lost to an exception. One policy failing
        does not stop the remaining due policies from running.

        Every outcome is appended to a durable run ledger
        (``<policy_root>/<tenant_id>/_runs.jsonl``) before the policy schedule is
        advanced, because :meth:`PolicyEngine.record_run` moves ``next_run_at``
        forward without storing success, reason, or backup id. Without the ledger
        a failed backup would leave no trace except a schedule that skips it.

        Args:
            tenant_id: Tenant UUID string.
            dsn: PostgreSQL connection string. Defaults to ``DCC_DATABASE_URL``
                inside the engine, which refuses to run without one.

        Returns:
            One dict per due policy, with ``policy_id``, ``policy_name``,
            ``success``, ``backup_id``, ``message``, ``error``,
            ``duration_seconds``, ``timestamp``, and -- for completed dumps --
            ``size_bytes``, ``checksum``, ``verified`` and ``verification``.
        """
        due = self.get_due_policies(tenant_id)
        return [self._run_policy(tenant_id, policy, dsn=dsn) for policy in due]

    def _run_policy(
        self,
        tenant_id: str,
        policy: BackupPolicy,
        *,
        dsn: str | None,
    ) -> dict[str, Any]:
        """Execute one policy and return the honest outcome record."""
        started = datetime.now(timezone.utc)
        outcome = PolicyRunResult(success=False, policy_id=policy.policy_id)
        extras: dict[str, Any] = {
            "policy_name": policy.name,
            "backup_id": None,
            "size_bytes": None,
            "checksum": None,
            "verified": False,
        }

        try:
            engine = self.backup_engine
            params = policy.to_engine_params()
        except PolicyValidationError as exc:
            # Refuse, do not downgrade: a policy claiming protection the engine
            # cannot deliver must not be recorded as though it delivered it.
            outcome.error = str(exc)
            outcome.message = "policy has no executable equivalent"
        except Exception as exc:  # factory raised, backup root unwritable
            outcome.error = f"{type(exc).__name__}: {exc}"
            outcome.message = "policy could not be executed"
        else:
            if engine is None:
                outcome.error = (
                    "no backup engine configured: nothing was executed. Install "
                    "one with dcc.operations.backup.install_dr_backup_execution() "
                    "or pass backup_engine= to the orchestrator"
                )
                outcome.message = "policy was not run"
            else:
                try:
                    # Values from to_engine_params are the engine's own enum
                    # values as plain strings; the engine's enums are str-backed
                    # and compare equal, which is why this package can call it
                    # without importing it.
                    result = engine.create_backup(
                        **{**params, "tenant_id": tenant_id, "dsn": dsn}
                    )
                except Exception as exc:
                    # create_backup reports pg_dump failures as a result, but a
                    # filesystem error (mkdir/metadata before its own try) can
                    # still escape. Record it instead of losing the attempt.
                    outcome.error = f"{type(exc).__name__}: {exc}"
                    outcome.message = "backup engine raised before completing"
                else:
                    extras["backup_id"] = result.backup_id
                    if result.metadata is not None:
                        extras["size_bytes"] = result.metadata.size_bytes
                        extras["checksum"] = result.metadata.checksum

                    if not result.success:
                        outcome.error = result.error or result.message or "backup failed"
                        outcome.message = result.message
                    else:
                        self._accept_verified_backup(
                            engine, tenant_id, result, outcome, extras
                        )

        outcome.duration_seconds = (datetime.now(timezone.utc) - started).total_seconds()
        outcome.backup_id = extras["backup_id"]
        record = {**outcome.to_dict(), **extras}
        record["policy_name"] = policy.name
        record["success"] = outcome.success

        record_error = self._record_policy_outcome(tenant_id, policy, record)
        if record_error:
            record["record_error"] = record_error
        return record

    def _accept_verified_backup(
        self,
        engine: Any,
        tenant_id: str,
        result: Any,
        outcome: PolicyRunResult,
        extras: dict[str, Any],
    ) -> None:
        """Promote a completed backup to success only if its artifact verifies."""
        metadata = result.metadata
        if metadata is None or not metadata.checksum:
            outcome.error = (
                "backup reported success without a stored checksum; "
                "the artifact cannot be confirmed"
            )
            return
        if metadata.size_bytes <= 0:
            outcome.error = (
                f"backup reported success but the artifact is {metadata.size_bytes} bytes"
            )
            return

        try:
            verification = engine.verify_backup(tenant_id, result.backup_id)
        except Exception as exc:
            outcome.error = f"verification raised: {type(exc).__name__}: {exc}"
            return

        extras["verified"] = bool(verification.valid)
        extras["verification"] = verification.to_dict()

        if not (verification.valid and verification.checksum_match and verification.size_match):
            problems = list(verification.errors) or ["artifact did not verify"]
            outcome.error = "backup artifact failed verification: " + "; ".join(problems)
            return

        outcome.success = True
        outcome.message = result.message

    def _record_policy_outcome(
        self,
        tenant_id: str,
        policy: BackupPolicy,
        record: dict[str, Any],
    ) -> str | None:
        """Persist the outcome durably, then advance the policy schedule.

        Returns an error string if the policy file could not be updated, so the
        caller can surface it without pretending the run disappeared.
        """
        problems: list[str] = []
        try:
            self._append_run_record(tenant_id, record)
        except Exception as exc:
            # The ledger is the durable record; if it cannot be written, say so
            # rather than returning a clean-looking result.
            problems.append(f"run ledger not written: {type(exc).__name__}: {exc}")

        try:
            self._policy_engine.record_run(
                tenant_id,
                policy.policy_id,
                success=bool(record.get("success")),
                backup_id=record.get("backup_id"),
            )
        except Exception as exc:
            problems.append(f"policy schedule not updated: {type(exc).__name__}: {exc}")
        return "; ".join(problems) or None

    def _run_ledger_path(self, tenant_id: str) -> Path:
        """Path of the per-tenant run ledger."""
        return self._policy_engine.policy_root / tenant_id / "_runs.jsonl"

    def _append_run_record(self, tenant_id: str, record: dict[str, Any]) -> None:
        """Append one run outcome to the tenant's run ledger."""
        path = self._run_ledger_path(tenant_id)
        line = json.dumps({"tenant_id": tenant_id, **record}, default=str)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def list_policy_runs(
        self,
        tenant_id: str,
        *,
        policy_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read recorded policy runs, oldest first.

        Args:
            tenant_id: Tenant UUID string.
            policy_id: Only runs of this policy.
            limit: Return at most this many of the most recent runs.

        Returns:
            Run records, oldest first. An unreadable line is skipped rather than
            failing the whole history -- a truncated append must not hide the
            runs before it.
        """
        path = self._run_ledger_path(tenant_id)
        if not path.exists():
            return []

        records: list[dict[str, Any]] = []
        with self._lock:
            lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if policy_id is not None and record.get("policy_id") != policy_id:
                continue
            records.append(record)
        return records[-limit:] if limit > 0 else records

    # ------------------------------------------------------------------
    # Failover operations
    # ------------------------------------------------------------------

    def execute_failover(
        self,
        tenant_id: str,
        source_node: str,
        target_node: str | None = None,
        **kwargs: Any,
    ) -> FailoverResult:
        """Execute a failover for a tenant."""
        return self._failover_automation.execute_failover(
            tenant_id, source_node, target_node, **kwargs
        )

    def rollback_failover(self, execution_id: str) -> FailoverResult:
        """Rollback a failover execution."""
        return self._failover_automation.rollback(execution_id)

    # ------------------------------------------------------------------
    # RTO/RPO operations
    # ------------------------------------------------------------------

    def record_rto(
        self,
        tenant_id: str,
        value_seconds: float,
        **kwargs: Any,
    ):
        """Record an RTO measurement."""
        return self._rto_tracker.record_rto(tenant_id, value_seconds, **kwargs)

    def record_rpo(
        self,
        tenant_id: str,
        value_seconds: float,
        **kwargs: Any,
    ):
        """Record an RPO measurement."""
        return self._rto_tracker.record_rpo(tenant_id, value_seconds, **kwargs)

    def get_compliance_report(self, tenant_id: str) -> ComplianceReport:
        """Generate a compliance report for a tenant."""
        return self._rto_tracker.generate_compliance_report(tenant_id)

    # ------------------------------------------------------------------
    # Testing operations
    # ------------------------------------------------------------------

    def create_test_plan(
        self,
        tenant_id: str,
        name: str,
        **kwargs: Any,
    ):
        """Create a DR test plan."""
        return self._test_engine.create_plan(tenant_id, name, **kwargs)

    def execute_test(self, plan_id: str, **kwargs: Any) -> TestResultSummary:
        """Execute a DR test."""
        return self._test_engine.execute_test(plan_id, **kwargs)

    # ------------------------------------------------------------------
    # Summary and reporting
    # ------------------------------------------------------------------

    def get_tenant_summary(self, tenant_id: str) -> DRSummary:
        """Get a comprehensive DR readiness summary for a tenant.

        Args:
            tenant_id: Tenant UUID string.

        Returns:
            DRSummary with current status and recommendations.
        """
        # Policy stats
        policies = self._policy_engine.list_policies(tenant_id)
        active_policies = [p for p in policies if p.status == PolicyStatus.ACTIVE]
        due_policies = [p for p in active_policies if self._policy_engine.is_due(p)]

        # Failover stats
        failover_status = self._failover_automation.get_status()
        procedures = self._failover_automation.list_procedures()
        executions = self._failover_automation.list_executions(tenant_id=tenant_id)

        # RTO/RPO stats
        rto_stats = self._rto_tracker.get_statistics(tenant_id, MetricType.RTO)
        rpo_stats = self._rto_tracker.get_statistics(tenant_id, MetricType.RPO)
        targets = self._rto_tracker.get_targets(tenant_id)

        rto_compliant = rto_stats.get("breach_count", 0) == 0
        rpo_compliant = rpo_stats.get("breach_count", 0) == 0

        # Test stats
        test_plans = self._test_engine.list_plans(tenant_id=tenant_id)
        test_executions = self._test_engine.list_executions(tenant_id=tenant_id)
        test_status = self._test_engine.get_test_summary(tenant_id)

        passed = test_status.get("passed", 0)
        total_tests = test_status.get("total_executions", 0)
        pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0.0

        # Determine overall status
        recommendations: list[str] = []

        if not rto_compliant or not rpo_compliant:
            status = DROrchestratorStatus.UNHEALTHY
            if not rto_compliant:
                recommendations.append("RTO breaches detected - review failover procedures")
            if not rpo_compliant:
                recommendations.append("RPO breaches detected - increase backup frequency")
        elif due_policies:
            status = DROrchestratorStatus.DEGRADED
            recommendations.append(f"{len(due_policies)} backup policies are due")
        elif pass_rate < 80.0 and total_tests > 0:
            status = DROrchestratorStatus.DEGRADED
            recommendations.append("DR test pass rate below 80% - schedule testing")
        else:
            status = DROrchestratorStatus.HEALTHY

        if not policies:
            recommendations.append("No backup policies configured - run setup_tenant()")
        if not test_plans:
            recommendations.append("No DR test plans configured - run setup_tenant()")

        # Get last test result
        last_test_result = None
        if test_executions:
            last_exec = test_executions[0]
            last_test_result = last_exec.result

        return DRSummary(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            status=status,
            policy_count=len(policies),
            active_policy_count=len(active_policies),
            due_policy_count=len(due_policies),
            failover_procedure_count=len(procedures),
            failover_execution_count=len(executions),
            rto_compliant=rto_compliant,
            rpo_compliant=rpo_compliant,
            rto_avg_seconds=rto_stats.get("avg_seconds", 0.0),
            rpo_avg_seconds=rpo_stats.get("avg_seconds", 0.0),
            test_plan_count=len(test_plans),
            test_execution_count=total_tests,
            test_pass_rate=pass_rate,
            last_test_result=last_test_result,
            recommendations=recommendations,
        )

    def get_overall_status(self) -> dict[str, Any]:
        """Get overall DR orchestrator status across all tenants."""
        policy_stats = self._policy_engine.get_policy_stats("all") if hasattr(self._policy_engine, 'get_policy_stats') else {}
        failover_stats = self._failover_automation.get_status()
        test_stats = self._test_engine.get_status()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config.to_dict(),
            "failover": failover_stats,
            "testing": test_stats,
        }

    def export_summary(self, tenant_id: str, output_path: str | Path) -> Path:
        """Export a tenant summary to a JSON file.

        Args:
            tenant_id: Tenant UUID string.
            output_path: Path to write the summary.

        Returns:
            Path to the written file.
        """
        summary = self.get_tenant_summary(tenant_id)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(summary.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        return path


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_orchestrator(
    backup_root: str = "dcc_backups",
    policy_root: str = "dcc_policies",
    procedure_root: str = "dcc_procedures",
    tracker_root: str = "dcc_rto_tracking",
    test_root: str = "dcc_dr_tests",
) -> DROrchestrator:
    """Convenience function: create a DR orchestrator with default paths."""
    config = DROrchestratorConfig(
        backup_root=backup_root,
        policy_root=policy_root,
        procedure_root=procedure_root,
        tracker_root=tracker_root,
        test_root=test_root,
    )
    return DROrchestrator(config)


def setup_tenant(
    backup_root: str,
    policy_root: str,
    procedure_root: str,
    tracker_root: str,
    test_root: str,
    tenant_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience function: set up DR for a tenant."""
    orchestrator = create_orchestrator(
        backup_root, policy_root, procedure_root, tracker_root, test_root
    )
    return orchestrator.setup_tenant(tenant_id, **kwargs)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "DROrchestratorStatus",
    "DROrchestratorConfig",
    "DRSummary",
    "DROrchestrator",
    "create_orchestrator",
    "setup_tenant",
]
