"""Remediation tracking and workflow management.

Manages remediation tasks for vulnerabilities and compliance gaps,
tracking status from creation through verification and closure.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4


class RemediationStatus(str, Enum):
    """Status of a remediation task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    CLOSED = "closed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


@dataclass
class RemediationTask:
    """A single remediation task.

    Attributes
    ----------
    id:
        Unique task identifier.
    title:
        Short title of the remediation task.
    description:
        Detailed description of what needs to be remediated.
    status:
        Current status of the task.
    priority:
        Priority level (immediate, high, medium, low, scheduled).
    related_vulnerabilities:
        IDs of related vulnerabilities.
    related_compliance_controls:
        IDs of related compliance controls.
    assignee:
        Who is responsible for remediation.
    created_at:
        ISO timestamp when the task was created.
    due_date:
        ISO date (YYYY-MM-DD) when the task is due.
    completed_at:
        ISO timestamp when the task was completed.
    verification_evidence:
        Evidence that the remediation was verified.
    notes:
        Additional notes.
    tags:
        Arbitrary tags for categorization.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    status: RemediationStatus = RemediationStatus.PENDING
    priority: str = "medium"
    related_vulnerabilities: list[str] = field(default_factory=list)
    related_compliance_controls: list[str] = field(default_factory=list)
    assignee: str = ""
    created_at: str = ""
    due_date: str = ""
    completed_at: str = ""
    verification_evidence: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = dt.datetime.now(dt.timezone.utc).isoformat()

    @property
    def is_complete(self) -> bool:
        """Check if the task is complete."""
        return self.status in (
            RemediationStatus.VERIFIED,
            RemediationStatus.CLOSED,
            RemediationStatus.CANCELLED,
        )

    @property
    def is_active(self) -> bool:
        """Check if the task is still active."""
        return not self.is_complete

    @property
    def is_overdue(self) -> bool:
        """Check if the task is past its due date."""
        if not self.due_date or self.is_complete:
            return False
        try:
            due = dt.date.fromisoformat(self.due_date)
            return dt.date.today() > due
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "related_vulnerabilities": self.related_vulnerabilities,
            "related_compliance_controls": self.related_compliance_controls,
            "assignee": self.assignee,
            "created_at": self.created_at,
            "due_date": self.due_date,
            "completed_at": self.completed_at,
            "verification_evidence": self.verification_evidence,
            "notes": self.notes,
            "tags": self.tags,
            "is_complete": self.is_complete,
            "is_active": self.is_active,
            "is_overdue": self.is_overdue,
        }


@dataclass
class RemediationPlan:
    """A collection of remediation tasks.

    Attributes
    ----------
    name:
        Name of the remediation plan.
    description:
        Description of the plan.
    tasks:
        List of remediation tasks.
    created_at:
        ISO timestamp when the plan was created.
    metadata:
        Arbitrary metadata.
    """

    name: str = ""
    description: str = ""
    tasks: list[RemediationTask] = field(default_factory=list)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = dt.datetime.now(dt.timezone.utc).isoformat()

    @property
    def total_tasks(self) -> int:
        return len(self.tasks)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.is_complete)

    @property
    def active_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.is_active)

    @property
    def overdue_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.is_overdue)

    @property
    def completion_percentage(self) -> float:
        """Return completion percentage (0-100)."""
        if self.total_tasks == 0:
            return 0.0
        return round((self.completed_tasks / self.total_tasks) * 100, 2)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        return self.total_tasks > 0 and self.completed_tasks == self.total_tasks

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "active_tasks": self.active_tasks,
            "overdue_tasks": self.overdue_tasks,
            "completion_percentage": self.completion_percentage,
            "is_complete": self.is_complete,
            "tasks": [t.to_dict() for t in self.tasks],
            "metadata": self.metadata,
        }


class RemediationTracker:
    """Tracks remediation tasks and plans.

    Provides CRUD operations for remediation tasks and produces
    remediation plans.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, RemediationTask] = {}

    def add_task(self, task: RemediationTask) -> RemediationTask:
        """Add a remediation task."""
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> RemediationTask | None:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: str,
        **kwargs: Any,
    ) -> RemediationTask | None:
        """Update a task's attributes."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task. Returns True if removed."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def list_tasks(
        self,
        status: RemediationStatus | None = None,
        assignee: str | None = None,
    ) -> list[RemediationTask]:
        """List tasks, optionally filtered by status and assignee."""
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if assignee is not None:
            tasks = [t for t in tasks if t.assignee == assignee]
        return tasks

    def create_plan(
        self,
        name: str,
        description: str = "",
        tasks: Iterable[RemediationTask] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RemediationPlan:
        """Create a remediation plan from tasks."""
        task_list = list(tasks) if tasks else []
        # Add tasks to tracker
        for task in task_list:
            self.add_task(task)
        return RemediationPlan(
            name=name,
            description=description,
            tasks=task_list,
            metadata=metadata or {},
        )

    def get_plan(self, task_ids: Iterable[str]) -> RemediationPlan:
        """Build a plan from a set of task IDs."""
        tasks = [self._tasks[tid] for tid in task_ids if tid in self._tasks]
        return RemediationPlan(
            name="Ad-hoc Plan",
            tasks=tasks,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def create_remediation_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    related_vulnerabilities: Iterable[str] | None = None,
    related_compliance_controls: Iterable[str] | None = None,
    assignee: str = "",
    due_date: str = "",
    tags: Iterable[str] | None = None,
) -> RemediationTask:
    """Convenience factory for creating a remediation task."""
    return RemediationTask(
        title=title,
        description=description,
        priority=priority,
        related_vulnerabilities=list(related_vulnerabilities) if related_vulnerabilities else [],
        related_compliance_controls=list(related_compliance_controls) if related_compliance_controls else [],
        assignee=assignee,
        due_date=due_date,
        tags=list(tags) if tags else [],
    )
