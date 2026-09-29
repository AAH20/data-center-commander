"""Model drift detection for Data Center Commander.

Monitors model performance degradation over time using statistical methods
and sliding-window comparisons. Designed for tenant-scoped KPI and telemetry
data stored in the dcc schema.

No external dependencies — pure Python 3.11+.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Sequence


class DriftMethod(str, Enum):
    """Supported drift detection methods."""
    PSI = "psi"                          # Population Stability Index
    KS = "ks"                            # Kolmogorov-Smirnov (approximation)
    CUSUM = "cusum"                      # Cumulative sum control chart
    ERROR_RATE = "error_rate"            # Forecast error rate threshold
    MEAN_SHIFT = "mean_shift"            # Two-window mean comparison
    VARIANCE_SHIFT = "variance_shift"    # Two-window variance comparison


class DriftSeverity(str, Enum):
    """Severity levels for detected drift."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DriftThresholds:
    """Configurable thresholds for drift detection methods."""
    # PSI: <0.1 no drift, 0.1-0.2 moderate, >0.2 significant
    psi_low: float = 0.10
    psi_high: float = 0.20
    # KS: p-value threshold for rejecting same-distribution hypothesis
    ks_alpha: float = 0.05
    # CUSUM: decision interval (in standard deviations)
    cusum_threshold: float = 5.0
    # Error rate: acceptable error fraction before flagging
    error_rate_low: float = 0.10
    error_rate_high: float = 0.25
    # Mean shift: minimum relative change to flag
    mean_shift_low: float = 0.15
    mean_shift_high: float = 0.30
    # Variance shift: minimum ratio change to flag
    variance_shift_low: float = 1.5
    variance_shift_high: float = 2.5


@dataclass
class DriftResult:
    """Result of a drift detection check."""
    method: DriftMethod
    severity: DriftSeverity
    score: float
    threshold: float
    detected: bool
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method.value,
            "severity": self.severity.value,
            "score": round(self.score, 6),
            "threshold": self.threshold,
            "detected": self.detected,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ModelPerformanceSnapshot:
    """A point-in-time snapshot of model performance metrics."""
    model_id: str
    tenant_id: str
    window_start: datetime
    window_end: datetime
    predictions: int = 0
    actuals: int = 0
    errors: list[float] = field(default_factory=list)
    mae: float | None = None
    rmse: float | None = None
    mape: float | None = None
    bias: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_derived(self) -> None:
        """Compute MAE, RMSE, MAPE, and bias from stored errors."""
        if not self.errors:
            return
        n = len(self.errors)
        abs_errors = [abs(e) for e in self.errors]
        self.mae = sum(abs_errors) / n
        self.rmse = math.sqrt(sum(e * e for e in self.errors) / n)
        self.bias = sum(self.errors) / n
        # MAPE requires actuals; stored as metadata if available
        if self.metadata.get("actual_values"):
            actuals = self.metadata["actual_values"]
            if len(actuals) == n and all(a != 0 for a in actuals):
                self.mape = sum(abs(e / a) for e, a in zip(self.errors, actuals)) / n


