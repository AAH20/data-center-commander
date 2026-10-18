"""Reserved instance planner — recommends RI purchases for cost savings."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .models import (
    CloudProvider,
    InstanceType,
    PricingModel,
    ReservedInstancePlan,
    RiskLevel,
    Workload,
)


class ReservedInstancePlanner:
    """Plans reserved instance purchases based on workload patterns."""

    # Break-even thresholds
    MIN_SAVINGS_PERCENT = 10.0  # Minimum savings % to recommend

    # Payment option multipliers (relative to on-demand)
    PAYMENT_OPTIONS = {
        "all_upfront": {"discount": 0.60, "upfront_pct": 1.0},
        "partial_upfront": {"discount": 0.45, "upfront_pct": 0.5},
        "no_upfront": {"discount": 0.30, "upfront_pct": 0.0},
    }

    def plan(
        self,
        workloads: list[Workload],
        term_months: int = 12,
        payment_option: str = "partial_upfront",
    ) -> list[ReservedInstancePlan]:
        """Generate RI plans for stable on-demand workloads."""
        if term_months not in (12, 36):
            raise ValueError("term_months must be 12 or 36")

        if payment_option not in self.PAYMENT_OPTIONS:
            raise ValueError(
                f"payment_option must be one of {list(self.PAYMENT_OPTIONS.keys())}"
            )

        # Group workloads by instance type
        groups = self._group_by_instance_type(workloads)

        plans = []
        for instance_type, group_workloads in groups.items():
            # Only consider on-demand workloads
            on_demand = [
                w for w in group_workloads if w.pricing_model == PricingModel.ON_DEMAND
            ]
            if not on_demand:
                continue

            # Check if workloads are stable enough for RIs
            if not self._is_stable_for_ri(on_demand):
                continue

            plan = self._create_plan(
                instance_type, len(on_demand), term_months, payment_option
            )
            if plan and plan.savings_percent >= self.MIN_SAVINGS_PERCENT:
                plans.append(plan)

        return sorted(plans, key=lambda p: p.annual_savings, reverse=True)

    def plan_all_options(
        self, workloads: list[Workload]
    ) -> dict[str, list[ReservedInstancePlan]]:
        """Generate RI plans for all term/payment combinations."""
        results = {}
        for term in (12, 36):
            for payment in self.PAYMENT_OPTIONS:
                key = f"{term}mo_{payment}"
                results[key] = self.plan(workloads, term, payment)
        return results

    def _group_by_instance_type(
        self, workloads: list[Workload]
    ) -> dict[InstanceType, list[Workload]]:
        """Group workloads by their instance type."""
        groups: dict[InstanceType, list[Workload]] = defaultdict(list)
        for wl in workloads:
            groups[wl.instance_type].append(wl)
        return groups

    def _is_stable_for_ri(self, workloads: list[Workload]) -> bool:
        """Check if a group of workloads is stable enough for RIs."""
        if not workloads:
            return False

        # All workloads should be in production or staging
        for wl in workloads:
            if wl.environment not in ("production", "staging"):
                return False

        # Check uptime consistency
        uptimes = [wl.uptime_hours_monthly for wl in workloads]
        avg_uptime = sum(uptimes) / len(uptimes)
        if avg_uptime < 600:  # Less than ~80% monthly uptime
            return False

        return True

    def _create_plan(
        self,
        instance_type: InstanceType,
        quantity: int,
        term_months: int,
        payment_option: str,
    ) -> Optional[ReservedInstancePlan]:
        """Create an RI plan for a specific instance type."""
        pay_config = self.PAYMENT_OPTIONS[payment_option]

        # Determine base hourly rate
        if term_months == 12:
            base_hourly = instance_type.reserved_1yr_hourly
        else:
            base_hourly = instance_type.reserved_3yr_hourly

        # Apply payment option discount
        on_demand_hourly = instance_type.on_demand_hourly
        effective_hourly = on_demand_hourly * (1 - pay_config["discount"])

        # Calculate costs
        total_hours = term_months * 730
        total_upfront = effective_hourly * total_hours * pay_config["upfront_pct"] * quantity
        total_effective_monthly = effective_hourly * 730 * quantity
        on_demand_equivalent = on_demand_hourly * 730 * quantity

        monthly_savings = on_demand_equivalent - total_effective_monthly
        annual_savings = monthly_savings * 12
        savings_percent = (
            (monthly_savings / on_demand_equivalent * 100)
            if on_demand_equivalent > 0
            else 0
        )

        # Break-even calculation
        if monthly_savings > 0:
            break_even = total_upfront / monthly_savings
        else:
            break_even = float("inf")

        # Break-even should not exceed the RI term
        if break_even > term_months + 0.1:
            return None

        # Risk assessment
        risk = self._assess_risk(term_months, payment_option, instance_type)

        return ReservedInstancePlan(
            instance_type=instance_type,
            provider=instance_type.provider,
            term_months=term_months,
            payment_option=payment_option,
            quantity=quantity,
            hourly_rate=effective_hourly,
            total_upfront=total_upfront,
            total_effective_monthly=total_effective_monthly,
            on_demand_equivalent_monthly=on_demand_equivalent,
            monthly_savings=monthly_savings,
            annual_savings=annual_savings,
            savings_percent=savings_percent,
            break_even_months=break_even,
            risk_level=risk,
        )

    def _assess_risk(
        self, term_months: int, payment_option: str, instance_type: InstanceType
    ) -> RiskLevel:
        """Assess risk level of an RI purchase."""
        risk_score = 0

        # Longer terms = higher risk
        if term_months == 36:
            risk_score += 2
        else:
            risk_score += 1

        # Higher upfront = lower risk (more committed discount)
        if payment_option == "all_upfront":
            risk_score -= 1
        elif payment_option == "no_upfront":
            risk_score += 1

        # Newer instance families are lower risk (longer remaining lifespan)
        family = instance_type.name.split(".")[0]
        import re

        match = re.search(r"(\d+)", family)
        if match:
            gen = int(match.group(1))
            if gen >= 6:
                risk_score -= 1
            elif gen <= 4:
                risk_score += 1

        if risk_score <= 0:
            return RiskLevel.LOW
        elif risk_score <= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH
