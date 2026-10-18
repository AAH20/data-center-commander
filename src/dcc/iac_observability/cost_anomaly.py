"""IaC cost anomaly detection: detect unexpected cost changes.

Monitors infrastructure costs over time and detects anomalies using
statistical methods (z-score, IQR, moving average). Supports budget
variance detection and cost spike alerts.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class CostAnomalyType(str, Enum):
    """Types of cost anomalies."""

    SPIKE = "spike"                    # Sudden cost increase
    DROP = "drop"                      # Sudden cost decrease
    BUDGET_EXCEEDED = "budget_exceeded"  # Cost exceeds budget
    BUDGET_VARIANCE = "budget_variance"  # Cost significantly different from budget
    TREND_INCREASE = "trend_increase"  # Sustained upward trend
    TREND_DECREASE = "trend_decrease"  # Sustained downward trend
    SEASONAL_ANOMALY = "seasonal_anomaly"  # Deviation from seasonal pattern
    IDLE_RESOURCE = "idle_resource"    # Resource with cost but no utilization
    ORPHANED_RESOURCE = "orphaned_resource"  # Resource no longer needed


class CostAnomalySeverity(str, Enum):
    """Severity levels for cost anomalies."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class CostAnomaly:
    """A single cost anomaly finding."""

    anomaly_type: CostAnomalyType
    severity: CostAnomalySeverity
    resource_id: str
    resource_name: str
    resource_type: str
    description: str
    expected_cost: float | None = None
    actual_cost: float | None = None
    deviation_pct: float | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "description": self.description,
            "expected_cost": self.expected_cost,
            "actual_cost": self.actual_cost,
            "deviation_pct": round(self.deviation_pct, 4) if self.deviation_pct is not None else None,
            "detected_at": self.detected_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CostAnomalyReport:
    """Aggregate cost anomaly report."""

    total_anomalies: int = 0
    anomalies: list[CostAnomaly] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    type_counts: dict[str, int] = field(default_factory=dict)
    total_expected_cost: float = 0.0
    total_actual_cost: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_anomalies(self) -> bool:
        return self.total_anomalies > 0

    @property
    def total_variance(self) -> float:
        return self.total_actual_cost - self.total_expected_cost

    @property
    def variance_pct(self) -> float:
        if self.total_expected_cost == 0:
            return 0.0
        return (self.total_variance / self.total_expected_cost) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_anomalies": self.total_anomalies,
            "has_anomalies": self.has_anomalies,
            "severity_counts": self.severity_counts,
            "type_counts": self.type_counts,
            "total_expected_cost": round(self.total_expected_cost, 2),
            "total_actual_cost": round(self.total_actual_cost, 2),
            "total_variance": round(self.total_variance, 2),
            "variance_pct": round(self.variance_pct, 2),
            "generated_at": self.generated_at.isoformat(),
            "anomalies": [a.to_dict() for a in self.anomalies],
        }


