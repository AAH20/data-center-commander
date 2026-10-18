"""Spot instance planner — recommends spot instance strategies."""

from __future__ import annotations

from typing import Optional

from .models import (
    InstanceType,
    PricingModel,
    RiskLevel,
    SpotInstanceStrategy,
    Workload,
)


class SpotInstancePlanner:
    """Plans spot instance usage for fault-tolerant workloads."""

    # Interruption probability estimates by instance family age
    INTERRUPTION_RISK_BY_GENERATION = {
        # Newer generations have lower interruption rates
        "current_gen": 0.05,
        "previous_gen": 0.10,
        "older_gen": 0.20,
    }

    # Environment suitability for spot
    SPOT_SUITABLE_ENVIRONMENTS = {"dev", "test", "staging", "batch", "ci"}
    SPOT_MARGINALLY_SUITABLE = {"production"}  # Only with fallback

    # Maximum acceptable interruption probability
    MAX_INTERRUPTION_PROBABILITY = 0.15

    def __init__(self, instance_catalog: Optional[list[InstanceType]] = None):
        self.instance_catalog = instance_catalog or []

    def plan(self, workloads: list[Workload]) -> list[SpotInstanceStrategy]:
        """Generate spot instance strategies for suitable workloads."""
        strategies = []
        for wl in workloads:
            strategy = self._plan_for_workload(wl)
            if strategy:
                strategies.append(strategy)
        return sorted(strategies, key=lambda s: s.annual_savings, reverse=True)

    def _plan_for_workload(
        self, workload: Workload
    ) -> Optional[SpotInstanceStrategy]:
        """Create a spot strategy for a single workload."""
        # Check if workload is suitable for spot
        if not self._is_suitable_for_spot(workload):
            return None

        current = workload.instance_type

        # Find the best spot instance (same or newer family)
        recommended = self._find_best_spot_instance(workload)
        if not recommended:
            recommended = current

        # Calculate costs
        current_cost = self._get_current_monthly_cost(workload)
        spot_cost = recommended.spot_hourly * workload.uptime_hours_monthly
        savings = current_cost - spot_cost

        if savings <= 0:
            return None

        # Assess interruption risk
        interruption_prob = self._estimate_interruption_probability(recommended)
        if interruption_prob > self.MAX_INTERRUPTION_PROBABILITY:
            return None

        risk = self._assess_spot_risk(workload, interruption_prob)

        # Recommended bid (slightly above spot price to reduce interruptions)
        recommended_bid = recommended.spot_hourly * 1.1

        return SpotInstanceStrategy(
            workload_id=workload.workload_id,
            workload_name=workload.name,
            current_instance=current,
            recommended_instance=recommended,
            current_monthly_cost=current_cost,
            spot_monthly_cost=spot_cost,
            monthly_savings=savings,
            annual_savings=savings * 12,
            savings_percent=(savings / current_cost * 100) if current_cost > 0 else 0,
            interruption_risk=risk,
            interruption_probability=interruption_prob,
            recommended_max_bid=recommended_bid,
            diversification_recommendation=self._diversification_advice(recommended),
            fallback_strategy=self._fallback_strategy(workload),
            risk_level=risk,
        )

    def _is_suitable_for_spot(self, workload: Workload) -> bool:
        """Check if a workload is suitable for spot instances."""
        # Don't recommend spot for already-spot workloads
        if workload.pricing_model == PricingModel.SPOT:
            return False

        # Check environment suitability
        if workload.environment in self.SPOT_SUITABLE_ENVIRONMENTS:
            return True

        # Production workloads need fallback strategy
        if workload.environment in self.SPOT_MARGINALLY_SUITABLE:
            # Only if utilization is low (stateless, fault-tolerant)
            if workload.cpu_utilization_avg < 0.6:
                return True

        return False

    def _find_best_spot_instance(
        self, workload: Workload
    ) -> Optional[InstanceType]:
        """Find the best spot instance for a workload."""
        current = workload.instance_type

        if not self.instance_catalog:
            return current

        # Find instances with similar or better specs at lower spot price
        candidates = [
            it
            for it in self.instance_catalog
            if it.provider == current.provider
            and it.vcpus >= current.vcpus
            and it.memory_gb >= current.memory_gb
            and it.spot_hourly < current.on_demand_hourly
        ]

        if not candidates:
            return current

        # Prefer newer generations with lower spot prices
        return min(candidates, key=lambda it: it.spot_hourly)

    def _get_current_monthly_cost(self, workload: Workload) -> float:
        """Get the current monthly cost of a workload."""
        hourly_rates = {
            PricingModel.ON_DEMAND: workload.instance_type.on_demand_hourly,
            PricingModel.RESERVED_1YR: workload.instance_type.reserved_1yr_hourly,
            PricingModel.RESERVED_3YR: workload.instance_type.reserved_3yr_hourly,
            PricingModel.SPOT: workload.instance_type.spot_hourly,
            PricingModel.SAVINGS_PLAN_1YR: workload.instance_type.reserved_1yr_hourly,
            PricingModel.SAVINGS_PLAN_3YR: workload.instance_type.reserved_3yr_hourly,
        }
        return hourly_rates[workload.pricing_model] * workload.uptime_hours_monthly

    def _estimate_interruption_probability(self, instance: InstanceType) -> float:
        """Estimate spot interruption probability for an instance type."""
        family = instance.name.split(".")[0]

        import re

        match = re.search(r"(\d+)", family)
        if not match:
            return self.INTERRUPTION_RISK_BY_GENERATION["older_gen"]

        gen = int(match.group(1))
        if gen >= 7:
            return self.INTERRUPTION_RISK_BY_GENERATION["current_gen"]
        elif gen >= 5:
            return self.INTERRUPTION_RISK_BY_GENERATION["previous_gen"]
        else:
            return self.INTERRUPTION_RISK_BY_GENERATION["older_gen"]

    def _assess_spot_risk(
        self, workload: Workload, interruption_prob: float
    ) -> RiskLevel:
        """Assess overall risk of using spot for a workload."""
        if workload.environment in self.SPOT_SUITABLE_ENVIRONMENTS:
            if interruption_prob <= 0.05:
                return RiskLevel.LOW
            elif interruption_prob <= 0.10:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.HIGH

        # Production workloads are always at least medium risk
        if interruption_prob <= 0.05:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    def _diversification_advice(self, instance: InstanceType) -> str:
        """Provide advice on diversifying spot instance types."""
        family = instance.name.split(".")[0]
        return (
            f"Use a diversified spot fleet with {family} and at least "
            f"2 other instance families to reduce interruption risk. "
            f"Consider using spot instance pools with capacity-optimized allocation."
        )

    def _fallback_strategy(self, workload: Workload) -> str:
        """Recommend a fallback strategy for spot interruptions."""
        if workload.environment in self.SPOT_SUITABLE_ENVIRONMENTS:
            return (
                "Use spot instances with automatic restart. "
                "Implement checkpointing for long-running tasks. "
                "Use spot fleet with on-demand fallback."
            )
        else:
            return (
                "Use spot instances with on-demand fallback. "
                "Implement graceful shutdown handlers. "
                "Use capacity-optimized spot allocation strategy. "
                "Maintain on-demand capacity for critical components."
            )
