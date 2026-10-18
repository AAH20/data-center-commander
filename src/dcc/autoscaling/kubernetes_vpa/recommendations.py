"""VPA recommendation engine — parses and evaluates VPA recommendations.

Provides analysis of VPA recommendations, scaling decisions, and
confidence scoring for vertical pod autoscaling operations.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Optional

from .models import (
    ContainerScalingMode,
    ContainerUsageSample,
    PodResourcePolicy,
    PodUsageRecord,
    RecommendedContainerResources,
    RecommendationState,
    ResourceName,
    ResourcePolicy,
    ScalingDecision,
    VPAObject,
    VPARecommendation,
    VPAMetricsSummary,
)


class VPARecommendationEngine:
    """Analyzes VPA recommendations and produces scaling decisions."""

    # Thresholds for scaling decisions
    SCALE_UP_THRESHOLD_PERCENT = 15.0
    SCALE_DOWN_THRESHOLD_PERCENT = 15.0
    MIN_CONFIDENCE = 0.3
    HIGH_CONFIDENCE = 0.8

    # Resource-specific thresholds
    CPU_SCALE_UP_THRESHOLD = 20.0
    CPU_SCALE_DOWN_THRESHOLD = 20.0
    MEMORY_SCALE_UP_THRESHOLD = 25.0
    MEMORY_SCALE_DOWN_THRESHOLD = 25.0

    def __init__(self, min_confidence: float = MIN_CONFIDENCE):
        self.min_confidence = min_confidence

    def analyze_recommendation(
        self,
        vpa_object: VPAObject,
        current_cpu_millicores: int,
        current_memory_mb: int,
    ) -> list[ScalingDecision]:
        """Analyze a VPA recommendation and produce scaling decisions.

        Args:
            vpa_object: The VPA object with its recommendation
            current_cpu_millicores: Current CPU request in millicores
            current_memory_mb: Current memory request in MB

        Returns:
            List of scaling decisions per container
        """
        decisions: list[ScalingDecision] = []

        if not vpa_object.recommendation:
            return decisions

        rec = vpa_object.recommendation
        if rec.state == RecommendationState.REJECTED:
            return decisions

        for container_rec in rec.container_recommendations:
            decision = self._evaluate_container(
                vpa_object,
                container_rec,
                current_cpu_millicores,
                current_memory_mb,
            )
            if decision:
                decisions.append(decision)

        return decisions

    def _evaluate_container(
        self,
        vpa_object: VPAObject,
        container_rec: RecommendedContainerResources,
        current_cpu_millicores: int,
        current_memory_mb: int,
    ) -> Optional[ScalingDecision]:
        """Evaluate a single container recommendation."""
        container_name = container_rec.container_name

        # Extract recommended values
        rec_cpu = self._extract_millicores(container_rec.target, ResourceName.CPU)
        rec_memory = self._extract_megabytes(container_rec.target, ResourceName.MEMORY)

        if rec_cpu is None and rec_memory is None:
            return None

        # Use current values as fallback
        rec_cpu = rec_cpu or current_cpu_millicores
        rec_memory = rec_memory or current_memory_mb

        # Calculate changes
        cpu_change_pct = self._percent_change(current_cpu_millicores, rec_cpu)
        memory_change_pct = self._percent_change(current_memory_mb, rec_memory)

        # Determine action
        action = self._determine_action(cpu_change_pct, memory_change_pct)

        # Calculate confidence
        confidence = self._compute_confidence(
            container_rec, cpu_change_pct, memory_change_pct
        )

        if confidence < self.min_confidence:
            return None

        # Build reason
        reason = self._build_reason(
            action, cpu_change_pct, memory_change_pct, container_name
        )

        return ScalingDecision(
            workload_name=vpa_object.target_ref.name,
            namespace=vpa_object.namespace,
            container_name=container_name,
            current_cpu_millicores=current_cpu_millicores,
            current_memory_mb=current_memory_mb,
            recommended_cpu_millicores=rec_cpu,
            recommended_memory_mb=rec_memory,
            cpu_change_percent=cpu_change_pct,
            memory_change_percent=memory_change_pct,
            action=action,
            reason=reason,
            confidence=confidence,
        )

    def _extract_millicores(
        self, resources: dict, resource_name: ResourceName
    ) -> Optional[int]:
        """Extract CPU value in millicores from resource dict."""
        qty = resources.get(resource_name.value)
        if qty is None:
            return None
        return qty.millicores

    def _extract_megabytes(
        self, resources: dict, resource_name: ResourceName
    ) -> Optional[int]:
        """Extract memory value in MB from resource dict."""
        qty = resources.get(resource_name.value)
        if qty is None:
            return None
        return qty.megabytes

    def _percent_change(self, current: int, recommended: int) -> float:
        """Calculate percentage change between current and recommended."""
        if current == 0:
            return 0.0
        return ((recommended - current) / current) * 100.0

    def _determine_action(
        self, cpu_change_pct: float, memory_change_pct: float
    ) -> str:
        """Determine scaling action based on change percentages."""
        max_change = max(abs(cpu_change_pct), abs(memory_change_pct))

        if max_change < self.SCALE_UP_THRESHOLD_PERCENT:
            return "no_change"

        if cpu_change_pct > self.CPU_SCALE_UP_THRESHOLD:
            return "scale_up"
        if memory_change_pct > self.MEMORY_SCALE_UP_THRESHOLD:
            return "scale_up"
        if cpu_change_pct < -self.CPU_SCALE_DOWN_THRESHOLD:
            return "scale_down"
        if memory_change_pct < -self.MEMORY_SCALE_DOWN_THRESHOLD:
            return "scale_down"

        return "no_change"

    def _compute_confidence(
        self,
        container_rec: RecommendedContainerResources,
        cpu_change_pct: float,
        memory_change_pct: float,
    ) -> float:
        """Compute confidence score for a recommendation.

        Confidence is based on:
        - Presence of bounds (lower/upper)
        - Magnitude of change
        - Consistency between CPU and memory signals
        """
        confidence = 0.5  # Base confidence

        # Having bounds increases confidence
        has_lower = bool(container_rec.lower_bound)
        has_upper = bool(container_rec.upper_bound)
        if has_lower and has_upper:
            confidence += 0.2
        elif has_lower or has_upper:
            confidence += 0.1

        # Larger changes are more confident (clear signal)
        max_change = max(abs(cpu_change_pct), abs(memory_change_pct))
        if max_change > 50:
            confidence += 0.2
        elif max_change > 30:
            confidence += 0.1

        # Consistency between CPU and memory
        if (cpu_change_pct > 0 and memory_change_pct > 0) or (
            cpu_change_pct < 0 and memory_change_pct < 0
        ):
            confidence += 0.1

        return min(confidence, 1.0)

    def _build_reason(
        self,
        action: str,
        cpu_change_pct: float,
        memory_change_pct: float,
        container_name: str,
    ) -> str:
        """Build a human-readable reason for the scaling decision."""
        if action == "no_change":
            return (
                f"Container '{container_name}' resource usage is stable "
                f"(CPU: {cpu_change_pct:+.1f}%, Memory: {memory_change_pct:+.1f}%)"
            )

        parts = []
        if abs(cpu_change_pct) > self.SCALE_UP_THRESHOLD_PERCENT:
            direction = "increase" if cpu_change_pct > 0 else "decrease"
            parts.append(f"CPU {direction} of {abs(cpu_change_pct):.1f}%")
        if abs(memory_change_pct) > self.SCALE_UP_THRESHOLD_PERCENT:
            direction = "increase" if memory_change_pct > 0 else "decrease"
            parts.append(f"Memory {direction} of {abs(memory_change_pct):.1f}%")

        return f"Container '{container_name}' recommends {' and '.join(parts)}"

    def compute_metrics_summary(
        self,
        pod_records: list[PodUsageRecord],
        workload_name: str,
        namespace: str,
        time_window_hours: float = 24.0,
    ) -> VPAMetricsSummary:
        """Compute metrics summary from pod usage records.

        Args:
            pod_records: List of pod usage records
            workload_name: Name of the workload
            namespace: Namespace of the workload
            time_window_hours: Time window for the summary

        Returns:
            Metrics summary with averages and percentiles
        """
        all_cpu: list[float] = []
        all_memory: list[float] = []
        container_names: set[str] = set()

        for record in pod_records:
            for sample in record.samples:
                all_cpu.append(sample.cpu_usage_millicores)
                all_memory.append(sample.memory_usage_mb)
                container_names.add(sample.container_name)

        if not all_cpu:
            return VPAMetricsSummary(
                workload_name=workload_name,
                namespace=namespace,
                container_count=0,
                avg_cpu_millicores=0.0,
                avg_memory_mb=0.0,
                p95_cpu_millicores=0.0,
                p95_memory_mb=0.0,
                p99_cpu_millicores=0.0,
                p99_memory_mb=0.0,
                sample_count=0,
                time_window_hours=time_window_hours,
            )

        return VPAMetricsSummary(
            workload_name=workload_name,
            namespace=namespace,
            container_count=len(container_names),
            avg_cpu_millicores=statistics.mean(all_cpu),
            avg_memory_mb=statistics.mean(all_memory),
            p95_cpu_millicores=self._percentile(all_cpu, 95),
            p95_memory_mb=self._percentile(all_memory, 95),
            p99_cpu_millicores=self._percentile(all_cpu, 99),
            p99_memory_mb=self._percentile(all_memory, 99),
            sample_count=len(all_cpu),
            time_window_hours=time_window_hours,
        )

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Compute the given percentile of a dataset."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100.0)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def should_apply_recommendation(
        self,
        decision: ScalingDecision,
        update_mode: str,
        min_replicas: int = 2,
    ) -> bool:
        """Determine if a recommendation should be applied.

        Args:
            decision: The scaling decision
            update_mode: VPA update mode (Off, Initial, Auto, Recreate)
            min_replicas: Minimum replicas for Auto mode

        Returns:
            True if the recommendation should be applied
        """
        if update_mode == "Off":
            return False
        if update_mode == "Initial":
            return decision.action == "scale_up"
        if update_mode in ("Auto", "Recreate"):
            return decision.confidence >= self.min_confidence
        return False

    def filter_by_policy(
        self,
        decisions: list[ScalingDecision],
        resource_policy: Optional[PodResourcePolicy],
    ) -> list[ScalingDecision]:
        """Filter decisions based on resource policy constraints.

        Args:
            decisions: List of scaling decisions
            resource_policy: Resource policy with min/max constraints

        Returns:
            Filtered list of decisions that comply with policy
        """
        if not resource_policy or not resource_policy.container_policies:
            return decisions

        filtered = []
        for decision in decisions:
            policy = self._find_container_policy(
                resource_policy, decision.container_name
            )
            if policy and self._complies_with_policy(decision, policy):
                filtered.append(decision)

        return filtered

    def _find_container_policy(
        self, pod_policy: PodResourcePolicy, container_name: str
    ) -> Optional[ResourcePolicy]:
        """Find the resource policy for a specific container."""
        for policy in pod_policy.container_policies:
            if policy.container_name == container_name:
                return policy
        return None

    def _complies_with_policy(
        self, decision: ScalingDecision, policy: ResourcePolicy
    ) -> bool:
        """Check if a decision complies with a resource policy."""
        if policy.mode == ContainerScalingMode.OFF:
            return False

        if policy.min_allowed_cpu_millicores is not None:
            if decision.recommended_cpu_millicores < policy.min_allowed_cpu_millicores:
                return False
        if policy.max_allowed_cpu_millicores is not None:
            if decision.recommended_cpu_millicores > policy.max_allowed_cpu_millicores:
                return False
        if policy.min_allowed_memory_mb is not None:
            if decision.recommended_memory_mb < policy.min_allowed_memory_mb:
                return False
        if policy.max_allowed_memory_mb is not None:
            if decision.recommended_memory_mb > policy.max_allowed_memory_mb:
                return False

        return True
