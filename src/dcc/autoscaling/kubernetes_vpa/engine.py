"""Main VPA engine — orchestrates VPA analysis and scaling decisions.

Provides the primary entry point for Kubernetes VPA integration,
combining recommendations, update policies, and metrics analysis.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .models import (
    PodUsageRecord,
    ScalingDecision,
    UpdateMode,
    VPAObject,
    VPAReport,
    VPAMetricsSummary,
)
from .recommendations import VPARecommendationEngine
from .update_policies import RolloutState, UpdatePolicyConfig, UpdatePolicyEngine


class VPAEngine:
    """Main entry point for Kubernetes VPA integration.

    Orchestrates VPA recommendation analysis, update policy evaluation,
    and scaling decision generation.
    """

    def __init__(
        self,
        update_policy_config: Optional[UpdatePolicyConfig] = None,
        min_confidence: float = 0.3,
    ):
        self.recommendation_engine = VPARecommendationEngine(
            min_confidence=min_confidence
        )
        self.update_policy_engine = UpdatePolicyEngine(update_policy_config)

    def analyze_workload(
        self,
        vpa_object: VPAObject,
        current_cpu_millicores: int,
        current_memory_mb: int,
        current_replicas: int = 1,
    ) -> list[ScalingDecision]:
        """Analyze a single workload and produce scaling decisions.

        Args:
            vpa_object: The VPA object with its recommendation
            current_cpu_millicores: Current CPU request in millicores
            current_memory_mb: Current memory request in MB
            current_replicas: Current number of replicas

        Returns:
            List of scaling decisions
        """
        # Get recommendations
        decisions = self.recommendation_engine.analyze_recommendation(
            vpa_object, current_cpu_millicores, current_memory_mb
        )

        # Filter by resource policy
        if vpa_object.resource_policy:
            decisions = self.recommendation_engine.filter_by_policy(
                decisions, vpa_object.resource_policy
            )

        # Filter by update policy
        effective_config = self.update_policy_engine.compute_effective_policy(vpa_object)
        filtered = []
        for decision in decisions:
            if self.update_policy_engine.should_apply(decision, current_replicas):
                filtered.append(decision)

        return filtered

    def analyze_all(
        self,
        vpa_objects: list[VPAObject],
        current_resources: dict[str, tuple[int, int]],
        current_replicas: Optional[dict[str, int]] = None,
    ) -> VPAReport:
        """Analyze all workloads and produce a comprehensive VPA report.

        Args:
            vpa_objects: List of VPA objects to analyze
            current_resources: Dict mapping workload name to (cpu_millicores, memory_mb)
            current_replicas: Optional dict mapping workload name to replica count

        Returns:
            Comprehensive VPA report
        """
        all_decisions: list[ScalingDecision] = []
        errors: list[str] = []
        current_replicas = current_replicas or {}

        for vpa_obj in vpa_objects:
            workload_name = vpa_obj.target_ref.name
            resources = current_resources.get(workload_name)
            if not resources:
                errors.append(
                    f"No current resources found for workload '{workload_name}'"
                )
                continue

            cpu, memory = resources
            replicas = current_replicas.get(workload_name, 1)

            try:
                decisions = self.analyze_workload(vpa_obj, cpu, memory, replicas)
                all_decisions.extend(decisions)
            except Exception as exc:
                errors.append(
                    f"Error analyzing workload '{workload_name}': {type(exc).__name__}: {exc}"
                )

        # Count by action
        scale_up = sum(1 for d in all_decisions if d.action == "scale_up")
        scale_down = sum(1 for d in all_decisions if d.action == "scale_down")
        no_change = sum(1 for d in all_decisions if d.action == "no_change")

        return VPAReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_workloads=len(vpa_objects),
            total_recommendations=len(all_decisions),
            scale_up_count=scale_up,
            scale_down_count=scale_down,
            no_change_count=no_change,
            decisions=all_decisions,
            vpa_objects=vpa_objects,
            errors=errors,
        )

    def compute_metrics(
        self,
        pod_records: list[PodUsageRecord],
        workload_name: str,
        namespace: str,
        time_window_hours: float = 24.0,
    ) -> VPAMetricsSummary:
        """Compute metrics summary for a workload.

        Args:
            pod_records: List of pod usage records
            workload_name: Name of the workload
            namespace: Namespace of the workload
            time_window_hours: Time window for the summary

        Returns:
            Metrics summary
        """
        return self.recommendation_engine.compute_metrics_summary(
            pod_records, workload_name, namespace, time_window_hours
        )

    def create_rollout(
        self, total_replicas: int
    ) -> RolloutState:
        """Create a new rollout state for a scaling operation.

        Args:
            total_replicas: Total number of replicas

        Returns:
            New rollout state
        """
        return self.update_policy_engine.create_rollout_state(total_replicas)

    def advance_rollout(self, state: RolloutState) -> RolloutState:
        """Advance a rollout to the next phase.

        Args:
            state: Current rollout state

        Returns:
            Updated rollout state
        """
        return self.update_policy_engine.advance_rollout(state)

    def rollback_rollout(self, state: RolloutState) -> RolloutState:
        """Rollback a rollout.

        Args:
            state: Current rollout state

        Returns:
            Updated rollout state
        """
        return self.update_policy_engine.rollback(state)

    def validate_vpa(self, vpa_object: VPAObject) -> list[str]:
        """Validate a VPA object's configuration.

        Args:
            vpa_object: The VPA object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return self.update_policy_engine.validate_policy(vpa_object)
