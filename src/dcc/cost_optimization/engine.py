"""Main cost optimization engine — orchestrates all optimization analyses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .cloud_cost_analyzer import CloudCostAnalyzer
from .models import (
    InstanceType,
    OptimizationReport,
    RiskLevel,
    Workload,
)
from .reserved_instances import ReservedInstancePlanner
from .rightsizing import RightsizingEngine
from .spot_strategy import SpotInstancePlanner


class CostOptimizationEngine:
    """Main entry point for cost optimization analysis.

    Orchestrates cloud cost analysis, rightsizing recommendations,
    reserved instance planning, and spot instance strategy.
    """

    def __init__(
        self,
        instance_catalog: Optional[list[InstanceType]] = None,
    ):
        self.instance_catalog = instance_catalog or []
        self.analyzer = CloudCostAnalyzer()
        self.rightsizing = RightsizingEngine(instance_catalog)
        self.ri_planner = ReservedInstancePlanner()
        self.spot_planner = SpotInstancePlanner(instance_catalog)

    def run(self, workloads: list[Workload]) -> OptimizationReport:
        """Run full cost optimization analysis and generate report."""
        report = OptimizationReport()
        report.generated_at = datetime.now(timezone.utc).isoformat()
        report.total_workloads = len(workloads)

        # 1. Cost analysis
        report.cost_breakdown = self.analyzer.analyze(workloads)
        report.total_monthly_cost = report.cost_breakdown.total_monthly

        # 2. Rightsizing recommendations
        report.rightsizing_recommendations = self.rightsizing.recommend_all(workloads)

        # 3. Reserved instance plans
        report.reserved_instance_plans = self.ri_planner.plan(workloads)

        # 4. Spot instance strategies
        report.spot_strategies = self.spot_planner.plan(workloads)

        # 5. Calculate total potential savings
        rightsizing_savings = sum(
            r.annual_savings for r in report.rightsizing_recommendations
            if r.monthly_savings > 0
        )
        ri_savings = sum(p.annual_savings for p in report.reserved_instance_plans)
        spot_savings = sum(s.annual_savings for s in report.spot_strategies)

        report.total_potential_savings = rightsizing_savings + ri_savings + spot_savings
        if report.total_monthly_cost > 0:
            report.savings_percent = (
                report.total_potential_savings
                / (report.total_monthly_cost * 12)
                * 100
            )

        # 6. Risk summary
        report.risk_summary = self._summarize_risks(report)

        # 7. Quick wins and long-term recommendations
        report.quick_wins = self._identify_quick_wins(report)
        report.long_term_recommendations = self._identify_long_term(report)

        return report

    def _summarize_risks(self, report: OptimizationReport) -> dict[str, int]:
        """Summarize risk levels across all recommendations."""
        summary = {"low": 0, "medium": 0, "high": 0}

        for rec in report.rightsizing_recommendations:
            summary[rec.risk_level.value] += 1
        for plan in report.reserved_instance_plans:
            summary[plan.risk_level.value] += 1
        for strategy in report.spot_strategies:
            summary[strategy.risk_level.value] += 1

        return summary

    def _identify_quick_wins(self, report: OptimizationReport) -> list[str]:
        """Identify quick win opportunities."""
        quick_wins = []

        # Idle workloads
        # (Would need workloads passed in — using recommendations as proxy)
        idle_recs = [
            r for r in report.rightsizing_recommendations
            if r.action == "downsize" and r.risk_level == RiskLevel.LOW
        ]
        if idle_recs:
            top = idle_recs[0]
            quick_wins.append(
                f"Downsize {top.workload_name}: save ${top.monthly_savings:.2f}/month "
                f"({top.savings_percent:.0f}% reduction)"
            )

        # Low-risk RI plans
        low_risk_ri = [
            p for p in report.reserved_instance_plans
            if p.risk_level == RiskLevel.LOW and p.savings_percent > 20
        ]
        if low_risk_ri:
            top = low_risk_ri[0]
            quick_wins.append(
                f"Purchase {top.quantity}x {top.instance_type.name} RIs "
                f"({top.term_months}mo): save ${top.monthly_savings:.2f}/month"
            )

        # Low-risk spot strategies
        low_risk_spot = [
            s for s in report.spot_strategies
            if s.risk_level == RiskLevel.LOW and s.savings_percent > 50
        ]
        if low_risk_spot:
            top = low_risk_spot[0]
            quick_wins.append(
                f"Move {top.workload_name} to spot: save ${top.monthly_savings:.2f}/month "
                f"({top.savings_percent:.0f}% reduction)"
            )

        return quick_wins

    def _identify_long_term(self, report: OptimizationReport) -> list[str]:
        """Identify long-term strategic recommendations."""
        long_term = []

        # Family modernization
        family_changes = [
            r for r in report.rightsizing_recommendations
            if r.action == "family_change"
        ]
        if family_changes:
            long_term.append(
                f"Modernize {len(family_changes)} workloads to newer instance families "
                f"for better price/performance"
            )

        # 3-year RI commitments
        long_ri = [
            p for p in report.reserved_instance_plans
            if p.term_months == 36 and p.savings_percent > 30
        ]
        if long_ri:
            long_term.append(
                f"Consider 3-year RI commitments for {len(long_ri)} instance types "
                f"to maximize savings"
            )

        # Spot fleet diversification
        spot_strategies = report.spot_strategies
        if len(spot_strategies) > 3:
            long_term.append(
                f"Build a diversified spot fleet across {len(spot_strategies)} workloads "
                f"to optimize cost and reliability"
            )

        # Rightsizing program
        downsize_recs = [
            r for r in report.rightsizing_recommendations
            if r.action == "downsize"
        ]
        if len(downsize_recs) > 5:
            long_term.append(
                f"Establish a continuous rightsizing program — "
                f"{len(downsize_recs)} workloads are candidates for downsizing"
            )

        return long_term
