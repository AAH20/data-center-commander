"""Custom and external metrics handler for Kubernetes HPA."""
from __future__ import annotations

from typing import Any, Optional

from .models import (
    MetricSource,
    ScalingMetric,
    ScalingMetricType,
)


class MetricsCollector:
    """Collects and manages custom and external metrics for HPA."""

    def __init__(self):
        self._metrics: dict[str, ScalingMetric] = {}
        self._sources: dict[str, MetricSource] = {}

    def register_metric(
        self,
        name: str,
        metric_type: ScalingMetricType,
        source: MetricSource,
        target_value: float,
        unit: str = "",
        labels: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ScalingMetric:
        """Register a new metric for autoscaling."""
        metric = ScalingMetric(
            name=name,
            metric_type=metric_type,
            source=source,
            target_value=target_value,
            unit=unit,
            labels=labels or {},
            metadata=metadata or {},
        )
        self._metrics[name] = metric
        self._sources[name] = source
        return metric

    def update_metric_value(self, name: str, value: float) -> None:
        """Update the current value of a metric."""
        if name in self._metrics:
            self._metrics[name].current_value = value

    def get_metric(self, name: str) -> Optional[ScalingMetric]:
        """Get a metric by name."""
        return self._metrics.get(name)

    def get_metrics_by_type(self, metric_type: ScalingMetricType) -> list[ScalingMetric]:
        """Get all metrics of a specific type."""
        return [m for m in self._metrics.values() if m.metric_type == metric_type]

    def get_metrics_by_source(self, source: MetricSource) -> list[ScalingMetric]:
        """Get all metrics from a specific source."""
        return [m for m in self._metrics.values() if m.source == source]

    def get_all_metrics(self) -> list[ScalingMetric]:
        """Get all registered metrics."""
        return list(self._metrics.values())

    def remove_metric(self, name: str) -> bool:
        """Remove a metric."""
        if name in self._metrics:
            del self._metrics[name]
            del self._sources[name]
            return True
        return False

    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()
        self._sources.clear()

    def get_custom_metrics(self) -> list[ScalingMetric]:
        """Get all custom metrics."""
        return self.get_metrics_by_type(ScalingMetricType.CUSTOM)

    def get_external_metrics(self) -> list[ScalingMetric]:
        """Get all external metrics."""
        return self.get_metrics_by_type(ScalingMetricType.EXTERNAL)

    def get_resource_metrics(self) -> list[ScalingMetric]:
        """Get CPU and memory metrics."""
        return [
            m for m in self._metrics.values()
            if m.metric_type in (ScalingMetricType.CPU, ScalingMetricType.MEMORY)
        ]

    def calculate_desired_replicas(
        self,
        current_replicas: int,
        metric: ScalingMetric,
    ) -> int:
        """Calculate desired replicas based on a metric."""
        if metric.current_value is None or metric.target_value == 0:
            return current_replicas

        ratio = metric.current_value / metric.target_value
        desired = int(current_replicas * ratio)
        return max(1, desired)

    def get_scaling_decision(
        self,
        current_replicas: int,
        metrics: list[ScalingMetric],
        min_replicas: int = 1,
        max_replicas: int = 10,
    ) -> tuple[int, str]:
        """Get scaling decision based on multiple metrics."""
        if not metrics:
            return current_replicas, "No metrics available"

        # Find the metric with highest utilization
        max_util = 0.0
        max_metric = None

        for metric in metrics:
            if metric.current_value is None:
                continue
            util = metric.current_value / metric.target_value
            if util > max_util:
                max_util = util
                max_metric = metric

        if max_metric is None:
            return current_replicas, "No metric values available"

        if max_util > 1.0:
            # Scale up
            desired = self.calculate_desired_replicas(current_replicas, max_metric)
            desired = min(desired, max_replicas)
            reason = (
                f"Scale up: {max_metric.name} at {max_util * 100:.1f}% "
                f"({max_metric.current_value:.2f}/{max_metric.target_value:.2f})"
            )
            return desired, reason
        elif max_util < 0.5:
            # Scale down
            desired = self.calculate_desired_replicas(current_replicas, max_metric)
            desired = max(desired, min_replicas)
            reason = (
                f"Scale down: {max_metric.name} at {max_util * 100:.1f}% "
                f"({max_metric.current_value:.2f}/{max_metric.target_value:.2f})"
            )
            return desired, reason
        else:
            return current_replicas, (
                f"Stable: {max_metric.name} at {max_util * 100:.1f}%"
            )