class DriftDetector:
    """Multi-method model drift detector.

    Maintains a sliding window of reference data and compares incoming
    data against it using configurable statistical methods.
    """

    def __init__(
        self,
        thresholds: DriftThresholds | None = None,
        reference_window_size: int = 1000,
        min_samples: int = 30,
        methods: set[DriftMethod] | None = None,
    ) -> None:
        self.thresholds = thresholds or DriftThresholds()
        self.reference_window_size = reference_window_size
        self.min_samples = min_samples
        self.methods = methods or {
            DriftMethod.PSI,
            DriftMethod.CUSUM,
            DriftMethod.MEAN_SHIFT,
            DriftMethod.VARIANCE_SHIFT,
        }
        self._reference: deque[float] = deque(maxlen=reference_window_size)
        self._reference_mean: float | None = None
        self._reference_std: float | None = None
        self._cusum_pos: float = 0.0
        self._cusum_neg: float = 0.0
        self._history: list[DriftResult] = []

    # ------------------------------------------------------------------
    # Reference management
    # ------------------------------------------------------------------

    def set_reference(self, values: Sequence[float]) -> None:
        """Set the baseline reference distribution."""
        if len(values) < self.min_samples:
            raise ValueError(
                f"Need at least {self.min_samples} reference samples, got {len(values)}"
            )
        self._reference = deque(values, maxlen=self.reference_window_size)
        self._reference_mean = sum(values) / len(values)
        self._reference_std = _std(values, self._reference_mean)
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0

    def update_reference(self, values: Sequence[float]) -> None:
        """Incrementally update reference with new observations."""
        for v in values:
            self._reference.append(v)
        if len(self._reference) >= self.min_samples:
            ref_list = list(self._reference)
            self._reference_mean = sum(ref_list) / len(ref_list)
            self._reference_std = _std(ref_list, self._reference_mean)

    @property
    def has_reference(self) -> bool:
        return len(self._reference) >= self.min_samples

    @property
    def reference_stats(self) -> dict[str, float | int | None]:
        if not self.has_reference:
            return {"count": len(self._reference), "mean": None, "std": None}
        return {
            "count": len(self._reference),
            "mean": self._reference_mean,
            "std": self._reference_std,
        }

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def detect(self, incoming: Sequence[float]) -> list[DriftResult]:
        """Run all configured drift detection methods on incoming data."""
        if not self.has_reference:
            raise RuntimeError("Reference distribution not set; call set_reference() first")
        if len(incoming) < self.min_samples:
            raise ValueError(
                f"Need at least {self.min_samples} incoming samples, got {len(incoming)}"
            )

        results: list[DriftResult] = []
        for method in sorted(self.methods, key=lambda m: m.value):
            if method == DriftMethod.PSI:
                results.append(self._detect_psi(incoming))
            elif method == DriftMethod.KS:
                results.append(self._detect_ks(incoming))
            elif method == DriftMethod.CUSUM:
                results.append(self._detect_cusum(incoming))
            elif method == DriftMethod.MEAN_SHIFT:
                results.append(self._detect_mean_shift(incoming))
            elif method == DriftMethod.VARIANCE_SHIFT:
                results.append(self._detect_variance_shift(incoming))
            elif method == DriftMethod.ERROR_RATE:
                results.append(self._detect_error_rate(incoming))

        self._history.extend(results)
        return results

    def detect_from_performance(
        self,
        current: ModelPerformanceSnapshot,
        reference: ModelPerformanceSnapshot,
    ) -> list[DriftResult]:
        """Compare two performance snapshots for degradation."""
        results: list[DriftResult] = []

        # Error rate comparison
        if current.errors and reference.errors:
            current_rate = sum(1 for e in current.errors if abs(e) > 0) / len(current.errors)
            ref_rate = sum(1 for e in reference.errors if abs(e) > 0) / len(reference.errors)
            rate_change = current_rate - ref_rate
            severity = _severity_from_value(
                rate_change,
                self.thresholds.error_rate_low,
                self.thresholds.error_rate_high,
            )
            results.append(DriftResult(
                method=DriftMethod.ERROR_RATE,
                severity=severity,
                score=rate_change,
                threshold=self.thresholds.error_rate_low,
                detected=severity != DriftSeverity.NONE,
                details={
                    "current_error_rate": round(current_rate, 4),
                    "reference_error_rate": round(ref_rate, 4),
                    "current_mae": current.mae,
                    "reference_mae": reference.mae,
                },
            ))

        # MAE degradation
        if current.mae is not None and reference.mae is not None and reference.mae > 0:
            mae_ratio = current.mae / reference.mae
            severity = _severity_from_value(
                mae_ratio - 1.0,
                self.thresholds.mean_shift_low,
                self.thresholds.mean_shift_high,
            )
            results.append(DriftResult(
                method=DriftMethod.MEAN_SHIFT,
                severity=severity,
                score=mae_ratio,
                threshold=1.0 + self.thresholds.mean_shift_low,
                detected=severity != DriftSeverity.NONE,
                details={
                    "current_mae": round(current.mae, 6),
                    "reference_mae": round(reference.mae, 6),
                    "mae_ratio": round(mae_ratio, 4),
                },
            ))

        self._history.extend(results)
        return results

    # ------------------------------------------------------------------
    # Individual method implementations
    # ------------------------------------------------------------------

    def _detect_psi(self, incoming: Sequence[float]) -> DriftResult:
        """Population Stability Index between reference and incoming."""
        psi_value = _psi(list(self._reference), list(incoming))
        severity = _severity_from_value(
            psi_value, self.thresholds.psi_low, self.thresholds.psi_high
        )
        return DriftResult(
            method=DriftMethod.PSI,
            severity=severity,
            score=psi_value,
            threshold=self.thresholds.psi_low,
            detected=severity != DriftSeverity.NONE,
            details={"psi": round(psi_value, 6)},
        )

    def _detect_ks(self, incoming: Sequence[float]) -> DriftResult:
        """Kolmogorov-Smirnov test statistic (approximation)."""
        ks_stat, p_value = _ks_test(list(self._reference), list(incoming))
        severity = DriftSeverity.HIGH if p_value < self.thresholds.ks_alpha else DriftSeverity.NONE
        return DriftResult(
            method=DriftMethod.KS,
            severity=severity,
            score=ks_stat,
            threshold=self.thresholds.ks_alpha,
            detected=severity != DriftSeverity.NONE,
            details={"ks_statistic": round(ks_stat, 6), "p_value": round(p_value, 6)},
        )

    def _detect_cusum(self, incoming: Sequence[float]) -> DriftResult:
        """CUSUM control chart for mean shift detection."""
        if self._reference_mean is None or self._reference_std is None or self._reference_std == 0:
            return DriftResult(
                method=DriftMethod.CUSUM,
                severity=DriftSeverity.NONE,
                score=0.0,
                threshold=self.thresholds.cusum_threshold,
                detected=False,
                details={"error": "reference not ready"},
            )

        k = 0.5  # slack parameter (in std units)
        h = self.thresholds.cusum_threshold
        cusum_pos = 0.0
        cusum_neg = 0.0
        max_cusum = 0.0

        for x in incoming:
            normalized = (x - self._reference_mean) / self._reference_std
            cusum_pos = max(0, cusum_pos + normalized - k)
            cusum_neg = min(0, cusum_neg + normalized + k)
            max_cusum = max(max_cusum, abs(cusum_pos), abs(cusum_neg))

        self._cusum_pos = cusum_pos
        self._cusum_neg = cusum_neg

        severity = DriftSeverity.HIGH if max_cusum > h else DriftSeverity.NONE
        return DriftResult(
            method=DriftMethod.CUSUM,
            severity=severity,
            score=max_cusum,
            threshold=h,
            detected=severity != DriftSeverity.NONE,
            details={
                "cusum_pos": round(cusum_pos, 4),
                "cusum_neg": round(cusum_neg, 4),
                "max_cusum": round(max_cusum, 4),
            },
        )

    def _detect_mean_shift(self, incoming: Sequence[float]) -> DriftResult:
        """Compare means of reference and incoming windows."""
        if self._reference_mean is None:
            return DriftResult(
                method=DriftMethod.MEAN_SHIFT,
                severity=DriftSeverity.NONE,
                score=0.0,
                threshold=self.thresholds.mean_shift_low,
                detected=False,
                details={"error": "reference not ready"},
            )

        incoming_mean = sum(incoming) / len(incoming)
        # Use max(|ref_mean|, ref_std) as scale to handle near-zero means
        scale = max(abs(self._reference_mean), self._reference_std or 0.0, 1e-10)
        relative_change = abs(incoming_mean - self._reference_mean) / scale

        severity = _severity_from_value(
            relative_change,
            self.thresholds.mean_shift_low,
            self.thresholds.mean_shift_high,
        )
        return DriftResult(
            method=DriftMethod.MEAN_SHIFT,
            severity=severity,
            score=relative_change,
            threshold=self.thresholds.mean_shift_low,
            detected=severity != DriftSeverity.NONE,
            details={
                "reference_mean": round(self._reference_mean, 6),
                "incoming_mean": round(incoming_mean, 6),
                "relative_change": round(relative_change, 4),
            },
        )

    def _detect_variance_shift(self, incoming: Sequence[float]) -> DriftResult:
        """Compare variances of reference and incoming windows."""
        if self._reference_std is None or self._reference_std == 0:
            return DriftResult(
                method=DriftMethod.VARIANCE_SHIFT,
                severity=DriftSeverity.NONE,
                score=1.0,
                threshold=self.thresholds.variance_shift_low,
                detected=False,
                details={"error": "reference variance is zero or not ready"},
            )

        incoming_mean = sum(incoming) / len(incoming)
        incoming_std = _std(incoming, incoming_mean)
        variance_ratio = (incoming_std / self._reference_std) ** 2

        # Use log-ratio for symmetric severity
        log_ratio = abs(math.log(variance_ratio)) if variance_ratio > 0 else float("inf")
        threshold_log_low = math.log(self.thresholds.variance_shift_low)
        threshold_log_high = math.log(self.thresholds.variance_shift_high)
        severity = _severity_from_value(log_ratio, threshold_log_low, threshold_log_high)

        return DriftResult(
            method=DriftMethod.VARIANCE_SHIFT,
            severity=severity,
            score=variance_ratio,
            threshold=self.thresholds.variance_shift_low,
            detected=severity != DriftSeverity.NONE,
            details={
                "reference_variance": round(self._reference_std ** 2, 6),
                "incoming_variance": round(incoming_std ** 2, 6),
                "variance_ratio": round(variance_ratio, 4),
            },
        )

    def _detect_error_rate(self, incoming: Sequence[float]) -> DriftResult:
        """Detect drift based on fraction of large errors."""
        if self._reference_std is None or self._reference_std == 0:
            return DriftResult(
                method=DriftMethod.ERROR_RATE,
                severity=DriftSeverity.NONE,
                score=0.0,
                threshold=self.thresholds.error_rate_low,
                detected=False,
                details={"error": "reference not ready"},
            )

        # Count observations beyond 2-sigma as errors
        threshold = 2.0 * self._reference_std
        error_count = sum(1 for x in incoming if abs(x - (self._reference_mean or 0)) > threshold)
        error_rate = error_count / len(incoming)

        severity = _severity_from_value(
            error_rate,
            self.thresholds.error_rate_low,
            self.thresholds.error_rate_high,
        )
        return DriftResult(
            method=DriftMethod.ERROR_RATE,
            severity=severity,
            score=error_rate,
            threshold=self.thresholds.error_rate_low,
            detected=severity != DriftSeverity.NONE,
            details={
                "error_count": error_count,
                "total_count": len(incoming),
                "error_rate": round(error_rate, 4),
                "sigma_threshold": round(threshold, 4),
            },
        )

    # ------------------------------------------------------------------
    # History and reporting
    # ------------------------------------------------------------------

    @property
    def history(self) -> list[DriftResult]:
        return list(self._history)

    def get_recent_detections(
        self, since: datetime | None = None, severity: DriftSeverity | None = None
    ) -> list[DriftResult]:
        """Filter history by time and/or severity."""
        results = self._history
        if since is not None:
            results = [r for r in results if r.timestamp >= since]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results

    def summary(self) -> dict[str, Any]:
        """Summary of all drift detection history."""
        if not self._history:
            return {"total_checks": 0, "drift_detected": False, "by_severity": {}, "by_method": {}}

        by_severity: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._history:
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_method[r.method.value] = by_method.get(r.method.value, 0) + 1

        return {
            "total_checks": len(self._history),
            "drift_detected": any(r.detected for r in self._history),
            "by_severity": by_severity,
            "by_method": by_method,
            "reference_stats": self.reference_stats,
        }


