"""Alerting rules engine: threshold-based and anomaly detection alerts.

Provides a unified alerting framework for Data Center Commander with:
- Threshold-based alerts (static upper/lower bounds, hysteresis)
- Anomaly detection alerts (z-score, IQR, seasonal decomposition)
- Alert lifecycle management (firing, acknowledged, resolved)
- Alert routing and notification channels
- Alert history and deduplication

All calculations are pure-Python with no external dependencies.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence

from ..quality.anomaly import (
    AnomalyReport,
    iqr_detect,
    seasonal_decompose_detect,
    zscore_detect,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertState(str, Enum):
    """Lifecycle state of an alert."""

    INACTIVE = "inactive"
    PENDING = "pending"
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertType(str, Enum):
    """Type of alert rule."""

    THRESHOLD = "threshold"
    ANOMALY_ZSCORE = "anomaly_zscore"
    ANOMALY_IQR = "anomaly_iqr"
    ANOMALY_SEASONAL = "anomaly_seasonal"


class ComparisonOp(str, Enum):
    """Comparison operators for threshold rules."""

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdConfig:
    """Configuration for a threshold-based alert rule.

    Attributes:
        upper_critical: Critical upper bound (value > this triggers critical).
        upper_warning: Warning upper bound (value > this triggers warning).
        lower_warning: Warning lower bound (value < this triggers warning).
        lower_critical: Critical lower bound (value < this triggers critical).
        hysteresis: Hysteresis band to prevent flapping (default 0.0).
        sustained_for: Number of consecutive breaches before firing (default 1).
    """

    upper_critical: float | None = None
    upper_warning: float | None = None
    lower_warning: float | None = None
    lower_critical: float | None = None
    hysteresis: float = 0.0
    sustained_for: int = 1

    def __post_init__(self) -> None:
        if self.hysteresis < 0:
            raise ValueError("hysteresis must be non-negative")
        if self.sustained_for < 1:
            raise ValueError("sustained_for must be at least 1")
        # Validate ordering
        if (
            self.upper_critical is not None
            and self.upper_warning is not None
            and self.upper_critical < self.upper_warning
        ):
            raise ValueError("upper_critical must be >= upper_warning")
        if (
            self.lower_critical is not None
            and self.lower_warning is not None
            and self.lower_critical > self.lower_warning
        ):
            raise ValueError("lower_critical must be <= lower_warning")


@dataclass(frozen=True)
class AnomalyConfig:
    """Configuration for an anomaly detection alert rule.

    Attributes:
        method: Detection method — "zscore", "iqr", or "seasonal".
        threshold: Z-score threshold (for zscore/seasonal) or IQR multiplier.
        window: Rolling window size for zscore (None for global).
        period: Seasonal period for seasonal decomposition.
        min_points: Minimum data points required before evaluating.
        sensitivity: Severity sensitivity — "low", "medium", or "high".
    """

    method: str = "zscore"
    threshold: float = 3.0
    window: int | None = None
    period: int = 24
    min_points: int = 10
    sensitivity: str = "medium"

    def __post_init__(self) -> None:
        if self.method not in ("zscore", "iqr", "seasonal"):
            raise ValueError(f"unknown anomaly method: {self.method!r}")
        if self.threshold <= 0:
            raise ValueError("threshold must be positive")
        if self.window is not None and self.window < 2:
            raise ValueError("window must be at least 2")
        if self.period < 2:
            raise ValueError("period must be at least 2")
        if self.min_points < 1:
            raise ValueError("min_points must be at least 1")
        if self.sensitivity not in ("low", "medium", "high"):
            raise ValueError(f"unknown sensitivity: {self.sensitivity!r}")


@dataclass
class AlertRule:
    """An alerting rule definition.

    Attributes:
        name: Unique rule name.
        description: Human-readable description.
        alert_type: Type of alert (threshold or anomaly_*).
        severity: Default severity when the rule fires.
        threshold_config: Configuration for threshold rules.
        anomaly_config: Configuration for anomaly rules.
        labels: Optional labels for routing/grouping.
        enabled: Whether the rule is active.
    """

    name: str
    description: str = ""
    alert_type: AlertType = AlertType.THRESHOLD
    severity: AlertSeverity = AlertSeverity.WARNING
    threshold_config: ThresholdConfig | None = None
    anomaly_config: AnomalyConfig | None = None
    labels: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if self.alert_type == AlertType.THRESHOLD and self.threshold_config is None:
            raise ValueError("threshold rules require threshold_config")
        if (
            self.alert_type != AlertType.THRESHOLD
            and self.anomaly_config is None
        ):
            raise ValueError("anomaly rules require anomaly_config")


@dataclass
class AlertEvent:
    """A single alert event (firing or state change).

    Attributes:
        rule_name: Name of the rule that generated this event.
        state: Current alert state.
        severity: Severity at time of event.
        value: The observed value that triggered the event.
        threshold: The threshold that was breached (if applicable).
        message: Human-readable alert message.
        timestamp: Unix timestamp of the event.
        metadata: Additional context (anomaly details, etc.).
    """

    rule_name: str
    state: AlertState
    severity: AlertSeverity
    value: float | None = None
    threshold: float | None = None
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "state": self.state.value,
            "severity": self.severity.value,
            "value": round(self.value, 6) if self.value is not None else None,
            "threshold": round(self.threshold, 6) if self.threshold is not None else None,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Alert:
    """An active or recently-resolved alert instance.

    Attributes:
        rule_name: Name of the rule that generated this alert.
        state: Current lifecycle state.
        severity: Current severity.
        first_fired_at: Unix timestamp when the alert first fired.
        last_fired_at: Unix timestamp of the most recent firing.
        last_value: Most recent observed value.
        last_threshold: Most recent breached threshold.
        fire_count: Number of times this alert has fired.
        acknowledged_at: Unix timestamp when acknowledged (None if not).
        acknowledged_by: Who acknowledged the alert.
        resolved_at: Unix timestamp when resolved (None if not).
        message: Human-readable alert message.
        metadata: Additional context.
    """

    rule_name: str
    state: AlertState = AlertState.INACTIVE
    severity: AlertSeverity = AlertSeverity.WARNING
    first_fired_at: float | None = None
    last_fired_at: float | None = None
    last_value: float | None = None
    last_threshold: float | None = None
    fire_count: int = 0
    acknowledged_at: float | None = None
    acknowledged_by: str | None = None
    resolved_at: float | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "state": self.state.value,
            "severity": self.severity.value,
            "first_fired_at": self.first_fired_at,
            "last_fired_at": self.last_fired_at,
            "last_value": round(self.last_value, 6)
            if self.last_value is not None
            else None,
            "last_threshold": round(self.last_threshold, 6)
            if self.last_threshold is not None
            else None,
            "fire_count": self.fire_count,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass
class AlertReport:
    """Aggregated report of all alert activity.

    Attributes:
        generated_at: ISO timestamp of report generation.
        alerts: List of all alert instances.
        events: List of all alert events.
    """

    generated_at: str
    alerts: list[Alert] = field(default_factory=list)
    events: list[AlertEvent] = field(default_factory=list)

    @property
    def firing_count(self) -> int:
        return sum(1 for a in self.alerts if a.state == AlertState.FIRING)

    @property
    def pending_count(self) -> int:
        return sum(1 for a in self.alerts if a.state == AlertState.PENDING)

    @property
    def acknowledged_count(self) -> int:
        return sum(1 for a in self.alerts if a.state == AlertState.ACKNOWLEDGED)

    @property
    def resolved_count(self) -> int:
        return sum(1 for a in self.alerts if a.state == AlertState.RESOLVED)

    @property
    def firing_alerts(self) -> list[Alert]:
        return [a for a in self.alerts if a.state == AlertState.FIRING]

    @property
    def critical_alerts(self) -> list[Alert]:
        return [
            a
            for a in self.alerts
            if a.state == AlertState.FIRING
            and a.severity in (AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "summary": {
                "total": len(self.alerts),
                "firing": self.firing_count,
                "pending": self.pending_count,
                "acknowledged": self.acknowledged_count,
                "resolved": self.resolved_count,
            },
            "alerts": [a.to_dict() for a in self.alerts],
            "events": [e.to_dict() for e in self.events],
        }


# ---------------------------------------------------------------------------
# Threshold evaluation
# ---------------------------------------------------------------------------


def _compare(value: float, op: ComparisonOp, threshold: float) -> bool:
    """Compare a value against a threshold using the given operator."""
    if op == ComparisonOp.GT:
        return value > threshold
    if op == ComparisonOp.GTE:
        return value >= threshold
    if op == ComparisonOp.LT:
        return value < threshold
    if op == ComparisonOp.LTE:
        return value <= threshold
    if op == ComparisonOp.EQ:
        return value == threshold
    if op == ComparisonOp.NEQ:
        return value != threshold
    raise ValueError(f"unknown comparison operator: {op!r}")


def evaluate_threshold(
    value: float,
    config: ThresholdConfig,
) -> tuple[AlertSeverity | None, float | None]:
    """Evaluate a value against threshold configuration.

    Args:
        value: The observed value.
        config: Threshold configuration.

    Returns:
        Tuple of (severity, threshold) where severity is None if no
        threshold was breached, and threshold is the breached bound.
    """
    # Check critical upper bound
    if config.upper_critical is not None and value > config.upper_critical:
        return AlertSeverity.CRITICAL, config.upper_critical

    # Check critical lower bound
    if config.lower_critical is not None and value < config.lower_critical:
        return AlertSeverity.CRITICAL, config.lower_critical

    # Check warning upper bound
    if config.upper_warning is not None and value > config.upper_warning:
        return AlertSeverity.WARNING, config.upper_warning

    # Check warning lower bound
    if config.lower_warning is not None and value < config.lower_warning:
        return AlertSeverity.WARNING, config.lower_warning

    return None, None


def evaluate_threshold_with_hysteresis(
    value: float,
    config: ThresholdConfig,
    *,
    was_firing: bool = False,
) -> tuple[AlertSeverity | None, float | None]:
    """Evaluate a value with hysteresis to prevent flapping.

    When was_firing is True, the value must drop below the threshold
    minus the hysteresis band (for upper bounds) or rise above the
    threshold plus the hysteresis band (for lower bounds) to clear.

    Args:
        value: The observed value.
        config: Threshold configuration.
        was_firing: Whether the alert was previously firing.

    Returns:
        Tuple of (severity, threshold).
    """
    if not was_firing:
        return evaluate_threshold(value, config)

    # If was firing, check if we've recovered with hysteresis
    severity, threshold = evaluate_threshold(value, config)
    if severity is not None:
        return severity, threshold

    # Check if we're within the hysteresis band of any threshold
    if config.upper_critical is not None:
        if value > config.upper_critical - config.hysteresis:
            return AlertSeverity.CRITICAL, config.upper_critical
    if config.upper_warning is not None:
        if value > config.upper_warning - config.hysteresis:
            return AlertSeverity.WARNING, config.upper_warning
    if config.lower_critical is not None:
        if value < config.lower_critical + config.hysteresis:
            return AlertSeverity.CRITICAL, config.lower_critical
    if config.lower_warning is not None:
        if value < config.lower_warning + config.hysteresis:
            return AlertSeverity.WARNING, config.lower_warning

    return None, None


# ---------------------------------------------------------------------------
# Anomaly evaluation
# ---------------------------------------------------------------------------


def _sensitivity_multiplier(sensitivity: str) -> float:
    """Get the severity classification multiplier for a sensitivity level."""
    return {"low": 1.5, "medium": 1.0, "high": 0.5}[sensitivity]


def _classify_anomaly_severity(
    deviation: float,
    threshold: float,
    sensitivity: str,
) -> AlertSeverity:
    """Classify anomaly severity based on deviation relative to threshold."""
    mult = _sensitivity_multiplier(sensitivity)
    ratio = deviation / threshold if threshold > 0 else 0.0
    if ratio >= 3.0 * mult:
        return AlertSeverity.EMERGENCY
    if ratio >= 2.0 * mult:
        return AlertSeverity.CRITICAL
    if ratio >= 1.0 * mult:
        return AlertSeverity.WARNING
    return AlertSeverity.INFO


def evaluate_anomaly(
    values: Sequence[float],
    config: AnomalyConfig,
    timestamps: Sequence[float] | None = None,
) -> list[AlertEvent]:
    """Evaluate a time series for anomalies and generate alert events.

    Args:
        values: Numeric time-series values.
        config: Anomaly detection configuration.
        timestamps: Optional timestamps corresponding to values.

    Returns:
        List of AlertEvent objects for detected anomalies.
    """
    if len(values) < config.min_points:
        return []

    events: list[AlertEvent] = []

    if config.method == "zscore":
        report = zscore_detect(
            values,
            timestamps,
            threshold=config.threshold,
            window=config.window,
        )
    elif config.method == "iqr":
        report = iqr_detect(values, timestamps, k=config.threshold)
    elif config.method == "seasonal":
        report = seasonal_decompose_detect(
            values,
            timestamps,
            period=config.period,
            threshold=config.threshold,
        )
    else:
        raise ValueError(f"unknown anomaly method: {config.method!r}")

    for anomaly in report.anomalies:
        severity = _classify_anomaly_severity(
            abs(anomaly.deviation),
            config.threshold,
            config.sensitivity,
        )
        events.append(
            AlertEvent(
                rule_name="",
                state=AlertState.FIRING,
                severity=severity,
                value=anomaly.value,
                threshold=anomaly.expected,
                message=(
                    f"Anomaly detected at index {anomaly.index}: "
                    f"value={anomaly.value:.4f}, expected={anomaly.expected:.4f}, "
                    f"deviation={anomaly.deviation:.4f} ({anomaly.method})"
                ),
                timestamp=anomaly.timestamp or time.time(),
                metadata={
                    "index": anomaly.index,
                    "method": anomaly.method,
                    "deviation": round(anomaly.deviation, 6),
                    "expected": round(anomaly.expected, 6),
                    "anomaly_severity": anomaly.severity,
                },
            )
        )

    return events


# ---------------------------------------------------------------------------
# Alert engine
# ---------------------------------------------------------------------------


class AlertEngine:
    """Main alerting engine that manages rules, evaluates metrics, and tracks alert state.

    Usage:
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            name="cpu_high",
            description="CPU usage above 90%",
            alert_type=AlertType.THRESHOLD,
            severity=AlertSeverity.CRITICAL,
            threshold_config=ThresholdConfig(upper_critical=90.0),
        ))
        engine.submit("cpu_high", 95.0)
        report = engine.report()
    """

    def __init__(self) -> None:
        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[str, Alert] = {}
        self._events: list[AlertEvent] = []
        self._consecutive_breaches: dict[str, int] = {}
        self._last_values: dict[str, list[float]] = {}

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule to the engine."""
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> None:
        """Remove an alert rule."""
        self._rules.pop(name, None)
        self._alerts.pop(name, None)
        self._consecutive_breaches.pop(name, None)
        self._last_values.pop(name, None)

    def get_rule(self, name: str) -> AlertRule | None:
        """Get a rule by name."""
        return self._rules.get(name)

    def list_rules(self) -> list[AlertRule]:
        """List all registered rules."""
        return list(self._rules.values())

    def submit(self, rule_name: str, value: float) -> AlertEvent | None:
        """Submit a single metric value for a threshold-based rule.

        Args:
            rule_name: Name of the rule to evaluate.
            value: The observed metric value.

        Returns:
            AlertEvent if the alert state changed, None otherwise.
        """
        rule = self._rules.get(rule_name)
        if rule is None:
            raise KeyError(f"unknown rule: {rule_name!r}")
        if not rule.enabled:
            return None
        if rule.alert_type != AlertType.THRESHOLD:
            raise ValueError(
                f"rule {rule_name!r} is not a threshold rule; use submit_series()"
            )
        assert rule.threshold_config is not None

        config = rule.threshold_config
        alert = self._alerts.get(rule_name)
        was_firing = alert is not None and alert.state in (
            AlertState.FIRING,
            AlertState.ACKNOWLEDGED,
        )

        severity, threshold = evaluate_threshold_with_hysteresis(
            value, config, was_firing=was_firing
        )

        if severity is None:
            # Value is within normal range
            if was_firing:
                # Reset consecutive breaches
                self._consecutive_breaches[rule_name] = 0
                # Resolve the alert
                if alert is not None:
                    alert.state = AlertState.RESOLVED
                    alert.resolved_at = time.time()
                    event = AlertEvent(
                        rule_name=rule_name,
                        state=AlertState.RESOLVED,
                        severity=AlertSeverity.INFO,
                        value=value,
                        message=f"Alert resolved: value {value} is within normal range",
                    )
                    self._events.append(event)
                    return event
            self._consecutive_breaches[rule_name] = 0
            return None

        # Value breaches a threshold
        self._consecutive_breaches[rule_name] = (
            self._consecutive_breaches.get(rule_name, 0) + 1
        )

        # Check sustained_for
        if self._consecutive_breaches[rule_name] < config.sustained_for:
            if alert is None:
                alert = Alert(rule_name=rule_name, state=AlertState.PENDING)
                self._alerts[rule_name] = alert
            elif alert.state == AlertState.RESOLVED:
                alert.state = AlertState.PENDING
                alert.first_fired_at = None
                alert.fire_count = 0
                alert.resolved_at = None
            return None

        # Alert should fire
        now = time.time()
        if alert is None:
            alert = Alert(rule_name=rule_name)
            self._alerts[rule_name] = alert

        if alert.state in (AlertState.INACTIVE, AlertState.RESOLVED):
            alert.first_fired_at = now
            alert.fire_count = 0

        alert.state = AlertState.FIRING
        alert.severity = severity
        alert.last_fired_at = now
        alert.last_value = value
        alert.last_threshold = threshold
        alert.fire_count += 1
        alert.message = (
            f"Threshold breached: value {value} exceeds {severity.value} "
            f"threshold {threshold}"
        )

        event = AlertEvent(
            rule_name=rule_name,
            state=AlertState.FIRING,
            severity=severity,
            value=value,
            threshold=threshold,
            message=alert.message,
        )
        self._events.append(event)
        return event

    def submit_series(
        self,
        rule_name: str,
        values: Sequence[float],
        timestamps: Sequence[float] | None = None,
    ) -> list[AlertEvent]:
        """Submit a time series for an anomaly detection rule.

        Args:
            rule_name: Name of the rule to evaluate.
            values: Numeric time-series values.
            timestamps: Optional timestamps corresponding to values.

        Returns:
            List of AlertEvent objects for detected anomalies.
        """
        rule = self._rules.get(rule_name)
        if rule is None:
            raise KeyError(f"unknown rule: {rule_name!r}")
        if not rule.enabled:
            return []
        if rule.alert_type == AlertType.THRESHOLD:
            raise ValueError(
                f"rule {rule_name!r} is a threshold rule; use submit()"
            )
        assert rule.anomaly_config is not None

        # Store values for context
        self._last_values[rule_name] = list(values)

        events = evaluate_anomaly(values, rule.anomaly_config, timestamps)

        # Update alert state
        if events:
            now = time.time()
            alert = self._alerts.get(rule_name)
            if alert is None:
                alert = Alert(rule_name=rule_name)
                self._alerts[rule_name] = alert

            if alert.state in (AlertState.INACTIVE, AlertState.RESOLVED):
                alert.first_fired_at = now
                alert.fire_count = 0

            alert.state = AlertState.FIRING
            # Use the highest severity from events
            severity_order = {
                AlertSeverity.INFO: 0,
                AlertSeverity.WARNING: 1,
                AlertSeverity.CRITICAL: 2,
                AlertSeverity.EMERGENCY: 3,
            }
            alert.severity = max(
                (e.severity for e in events),
                key=lambda s: severity_order[s],
            )
            alert.last_fired_at = now
            alert.last_value = events[0].value
            alert.last_threshold = events[0].threshold
            alert.fire_count += 1
            alert.message = (
                f"Anomaly detected: {len(events)} anomalous points found"
            )
            alert.metadata = {
                "anomaly_count": len(events),
                "method": rule.anomaly_config.method,
            }

            # Set rule_name on events
            for e in events:
                e.rule_name = rule_name

            self._events.extend(events)
        else:
            # No anomalies — resolve if firing
            alert = self._alerts.get(rule_name)
            if alert is not None and alert.state in (
                AlertState.FIRING,
                AlertState.ACKNOWLEDGED,
            ):
                alert.state = AlertState.RESOLVED
                alert.resolved_at = time.time()
                self._events.append(
                    AlertEvent(
                        rule_name=rule_name,
                        state=AlertState.RESOLVED,
                        severity=AlertSeverity.INFO,
                        message="No anomalies detected — alert resolved",
                    )
                )

        return events

    def acknowledge(
        self,
        rule_name: str,
        acknowledged_by: str = "",
    ) -> AlertEvent | None:
        """Acknowledge a firing alert.

        Args:
            rule_name: Name of the rule to acknowledge.
            acknowledged_by: Who is acknowledging the alert.

        Returns:
            AlertEvent for the acknowledgment, None if not firing.
        """
        alert = self._alerts.get(rule_name)
        if alert is None or alert.state != AlertState.FIRING:
            return None

        alert.state = AlertState.ACKNOWLEDGED
        alert.acknowledged_at = time.time()
        alert.acknowledged_by = acknowledged_by

        event = AlertEvent(
            rule_name=rule_name,
            state=AlertState.ACKNOWLEDGED,
            severity=alert.severity,
            value=alert.last_value,
            threshold=alert.last_threshold,
            message=f"Alert acknowledged by {acknowledged_by}",
        )
        self._events.append(event)
        return event

    def resolve(self, rule_name: str) -> AlertEvent | None:
        """Manually resolve an alert.

        Args:
            rule_name: Name of the rule to resolve.

        Returns:
            AlertEvent for the resolution, None if not active.
        """
        alert = self._alerts.get(rule_name)
        if alert is None or alert.state not in (
            AlertState.FIRING,
            AlertState.ACKNOWLEDGED,
            AlertState.PENDING,
        ):
            return None

        alert.state = AlertState.RESOLVED
        alert.resolved_at = time.time()

        event = AlertEvent(
            rule_name=rule_name,
            state=AlertState.RESOLVED,
            severity=AlertSeverity.INFO,
            value=alert.last_value,
            threshold=alert.last_threshold,
            message="Alert manually resolved",
        )
        self._events.append(event)
        return event

    def get_alert(self, rule_name: str) -> Alert | None:
        """Get the current alert for a rule."""
        return self._alerts.get(rule_name)

    def list_alerts(
        self,
        *,
        state: AlertState | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """List alerts, optionally filtered by state and/or severity."""
        alerts = list(self._alerts.values())
        if state is not None:
            alerts = [a for a in alerts if a.state == state]
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts

    def list_events(
        self,
        *,
        rule_name: str | None = None,
        state: AlertState | None = None,
        limit: int | None = None,
    ) -> list[AlertEvent]:
        """List alert events, optionally filtered."""
        events = list(self._events)
        if rule_name is not None:
            events = [e for e in events if e.rule_name == rule_name]
        if state is not None:
            events = [e for e in events if e.state == state]
        if limit is not None:
            events = events[-limit:]
        return events

    def report(self) -> AlertReport:
        """Generate a complete alert report."""
        return AlertReport(
            generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            alerts=list(self._alerts.values()),
            events=list(self._events),
        )

    def reset(self) -> None:
        """Reset all alert state (useful for testing)."""
        self._alerts.clear()
        self._events.clear()
        self._consecutive_breaches.clear()
        self._last_values.clear()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_threshold_rule(
    name: str,
    *,
    description: str = "",
    upper_critical: float | None = None,
    upper_warning: float | None = None,
    lower_warning: float | None = None,
    lower_critical: float | None = None,
    hysteresis: float = 0.0,
    sustained_for: int = 1,
    severity: AlertSeverity = AlertSeverity.WARNING,
    labels: dict[str, str] | None = None,
) -> AlertRule:
    """Convenience factory for a threshold-based alert rule."""
    return AlertRule(
        name=name,
        description=description,
        alert_type=AlertType.THRESHOLD,
        severity=severity,
        threshold_config=ThresholdConfig(
            upper_critical=upper_critical,
            upper_warning=upper_warning,
            lower_warning=lower_warning,
            lower_critical=lower_critical,
            hysteresis=hysteresis,
            sustained_for=sustained_for,
        ),
        labels=labels or {},
    )


def create_anomaly_rule(
    name: str,
    *,
    description: str = "",
    method: str = "zscore",
    threshold: float = 3.0,
    window: int | None = None,
    period: int = 24,
    min_points: int = 10,
    sensitivity: str = "medium",
    severity: AlertSeverity = AlertSeverity.WARNING,
    labels: dict[str, str] | None = None,
) -> AlertRule:
    """Convenience factory for an anomaly detection alert rule."""
    return AlertRule(
        name=name,
        description=description,
        alert_type=AlertType(f"anomaly_{method}"),
        severity=severity,
        anomaly_config=AnomalyConfig(
            method=method,
            threshold=threshold,
            window=window,
            period=period,
            min_points=min_points,
            sensitivity=sensitivity,
        ),
        labels=labels or {},
    )


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "AlertSeverity",
    "AlertState",
    "AlertType",
    "ComparisonOp",
    "ThresholdConfig",
    "AnomalyConfig",
    "AlertRule",
    "AlertEvent",
    "Alert",
    "AlertReport",
    "AlertEngine",
    "evaluate_threshold",
    "evaluate_threshold_with_hysteresis",
    "evaluate_anomaly",
    "create_threshold_rule",
    "create_anomaly_rule",
]
