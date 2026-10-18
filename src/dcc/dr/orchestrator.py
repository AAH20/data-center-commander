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
from typing import Any
from uuid import uuid4

from .policies import (
    BackupPolicy,
    PolicyEngine,
    PolicySchedule,
    PolicyStatus,
    PolicyType,
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

    Usage::

        orchestrator = DROrchestrator("/path/to/dr/data")
        summary = orchestrator.get_tenant_summary("tenant-uuid")
    """

    def __init__(
        self,
        config: DROrchestratorConfig | None = None,
        *,
        backup_root: str | None = None,
        policy_root: str | None = None,
        procedure_root: str | None = None,
        tracker_root: str | None = None,
        test_root: str | None = None,
    ) -> None:
        """Initialize the DR orchestrator.

        Args:
            config: Configuration object (optional).
            backup_root: Override backup root directory.
            policy_root: Override policy root directory.
            procedure_root: Override procedure root directory.
            tracker_root: Override tracker root directory.
            test_root: Override test root directory.
        """
        self.config = config or DROrchestratorConfig()

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

        self._lock = threading.RLock()

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

    def run_due_policies(self, tenant_id: str) -> list[dict[str, Any]]:
        """Run all due policies for a tenant.

        Returns:
            List of policy run results.
        """
        due = self.get_due_policies(tenant_id)
        results = []
        for policy in due:
            # In production, this would trigger actual backup execution
            self._policy_engine.record_run(tenant_id, policy.policy_id, success=True)
            results.append({
                "policy_id": policy.policy_id,
                "policy_name": policy.name,
                "success": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return results

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
