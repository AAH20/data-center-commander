"""Prometheus metrics engine for Data Center Commander.

Self-contained, dependency-free implementation of Prometheus-compatible
metrics: request latency histograms, error rate counters, throughput
counters, and resource utilization gauges. Exports in Prometheus text
format.

Usage:
    from dcc.observability.metrics import MetricsEngine, MetricType

    engine = MetricsEngine()
    engine.record_latency("api_request", 0.42, labels={"route": "/v1/assets"})
    engine.increment_counter("api_errors", labels={"type": "timeout"})
    engine.set_gauge("cpu_utilization", 0.75, labels={"host": "dc-01"})
    engine.increment_throughput("requests_total")

    text_output = engine.render_prometheus()
"""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable


# ---------------------------------------------------------------------------
# Metric types
# ---------------------------------------------------------------------------

class MetricType(str, Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class ErrorType(str, Enum):
    """Classification of error types for error rate tracking."""
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    INTERNAL = "internal"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


class ResourceType(str, Enum):
    """Classification of resource types for utilization tracking."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    POWER = "power"
    COOLING = "cooling"
    GPU = "gpu"
    STORAGE_IOPS = "storage_iops"
    NETWORK_BANDWIDTH = "network_bandwidth"


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _validate_label_value(value: Any) -> str:
    """Validate and convert a label value to a string."""
    if value is None:
        return ""
    # Use .value for Enum members (e.g., ErrorType.TIMEOUT -> "timeout")
    if isinstance(value, Enum):
        s = str(value.value)
    else:
        s = str(value)
    if len(s) > 256:
        raise ValueError(f"label value exceeds 256 characters: {s[:50]}...")
    return s


def _format_labels(labels: dict[str, Any] | None) -> str:
    """Format labels as Prometheus label string: {key="value",...}."""
    if not labels:
        return ""
    parts = []
    for key in sorted(labels.keys()):
        value = _validate_label_value(labels[key])
        # Escape special characters in label values
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        parts.append(f'{key}="{escaped}"')
    return "{" + ",".join(parts) + "}"


def _labels_to_key(labels: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    """Convert labels dict to a hashable sorted tuple for internal keying."""
    if not labels:
        return ()
    return tuple(sorted((k, _validate_label_value(v)) for k, v in labels.items()))


# ---------------------------------------------------------------------------
# Histogram buckets
# ---------------------------------------------------------------------------

DEFAULT_LATENCY_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0,
)

DEFAULT_THROUGHPUT_BUCKETS: tuple[float, ...] = (
    1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0,
)


# ---------------------------------------------------------------------------
# Metric series (internal storage)
# ---------------------------------------------------------------------------

@dataclass
class CounterSeries:
    """A single counter time series identified by its label set."""
    value: float = 0.0
    labels: dict[str, Any] = field(default_factory=dict)


@dataclass
class GaugeSeries:
    """A single gauge time series identified by its label set."""
    value: float = 0.0
    labels: dict[str, Any] = field(default_factory=dict)


@dataclass
class HistogramSeries:
    """A single histogram time series identified by its label set."""
    buckets: dict[float, int] = field(default_factory=dict)
    count: int = 0
    sum: float = 0.0
    labels: dict[str, Any] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        """Record an observation."""
        self.count += 1
        self.sum += value
        for bound in self.buckets:
            if value <= bound:
                self.buckets[bound] += 1


# ---------------------------------------------------------------------------
# Public metric wrappers
# ---------------------------------------------------------------------------

class LatencyHistogram:
    """Tracks request latency as a Prometheus histogram.

    Records observations into configurable buckets and exposes count/sum.
    """

    def __init__(
        self,
        name: str,
        buckets: Iterable[float] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self._bucket_bounds = tuple(buckets) if buckets is not None else DEFAULT_LATENCY_BUCKETS
        self._labels = labels or {}
        self._series: dict[tuple[tuple[str, str], ...], HistogramSeries] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, labels: dict[str, Any] | None = None) -> None:
        """Record a latency observation in seconds.

        Args:
            value: Latency in seconds (must be non-negative).
            labels: Optional label overrides for this observation.
        """
        if value < 0:
            raise ValueError(f"latency must be non-negative, got {value}")
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"latency must be finite, got {value}")

        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)

        with self._lock:
            if key not in self._series:
                self._series[key] = HistogramSeries(
                    buckets={b: 0 for b in self._bucket_bounds},
                    labels=merged,
                )
            self._series[key].observe(value)

    def get_count(self, labels: dict[str, Any] | None = None) -> int:
        """Get the total observation count for a label set."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            return series.count if series else 0

    def get_sum(self, labels: dict[str, Any] | None = None) -> float:
        """Get the sum of all observations for a label set."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            return series.sum if series else 0.0

    def get_mean(self, labels: dict[str, Any] | None = None) -> float:
        """Get the mean latency for a label set."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            if series is None or series.count == 0:
                return 0.0
            return series.sum / series.count

    def get_percentile(self, p: float, labels: dict[str, Any] | None = None) -> float:
        """Get an approximate percentile from histogram buckets.

        Uses linear interpolation between bucket boundaries.
        """
        if not 0 < p <= 100:
            raise ValueError(f"percentile must be in (0, 100], got {p}")
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            if series is None or series.count == 0:
                return 0.0

            target = (p / 100.0) * series.count
            sorted_bounds = sorted(series.buckets.keys())
            prev_bound = 0.0
            prev_count = 0
            for bound in sorted_bounds:
                count = series.buckets[bound]
                if count >= target:
                    if count == prev_count:
                        return bound
                    # Linear interpolation
                    fraction = (target - prev_count) / (count - prev_count)
                    return prev_bound + fraction * (bound - prev_bound)
                prev_bound = bound
                prev_count = count
            return sorted_bounds[-1] if sorted_bounds else 0.0

    def reset(self) -> None:
        """Reset all observations."""
        with self._lock:
            self._series.clear()


class ErrorCounter:
    """Tracks error counts as a Prometheus counter, broken down by error type."""

    def __init__(self, name: str, labels: dict[str, Any] | None = None) -> None:
        self.name = name
        self._labels = labels or {}
        self._series: dict[tuple[tuple[str, str], ...], CounterSeries] = {}
        self._lock = threading.Lock()

    def increment(
        self,
        amount: float = 1.0,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Increment the error counter.

        Args:
            amount: Amount to increment by (must be non-negative).
            labels: Optional label overrides.
        """
        if amount < 0:
            raise ValueError(f"increment amount must be non-negative, got {amount}")
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            if key not in self._series:
                self._series[key] = CounterSeries(value=0.0, labels=merged)
            self._series[key].value += amount

    def get_value(self, labels: dict[str, Any] | None = None) -> float:
        """Get the current counter value for a label set."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            return series.value if series else 0.0

    def get_error_rate(
        self,
        total_requests: float,
        labels: dict[str, Any] | None = None,
    ) -> float:
        """Get the error rate as a fraction (0.0 to 1.0)."""
        if total_requests <= 0:
            return 0.0
        return min(1.0, self.get_value(labels) / total_requests)

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            self._series.clear()


class ThroughputCounter:
    """Tracks throughput (requests per second) as a Prometheus counter."""

    def __init__(self, name: str, labels: dict[str, Any] | None = None) -> None:
        self.name = name
        self._labels = labels or {}
        self._series: dict[tuple[tuple[str, str], ...], CounterSeries] = {}
        self._lock = threading.Lock()

    def increment(
        self,
        amount: float = 1.0,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Increment the throughput counter."""
        if amount < 0:
            raise ValueError(f"increment amount must be non-negative, got {amount}")
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            if key not in self._series:
                self._series[key] = CounterSeries(value=0.0, labels=merged)
            self._series[key].value += amount

    def get_rate(
        self,
        window_seconds: float,
        labels: dict[str, Any] | None = None,
    ) -> float:
        """Get the throughput rate over a time window."""
        if window_seconds <= 0:
            return 0.0
        return self.get_value(labels) / window_seconds

    def get_value(self, labels: dict[str, Any] | None = None) -> float:
        """Get the current counter value."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            return series.value if series else 0.0

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            self._series.clear()


class ResourceGauge:
    """Tracks resource utilization as a Prometheus gauge (0.0 to 1.0)."""

    def __init__(self, name: str, labels: dict[str, Any] | None = None) -> None:
        self.name = name
        self._labels = labels or {}
        self._series: dict[tuple[tuple[str, str], ...], GaugeSeries] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: dict[str, Any] | None = None) -> None:
        """Set the gauge value.

        Args:
            value: Utilization ratio (0.0 to 1.0).
            labels: Optional label overrides.
        """
        if value < 0:
            raise ValueError(f"gauge value must be non-negative, got {value}")
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"gauge value must be finite, got {value}")
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            if key not in self._series:
                self._series[key] = GaugeSeries(value=0.0, labels=merged)
            self._series[key].value = value

    def inc(self, amount: float = 1.0, labels: dict[str, Any] | None = None) -> None:
        """Increment the gauge by an amount."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            if key not in self._series:
                self._series[key] = GaugeSeries(value=0.0, labels=merged)
            self._series[key].value += amount

    def dec(self, amount: float = 1.0, labels: dict[str, Any] | None = None) -> None:
        """Decrement the gauge by an amount."""
        self.inc(-amount, labels)

    def get_value(self, labels: dict[str, Any] | None = None) -> float:
        """Get the current gauge value."""
        merged = {**self._labels, **(labels or {})}
        key = _labels_to_key(merged)
        with self._lock:
            series = self._series.get(key)
            return series.value if series else 0.0

    def reset(self) -> None:
        """Reset all gauges."""
        with self._lock:
            self._series.clear()


# ---------------------------------------------------------------------------
# Metrics registry
# ---------------------------------------------------------------------------

class MetricsRegistry:
    """Thread-safe registry of all metrics.

    Manages named collections of counters, gauges, and histograms.
    """

    def __init__(self) -> None:
        self._counters: dict[str, ErrorCounter] = {}
        self._gauges: dict[str, ResourceGauge] = {}
        self._histograms: dict[str, LatencyHistogram] = {}
        self._throughputs: dict[str, ThroughputCounter] = {}
        self._lock = threading.Lock()

    # -- Registration -------------------------------------------------------

    def register_counter(self, name: str, labels: dict[str, Any] | None = None) -> ErrorCounter:
        """Register or retrieve an error counter."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = ErrorCounter(name, labels)
            return self._counters[name]

    def register_gauge(self, name: str, labels: dict[str, Any] | None = None) -> ResourceGauge:
        """Register or retrieve a resource gauge."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = ResourceGauge(name, labels)
            return self._gauges[name]

    def register_histogram(
        self,
        name: str,
        buckets: Iterable[float] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> LatencyHistogram:
        """Register or retrieve a latency histogram."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = LatencyHistogram(name, buckets, labels)
            return self._histograms[name]

    def register_throughput(self, name: str, labels: dict[str, Any] | None = None) -> ThroughputCounter:
        """Register or retrieve a throughput counter."""
        with self._lock:
            if name not in self._throughputs:
                self._throughputs[name] = ThroughputCounter(name, labels)
            return self._throughputs[name]

    # -- Lookup -------------------------------------------------------------

    def get_counter(self, name: str) -> ErrorCounter | None:
        with self._lock:
            return self._counters.get(name)

    def get_gauge(self, name: str) -> ResourceGauge | None:
        with self._lock:
            return self._gauges.get(name)

    def get_histogram(self, name: str) -> LatencyHistogram | None:
        with self._lock:
            return self._histograms.get(name)

    def get_throughput(self, name: str) -> ThroughputCounter | None:
        with self._lock:
            return self._throughputs.get(name)

    # -- Enumeration --------------------------------------------------------

    @property
    def counter_names(self) -> list[str]:
        with self._lock:
            return sorted(self._counters.keys())

    @property
    def gauge_names(self) -> list[str]:
        with self._lock:
            return sorted(self._gauges.keys())

    @property
    def histogram_names(self) -> list[str]:
        with self._lock:
            return sorted(self._histograms.keys())

    @property
    def throughput_names(self) -> list[str]:
        with self._lock:
            return sorted(self._throughputs.keys())

    def reset_all(self) -> None:
        """Reset all metrics in the registry."""
        with self._lock:
            for s in self._counters.values():
                s.reset()
            for s in self._gauges.values():
                s.reset()
            for s in self._histograms.values():
                s.reset()
            for s in self._throughputs.values():
                s.reset()


# ---------------------------------------------------------------------------
# Prometheus text renderer
# ---------------------------------------------------------------------------

def _render_counter(name: str, counter: ErrorCounter) -> list[str]:
    """Render a counter metric in Prometheus text format."""
    lines = [
        f"# HELP {name} Total count of {name}",
        f"# TYPE {name} counter",
    ]
    with counter._lock:
        for key, series in sorted(counter._series.items()):
            label_str = _format_labels(series.labels)
            lines.append(f"{name}{label_str} {series.value:.6g}")
    return lines


def _render_gauge(name: str, gauge: ResourceGauge) -> list[str]:
    """Render a gauge metric in Prometheus text format."""
    lines = [
        f"# HELP {name} Current value of {name}",
        f"# TYPE {name} gauge",
    ]
    with gauge._lock:
        for key, series in sorted(gauge._series.items()):
            label_str = _format_labels(series.labels)
            lines.append(f"{name}{label_str} {series.value:.6g}")
    return lines


def _render_histogram(name: str, histogram: LatencyHistogram) -> list[str]:
    """Render a histogram metric in Prometheus text format."""
    lines = [
        f"# HELP {name} Latency distribution for {name}",
        f"# TYPE {name} histogram",
    ]
    with histogram._lock:
        for key, series in sorted(histogram._series.items()):
            label_str = _format_labels(series.labels)
            sorted_bounds = sorted(series.buckets.keys())
            for bound in sorted_bounds:
                bucket_labels = dict(series.labels)
                bucket_labels["le"] = f"{bound:g}"
                bucket_label_str = _format_labels(bucket_labels)
                lines.append(f"{name}_bucket{bucket_label_str} {series.buckets[bound]}")
            # +Inf bucket
            inf_labels = dict(series.labels)
            inf_labels["le"] = "+Inf"
            inf_label_str = _format_labels(inf_labels)
            lines.append(f"{name}_bucket{inf_label_str} {series.count}")
            lines.append(f"{name}_sum{label_str} {series.sum:.6g}")
            lines.append(f"{name}_count{label_str} {series.count}")
    return lines


def _render_throughput(name: str, throughput: ThroughputCounter) -> list[str]:
    """Render a throughput counter in Prometheus text format."""
    lines = [
        f"# HELP {name} Total throughput count for {name}",
        f"# TYPE {name} counter",
    ]
    with throughput._lock:
        for key, series in sorted(throughput._series.items()):
            label_str = _format_labels(series.labels)
            lines.append(f"{name}{label_str} {series.value:.6g}")
    return lines


def render_prometheus_text(registry: MetricsRegistry) -> str:
    """Render all metrics in the registry as Prometheus text format.

    Returns a string in the Prometheus exposition format suitable for
    scraping by a Prometheus server.
    """
    lines: list[str] = []

    # Counters
    for name in registry.counter_names:
        counter = registry.get_counter(name)
        if counter:
            lines.extend(_render_counter(name, counter))

    # Gauges
    for name in registry.gauge_names:
        gauge = registry.get_gauge(name)
        if gauge:
            lines.extend(_render_gauge(name, gauge))

    # Histograms
    for name in registry.histogram_names:
        histogram = registry.get_histogram(name)
        if histogram:
            lines.extend(_render_histogram(name, histogram))

    # Throughputs
    for name in registry.throughput_names:
        throughput = registry.get_throughput(name)
        if throughput:
            lines.extend(_render_throughput(name, throughput))

    return "\n".join(lines) + "\n" if lines else ""


# ---------------------------------------------------------------------------
# Metrics engine (high-level facade)
# ---------------------------------------------------------------------------

class MetricsEngine:
    """High-level facade for recording and exporting metrics.

    Provides a simple interface for recording latencies, errors,
    throughput, and resource utilization, and rendering them in
    Prometheus text format.

    Example:
        engine = MetricsEngine()

        # Record API request latency
        engine.record_latency("api_request_duration_seconds", 0.42,
                              labels={"route": "/v1/assets", "method": "GET"})

        # Record an error
        engine.increment_error("api_errors_total",
                               labels={"type": "timeout", "route": "/v1/assets"})

        # Record throughput
        engine.increment_throughput("api_requests_total",
                                    labels={"route": "/v1/assets"})

        # Record resource utilization
        engine.set_gauge("dc_cpu_utilization", 0.75, labels={"host": "dc-01"})

        # Export
        prometheus_text = engine.render()
    """

    def __init__(self) -> None:
        self._registry = MetricsRegistry()

    @property
    def registry(self) -> MetricsRegistry:
        return self._registry

    # -- Latency ------------------------------------------------------------

    def record_latency(
        self,
        name: str,
        value: float,
        labels: dict[str, Any] | None = None,
        *,
        buckets: Iterable[float] | None = None,
    ) -> None:
        """Record a latency observation.

        Args:
            name: Metric name (e.g., "api_request_duration_seconds").
            value: Latency in seconds.
            labels: Optional labels.
            buckets: Optional custom histogram buckets.
        """
        hist = self._registry.register_histogram(name, buckets, labels)
        hist.observe(value, labels)

    # -- Errors -------------------------------------------------------------

    def increment_error(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Increment an error counter.

        Args:
            name: Metric name (e.g., "api_errors_total").
            amount: Increment amount.
            labels: Optional labels (typically includes "type").
        """
        counter = self._registry.register_counter(name, labels)
        counter.increment(amount, labels)

    def record_error(
        self,
        error_type: ErrorType | str,
        labels: dict[str, Any] | None = None,
        *,
        metric_name: str = "api_errors_total",
    ) -> None:
        """Record an error with a typed error label.

        Args:
            error_type: The type of error.
            labels: Additional labels.
            metric_name: Override the metric name.
        """
        merged = dict(labels or {})
        merged["type"] = error_type.value if isinstance(error_type, ErrorType) else str(error_type)
        self.increment_error(metric_name, labels=merged)

    # -- Throughput ----------------------------------------------------------

    def increment_throughput(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Increment a throughput counter.

        Args:
            name: Metric name (e.g., "api_requests_total").
            amount: Increment amount.
            labels: Optional labels.
        """
        counter = self._registry.register_throughput(name, labels)
        counter.increment(amount, labels)

    # -- Resource utilization -------------------------------------------------

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Set a resource utilization gauge.

        Args:
            name: Metric name (e.g., "dc_cpu_utilization").
            value: Current value (typically 0.0 to 1.0 for ratios).
            labels: Optional labels.
        """
        gauge = self._registry.register_gauge(name, labels)
        gauge.set(value, labels)

    def record_resource(
        self,
        resource_type: ResourceType | str,
        value: float,
        labels: dict[str, Any] | None = None,
        *,
        metric_name: str | None = None,
    ) -> None:
        """Record a resource utilization gauge with a typed resource label.

        Args:
            resource_type: The type of resource.
            value: Current utilization (0.0 to 1.0).
            labels: Additional labels.
            metric_name: Override the metric name.
        """
        merged = dict(labels or {})
        merged["resource"] = resource_type.value if isinstance(resource_type, ResourceType) else str(resource_type)
        name = metric_name or f"dc_{merged['resource']}_utilization"
        self.set_gauge(name, value, merged)

    # -- Timing decorator -----------------------------------------------------

    def timed(
        self,
        name: str,
        labels: dict[str, Any] | None = None,
        *,
        buckets: Iterable[float] | None = None,
    ) -> Callable:
        """Decorator that records function execution time as a histogram.

        Usage:
            @engine.timed("api_request_duration_seconds", labels={"route": "/v1/assets"})
            def handle_request():
                ...
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.monotonic()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed = time.monotonic() - start
                    self.record_latency(name, elapsed, labels, buckets=buckets)
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        return decorator

    # -- Export ---------------------------------------------------------------

    def render(self) -> str:
        """Render all metrics in Prometheus text format."""
        return render_prometheus_text(self._registry)

    def reset(self) -> None:
        """Reset all metrics."""
        self._registry.reset_all()

    # -- Snapshot -------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all current metric values."""
        result: dict[str, Any] = {
            "counters": {},
            "gauges": {},
            "histograms": {},
            "throughputs": {},
        }
        for name in self._registry.counter_names:
            counter = self._registry.get_counter(name)
            if counter:
                with counter._lock:
                    result["counters"][name] = {
                        str(k): v.value for k, v in counter._series.items()
                    }
        for name in self._registry.gauge_names:
            gauge = self._registry.get_gauge(name)
            if gauge:
                with gauge._lock:
                    result["gauges"][name] = {
                        str(k): v.value for k, v in gauge._series.items()
                    }
        for name in self._registry.histogram_names:
            hist = self._registry.get_histogram(name)
            if hist:
                with hist._lock:
                    result["histograms"][name] = {}
                    for k, v in hist._series.items():
                        result["histograms"][name][str(k)] = {
                            "count": v.count,
                            "sum": v.sum,
                            "buckets": dict(v.buckets),
                        }
        for name in self._registry.throughput_names:
            tp = self._registry.get_throughput(name)
            if tp:
                with tp._lock:
                    result["throughputs"][name] = {
                        str(k): v.value for k, v in tp._series.items()
                    }
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_engine: MetricsEngine | None = None
_default_lock = threading.Lock()


def get_metrics_engine() -> MetricsEngine:
    """Return the process-wide default metrics engine."""
    global _default_engine
    if _default_engine is None:
        with _default_lock:
            if _default_engine is None:
                _default_engine = MetricsEngine()
    return _default_engine
