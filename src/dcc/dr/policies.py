"""Backup policy management for Data Center Commander.

Provides declarative backup policies that define what to back up, when,
and how long to keep it. Policies are tenant-scoped and produce
structured, auditable results.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PolicyError(Exception):
    """Base exception for policy failures."""

    def __init__(self, message: str, code: str = "policy_error") -> None:
        self.code = code
        super().__init__(message)


class PolicyNotFoundError(PolicyError):
    """Raised when a policy cannot be found."""

    def __init__(self, policy_id: str) -> None:
        super().__init__(f"policy {policy_id!r} not found", "policy_not_found")


class PolicyValidationError(PolicyError):
    """Raised when a policy definition is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "policy_validation_error")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyType(str, Enum):
    """Type of backup policy."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    CONTINUOUS = "continuous"
    SNAPSHOT = "snapshot"


class PolicySchedule(str, Enum):
    """Schedule frequency for a policy."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class PolicyStatus(str, Enum):
    """Lifecycle status of a policy."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupPolicy:
    """Declarative backup policy.

    Attributes:
        policy_id: Unique identifier.
        tenant_id: Tenant this policy belongs to.
        name: Human-readable name.
        policy_type: Type of backup.
        schedule: How often to run.
        retention_days: How long to keep backups.
        tables: Tables to include (empty = all).
        compression: Whether to compress.
        verify_after: Whether to verify after backup.
        enabled: Whether the policy is active.
        tags: Arbitrary metadata.
        created_at: When the policy was created.
        updated_at: When the policy was last updated.
        last_run_at: When the policy last ran.
        next_run_at: When the policy is next scheduled.
    """

    policy_id: str
    tenant_id: str
    name: str
    policy_type: PolicyType = PolicyType.FULL
    schedule: PolicySchedule = PolicySchedule.DAILY
    retention_days: int = 30
    tables: list[str] = field(default_factory=list)
    compression: bool = True
    verify_after: bool = True
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    status: PolicyStatus = PolicyStatus.ACTIVE
    custom_cron: str | None = None

    def __post_init__(self) -> None:
        if self.retention_days < 1:
            raise PolicyValidationError("retention_days must be >= 1")
        if self.schedule == PolicySchedule.CUSTOM and not self.custom_cron:
            raise PolicyValidationError("custom schedule requires custom_cron")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "policy_type": self.policy_type.value,
            "schedule": self.schedule.value,
            "retention_days": self.retention_days,
            "tables": list(self.tables),
            "compression": self.compression,
            "verify_after": self.verify_after,
            "enabled": self.enabled,
            "tags": dict(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "status": self.status.value,
            "custom_cron": self.custom_cron,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupPolicy:
        return cls(
            policy_id=data["policy_id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            policy_type=PolicyType(data.get("policy_type", "full")),
            schedule=PolicySchedule(data.get("schedule", "daily")),
            retention_days=int(data.get("retention_days", 30)),
            tables=list(data.get("tables", [])),
            compression=bool(data.get("compression", True)),
            verify_after=bool(data.get("verify_after", True)),
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
            status=PolicyStatus(data.get("status", "active")),
            custom_cron=data.get("custom_cron"),
        )


@dataclass
class PolicyRunResult:
    """Result of executing a policy."""

    success: bool
    policy_id: str
    backup_id: str | None = None
    message: str = ""
    duration_seconds: float = 0.0
    error: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "policy_id": self.policy_id,
            "backup_id": self.backup_id,
            "message": self.message,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------


class PolicyEngine:
    """Manages backup policies for tenants.

    Stores policies on the filesystem with a structured layout::

        <policy_root>/
        ├── <tenant_id>/
        │   ├── <policy_id>.json
        │   └── ...
        └── _defaults.json

    All operations are synchronous and thread-safe at the filesystem level
    via atomic writes.
    """

    def __init__(self, policy_root: str | Path) -> None:
        self.policy_root = Path(policy_root).resolve()
        self._ensure_root()

    def _ensure_root(self) -> None:
        self.policy_root.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: str) -> Path:
        return self.policy_root / tenant_id

    def _policy_path(self, tenant_id: str, policy_id: str) -> Path:
        return self._tenant_dir(tenant_id) / f"{policy_id}.json"

    def _write_policy(self, policy: BackupPolicy) -> None:
        path = self._policy_path(policy.tenant_id, policy.policy_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(policy.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_policy(self, tenant_id: str, policy_id: str) -> BackupPolicy:
        path = self._policy_path(tenant_id, policy_id)
        if not path.exists():
            raise PolicyNotFoundError(policy_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return BackupPolicy.from_dict(data)

    def create_policy(
        self,
        tenant_id: str,
        name: str,
        *,
        policy_type: PolicyType = PolicyType.FULL,
        schedule: PolicySchedule = PolicySchedule.DAILY,
        retention_days: int = 30,
        tables: list[str] | None = None,
        compression: bool = True,
        verify_after: bool = True,
        tags: dict[str, str] | None = None,
        custom_cron: str | None = None,
    ) -> BackupPolicy:
        """Create a new backup policy.

        Args:
            tenant_id: Tenant UUID string.
            name: Human-readable policy name.
            policy_type: Type of backup.
            schedule: How often to run.
            retention_days: How long to keep backups.
            tables: Tables to include (None = all).
            compression: Whether to compress.
            verify_after: Whether to verify after backup.
            tags: Arbitrary metadata.
            custom_cron: Cron expression for custom schedules.

        Returns:
            The created BackupPolicy.
        """
        policy_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Calculate next run time
        next_run = self._calculate_next_run(schedule, now)

        policy = BackupPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            name=name,
            policy_type=policy_type,
            schedule=schedule,
            retention_days=retention_days,
            tables=tables or [],
            compression=compression,
            verify_after=verify_after,
            tags=tags or {},
            created_at=now,
            updated_at=now,
            next_run_at=next_run,
            custom_cron=custom_cron,
        )
        self._write_policy(policy)
        return policy

    def _calculate_next_run(
        self, schedule: PolicySchedule, now: datetime
    ) -> datetime | None:
        """Calculate the next run time for a schedule."""
        if schedule == PolicySchedule.HOURLY:
            return now + timedelta(hours=1)
        if schedule == PolicySchedule.DAILY:
            return now + timedelta(days=1)
        if schedule == PolicySchedule.WEEKLY:
            return now + timedelta(weeks=1)
        if schedule == PolicySchedule.MONTHLY:
            # Approximate: add 30 days
            return now + timedelta(days=30)
        return None  # CUSTOM

    def get_policy(self, tenant_id: str, policy_id: str) -> BackupPolicy:
        """Get a policy by ID."""
        return self._read_policy(tenant_id, policy_id)

    def list_policies(
        self,
        tenant_id: str,
        *,
        status: PolicyStatus | None = None,
        enabled_only: bool = False,
    ) -> list[BackupPolicy]:
        """List policies for a tenant.

        Args:
            tenant_id: Tenant UUID string.
            status: Filter by status.
            enabled_only: Only return enabled policies.

        Returns:
            List of BackupPolicy, sorted by created_at descending.
        """
        tenant_dir = self._tenant_dir(tenant_id)
        if not tenant_dir.exists():
            return []

        results: list[BackupPolicy] = []
        for entry in tenant_dir.iterdir():
            if not entry.is_file() or not entry.name.endswith(".json"):
                continue
            if entry.name.startswith("_"):
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
                policy = BackupPolicy.from_dict(data)
            except Exception:
                continue
            if status and policy.status != status:
                continue
            if enabled_only and not policy.enabled:
                continue
            results.append(policy)

        results.sort(key=lambda p: p.created_at, reverse=True)
        return results

    def update_policy(
        self,
        tenant_id: str,
        policy_id: str,
        **updates: Any,
    ) -> BackupPolicy:
        """Update a policy.

        Args:
            tenant_id: Tenant UUID string.
            policy_id: Policy UUID string.
            **updates: Fields to update.

        Returns:
            The updated BackupPolicy.
        """
        policy = self._read_policy(tenant_id, policy_id)
        data = policy.to_dict()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        for key, value in updates.items():
            if key in data and key not in ("policy_id", "tenant_id", "created_at"):
                data[key] = value

        updated = BackupPolicy.from_dict(data)
        self._write_policy(updated)
        return updated

    def delete_policy(self, tenant_id: str, policy_id: str) -> bool:
        """Delete a policy.

        Returns:
            True if deleted, False if not found.
        """
        path = self._policy_path(tenant_id, policy_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def is_due(self, policy: BackupPolicy, now: datetime | None = None) -> bool:
        """Check if a policy is due to run.

        Args:
            policy: The policy to check.
            now: Current time (defaults to now).

        Returns:
            True if the policy should run.
        """
        if not policy.enabled or policy.status != PolicyStatus.ACTIVE:
            return False
        current = now or datetime.now(timezone.utc)
        if policy.next_run_at is None:
            return True
        return current >= policy.next_run_at

    def record_run(
        self,
        tenant_id: str,
        policy_id: str,
        *,
        success: bool,
        backup_id: str | None = None,
    ) -> BackupPolicy:
        """Record that a policy ran.

        Args:
            tenant_id: Tenant UUID string.
            policy_id: Policy UUID string.
            success: Whether the run succeeded.
            backup_id: ID of the backup created.

        Returns:
            The updated BackupPolicy.
        """
        policy = self._read_policy(tenant_id, policy_id)
        now = datetime.now(timezone.utc)
        data = policy.to_dict()
        data["last_run_at"] = now.isoformat()
        data["updated_at"] = now.isoformat()

        # Calculate next run
        next_run = self._calculate_next_run(policy.schedule, now)
        data["next_run_at"] = next_run.isoformat() if next_run else None

        updated = BackupPolicy.from_dict(data)
        self._write_policy(updated)
        return updated

    def get_due_policies(
        self,
        tenant_id: str,
        now: datetime | None = None,
    ) -> list[BackupPolicy]:
        """Get all policies that are due to run for a tenant."""
        policies = self.list_policies(tenant_id, enabled_only=True)
        return [p for p in policies if self.is_due(p, now)]

    def get_policy_stats(self, tenant_id: str) -> dict[str, Any]:
        """Get policy statistics for a tenant."""
        policies = self.list_policies(tenant_id)
        active = [p for p in policies if p.status == PolicyStatus.ACTIVE]
        enabled = [p for p in policies if p.enabled]
        due = [p for p in enabled if self.is_due(p)]

        return {
            "tenant_id": tenant_id,
            "total_policies": len(policies),
            "active_policies": len(active),
            "enabled_policies": len(enabled),
            "due_policies": len(due),
            "policies": [p.to_dict() for p in policies],
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_policy(
    policy_root: str | Path,
    tenant_id: str,
    name: str,
    **kwargs: Any,
) -> BackupPolicy:
    """Convenience function: create a policy with a new engine."""
    engine = PolicyEngine(policy_root)
    return engine.create_policy(tenant_id, name, **kwargs)


def get_policy(
    policy_root: str | Path,
    tenant_id: str,
    policy_id: str,
) -> BackupPolicy:
    """Convenience function: get a policy with a new engine."""
    engine = PolicyEngine(policy_root)
    return engine.get_policy(tenant_id, policy_id)


def list_policies(
    policy_root: str | Path,
    tenant_id: str,
    **kwargs: Any,
) -> list[BackupPolicy]:
    """Convenience function: list policies with a new engine."""
    engine = PolicyEngine(policy_root)
    return engine.list_policies(tenant_id, **kwargs)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "PolicyError",
    "PolicyNotFoundError",
    "PolicyValidationError",
    "PolicyType",
    "PolicySchedule",
    "PolicyStatus",
    "BackupPolicy",
    "PolicyRunResult",
    "PolicyEngine",
    "create_policy",
    "get_policy",
    "list_policies",
]