class CostAnomalyDetector:
    """Detects cost anomalies in infrastructure spending.

    Uses statistical methods to identify unexpected cost changes,
    budget variances, and spending trends.
    """

    def __init__(
        self,
        zscore_threshold: float = 2.5,
        iqr_multiplier: float = 1.5,
        budget_variance_threshold: float = 0.10,  # 10%
        spike_threshold: float = 0.25,  # 25% increase
        trend_window: int = 7,
    ) -> None:
        self.zscore_threshold = zscore_threshold
        self.iqr_multiplier = iqr_multiplier
        self.budget_variance_threshold = budget_variance_threshold
        self.spike_threshold = spike_threshold
        self.trend_window = trend_window

    def detect(
        self,
        cost_data: Sequence[Mapping[str, Any]],
        budget_data: Mapping[str, float] | None = None,
    ) -> CostAnomalyReport:
        """Detect cost anomalies from time-series cost data.

        Args:
            cost_data: List of cost records with keys:
                - resource_id, resource_name, resource_type
                - timestamp, cost, expected_cost (optional)
            budget_data: Optional mapping of resource_id -> budget amount.

        Returns:
            CostAnomalyReport with all detected anomalies.
        """
        anomalies: list[CostAnomaly] = []
        severity_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        total_expected = 0.0
        total_actual = 0.0

        # Group by resource
        by_resource: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in cost_data:
            rid = record.get("resource_id", "unknown")
            by_resource[rid].append(record)

        for rid, records in by_resource.items():
            # Sort by timestamp
            records.sort(key=lambda r: r.get("timestamp", ""))

            costs = [float(r.get("cost", 0)) for r in records]
            expected_costs = [float(r.get("expected_cost", r.get("cost", 0))) for r in records]

            total_expected += sum(expected_costs)
            total_actual += sum(costs)

            # Detect spikes and drops
            spike_anomalies = self._detect_spikes(rid, records, costs)
            anomalies.extend(spike_anomalies)

            # Detect budget variance
            if budget_data and rid in budget_data:
                budget = budget_data[rid]
                actual = sum(costs)
                variance = (actual - budget) / budget if budget > 0 else 0
                if abs(variance) > self.budget_variance_threshold:
                    severity = self._variance_severity(variance)
                    anomalies.append(CostAnomaly(
                        anomaly_type=CostAnomalyType.BUDGET_VARIANCE,
                        severity=severity,
                        resource_id=rid,
                        resource_name=records[0].get("resource_name", rid),
                        resource_type=records[0].get("resource_type", "unknown"),
                        description=f"Budget variance: {variance*100:.1f}% ({'over' if variance > 0 else 'under'} budget)",
                        expected_cost=budget,
                        actual_cost=actual,
                        deviation_pct=variance * 100,
                    ))

            # Detect trends
            trend_anomalies = self._detect_trends(rid, records, costs)
            anomalies.extend(trend_anomalies)

            # Detect idle resources
            idle_anomalies = self._detect_idle_resources(rid, records, costs)
            anomalies.extend(idle_anomalies)

        # Count severities and types
        for a in anomalies:
            severity_counts[a.severity.value] += 1
            type_counts[a.anomaly_type.value] += 1

        return CostAnomalyReport(
            total_anomalies=len(anomalies),
            anomalies=anomalies,
            severity_counts=dict(severity_counts),
            type_counts=dict(type_counts),
            total_expected_cost=total_expected,
            total_actual_cost=total_actual,
        )

    def _detect_spikes(
        self,
        resource_id: str,
        records: list[Mapping[str, Any]],
        costs: list[float],
    ) -> list[CostAnomaly]:
        """Detect cost spikes and drops."""
        anomalies: list[CostAnomaly] = []
        if len(costs) < 2:
            return anomalies

        mean = statistics.fmean(costs)
        std = statistics.stdev(costs) if len(costs) > 1 else 0

        for i, cost in enumerate(costs):
            if std > 0:
                zscore = (cost - mean) / std
                if abs(zscore) > self.zscore_threshold:
                    is_spike = zscore > 0
                    anomaly_type = CostAnomalyType.SPIKE if is_spike else CostAnomalyType.DROP
                    severity = self._zscore_severity(abs(zscore))
                    anomalies.append(CostAnomaly(
                        anomaly_type=anomaly_type,
                        severity=severity,
                        resource_id=resource_id,
                        resource_name=records[i].get("resource_name", resource_id),
                        resource_type=records[i].get("resource_type", "unknown"),
                        description=f"Cost {'spike' if is_spike else 'drop'}: ${cost:.2f} (z-score: {zscore:.2f})",
                        expected_cost=mean,
                        actual_cost=cost,
                        deviation_pct=((cost - mean) / mean * 100) if mean > 0 else 0,
                        metadata={"zscore": round(zscore, 4), "index": i},
                    ))

        return anomalies

    def _detect_trends(
        self,
        resource_id: str,
        records: list[Mapping[str, Any]],
        costs: list[float],
    ) -> list[CostAnomaly]:
        """Detect sustained cost trends."""
        anomalies: list[CostAnomaly] = []
        if len(costs) < self.trend_window * 2:
            return anomalies

        # Compare first half vs second half
        mid = len(costs) // 2
        first_half = costs[:mid]
        second_half = costs[mid:]

        first_mean = statistics.fmean(first_half)
        second_mean = statistics.fmean(second_half)

        if first_mean > 0:
            change_pct = (second_mean - first_mean) / first_mean
            if abs(change_pct) > self.spike_threshold:
                is_increase = change_pct > 0
                anomaly_type = CostAnomalyType.TREND_INCREASE if is_increase else CostAnomalyType.TREND_DECREASE
                severity = self._trend_severity(abs(change_pct))
                anomalies.append(CostAnomaly(
                    anomaly_type=anomaly_type,
                    severity=severity,
                    resource_id=resource_id,
                    resource_name=records[0].get("resource_name", resource_id),
                    resource_type=records[0].get("resource_type", "unknown"),
                    description=f"Cost {'increasing' if is_increase else 'decreasing'} trend: {change_pct*100:.1f}% change",
                    expected_cost=first_mean,
                    actual_cost=second_mean,
                    deviation_pct=change_pct * 100,
                ))

        return anomalies

    def _detect_idle_resources(
        self,
        resource_id: str,
        records: list[Mapping[str, Any]],
        costs: list[float],
    ) -> list[CostAnomaly]:
        """Detect resources with cost but no utilization."""
        anomalies: list[CostAnomaly] = []
        for i, record in enumerate(records):
            utilization = record.get("utilization", record.get("cpu_utilization"))
            cost = costs[i]
            if utilization is not None and cost > 0:
                util_float = float(utilization)
                if util_float < 0.05:  # Less than 5% utilization
                    anomalies.append(CostAnomaly(
                        anomaly_type=CostAnomalyType.IDLE_RESOURCE,
                        severity=CostAnomalySeverity.MEDIUM,
                        resource_id=resource_id,
                        resource_name=record.get("resource_name", resource_id),
                        resource_type=record.get("resource_type", "unknown"),
                        description=f"Resource has low utilization ({util_float*100:.1f}%) but costs ${cost:.2f}",
                        actual_cost=cost,
                        metadata={"utilization": util_float},
                    ))

        return anomalies

    def _zscore_severity(self, zscore: float) -> CostAnomalySeverity:
        if zscore > 4.0:
            return CostAnomalySeverity.CRITICAL
        if zscore > 3.0:
            return CostAnomalySeverity.HIGH
        if zscore > 2.5:
            return CostAnomalySeverity.MEDIUM
        return CostAnomalySeverity.LOW

    def _variance_severity(self, variance: float) -> CostAnomalySeverity:
        abs_var = abs(variance)
        if abs_var > 0.50:
            return CostAnomalySeverity.CRITICAL
        if abs_var > 0.25:
            return CostAnomalySeverity.HIGH
        if abs_var > 0.10:
            return CostAnomalySeverity.MEDIUM
        return CostAnomalySeverity.LOW

    def _trend_severity(self, change_pct: float) -> CostAnomalySeverity:
        if change_pct > 0.50:
            return CostAnomalySeverity.CRITICAL
        if change_pct > 0.25:
            return CostAnomalySeverity.HIGH
        if change_pct > 0.10:
            return CostAnomalySeverity.MEDIUM
        return CostAnomalySeverity.LOW