# ----------------------------------------------------------------------
# Standalone functions for simple use cases
# ----------------------------------------------------------------------


def detect_drift(
    reference: Sequence[float],
    incoming: Sequence[float],
    *,
    methods: set[DriftMethod] | None = None,
    thresholds: DriftThresholds | None = None,
    min_samples: int = 30,
) -> list[DriftResult]:
    """One-shot drift detection between two sample sets.

    Convenience function that creates a temporary DriftDetector.
    """
    detector = DriftDetector(
        thresholds=thresholds,
        min_samples=min_samples,
        methods=methods,
    )
    detector.set_reference(reference)
    return detector.detect(incoming)


def compute_psi(reference: Sequence[float], incoming: Sequence[float], bins: int = 10) -> float:
    """Compute Population Stability Index between two distributions."""
    return _psi(list(reference), list(incoming), bins)


def compute_ks_statistic(reference: Sequence[float], incoming: Sequence[float]) -> tuple[float, float]:
    """Compute KS test statistic and approximate p-value."""
    return _ks_test(list(reference), list(incoming))


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _std(values: Sequence[float], mean: float) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    return math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))


def _severity_from_value(value: float, low: float, high: float) -> DriftSeverity:
    """Map a numeric value to severity using low/high thresholds."""
    if value < low:
        return DriftSeverity.NONE
    if value < high:
        return DriftSeverity.LOW
    return DriftSeverity.HIGH


