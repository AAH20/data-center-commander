"""Horizontal Pod Autoscaler engine — core scaling logic."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from .metrics import MetricsCollector
from .models import (
    HPAConfiguration,
    HPATarget,
    HPATargetKind,
    ScalingDirection,
    ScalingEvent,
    ScalingMetric,
    ScalingPolicy,
    ScalingPolicyConfig,
    ScalingRecommendation,
    ScalingStatus,
)


class HPAEngine:
    """Core HPA engine for scaling decisions."""

    def __init__(self):
        self._hpas: dict[str, HPAConfiguration] = {}
        self._events: list[ScalingEvent] = []
        self._collector = MetricsCollector()

    def create_hpa(
        self,
        target: HPATarget,
        metrics: Optional[list[ScalingMetric]] = None,
        policies: Optional[list[ScalingPolicyConfig]] = None,
    ) -> HPAConfiguration:
        """Create a new HPA configuration."""
        hpa = HPAConfiguration(
            target=target,
            metrics=metrics or [],
            policies=policies or [],
        )
        key = f"{target.cluster}/{target.namespace}/{target.name}"
        self._hpas[key] = hpa

        # Register metrics with collector
        for metric in hpa.metrics:
            self._collector.register_metric(
                name=metric.name,
                metric_type=metric.metric_type,
                source=metric.source,
                target_value=metric.target_value,
                unit=metric.unit,
                labels=metric.labels,
                metadata=metric.metadata,
            )

        return hpa

    def get_hpa(self, cluster: str, namespace: str, name: str) -> Optional[HPAConfiguration]:
        """Get an HPA configuration by target."""
        key = f"{cluster}/{namespace}/{name}"
        return self._hpas.get(key)

    def get_all_hpas(self) -> list[HPAConfiguration]:
        """Get all HPA configurations."""
        return list(self._hpas.values())

    def delete_hpa(self, cluster: str, namespace: str, name: str) -> bool:
        """Delete an HPA configuration."""
        key = f"{cluster}/{namespace}/{name}"
        if key in self._hpas:
            del self._hpas[key]
            return True
        return False

    def update_metric(
        self,
        cluster: str,
        namespace: str,
        name: str,
        metric_name: str,
        value: float,
    ) -> bool:
        """Update a metric value for an HPA target."""
        hpa = self.get_hpa(cluster, namespace, name)
        if hpa is None:
            return False

        for metric in hpa.metrics:
            if metric.name == metric_name:
                metric.current_value = value
                self._collector.update_metric_value(metric_name, value)
                return True
        return False

    def evaluate_scaling(
        self,
        cluster: str,
        namespace: str,
        name: str,
    ) -> Optional[ScalingRecommendation]:
        """Evaluate scaling for a target and return recommendation."""
        hpa = self.get_hpa(cluster, namespace, name)
        if hpa is None:
            return None

        if not hpa.metrics:
            return None

        # Get scaling decision from collector
        desired, reason = self._collector.get_scaling_decision(
            current_replicas=hpa.target.current_replicas,
            metrics=hpa.metrics,
            min_replicas=hpa.target.min_replicas,
            max_replicas=hpa.target.max_replicas,
        )

        current = hpa.target.current_replicas
        if desired == current:
            return None

        direction = ScalingDirection.UP if desired > current else ScalingDirection.DOWN

        # Calculate confidence based on metric data
        confidence = self._calculate_confidence(hpa.metrics)

        # Determine risk level
        risk_level = self._assess_risk(hpa, desired, direction)

        # Generate actions
        actions = self._generate_actions(hpa, desired, direction)

        recommendation = ScalingRecommendation(
            target=hpa.target,
            current_replicas=current,
            recommended_replicas=desired,
            reason=reason,
            confidence=confidence,
            metrics=list(hpa.metrics),
            risk_level=risk_level,
            actions=actions,
        )

        return recommendation

    def apply_scaling(
        self,
        cluster: str,
        namespace: str,
        name: str,
        replicas: int,
        reason: str = "",
    ) -> Optional[ScalingEvent]:
        """Apply scaling to a target."""
        hpa = self.get_hpa(cluster, namespace, name)
        if hpa is None:
            return None

        old_replicas = hpa.target.current_replicas
        new_replicas = max(hpa.target.min_replicas, min(hpa.target.max_replicas, replicas))

        if old_replicas == new_replicas:
            return None

        direction = ScalingDirection.UP if new_replicas > old_replicas else ScalingDirection.DOWN

        event = ScalingEvent(
            event_id=f"evt-{datetime.now(timezone.utc).timestamp()}",
            target=hpa.target,
            timestamp=datetime.now(timezone.utc),
            direction=direction,
            from_replicas=old_replicas,
            to_replicas=new_replicas,
            reason=reason or f"Scaled from {old_replicas} to {new_replicas}",
            metrics=list(hpa.metrics),
            status=ScalingStatus.SCALING,
        )

        # Update target
        hpa.target.current_replicas = new_replicas
        hpa.last_scale_time = datetime.now(timezone.utc)
        hpa.status = ScalingStatus.SCALING
        hpa.updated_at = datetime.now(timezone.utc)

        self._events.append(event)
        return event

    def get_events(
        self,
        cluster: Optional[str] = None,
        namespace: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[ScalingEvent]:
        """Get scaling events, optionally filtered."""
        events = self._events
        if cluster:
            events = [e for e in events if e.target.cluster == cluster]
        if namespace:
            events = [e for e in events if e.target.namespace == namespace]
        if name:
            events = [e for e in events if e.target.name == name]
        return events

    def get_metrics_collector(self) -> MetricsCollector:
        """Get the metrics collector."""
        return self._collector

    def _calculate_confidence(self, metrics: list[ScalingMetric]) -> float:
        """Calculate confidence score for scaling decision."""
        if not metrics:
            return 0.0

        total_confidence = 0.0
        count = 0

        for metric in metrics:
            if metric.current_value is None:
                continue
            # Higher confidence when further from target
            if metric.target_value > 0:
                ratio = metric.current_value / metric.target_value
                # Confidence increases as we move away from 1.0
                confidence = min(1.0, abs(ratio - 1.0) * 2)
                total_confidence += confidence
                count += 1

        return total_confidence / count if count > 0 else 0.0

    def _assess_risk(
        self,
        hpa: HPAConfiguration,
        desired: int,
        direction: ScalingDirection,
    ) -> str:
        """Assess risk level of scaling operation."""
        current = hpa.target.current_replicas
        change_ratio = abs(desired - current) / max(current, 1)

        # High risk: large scale down or scaling to max
        if direction == ScalingDirection.DOWN and change_ratio > 0.5:
            return "high"
        if desired >= hpa.target.max_replicas:
            return "high"

        # Medium risk: moderate changes
        if change_ratio > 0.3:
            return "medium"

        return "low"

    def _generate_actions(
        self,
        hpa: HPAConfiguration,
        desired: int,
        direction: ScalingDirection,
    ) -> list[str]:
        """Generate action items for scaling."""
        actions: list[str] = []

        if direction == ScalingDirection.UP:
            actions.append(f"Scale up {hpa.target.name} from {hpa.target.current_replicas} to {desired} replicas")
            actions.append("Verify resource availability in cluster")
            actions.append("Monitor pod startup and readiness")
        else:
            actions.append(f"Scale down {hpa.target.name} from {hpa.target.current_replicas} to {desired} replicas")
            actions.append("Drain connections from removed pods")
            actions.append("Verify no critical workloads affected")

        return actions

    def generate_scaling_manifest(self, hpa: HPAConfiguration) -> str:
        """Generate Kubernetes HPA manifest YAML."""
        target = hpa.target
        metrics_yaml = []

        for metric in hpa.metrics:
            if metric.metric_type.value == "cpu":
                metrics_yaml.append({
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": int(metric.target_value),
                        },
                    },
                })
            elif metric.metric_type.value == "memory":
                metrics_yaml.append({
                    "type": "Resource",
                    "resource": {
                        "name": "memory",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": int(metric.target_value),
                        },
                    },
                })
            else:
                metrics_yaml.append({
                    "type": "External" if metric.metric_type.value == "external" else "Object",
                    "external" if metric.metric_type.value == "external" else "object": {
                        "metric": {
                            "name": metric.name,
                            "selector": {
                                "matchLabels": metric.labels,
                            },
                        },
                        "target": {
                            "type": "Value" if not metric.target_average else "AverageValue",
                            "value": str(int(metric.target_value)) if not metric.target_average else None,
                            "averageValue": str(int(metric.target_value)) if metric.target_average else None,
                        },
                    },
                })

        manifest = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": target.name,
                "namespace": target.namespace,
                "labels": target.labels,
                "annotations": target.annotations,
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersions": "apps/v1",
                    "kind": target.kind.value,
                    "name": target.name,
                },
                "minReplicas": target.min_replicas,
                "maxReplicas": target.max_replicas,
                "metrics": metrics_yaml,
            },
        }

        import yaml
        return yaml.dump(manifest, default_flow_style=False)