def detect_cost_anomalies(
    cost_data: Sequence[Mapping[str, Any]],
    budget_data: Mapping[str, float] | None = None,
    **kwargs: Any,
) -> CostAnomalyReport:
    """Convenience function to detect cost anomalies."""
    detector = CostAnomalyDetector(**kwargs)
    return detector.detect(cost_data, budget_data)


def build_cost_dashboard(report: CostAnomalyReport) -> dict[str, Any]:
    """Build dashboard-ready cost anomaly data."""
    return {
        "total_anomalies": report.total_anomalies,
        "has_anomalies": report.has_anomalies,
        "total_expected_cost": round(report.total_expected_cost, 2),
        "total_actual_cost": round(report.total_actual_cost, 2),
        "total_variance": round(report.total_variance, 2),
        "variance_pct": round(report.variance_pct, 2),
        "severity_counts": report.severity_counts,
        "type_counts": report.type_counts,
        "top_anomalies": [
            {
                "anomaly_type": a.anomaly_type.value,
                "severity": a.severity.value,
                "resource_id": a.resource_id,
                "resource_name": a.resource_name,
                "description": a.description,
                "deviation_pct": round(a.deviation_pct, 2) if a.deviation_pct is not None else None,
            }
            for a in sorted(
                report.anomalies,
                key=lambda x: (
                    0 if x.severity == CostAnomalySeverity.CRITICAL else
                    1 if x.severity == CostAnomalySeverity.HIGH else
                    2 if x.severity == CostAnomalySeverity.MEDIUM else 3
                ),
            )[:20]
        ],
    }
