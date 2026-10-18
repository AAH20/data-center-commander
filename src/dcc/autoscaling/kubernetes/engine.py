"""Main autoscaling engine — orchestrates HPA analyses and recommendations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .hpa import HPAEngine
from .metrics import MetricsCollector
from .models import (
    AutoscalingReport,
    HPAConfiguration,
    HPATarget,
    HPATargetKind,
    ScalingDirection,
    ScalingEvent,
    ScalingMetric,
    ScalingMetricType,
    ScalingPolicy,
    ScalingPolicyConfig,
    ScalingRecommendation,
    ScalingStatus,
)


class AutoscalingEngine:
    """Main entry point for Kubernetes autoscaling.

    Orchestrates HPA configuration, custom metrics, external metrics,
    scaling recommendations, and cost optimization across clusters.
    """

    def __init__(self):
        self.hpa_engine = HPAEngine()
        self.metrics_collector = MetricsCollector()

    def create_hpa(
        self,
        target: HPATarget,
        metrics: Optional[list[ScalingMetric]] = None,
        policies: Optional[list[ScalingPolicyConfig]] = None,
    ) -> HPAConfiguration:
        """Create a new HPA configuration."""
        return self.hpa_engine.create_hpa(target, metrics, policies)

    def evaluate_all(self) -> list[ScalingRecommendation]:
        """Evaluate scaling for all HPA targets."""
        recommendations: list[ScalingRecommendation] = []

        for hpa in self.hpa_engine.get_all_hpas():
            rec = self.hpa_engine.evaluate_scaling(
                hpa.target.cluster,
                hpa.target.namespace,
                hpa.target.name,
            )
            if rec is not None:
                recommendations.append(rec)

        return recommendations

    def run(
        self,
        targets: list[HPATarget],
        metrics: Optional[dict[str, list[ScalingMetric]]] = None,
        policies: Optional[dict[str, list[ScalingPolicyConfig]]] = None,
    ) -> AutoscalingReport:
        """Run full autoscaling analysis and generate report."""
        report = AutoscalingReport()
        report.generated_at = datetime.now(timezone.utc).isoformat()

        # Create HPAs for all targets
        for target in targets:
            target_metrics = metrics.get(target.name, []) if metrics else []
            target_policies = policies.get(target.name, []) if policies else []
            self.create_hpa(target, target_metrics, target_policies)

        report.total_targets = len(targets)
        report.total_hpas = len(self.hpa_engine.get_all_hpas())
        report.active_hpas = sum(
            1 for hpa in self.hpa_engine.get_all_hpas()
            if hpa.status == ScalingStatus.STABLE
        )

        # Evaluate scaling recommendations
        report.scaling_recommendations = self.evaluate_all()

        # Get recent events
        report.scaling_events = self.hpa_engine.get_events()

        # Metrics summary
        report.metrics_summary = self._summarize_metrics()

        # Cost estimation
        report.estimated_monthly_cost = self._estimate_monthly_cost(report)
        report.potential_savings = self._estimate_potential_savings(report)

        # Risk summary
        report.risk_summary = self._summarize_risks(report)

        # Recommendations
        report.quick_wins = self._identify_quick_wins(report)
        report.long_term_recommendations = self._identify_long_term(report)

        return report

    def _summarize_metrics(self) -> dict:
        """Summarize all metrics."""
        all_metrics = self.metrics_collector.get_all_metrics()

        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}

        for metric in all_metrics:
            type_key = metric.metric_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            source_key = metric.source.value
            by_source[source_key] = by_source.get(source_key, 0) + 1

        return {
            "total_metrics": len(all_metrics),
            "by_type": by_type,
            "by_source": by_source,
            "custom_metrics": len(self.metrics_collector.get_custom_metrics()),
            "external_metrics": len(self.metrics_collector.get_external_metrics()),
            "resource_metrics": len(self.metrics_collector.get_resource_metrics()),
        }

    def _estimate_monthly_cost(self, report: AutoscalingReport) -> float:
        """Estimate total monthly cost of running workloads."""
        total = 0.0

        for hpa in self.hpa_engine.get_all_hpas():
            # Base cost per replica (simplified)
            base_cost_per_replica = 50.0  # $50/month per replica

            # Add cost for custom/external metrics
            metric_cost = len(hpa.metrics) * 10.0  # $10/month per metric

            total += (hpa.target.current_replicas * base_cost_per_replica) + metric_cost

        return total

    def _estimate_potential_savings(self, report: AutoscalingReport) -> float:
        """Estimate potential savings from optimization."""
        savings = 0.0

        for rec in report.scaling_recommendations:
            if rec.recommended_replicas < rec.current_replicas:
                # Scaling down saves money
                diff = rec.current_replicas - rec.recommended_replicas
                savings += diff * 50.0  # $50/month per replica saved

        return max(0.0, savings)

    def _summarize_risks(self, report: AutoscalingReport) -> dict[str, int]:
        """Summarize risk levels across all recommendations."""
        summary = {"low": 0, "medium": 0, "high": 0}

        for rec in report.scaling_recommendations:
            summary[rec.risk_level] = summary.get(rec.risk_level, 0) + 1

        return summary

    def _identify_quick_wins(self, report: AutoscalingReport) -> list[str]:
        """Identify quick win opportunities."""
        quick_wins: list[str] = []

        # Low-risk scale-down opportunities
        for rec in report.scaling_recommendations:
            if rec.risk_level == "low" and rec.recommended_replicas < rec.current_replicas:
                quick_wins.append(
                    f"Scale down {rec.target.name} from {rec.current_replicas} to "
                    f"{rec.recommended_replicas} replicas (low risk, saves "
                    f"${(rec.current_replicas - rec.recommended_replicas) * 50:.0f}/mo)"
                )

        # Metrics without current values
        for hpa in self.hpa_engine.get_all_hpas():
            for metric in hpa.metrics:
                if metric.current_value is None:
                    quick_wins.append(
                        f"Configure metrics pipeline for {metric.name} on {hpa.target.name}"
                    )

        return quick_wins[:5]

    def _identify_long_term(self, report: AutoscalingReport) -> list[str]:
        """Identify long-term strategic recommendations."""
        long_term: list[str] = []

        # Check for targets without custom metrics
        for hpa in self.hpa_engine.get_all_hpas():
            has_custom = any(
                m.metric_type == ScalingMetricType.CUSTOM for m in hpa.metrics
            )
            if not has_custom:
                long_term.append(
                    f"Add custom metrics for {hpa.target.name} to improve scaling accuracy"
                )

        # Check for targets with high max replicas
        for hpa in self.hpa_engine.get_all_hpas():
            if hpa.target.max_replicas > 50:
                long_term.append(
                    f"Review max replicas for {hpa.target.name} "
                    f"({hpa.target.max_replicas}) — consider cluster autoscaler"
                )

        # Check for frequent scaling events
        events = self.hpa_engine.get_events()
        target_event_counts: dict[str, int] = {}
        for event in events:
            key = f"{event.target.cluster}/{event.target.namespace}/{event.target.name}"
            target_event_counts[key] = target_event_counts.get(key, 0) + 1

        for key, count in target_event_counts.items():
            if count > 10:
                long_term.append(
                    f"Investigate frequent scaling for {key} ({count} events) — "
                    f"consider tuning HPA parameters"
                )

        return long_term
