"""VPA update policies — manages update modes and rollout strategies.

Provides policy evaluation for VPA update modes (Off, Initial, Auto, Recreate)
and rollout strategies for applying recommendations safely.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .models import (
    ContainerScalingMode,
    RecommendationState,
    ResourcePolicy,
    ScalingDecision,
    UpdateMode,
    VPAObject,
    VPARecommendation,
)


class RolloutStrategy(str, Enum):
    """Strategy for rolling out VPA recommendations."""

    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    IMMEDIATE = "immediate"


class RolloutPhase(str, Enum):
    """Phase of a rollout."""

    PENDING = "pending"
    CANARY = "canary"
    ANALYZING = "analyzing"
    PROMOTING = "promoting"
    COMPLETE = "complete"
    ROLLED_BACK = "rolled_back"


@dataclass
class RolloutConfig:
    """Configuration for a rollout strategy."""

    strategy: RolloutStrategy = RolloutStrategy.ROLLING
    canary_percentage: int = 10
    canary_duration_minutes: int = 30
    analysis_duration_minutes: int = 15
    max_unavailable: int = 1
    max_surge: int = 1
    auto_promote: bool = False
    rollback_on_error: bool = True


@dataclass
class RolloutState:
    """Current state of a rollout."""

    phase: RolloutPhase = RolloutPhase.PENDING
    current_percentage: int = 0
    canary_start_time: Optional[str] = None
    analysis_start_time: Optional[str] = None
    promote_time: Optional[str] = None
    error_message: Optional[str] = None
    replicas_updated: int = 0
    replicas_total: int = 0


@dataclass
class UpdatePolicyConfig:
    """Complete update policy configuration for a VPA."""

    update_mode: UpdateMode = UpdateMode.OFF
    min_replicas: int = 2
    rollout_config: RolloutConfig = field(default_factory=RolloutConfig)
    container_policies: list[ResourcePolicy] = field(default_factory=list)
    respect_min_replicas: bool = True
    scale_down_delay_seconds: int = 300
    scale_up_delay_seconds: int = 60
    max_scale_down_percent: float = 50.0
    max_scale_up_percent: float = 200.0


class UpdatePolicyEngine:
    """Evaluates and manages VPA update policies.

    Determines whether and how VPA recommendations should be applied
    based on the configured update mode and rollout strategy.
    """

    def __init__(self, config: Optional[UpdatePolicyConfig] = None):
        self.config = config or UpdatePolicyConfig()

    def should_apply(
        self,
        decision: ScalingDecision,
        current_replicas: int = 1,
    ) -> bool:
        """Determine if a scaling decision should be applied.

        Args:
            decision: The scaling decision to evaluate
            current_replicas: Current number of replicas

        Returns:
            True if the decision should be applied
        """
        mode = self.config.update_mode

        if mode == UpdateMode.OFF:
            return False

        if mode == UpdateMode.INITIAL:
            return decision.action == "scale_up"

        if mode == UpdateMode.AUTO:
            return self._should_auto_apply(decision, current_replicas)

        if mode == UpdateMode.RECREATE:
            return self._should_recreate_apply(decision, current_replicas)

        return False

    def _should_auto_apply(
        self, decision: ScalingDecision, current_replicas: int
    ) -> bool:
        """Evaluate Auto mode application."""
        if decision.confidence < 0.5:
            return False

        if self.config.respect_min_replicas and current_replicas < self.config.min_replicas:
            return False

        # Check scale limits
        if decision.action == "scale_down":
            if abs(decision.cpu_change_percent) > self.config.max_scale_down_percent:
                return False
            if abs(decision.memory_change_percent) > self.config.max_scale_down_percent:
                return False

        if decision.action == "scale_up":
            if decision.cpu_change_percent > self.config.max_scale_up_percent:
                return False
            if decision.memory_change_percent > self.config.max_scale_up_percent:
                return False

        return True

    def _should_recreate_apply(
        self, decision: ScalingDecision, current_replicas: int
    ) -> bool:
        """Evaluate Recreate mode application."""
        if decision.confidence < 0.7:
            return False

        if self.config.respect_min_replicas and current_replicas < self.config.min_replicas:
            return False

        return True

    def get_rollout_strategy(self) -> RolloutStrategy:
        """Get the appropriate rollout strategy for the current mode."""
        mode = self.config.update_mode

        if mode == UpdateMode.OFF:
            return RolloutStrategy.IMMEDIATE
        if mode == UpdateMode.INITIAL:
            return RolloutStrategy.IMMEDIATE
        if mode == UpdateMode.AUTO:
            return self.config.rollout_config.strategy
        if mode == UpdateMode.RECREATE:
            return RolloutStrategy.ROLLING

        return RolloutStrategy.ROLLING

    def create_rollout_state(
        self, total_replicas: int
    ) -> RolloutState:
        """Create a new rollout state for a scaling operation."""
        return RolloutState(
            phase=RolloutPhase.PENDING,
            current_percentage=0,
            replicas_total=total_replicas,
        )

    def advance_rollout(
        self, state: RolloutState
    ) -> RolloutState:
        """Advance the rollout to the next phase.

        Args:
            state: Current rollout state

        Returns:
            Updated rollout state
        """
        if state.phase == RolloutPhase.PENDING:
            state.phase = RolloutPhase.CANARY
            state.current_percentage = self.config.rollout_config.canary_percentage
            state.replicas_updated = max(
                1, int(state.replicas_total * state.current_percentage / 100)
            )

        elif state.phase == RolloutPhase.CANARY:
            state.phase = RolloutPhase.ANALYZING

        elif state.phase == RolloutPhase.ANALYZING:
            if self.config.rollout_config.auto_promote:
                state.phase = RolloutPhase.PROMOTING
                state.current_percentage = 100
                state.replicas_updated = state.replicas_total

        elif state.phase == RolloutPhase.PROMOTING:
            state.phase = RolloutPhase.COMPLETE
            state.current_percentage = 100
            state.replicas_updated = state.replicas_total

        return state

    def rollback(self, state: RolloutState) -> RolloutState:
        """Rollback a rollout.

        Args:
            state: Current rollout state

        Returns:
            Updated rollout state
        """
        state.phase = RolloutPhase.ROLLED_BACK
        state.current_percentage = 0
        state.replicas_updated = 0
        return state

    def validate_policy(self, vpa_object: VPAObject) -> list[str]:
        """Validate a VPA object's policy configuration.

        Args:
            vpa_object: The VPA object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        if vpa_object.update_policy.min_replicas < 0:
            errors.append("min_replicas must be non-negative")

        if vpa_object.update_policy.update_mode == UpdateMode.AUTO:
            if vpa_object.update_policy.min_replicas < 1:
                errors.append("Auto mode requires min_replicas >= 1")

        if vpa_object.resource_policy:
            for policy in vpa_object.resource_policy.container_policies:
                if policy.min_allowed_cpu_millicores is not None:
                    if policy.min_allowed_cpu_millicores < 0:
                        errors.append(
                            f"Container '{policy.container_name}': min_allowed_cpu_millicores must be non-negative"
                        )
                if policy.max_allowed_cpu_millicores is not None:
                    if policy.max_allowed_cpu_millicores < 0:
                        errors.append(
                            f"Container '{policy.container_name}': max_allowed_cpu_millicores must be non-negative"
                        )
                if (
                    policy.min_allowed_cpu_millicores is not None
                    and policy.max_allowed_cpu_millicores is not None
                ):
                    if policy.min_allowed_cpu_millicores > policy.max_allowed_cpu_millicores:
                        errors.append(
                            f"Container '{policy.container_name}': min_allowed_cpu_millicores exceeds max_allowed_cpu_millicores"
                        )
                if policy.min_allowed_memory_mb is not None:
                    if policy.min_allowed_memory_mb < 0:
                        errors.append(
                            f"Container '{policy.container_name}': min_allowed_memory_mb must be non-negative"
                        )
                if policy.max_allowed_memory_mb is not None:
                    if policy.max_allowed_memory_mb < 0:
                        errors.append(
                            f"Container '{policy.container_name}': max_allowed_memory_mb must be non-negative"
                        )
                if (
                    policy.min_allowed_memory_mb is not None
                    and policy.max_allowed_memory_mb is not None
                ):
                    if policy.min_allowed_memory_mb > policy.max_allowed_memory_mb:
                        errors.append(
                            f"Container '{policy.container_name}': min_allowed_memory_mb exceeds max_allowed_memory_mb"
                        )

        return errors

    def compute_effective_policy(
        self, vpa_object: VPAObject
    ) -> UpdatePolicyConfig:
        """Compute the effective update policy for a VPA object.

        Merges the VPA object's policy with the engine's default config.

        Args:
            vpa_object: The VPA object

        Returns:
            Effective update policy configuration
        """
        return UpdatePolicyConfig(
            update_mode=vpa_object.update_policy.update_mode,
            min_replicas=vpa_object.update_policy.min_replicas,
            rollout_config=self.config.rollout_config,
            container_policies=(
                vpa_object.resource_policy.container_policies
                if vpa_object.resource_policy
                else []
            ),
            respect_min_replicas=self.config.respect_min_replicas,
            scale_down_delay_seconds=self.config.scale_down_delay_seconds,
            scale_up_delay_seconds=self.config.scale_up_delay_seconds,
            max_scale_down_percent=self.config.max_scale_down_percent,
            max_scale_up_percent=self.config.max_scale_up_percent,
        )