def _psi(reference: list[float], incoming: list[float], bins: int = 10) -> float:
    """Population Stability Index.

    PSI = sum((incoming_pct - reference_pct) * ln(incoming_pct / reference_pct))
    """
    if not reference or not incoming:
        return 0.0

    # Create bins from reference distribution
    ref_min, ref_max = min(reference), max(reference)
    if ref_min == ref_max:
        # Degenerate reference — check if incoming matches
        incoming_match = sum(1 for x in incoming if x == ref_min) / len(incoming)
        return 0.0 if incoming_match > 0.99 else float("inf")

    bin_width = (ref_max - ref_min) / bins
    edges = [ref_min + i * bin_width for i in range(bins + 1)]
    edges[-1] = ref_max + 1e-10  # Ensure max value falls in last bin

    ref_counts = [0] * bins
    for x in reference:
        for i in range(bins):
            if edges[i] <= x < edges[i + 1]:
                ref_counts[i] += 1
                break

    inc_counts = [0] * bins
    for x in incoming:
        for i in range(bins):
            if edges[i] <= x < edges[i + 1]:
                inc_counts[i] += 1
                break

    psi_value = 0.0
    for i in range(bins):
        ref_pct = max(ref_counts[i] / len(reference), 1e-6)
        inc_pct = max(inc_counts[i] / len(incoming), 1e-6)
        psi_value += (inc_pct - ref_pct) * math.log(inc_pct / ref_pct)

    return psi_value


