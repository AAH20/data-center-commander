"""Rightsizing engine — recommends optimal instance sizes for workloads."""

from __future__ import annotations

from typing import Optional

from .models import (
    InstanceType,
    PricingModel,
    RightsizingRecommendation,
    RiskLevel,
    Workload,
)


class RightsizingEngine:
    """Analyzes workload utilization and recommends rightsizing actions."""

    # Utilization thresholds
    DOWNSIZE_CPU_THRESHOLD = 0.25
    DOWNSIZE_MEMORY_THRESHOLD = 0.30
    UPSIZE_CPU_THRESHOLD = 0.80
    UPSIZE_MEMORY_THRESHOLD = 0.85

    # Safety margins for recommendations
    SAFETY_MARGIN = 0.15  # 15% headroom

    def __init__(self, instance_catalog: Optional[list[InstanceType]] = None):
        self.instance_catalog = instance_catalog or []

    def recommend(
        self, workload: Workload
    ) -> list[RightsizingRecommendation]:
        """Generate rightsizing recommendations for a single workload."""
        recommendations = []

        # Check for downsizing opportunity
        downsize = self._check_downsize(workload)
        if downsize:
            recommendations.append(downsize)

        # Check for upsizing opportunity
        upsize = self._check_upsize(workload)
        if upsize:
            recommendations.append(upsize)

        # Check for family modernization
        family_change = self._check_family_modernization(workload)
        if family_change:
            recommendations.append(family_change)

        return recommendations

    def recommend_all(
        self, workloads: list[Workload]
    ) -> list[RightsizingRecommendation]:
        """Generate rightsizing recommendations for all workloads."""
        all_recs = []
        for wl in workloads:
            recs = self.recommend(wl)
            all_recs.extend(recs)
        return sorted(all_recs, key=lambda r: r.annual_savings, reverse=True)

    def _check_downsize(
        self, workload: Workload
    ) -> Optional[RightsizingRecommendation]:
        """Check if workload can be downsized."""
        if not self.instance_catalog:
            return None

        current = workload.instance_type
        target_vcpus = self._compute_target_vcpus(workload)
        target_memory = self._compute_target_memory(workload)

        # Find a smaller instance that meets requirements
        candidates = [
            it
            for it in self.instance_catalog
            if it.provider == current.provider
            and it.vcpus >= target_vcpus
            and it.memory_gb >= target_memory
            and it.vcpus < current.vcpus
            and it.on_demand_hourly < current.on_demand_hourly
        ]

        if not candidates:
            return None

        # Pick the cheapest candidate
        recommended = min(candidates, key=lambda it: it.on_demand_hourly)

        current_cost = current.on_demand_hourly * workload.uptime_hours_monthly
        recommended_cost = recommended.on_demand_hourly * workload.uptime_hours_monthly
        savings = current_cost - recommended_cost

        if savings <= 0:
            return None

        risk = self._assess_downsize_risk(workload, current, recommended)

        return RightsizingRecommendation(
            workload_id=workload.workload_id,
            workload_name=workload.name,
            current_instance=current,
            recommended_instance=recommended,
            current_monthly_cost=current_cost,
            recommended_monthly_cost=recommended_cost,
            monthly_savings=savings,
            annual_savings=savings * 12,
            savings_percent=(savings / current_cost * 100) if current_cost > 0 else 0,
            reason=(
                f"CPU avg {workload.cpu_utilization_avg:.0%}, "
                f"Memory avg {workload.memory_utilization_avg:.0%} — "
                f"downsize from {current.name} to {recommended.name}"
            ),
            risk_level=risk,
            confidence=self._compute_confidence(workload),
            action="downsize",
            estimated_downtime_minutes=15.0,
        )

    def _check_upsize(
        self, workload: Workload
    ) -> Optional[RightsizingRecommendation]:
        """Check if workload needs to be upsized."""
        if not self.instance_catalog:
            return None

        current = workload.instance_type
        target_vcpus = self._compute_target_vcpus(workload)
        target_memory = self._compute_target_memory(workload)

        # Find a larger instance if current is insufficient
        if (
            current.vcpus >= target_vcpus
            and current.memory_gb >= target_memory
        ):
            return None

        candidates = [
            it
            for it in self.instance_catalog
            if it.provider == current.provider
            and it.vcpus >= target_vcpus
            and it.memory_gb >= target_memory
            and it.vcpus > current.vcpus
        ]

        if not candidates:
            return None

        recommended = min(candidates, key=lambda it: it.on_demand_hourly)

        current_cost = current.on_demand_hourly * workload.uptime_hours_monthly
        recommended_cost = recommended.on_demand_hourly * workload.uptime_hours_monthly
        extra_cost = recommended_cost - current_cost

        return RightsizingRecommendation(
            workload_id=workload.workload_id,
            workload_name=workload.name,
            current_instance=current,
            recommended_instance=recommended,
            current_monthly_cost=current_cost,
            recommended_monthly_cost=recommended_cost,
            monthly_savings=-extra_cost,
            annual_savings=-extra_cost * 12,
            savings_percent=(-extra_cost / current_cost * 100) if current_cost > 0 else 0,
            reason=(
                f"CPU p95 {workload.cpu_utilization_p95:.0%}, "
                f"Memory p95 {workload.memory_utilization_p95:.0%} — "
                f"upsize from {current.name} to {recommended.name}"
            ),
            risk_level=RiskLevel.LOW,
            confidence=self._compute_confidence(workload),
            action="upsizing",
            estimated_downtime_minutes=15.0,
        )

    def _check_family_modernization(
        self, workload: Workload
    ) -> Optional[RightsizingRecommendation]:
        """Check if moving to a newer instance family would save money."""
        if not self.instance_catalog:
            return None

        current = workload.instance_type
        current_family = current.name.split(".")[0]

        # Find newer generation families (heuristic: higher version numbers)
        # e.g., m5 -> m6, m6i, m7i etc.
        newer_families = self._get_newer_families(current_family)

        if not newer_families:
            return None

        target_vcpus = self._compute_target_vcpus(workload)
        target_memory = self._compute_target_memory(workload)

        candidates = [
            it
            for it in self.instance_catalog
            if it.provider == current.provider
            and it.name.split(".")[0] in newer_families
            and it.vcpus >= target_vcpus
            and it.memory_gb >= target_memory
            and it.on_demand_hourly < current.on_demand_hourly
        ]

        if not candidates:
            return None

        recommended = min(candidates, key=lambda it: it.on_demand_hourly)

        current_cost = current.on_demand_hourly * workload.uptime_hours_monthly
        recommended_cost = recommended.on_demand_hourly * workload.uptime_hours_monthly
        savings = current_cost - recommended_cost

        if savings <= 0:
            return None

        return RightsizingRecommendation(
            workload_id=workload.workload_id,
            workload_name=workload.name,
            current_instance=current,
            recommended_instance=recommended,
            current_monthly_cost=current_cost,
            recommended_monthly_cost=recommended_cost,
            monthly_savings=savings,
            annual_savings=savings * 12,
            savings_percent=(savings / current_cost * 100) if current_cost > 0 else 0,
            reason=(
                f"Modernize from {current_family} to "
                f"{recommended.name.split('.')[0]} family"
            ),
            risk_level=RiskLevel.MEDIUM,
            confidence=0.7,
            action="family_change",
            estimated_downtime_minutes=30.0,
        )

    def _compute_target_vcpus(self, workload: Workload) -> int:
        """Compute target vCPUs based on utilization with safety margin."""
        if workload.cpu_utilization_avg > 0:
            used_vcpus = workload.instance_type.vcpus * workload.cpu_utilization_avg
            target = used_vcpus * (1 + self.SAFETY_MARGIN)
            return max(1, int(target))
        return 1

    def _compute_target_memory(self, workload: Workload) -> float:
        """Compute target memory based on utilization with safety margin."""
        if workload.memory_utilization_avg > 0:
            used_memory = (
                workload.instance_type.memory_gb * workload.memory_utilization_avg
            )
            target = used_memory * (1 + self.SAFETY_MARGIN)
            return max(1.0, round(target, 1))
        return 1.0

    def _assess_downsize_risk(
        self,
        workload: Workload,
        current: InstanceType,
        recommended: InstanceType,
    ) -> RiskLevel:
        """Assess risk level of a downsize recommendation."""
        # Production workloads are higher risk
        if workload.environment == "production":
            # Check if utilization is very low (safe) or borderline
            if (
                workload.cpu_utilization_avg < 0.15
                and workload.memory_utilization_avg < 0.20
            ):
                return RiskLevel.LOW
            return RiskLevel.MEDIUM
        elif workload.environment in ("staging", "dev", "test"):
            return RiskLevel.LOW
        return RiskLevel.MEDIUM

    def _compute_confidence(self, workload: Workload) -> float:
        """Compute confidence score based on data quality."""
        confidence = 0.5

        # More metrics = higher confidence
        if workload.cpu_utilization_avg > 0:
            confidence += 0.15
        if workload.cpu_utilization_p95 > 0:
            confidence += 0.10
        if workload.memory_utilization_avg > 0:
            confidence += 0.15
        if workload.memory_utilization_p95 > 0:
            confidence += 0.10

        return min(1.0, confidence)

    def _get_newer_families(self, current_family: str) -> set[str]:
        """Get set of newer instance families (simplified heuristic)."""
        # Extract generation number from family name
        # e.g., "m5" -> 5, "c6i" -> 6
        families = set()

        # Common patterns: m5, m6i, m7i, c5, c6g, etc.
        import re

        match = re.match(r"([a-z]+)(\d+)([a-z]*)", current_family)
        if match:
            prefix = match.group(1)
            gen = int(match.group(2))
            suffix = match.group(3)

            # Add next 2 generations with common suffixes
            for next_gen in range(gen + 1, gen + 3):
                families.add(f"{prefix}{next_gen}")
                families.add(f"{prefix}{next_gen}i")
                families.add(f"{prefix}{next_gen}g")

        return families
