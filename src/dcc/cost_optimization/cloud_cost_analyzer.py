"""Cloud cost analyzer — aggregates and analyzes cloud spending."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .models import (
    CloudProvider,
    CostBreakdown,
    PricingModel,
    Workload,
)


class CloudCostAnalyzer:
    """Analyzes cloud costs across providers, regions, teams, and environments."""

    def analyze(self, workloads: list[Workload]) -> CostBreakdown:
        """Produce a full cost breakdown from a list of workloads."""
        breakdown = CostBreakdown()
        breakdown.workload_count = len(workloads)

        for wl in workloads:
            cost = wl.monthly_cost
            breakdown.total_monthly += cost

            # By provider
            provider_key = wl.instance_type.provider.value
            breakdown.by_provider[provider_key] = (
                breakdown.by_provider.get(provider_key, 0.0) + cost
            )

            # By region
            breakdown.by_region[wl.region] = (
                breakdown.by_region.get(wl.region, 0.0) + cost
            )

            # By team
            breakdown.by_team[wl.team] = (
                breakdown.by_team.get(wl.team, 0.0) + cost
            )

            # By environment
            breakdown.by_environment[wl.environment] = (
                breakdown.by_environment.get(wl.environment, 0.0) + cost
            )

            # By pricing model
            pricing_key = wl.pricing_model.value
            breakdown.by_pricing_model[pricing_key] = (
                breakdown.by_pricing_model.get(pricing_key, 0.0) + cost
            )

            # By instance family (e.g., "m5" from "m5.xlarge")
            family = self._extract_family(wl.instance_type.name)
            breakdown.by_instance_family[family] = (
                breakdown.by_instance_family.get(family, 0.0) + cost
            )

            # Compute vs storage vs network (simplified model)
            breakdown.compute_monthly += cost * 0.85
            breakdown.storage_monthly += cost * 0.10
            breakdown.network_monthly += cost * 0.05

        breakdown.other_monthly = (
            breakdown.total_monthly
            - breakdown.compute_monthly
            - breakdown.storage_monthly
            - breakdown.network_monthly
        )

        return breakdown

    def top_spenders(
        self, workloads: list[Workload], n: int = 10
    ) -> list[Workload]:
        """Return the top N workloads by monthly cost."""
        return sorted(workloads, key=lambda w: w.monthly_cost, reverse=True)[:n]

    def idle_workloads(
        self,
        workloads: list[Workload],
        cpu_threshold: float = 0.05,
        memory_threshold: float = 0.10,
    ) -> list[Workload]:
        """Find workloads with very low utilization (candidates for termination)."""
        idle = []
        for wl in workloads:
            if (
                wl.cpu_utilization_avg < cpu_threshold
                and wl.memory_utilization_avg < memory_threshold
            ):
                idle.append(wl)
        return idle

    def underutilized_workloads(
        self,
        workloads: list[Workload],
        cpu_threshold: float = 0.25,
        memory_threshold: float = 0.30,
    ) -> list[Workload]:
        """Find workloads with low utilization (rightsizing candidates)."""
        under = []
        for wl in workloads:
            if (
                wl.cpu_utilization_avg < cpu_threshold
                and wl.memory_utilization_avg < memory_threshold
            ):
                under.append(wl)
        return under

    def overutilized_workloads(
        self,
        workloads: list[Workload],
        cpu_threshold: float = 0.80,
        memory_threshold: float = 0.85,
    ) -> list[Workload]:
        """Find workloads with high utilization (upsizing candidates)."""
        over = []
        for wl in workloads:
            if (
                wl.cpu_utilization_p95 > cpu_threshold
                or wl.memory_utilization_p95 > memory_threshold
            ):
                over.append(wl)
        return over

    def cost_trend(
        self,
        current_workloads: list[Workload],
        previous_workloads: list[Workload],
    ) -> dict[str, float]:
        """Compare current vs previous period costs."""
        current_total = sum(w.monthly_cost for w in current_workloads)
        previous_total = sum(w.monthly_cost for w in previous_workloads)

        delta = current_total - previous_total
        percent = (delta / previous_total * 100) if previous_total > 0 else 0.0

        return {
            "current_monthly": current_total,
            "previous_monthly": previous_total,
            "delta": delta,
            "percent_change": percent,
        }

    def provider_distribution(
        self, workloads: list[Workload]
    ) -> dict[str, float]:
        """Get cost distribution by provider as percentages."""
        breakdown = self.analyze(workloads)
        total = breakdown.total_monthly
        if total == 0:
            return {}
        return {
            provider: cost / total * 100
            for provider, cost in breakdown.by_provider.items()
        }

    def _extract_family(self, instance_name: str) -> str:
        """Extract instance family from name (e.g., 'm5.xlarge' -> 'm5')."""
        parts = instance_name.split(".")
        return parts[0] if parts else instance_name