def _ks_test(reference: list[float], incoming: list[float]) -> tuple[float, float]:
    """Kolmogorov-Smirnov two-sample test.

    Returns (statistic, approximate p-value).
    """
    ref_sorted = sorted(reference)
    inc_sorted = sorted(incoming)
    n1, n2 = len(ref_sorted), len(inc_sorted)

    # Compute empirical CDFs and find max difference
    all_values = sorted(set(ref_sorted + inc_sorted))
    max_diff = 0.0
    i, j = 0, 0

    for v in all_values:
        while i < n1 and ref_sorted[i] <= v:
            i += 1
        while j < n2 and inc_sorted[j] <= v:
            j += 1
        diff = abs(i / n1 - j / n2)
        max_diff = max(max_diff, diff)

    # Approximate p-value using Kolmogorov distribution
    en = math.sqrt(n1 * n2 / (n1 + n2))
    lambda_val = (en + 0.12 + 0.11 / en) * max_diff
    p_value = _kolmogorov_cdf(lambda_val)

    return max_diff, p_value


def _kolmogorov_cdf(x: float) -> float:
    """Approximate Kolmogorov distribution CDF.

    Uses the series expansion: Q(x) = 2 * sum((-1)^(k-1) * exp(-2*k^2*x^2))
    """
    if x <= 0:
        return 1.0
    if x > 3.0:
        return 0.0

    total = 0.0
    for k in range(1, 101):
        term = 2 * ((-1) ** (k - 1)) * math.exp(-2 * k * k * x * x)
        total += term
        if abs(term) < 1e-10:
            break
    return max(0.0, min(1.0, total))


# ----------------------------------------------------------------------
# Performance tracker for ongoing monitoring
# ----------------------------------------------------------------------


class PerformanceTracker:
    """Track model performance over time and detect degradation.

    Maintains a rolling history of performance snapshots and compares
    recent windows against a reference baseline.
    """

    def __init__(
        self,
        model_id: str,
        tenant_id: str,
        window_size: int = 100,
        reference_windows: int = 5,
        thresholds: DriftThresholds | None = None,
    ) -> None:
        self.model_id = model_id
        self.tenant_id = tenant_id
        self.window_size = window_size
        self.reference_windows = reference_windows
        self.thresholds = thresholds or DriftThresholds()
        self._snapshots: deque[ModelPerformanceSnapshot] = deque(maxlen=max(reference_windows * window_size, 50))
        self._reference: ModelPerformanceSnapshot | None = None
        self._detector = DriftDetector(thresholds=self.thresholds)

    def record(self, snapshot: ModelPerformanceSnapshot) -> list[DriftResult]:
        """Record a performance snapshot and check for drift."""
        self._snapshots.append(snapshot)

        # Build reference from older snapshots if needed
        if self._reference is None and len(self._snapshots) >= self.reference_windows:
            self._build_reference()

        if self._reference is None:
            return []

        results = self._detector.detect_from_performance(snapshot, self._reference)

        # Update reference periodically (every window_size records)
        if len(self._snapshots) % self.window_size == 0:
            self._build_reference()

        return results

    def _build_reference(self) -> None:
        """Build reference snapshot from historical data."""
        if len(self._snapshots) < 2:
            return

        # Use all but the most recent snapshot as reference
        ref_snapshots = list(self._snapshots)[:-1]
        all_errors: list[float] = []
        for s in ref_snapshots:
            all_errors.extend(s.errors)

        if all_errors:
            self._reference = ModelPerformanceSnapshot(
                model_id=self.model_id,
                tenant_id=self.tenant_id,
                window_start=ref_snapshots[0].window_start,
                window_end=ref_snapshots[-1].window_end,
                predictions=sum(s.predictions for s in ref_snapshots),
                actuals=sum(s.actuals for s in ref_snapshots),
                errors=all_errors,
            )
            self._reference.compute_derived()

    @property
    def reference(self) -> ModelPerformanceSnapshot | None:
        return self._reference

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)
