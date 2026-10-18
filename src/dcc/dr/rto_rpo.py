"""RTO/RPO tracking for Data Center Commander.

Provides Recovery Time Objective (RTO) and Recovery Point Objective (RPO)
tracking, measurement, and reporting. Tracks actual vs target metrics,
calculates compliance, and produces audit-ready reports.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import json
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RTOTrackingError(Exception):
    """Base exception for RTO/RPO tracking failures."""

    def __init__(self, message: str, code: str = "rto_tracking_error") -> None:
        self.code = code
        super().__init__(message)


class MetricNotFoundError(RTOTrackingError):
    """Raised when a metric cannot be found."""

    def __init__(self, metric_id: str) -> None:
        super().__init__(f"metric {metric_id!r} not found", "metric_not_found")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MetricType(str, Enum):
    """Type of metric."""

    RTO = "rto"
    RPO = "rpo"
    RTO_VARIANCE = "rto_variance"
    RPO_VARIANCE = "rpo_variance"


class MetricStatus(str, Enum):
    """Compliance status of a metric."""

    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACH = "breach"
    UNKNOWN = "unknown"


class MeasurementSource(str, Enum):
    """Source of the measurement."""

    ACTUAL = "actual"
    TEST = "test"
    SIMULATED = "simulated"
    PROJECTED = "projected"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RTOTarget:
    """RTO/RPO target configuration.

    Attributes:
        rto_target_seconds: Target recovery time in seconds.
        rpo_target_seconds: Target recovery point in seconds.
        warning_threshold_pct: Percentage of target that triggers warning.
        breach_threshold_pct: Percentage of target that triggers breach.
    """

    rto_target_seconds: float = 3600.0  # 1 hour default
    rpo_target_seconds: float = 300.0   # 5 minutes default
    warning_threshold_pct: float = 80.0
    breach_threshold_pct: float = 100.0

    def __post_init__(self) -> None:
        if self.rto_target_seconds <= 0:
            raise RTOTrackingError("rto_target_seconds must be positive")
        if self.rpo_target_seconds <= 0:
            raise RTOTrackingError("rpo_target_seconds must be positive")
        if not (0 < self.warning_threshold_pct <= self.breach_threshold_pct):
            raise RTOTrackingError("thresholds must satisfy 0 < warning <= breach")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rto_target_seconds": self.rto_target_seconds,
            "rpo_target_seconds": self.rpo_target_seconds,
            "warning_threshold_pct": self.warning_threshold_pct,
            "breach_threshold_pct": self.breach_threshold_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RTOTarget:
        return cls(
            rto_target_seconds=float(data.get("rto_target_seconds", 3600.0)),
            rpo_target_seconds=float(data.get("rpo_target_seconds", 300.0)),
            warning_threshold_pct=float(data.get("warning_threshold_pct", 80.0)),
            breach_threshold_pct=float(data.get("breach_threshold_pct", 100.0)),
        )


@dataclass(frozen=True)
class MetricMeasurement:
    """A single RTO/RPO measurement.

    Attributes:
        measurement_id: Unique identifier.
        tenant_id: Tenant this measurement belongs to.
        metric_type: Type of metric (RTO or RPO).
        value_seconds: Measured value in seconds.
        target_seconds: Target value in seconds.
        status: Compliance status.
        source: Source of the measurement.
        timestamp: When the measurement was taken.
        metadata: Additional context.
    """

    measurement_id: str
    tenant_id: str
    metric_type: MetricType
    value_seconds: float
    target_seconds: float
    status: MetricStatus
    source: MeasurementSource
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.value_seconds < 0:
            raise RTOTrackingError("value_seconds must be non-negative")

    @property
    def variance_seconds(self) -> float:
        """Variance from target (positive = worse than target)."""
        return self.value_seconds - self.target_seconds

    @property
    def variance_pct(self) -> float:
        """Variance as percentage of target."""
        if self.target_seconds == 0:
            return 0.0
        return (self.value_seconds / self.target_seconds) * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "tenant_id": self.tenant_id,
            "metric_type": self.metric_type.value,
            "value_seconds": self.value_seconds,
            "target_seconds": self.target_seconds,
            "status": self.status.value,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricMeasurement:
        return cls(
            measurement_id=data["measurement_id"],
            tenant_id=data["tenant_id"],
            metric_type=MetricType(data.get("metric_type", "rto")),
            value_seconds=float(data.get("value_seconds", 0.0)),
            target_seconds=float(data.get("target_seconds", 0.0)),
            status=MetricStatus(data.get("status", "unknown")),
            source=MeasurementSource(data.get("source", "actual")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ComplianceReport:
    """RTO/RPO compliance report for a tenant."""

    tenant_id: str
    generated_at: datetime
    rto_target: RTOTarget
    rpo_target: RTOTarget
    rto_measurements: list[MetricMeasurement] = field(default_factory=list)
    rpo_measurements: list[MetricMeasurement] = field(default_factory=list)
    rto_compliant_count: int = 0
    rto_warning_count: int = 0
    rto_breach_count: int = 0
    rpo_compliant_count: int = 0
    rpo_warning_count: int = 0
    rpo_breach_count: int = 0
    rto_avg_seconds: float = 0.0
    rto_p95_seconds: float = 0.0
    rpo_avg_seconds: float = 0.0
    rpo_p95_seconds: float = 0.0
    overall_status: MetricStatus = MetricStatus.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "generated_at": self.generated_at.isoformat(),
            "rto_target": self.rto_target.to_dict(),
            "rpo_target": self.rpo_target.to_dict(),
            "rto_measurements": [m.to_dict() for m in self.rto_measurements],
            "rpo_measurements": [m.to_dict() for m in self.rpo_measurements],
            "rto_compliant_count": self.rto_compliant_count,
            "rto_warning_count": self.rto_warning_count,
            "rto_breach_count": self.rto_breach_count,
            "rpo_compliant_count": self.rpo_compliant_count,
            "rpo_warning_count": self.rpo_warning_count,
            "rpo_breach_count": self.rpo_breach_count,
            "rto_avg_seconds": round(self.rto_avg_seconds, 3),
            "rto_p95_seconds": round(self.rto_p95_seconds, 3),
            "rpo_avg_seconds": round(self.rpo_avg_seconds, 3),
            "rpo_p95_seconds": round(self.rpo_p95_seconds, 3),
            "overall_status": self.overall_status.value,
        }


# ---------------------------------------------------------------------------
# RTO/RPO tracking engine
# ---------------------------------------------------------------------------


class RTOTracker:
    """Tracks RTO/RPO metrics for tenants.

    Stores measurements on the filesystem with a structured layout::

        <tracker_root>/
        ├── <tenant_id>/
        │   ├── _targets.json
        │   ├── measurements.jsonl
        │   └── reports/
        │       └── <report_id>.json
        └── ...

    All operations are synchronous and thread-safe at the filesystem level
    via atomic writes.
    """

    def __init__(self, tracker_root: str | Path) -> None:
        self.tracker_root = Path(tracker_root).resolve()
        self._ensure_root()
        self._lock = threading.RLock()
        self._measurements: dict[str, list[MetricMeasurement]] = {}

    def _ensure_root(self) -> None:
        self.tracker_root.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: str) -> Path:
        return self.tracker_root / tenant_id

    def _targets_path(self, tenant_id: str) -> Path:
        return self._tenant_dir(tenant_id) / "_targets.json"

    def _measurements_path(self, tenant_id: str) -> Path:
        return self._tenant_dir(tenant_id) / "measurements.jsonl"

    def _reports_dir(self, tenant_id: str) -> Path:
        return self._tenant_dir(tenant_id) / "reports"

    def _write_targets(self, tenant_id: str, targets: RTOTarget) -> None:
        path = self._targets_path(tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(targets.to_dict(), indent=2),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_targets(self, tenant_id: str) -> RTOTarget:
        path = self._targets_path(tenant_id)
        if not path.exists():
            return RTOTarget()
        data = json.loads(path.read_text(encoding="utf-8"))
        return RTOTarget.from_dict(data)

    def _append_measurement(self, measurement: MetricMeasurement) -> None:
        path = self._measurements_path(measurement.tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(measurement.to_dict(), default=str) + "\n")

    def _read_measurements(self, tenant_id: str) -> list[MetricMeasurement]:
        path = self._measurements_path(tenant_id)
        if not path.exists():
            return []
        measurements = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    measurements.append(MetricMeasurement.from_dict(data))
                except Exception:
                    continue
        return measurements

    # ------------------------------------------------------------------
    # Target management
    # ------------------------------------------------------------------

    def set_targets(self, tenant_id: str, targets: RTOTarget) -> None:
        """Set RTO/RPO targets for a tenant."""
        self._write_targets(tenant_id, targets)

    def get_targets(self, tenant_id: str) -> RTOTarget:
        """Get RTO/RPO targets for a tenant."""
        return self._read_targets(tenant_id)

    # ------------------------------------------------------------------
    # Measurement recording
    # ------------------------------------------------------------------

    def record_measurement(
        self,
        tenant_id: str,
        metric_type: MetricType,
        value_seconds: float,
        *,
        source: MeasurementSource | str = MeasurementSource.ACTUAL,
        metadata: dict[str, Any] | None = None,
    ) -> MetricMeasurement:
        """Record a new RTO/RPO measurement.

        Args:
            tenant_id: Tenant UUID string.
            metric_type: Type of metric (RTO or RPO).
            value_seconds: Measured value in seconds.
            source: Source of the measurement.
            metadata: Additional context.

        Returns:
            The recorded MetricMeasurement.
        """
        if isinstance(source, str):
            source = MeasurementSource(source)

        targets = self._read_targets(tenant_id)
        target_seconds = (
            targets.rto_target_seconds
            if metric_type == MetricType.RTO
            else targets.rpo_target_seconds
        )

        # Determine status
        pct = (value_seconds / target_seconds * 100.0) if target_seconds > 0 else 0.0
        if pct >= targets.breach_threshold_pct:
            status = MetricStatus.BREACH
        elif pct >= targets.warning_threshold_pct:
            status = MetricStatus.WARNING
        else:
            status = MetricStatus.COMPLIANT

        measurement = MetricMeasurement(
            measurement_id=str(uuid4()),
            tenant_id=tenant_id,
            metric_type=metric_type,
            value_seconds=value_seconds,
            target_seconds=target_seconds,
            status=status,
            source=source,
            metadata=metadata or {},
        )

        with self._lock:
            self._append_measurement(measurement)
            if tenant_id not in self._measurements:
                self._measurements[tenant_id] = []
            self._measurements[tenant_id].append(measurement)

        return measurement

    def record_rto(
        self,
        tenant_id: str,
        value_seconds: float,
        **kwargs: Any,
    ) -> MetricMeasurement:
        """Record an RTO measurement."""
        return self.record_measurement(tenant_id, MetricType.RTO, value_seconds, **kwargs)

    def record_rpo(
        self,
        tenant_id: str,
        value_seconds: float,
        **kwargs: Any,
    ) -> MetricMeasurement:
        """Record an RPO measurement."""
        return self.record_measurement(tenant_id, MetricType.RPO, value_seconds, **kwargs)

    # ------------------------------------------------------------------
    # Measurement queries
    # ------------------------------------------------------------------

    def get_measurements(
        self,
        tenant_id: str,
        *,
        metric_type: MetricType | None = None,
        status: MetricStatus | None = None,
        source: MeasurementSource | None = None,
        limit: int = 100,
    ) -> list[MetricMeasurement]:
        """Get measurements for a tenant, optionally filtered."""
        with self._lock:
            measurements = list(self._measurements.get(tenant_id, []))

        # Also load from disk
        disk_measurements = self._read_measurements(tenant_id)
        existing_ids = {m.measurement_id for m in measurements}
        for m in disk_measurements:
            if m.measurement_id not in existing_ids:
                measurements.append(m)

        if metric_type:
            measurements = [m for m in measurements if m.metric_type == metric_type]
        if status:
            measurements = [m for m in measurements if m.status == status]
        if source:
            measurements = [m for m in measurements if m.source == source]

        measurements.sort(key=lambda m: m.timestamp, reverse=True)
        return measurements[:limit]

    def get_latest_measurement(
        self,
        tenant_id: str,
        metric_type: MetricType,
    ) -> MetricMeasurement | None:
        """Get the latest measurement for a tenant and metric type."""
        measurements = self.get_measurements(tenant_id, metric_type=metric_type, limit=1)
        return measurements[0] if measurements else None

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(
        self,
        tenant_id: str,
        metric_type: MetricType,
    ) -> dict[str, Any]:
        """Get statistics for a metric type."""
        measurements = self.get_measurements(tenant_id, metric_type=metric_type, limit=1000)
        if not measurements:
            return {
                "tenant_id": tenant_id,
                "metric_type": metric_type.value,
                "count": 0,
                "avg_seconds": 0.0,
                "min_seconds": 0.0,
                "max_seconds": 0.0,
                "p95_seconds": 0.0,
                "compliant_count": 0,
                "warning_count": 0,
                "breach_count": 0,
            }

        values = [m.value_seconds for m in measurements]
        compliant = sum(1 for m in measurements if m.status == MetricStatus.COMPLIANT)
        warning = sum(1 for m in measurements if m.status == MetricStatus.WARNING)
        breach = sum(1 for m in measurements if m.status == MetricStatus.BREACH)

        sorted_values = sorted(values)
        p95_idx = int(len(sorted_values) * 0.95)
        p95 = sorted_values[min(p95_idx, len(sorted_values) - 1)]

        return {
            "tenant_id": tenant_id,
            "metric_type": metric_type.value,
            "count": len(measurements),
            "avg_seconds": round(statistics.fmean(values), 3),
            "min_seconds": round(min(values), 3),
            "max_seconds": round(max(values), 3),
            "p95_seconds": round(p95, 3),
            "compliant_count": compliant,
            "warning_count": warning,
            "breach_count": breach,
        }

    # ------------------------------------------------------------------
    # Compliance reporting
    # ------------------------------------------------------------------

    def generate_compliance_report(self, tenant_id: str) -> ComplianceReport:
        """Generate a compliance report for a tenant.

        Args:
            tenant_id: Tenant UUID string.

        Returns:
            ComplianceReport with current metrics and status.
        """
        targets = self._read_targets(tenant_id)
        rto_measurements = self.get_measurements(tenant_id, metric_type=MetricType.RTO, limit=1000)
        rpo_measurements = self.get_measurements(tenant_id, metric_type=MetricType.RPO, limit=1000)

        rto_compliant = sum(1 for m in rto_measurements if m.status == MetricStatus.COMPLIANT)
        rto_warning = sum(1 for m in rto_measurements if m.status == MetricStatus.WARNING)
        rto_breach = sum(1 for m in rto_measurements if m.status == MetricStatus.BREACH)

        rpo_compliant = sum(1 for m in rpo_measurements if m.status == MetricStatus.COMPLIANT)
        rpo_warning = sum(1 for m in rpo_measurements if m.status == MetricStatus.WARNING)
        rpo_breach = sum(1 for m in rpo_measurements if m.status == MetricStatus.BREACH)

        rto_values = [m.value_seconds for m in rto_measurements]
        rpo_values = [m.value_seconds for m in rpo_measurements]

        rto_avg = statistics.fmean(rto_values) if rto_values else 0.0
        rpo_avg = statistics.fmean(rpo_values) if rpo_values else 0.0

        rto_sorted = sorted(rto_values)
        rpo_sorted = sorted(rpo_values)
        rto_p95 = rto_sorted[min(int(len(rto_sorted) * 0.95), len(rto_sorted) - 1)] if rto_sorted else 0.0
        rpo_p95 = rpo_sorted[min(int(len(rpo_sorted) * 0.95), len(rpo_sorted) - 1)] if rpo_sorted else 0.0

        # Determine overall status
        if rto_breach > 0 or rpo_breach > 0:
            overall = MetricStatus.BREACH
        elif rto_warning > 0 or rpo_warning > 0:
            overall = MetricStatus.WARNING
        elif rto_compliant > 0 or rpo_compliant > 0:
            overall = MetricStatus.COMPLIANT
        else:
            overall = MetricStatus.UNKNOWN

        report = ComplianceReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            rto_target=targets,
            rpo_target=targets,
            rto_measurements=rto_measurements,
            rpo_measurements=rpo_measurements,
            rto_compliant_count=rto_compliant,
            rto_warning_count=rto_warning,
            rto_breach_count=rto_breach,
            rpo_compliant_count=rpo_compliant,
            rpo_warning_count=rpo_warning,
            rpo_breach_count=rpo_breach,
            rto_avg_seconds=rto_avg,
            rto_p95_seconds=rto_p95,
            rpo_avg_seconds=rpo_avg,
            rpo_p95_seconds=rpo_p95,
            overall_status=overall,
        )

        # Save report
        reports_dir = self._reports_dir(tenant_id)
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{report.generated_at.strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

        return report

    def get_compliance_summary(self, tenant_id: str) -> dict[str, Any]:
        """Get a quick compliance summary for a tenant."""
        rto_stats = self.get_statistics(tenant_id, MetricType.RTO)
        rpo_stats = self.get_statistics(tenant_id, MetricType.RPO)
        targets = self._read_targets(tenant_id)

        return {
            "tenant_id": tenant_id,
            "rto": {
                "target_seconds": targets.rto_target_seconds,
                **rto_stats,
            },
            "rpo": {
                "target_seconds": targets.rpo_target_seconds,
                **rpo_stats,
            },
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def record_rto(
    tracker_root: str | Path,
    tenant_id: str,
    value_seconds: float,
    **kwargs: Any,
) -> MetricMeasurement:
    """Convenience function: record RTO with a new tracker."""
    tracker = RTOTracker(tracker_root)
    return tracker.record_rto(tenant_id, value_seconds, **kwargs)


def record_rpo(
    tracker_root: str | Path,
    tenant_id: str,
    value_seconds: float,
    **kwargs: Any,
) -> MetricMeasurement:
    """Convenience function: record RPO with a new tracker."""
    tracker = RTOTracker(tracker_root)
    return tracker.record_rpo(tenant_id, value_seconds, **kwargs)


def generate_compliance_report(
    tracker_root: str | Path,
    tenant_id: str,
) -> ComplianceReport:
    """Convenience function: generate report with a new tracker."""
    tracker = RTOTracker(tracker_root)
    return tracker.generate_compliance_report(tenant_id)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "RTOTrackingError",
    "MetricNotFoundError",
    "MetricType",
    "MetricStatus",
    "MeasurementSource",
    "RTOTarget",
    "MetricMeasurement",
    "ComplianceReport",
    "RTOTracker",
    "record_rto",
    "record_rpo",
    "generate_compliance_report",
]
