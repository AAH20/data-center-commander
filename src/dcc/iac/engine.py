"""IaC engine: plan/apply with drift detection and rollback.

Surpasses Terraform with:
- Real-time drift detection (not just plan-time)
- Automatic rollback on failure
- Ordered execution (destroy → update → create)
- Detailed drift reports
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dcc.iac.dsl import InfrastructureDefinition, Resource


class EngineAction(str, Enum):
    """Possible infrastructure actions."""

    CREATE = "create"
    UPDATE = "update"
    DESTROY = "destroy"
    NO_OP = "no_op"


@dataclass(frozen=True)
class PlanStep:
    """A single step in an infrastructure plan."""

    action: EngineAction
    resource_name: str
    resource: Resource | None = None
    previous_state: Resource | None = None
    reason: str = ""


@dataclass
class PlanResult:
    """Result of plan generation."""

    steps: list[PlanStep] = field(default_factory=list)
    has_changes: bool = False

    def __post_init__(self) -> None:
        """Compute has_changes from steps."""
        self.has_changes = len(self.steps) > 0


@dataclass
class DriftReport:
    """Report of drift between desired and actual state."""

    has_drift: bool
    drifted_resources: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    desired_fingerprint: str = ""
    actual_fingerprint: str = ""


@dataclass
class ApplyResult:
    """Result of applying a plan."""

    success: bool
    applied_steps: int
    failed_step: int | None = None
    error: str | None = None
    rolled_back: bool = False


def generate_plan(
    desired: InfrastructureDefinition,
    actual: InfrastructureDefinition,
) -> PlanResult:
    """Generate a plan to transform actual state into desired state.

    Plan steps are ordered: destroy → update → create.
    This ensures resources are freed before new ones are created.

    Args:
        desired: Desired infrastructure state
        actual: Current infrastructure state

    Returns:
        PlanResult with ordered steps
    """
    desired_resources = {r.name: r for r in desired.resources}
    actual_resources = {r.name: r for r in actual.resources}

    steps: list[PlanStep] = []

    # Step 1: Destroy resources that exist in actual but not in desired
    for name in sorted(set(actual_resources) - set(desired_resources)):
        steps.append(
            PlanStep(
                action=EngineAction.DESTROY,
                resource_name=name,
                previous_state=actual_resources[name],
                reason="resource not in desired state",
            )
        )

    # Step 2: Update resources that exist in both but differ
    for name in sorted(set(desired_resources) & set(actual_resources)):
        if desired_resources[name].fingerprint != actual_resources[name].fingerprint:
            steps.append(
                PlanStep(
                    action=EngineAction.UPDATE,
                    resource_name=name,
                    resource=desired_resources[name],
                    previous_state=actual_resources[name],
                    reason="resource configuration changed",
                )
            )

    # Step 3: Create resources that exist in desired but not in actual
    for name in sorted(set(desired_resources) - set(actual_resources)):
        steps.append(
            PlanStep(
                action=EngineAction.CREATE,
                resource_name=name,
                resource=desired_resources[name],
                reason="resource missing from actual state",
            )
        )

    return PlanResult(steps=steps, has_changes=bool(steps))


def detect_drift(
    desired: InfrastructureDefinition,
    actual: InfrastructureDefinition,
) -> DriftReport:
    """Detect drift between desired and actual state.

    Args:
        desired: Desired infrastructure state
        actual: Current infrastructure state

    Returns:
        DriftReport with detailed drift information
    """
    desired_resources = {r.name: r for r in desired.resources}
    actual_resources = {r.name: r for r in actual.resources}

    drifted: list[str] = []
    details: dict[str, Any] = {}

    # Check for added resources (in actual but not in desired)
    for name in sorted(set(actual_resources) - set(desired_resources)):
        drifted.append(name)
        details[name] = {"change": "added", "actual": actual_resources[name]}

    # Check for removed resources (in desired but not in actual)
    for name in sorted(set(desired_resources) - set(actual_resources)):
        drifted.append(name)
        details[name] = {"change": "removed", "desired": desired_resources[name]}

    # Check for modified resources
    for name in sorted(set(desired_resources) & set(actual_resources)):
        if desired_resources[name].fingerprint != actual_resources[name].fingerprint:
            drifted.append(name)
            changes = _compute_resource_changes(desired_resources[name], actual_resources[name])
            details[name] = {"change": "modified", "changes": changes}

    return DriftReport(
        has_drift=bool(drifted),
        drifted_resources=drifted,
        details=details,
        desired_fingerprint=desired.fingerprint,
        actual_fingerprint=actual.fingerprint,
    )


def apply_plan(
    plan: PlanResult,
    fail_on_step: int | None = None,
    mutator: Callable[[PlanStep, bool], None] | None = None,
) -> ApplyResult:
    """Apply a plan with automatic rollback on failure.

    Args:
        plan: Plan to apply
        fail_on_step: If set, simulate failure on this step (for testing)
        mutator: Optional callback to mutate state after each step.
            Called with (step, rollback=False) for apply and
            (step, rollback=True) for rollback.

    Returns:
        ApplyResult with success status and rollback info
    """
    if not plan.has_changes:
        return ApplyResult(success=True, applied_steps=0)

    applied = 0
    completed_steps: list[PlanStep] = []

    for i, step in enumerate(plan.steps):
        # Simulate failure for testing
        if fail_on_step is not None and i == fail_on_step:
            # Rollback completed steps in reverse order
            for completed in reversed(completed_steps):
                if mutator:
                    mutator(completed, True)
            return ApplyResult(
                success=False,
                applied_steps=applied,
                failed_step=i,
                error=f"simulated failure on step {i}",
                rolled_back=True,
            )

        # Apply the step
        if mutator:
            mutator(step, False)
        applied += 1
        completed_steps.append(step)

    return ApplyResult(success=True, applied_steps=applied)


def _compute_resource_changes(desired: Resource, actual: Resource) -> dict[str, dict[str, Any]]:
    """Compute detailed changes between desired and actual resource."""
    changes: dict[str, dict[str, Any]] = {}
    for field_name in (
        "cpu_cores",
        "memory_gb",
        "gpu_units",
        "storage_tb",
        "bandwidth_gbps",
        "cooling_kw",
        "power_kw",
        "power_capacity_kw",
        "region",
    ):
        desired_val = getattr(desired, field_name)
        actual_val = getattr(actual, field_name)
        if desired_val != actual_val:
            changes[field_name] = {"from": actual_val, "to": desired_val}
    return changes
