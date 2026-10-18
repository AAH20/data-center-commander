"""Alert correlation and root-cause analysis.

Correlates alerts from multiple sources (SOC, auto-scaling, container,
observability, security posture) to identify root causes and reduce
alert fatigue through intelligent grouping and deduplication.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Sequence

from .models import (
    CorrelationResult,
    EventSeverity,
    IntegrationAlert,
    IntegrationEvent,
)


# Correlation window in seconds — alerts within this window are candidates
DEFAULT_CORRELATION_WINDOW = 300.0  # 5 minutes

# Minimum confidence threshold for a correlation to be considered valid
MIN_CORRELATION_CONFIDENCE = 0.3


class AlertCorrelator:
    """Correlates alerts from multiple sources to identify root causes.

    Uses temporal proximity, source diversity, and severity weighting
    to group related alerts and identify the most likely root cause.

    Usage:
        correlator = AlertCorrelator()
        correlator.add_alert(alert)
        results = correlator.correlate()
    """

    def __init__(
        self,
        correlation_window: float = DEFAULT_CORRELATION_WINDOW,
        min_confidence: float = MIN_CORRELATION_CONFIDENCE,
    ) -> None:
        self.correlation_window = correlation_window
        self.min_confidence = min_confidence
        self._alerts: dict[str, IntegrationAlert] = {}
        self._events: dict[str, IntegrationEvent] = {}

    def add_alert(self, alert: IntegrationAlert) -> None:
        """Add an alert for correlation."""
        self._alerts[alert.alert_id] = alert

    def add_event(self, event: IntegrationEvent) -> None:
        """Add an event for correlation context."""
        self._events[event.event_id] = event

    def correlate(self) -> list[CorrelationResult]:
        """Run correlation analysis on all added alerts.

        Returns:
            List of CorrelationResult objects, sorted by confidence
            (highest first).
        """
        if not self._alerts:
            return []

        alerts = list(self._alerts.values())
        # Sort by timestamp
        alerts.sort(key=lambda a: a.timestamp)

        # Group alerts into correlation clusters
        clusters = self._cluster_alerts(alerts)

        results: list[CorrelationResult] = []
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            result = self._analyze_cluster(cluster)
            if result and result.confidence >= self.min_confidence:
                results.append(result)

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def _cluster_alerts(
        self, alerts: list[IntegrationAlert]
    ) -> list[list[IntegrationAlert]]:
        """Group alerts into clusters based on temporal proximity."""
        if not alerts:
            return []

        clusters: list[list[IntegrationAlert]] = []
        current_cluster: list[IntegrationAlert] = [alerts[0]]

        for i in range(1, len(alerts)):
            prev = alerts[i - 1]
            curr = alerts[i]
            if curr.timestamp - prev.timestamp <= self.correlation_window:
                current_cluster.append(curr)
            else:
                clusters.append(current_cluster)
                current_cluster = [curr]

        clusters.append(current_cluster)
        return clusters

    def _analyze_cluster(
        self, cluster: list[IntegrationAlert]
    ) -> CorrelationResult | None:
        """Analyze a cluster of alerts to identify root cause."""
        if len(cluster) < 2:
            return None

        # Score each alert as a potential root cause
        scores: dict[str, float] = {}
        for alert in cluster:
            score = self._score_root_cause_potential(alert, cluster)
            scores[alert.alert_id] = score

        # The alert with the highest score is the primary (root cause)
        primary_id = max(scores, key=scores.get)
        primary = next(a for a in cluster if a.alert_id == primary_id)

        # Correlated alerts are all others in the cluster
        correlated_ids = [a.alert_id for a in cluster if a.alert_id != primary_id]

        # Calculate confidence based on cluster characteristics
        confidence = self._calculate_confidence(cluster, primary)

        # Generate root cause description
        root_cause = self._generate_root_cause(primary, cluster)

        # Generate recommended action
        recommended_action = self._generate_recommendation(primary, cluster)

        # Update alert with correlation info
        primary.correlated_alert_ids = correlated_ids
        primary.root_cause = root_cause

        return CorrelationResult(
            correlation_id=f"corr-{primary_id}",
            primary_alert_id=primary_id,
            correlated_alert_ids=correlated_ids,
            confidence=confidence,
            root_cause=root_cause,
            recommended_action=recommended_action,
            metadata={
                "cluster_size": len(cluster),
                "sources": list({a.source.value for a in cluster}),
                "time_span_seconds": cluster[-1].timestamp - cluster[0].timestamp,
            },
        )

    def _score_root_cause_potential(
        self, alert: IntegrationAlert, cluster: list[IntegrationAlert]
    ) -> float:
        """Score an alert's potential as the root cause.

        Higher score = more likely to be the root cause.
        """
        score = 0.0

        # Severity weight: higher severity = more likely root cause
        severity_weights = {
            EventSeverity.INFO: 0.1,
            EventSeverity.WARNING: 0.3,
            EventSeverity.CRITICAL: 0.6,
            EventSeverity.EMERGENCY: 0.8,
        }
        score += severity_weights.get(alert.severity, 0.1)

        # Source weight: infrastructure sources more likely to be root cause
        source_weights = {
            "soc": 0.3,
            "auto_scaling": 0.2,
            "container": 0.4,
            "observability": 0.3,
            "security_posture": 0.2,
            "forecasting": 0.1,
        }
        score += source_weights.get(alert.source.value, 0.1)

        # Temporal weight: earlier alerts more likely to be root cause
        timestamps = [a.timestamp for a in cluster]
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        if max_ts > min_ts:
            time_ratio = 1.0 - (alert.timestamp - min_ts) / (max_ts - min_ts)
            score += time_ratio * 0.3

        return score

    def _calculate_confidence(
        self, cluster: list[IntegrationAlert], primary: IntegrationAlert
    ) -> float:
        """Calculate confidence in the correlation result."""
        confidence = 0.0

        # More correlated alerts = higher confidence (up to a point)
        confidence += min(len(cluster) * 0.1, 0.3)

        # Diverse sources = higher confidence
        sources = {a.source.value for a in cluster}
        confidence += min(len(sources) * 0.1, 0.2)

        # Higher primary severity = higher confidence
        severity_confidence = {
            EventSeverity.INFO: 0.1,
            EventSeverity.WARNING: 0.2,
            EventSeverity.CRITICAL: 0.3,
            EventSeverity.EMERGENCY: 0.4,
        }
        confidence += severity_confidence.get(primary.severity, 0.1)

        # Tight time cluster = higher confidence
        timestamps = [a.timestamp for a in cluster]
        time_span = max(timestamps) - min(timestamps)
        if time_span < 60:
            confidence += 0.2
        elif time_span < 300:
            confidence += 0.1

        return min(confidence, 1.0)

    def _generate_root_cause(
        self, primary: IntegrationAlert, cluster: list[IntegrationAlert]
    ) -> str:
        """Generate a human-readable root cause description."""
        parts = [f"Primary: {primary.title}"]
        if primary.description:
            parts.append(f"Details: {primary.description[:200]}")
        if len(cluster) > 1:
            parts.append(f"Correlated with {len(cluster) - 1} other alert(s)")
        return " | ".join(parts)

    def _generate_recommendation(
        self, primary: IntegrationAlert, cluster: list[IntegrationAlert]
    ) -> str:
        """Generate a recommended action based on the primary alert."""
        source = primary.source.value
        severity = primary.severity.value

        recommendations = {
            ("container", "critical"): "Investigate container platform health; check node status and pod scheduling",
            ("container", "warning"): "Review container resource utilization and scaling policies",
            ("auto_scaling", "critical"): "Review auto-scaling policies and current capacity",
            ("auto_scaling", "warning"): "Monitor scaling trends and adjust thresholds if needed",
            ("soc", "critical"): "Initiate SOC incident response procedure",
            ("soc", "warning"): "Review SOC alerts and investigate potential security events",
            ("observability", "critical"): "Check observability pipeline and alert on-call engineer",
            ("observability", "warning"): "Review monitoring dashboards and alert rules",
            ("security_posture", "critical"): "Initiate security incident response; isolate affected systems",
            ("security_posture", "warning"): "Review security posture and schedule remediation",
            ("forecasting", "warning"): "Review capacity forecasts and adjust provisioning",
        }

        return recommendations.get(
            (source, severity),
            f"Investigate {source} alert: {primary.title}",
        )

    def reset(self) -> None:
        """Clear all alerts and events."""
        self._alerts.clear()
        self._events.clear()


__all__ = ["AlertCorrelator", "DEFAULT_CORRELATION_WINDOW", "MIN_CORRELATION_CONFIDENCE"]
