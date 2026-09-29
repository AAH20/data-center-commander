"""SLO/SLA tracking: availability, latency, and error budget monitoring.

Provides classes and functions for tracking Service Level Objectives (SLOs)
and Service Level Agreements (SLAs) including:
- Availability SLOs (uptime percentage)
- Latency SLOs (response time percentiles)
- Error budget tracking (burn rate, remaining budget)
- SLA compliance reporting

All calculations are pure-Python with no external dependencies.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SLOStatus(str, Enum):
    """Status of an SLO against its target."""

    OK = "ok"
    WARNING = "warning"
    VIOLATION = "violation"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AvailabilitySLO:
    """Availability SLO: percentage of successful requests over total requests.

    Attributes:
        name: Human-readable SLO name.
        target_pct: Target availability percentage (0-100).
        window_days: Rolling window in days.
        total_requests: Total requests in the window.
        failed_requests: Failed requests in the window.
    """

    name: str
    target_pct: float
    window_days: int
    total_requests: int
    failed_requests: int

    @property
    def availability_pct(self) -> float:
        """Actual availability percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.total_requests - self.failed_requests) / self.total_requests * 100.0

    @property
    def error_rate_pct(self) -> float:
        """Error rate percentage."""
        return 100.0 - self.availability_pct

    @property
    def status(self) -> SLOStatus:
        """Evaluate SLO status against target."""
        if self.total_requests == 0:
            return SLOStatus.UNKNOWN
        if self.availability_pct >= self.target_pct:
            return SLOStatus.OK
        # Warning if within 0.5% of target
        if self.availability_pct >= self.target_pct - 0.5:
            return SLOStatus.WARNING
        return SLOStatus.VIOLATION

    @property
    def error_budget_remaining_pct(self) -> float:
        """Remaining error budget as a percentage of total requests.

        Error budget = (100 - target_pct) - (100 - availability_pct)
        """
        budget = (100.0 - self.target_pct) - (100.0 - self.availability_pct)
        return budget

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_pct": self.target_pct,
            "window_days": self.window_days,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "availability_pct": round(self.availability_pct, 4),
            "error_rate_pct": round(self.error_rate_pct, 4),
            "status": self.status.value,
            "error_budget_remaining_pct": round(self.error_budget_remaining_pct, 4),
        }


@dataclass(frozen=True)
class LatencySLO:
    """Latency SLO: response time percentile within a threshold.

    Attributes:
        name: Human-readable SLO name.
        target_ms: Target latency in milliseconds.
        percentile: Target percentile (e.g., 95, 99).
        window_days: Rolling window in days.
        latencies_ms: List of observed latencies in milliseconds.
    """

    name: str
    target_ms: float
    percentile: float
    window_days: int
    latencies_ms: list[float]

    @property
    def actual_percentile_ms(self) -> float:
        """Actual latency at the target percentile."""
        if not self.latencies_ms:
            return 0.0
        return _percentile(self.latencies_ms, self.percentile)

    @property
    def status(self) -> SLOStatus:
        """Evaluate SLO status against target."""
        if not self.latencies_ms:
            return SLOStatus.UNKNOWN
        actual = self.actual_percentile_ms
        if actual <= self.target_ms:
            return SLOStatus.OK
        # Warning if within 20% of target
        if actual <= self.target_ms * 1.2:
            return SLOStatus.WARNING
        return SLOStatus.VIOLATION

    @property
    def mean_ms(self) -> float:
        """Mean latency in milliseconds."""
        if not self.latencies_ms:
            return 0.0
        return statistics.fmean(self.latencies_ms)

    @property
    def p50_ms(self) -> float:
        """Median (P50) latency in milliseconds."""
        return _percentile(self.latencies_ms, 50)

    @property
    def p95_ms(self) -> float:
        """P95 latency in milliseconds."""
        return _percentile(self.latencies_ms, 95)

    @property
    def p99_ms(self) -> float:
        """P99 latency in milliseconds."""
        return _percentile(self.latencies_ms, 99)

    @property
    def min_ms(self) -> float:
        """Minimum latency in milliseconds."""
        if not self.latencies_ms:
            return 0.0
        return min(self.latencies_ms)

    @property
    def max_ms(self) -> float:
        """Maximum latency in milliseconds."""
        if not self.latencies_ms:
            return 0.0
        return max(self.latencies_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_ms": self.target_ms,
            "percentile": self.percentile,
            "window_days": self.window_days,
            "sample_count": len(self.latencies_ms),
            "actual_percentile_ms": round(self.actual_percentile_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "status": self.status.value,
        }


@dataclass
class ErrorBudget:
    """Error budget tracking for an SLO.

    The error budget is the allowable amount of failure over a time window.
    It is calculated as: budget = (1 - target_availability) * total_requests

    Attributes:
        slo_name: Name of the SLO this budget belongs to.
        target_pct: Target availability percentage (0-100).
        window_days: Rolling window in days.
        total_requests: Total requests in the window.
        failed_requests: Failed requests in the window.
    """

    slo_name: str
    target_pct: float
    window_days: int
    total_requests: int
    failed_requests: int

    @property
    def budget_total(self) -> float:
        """Total error budget in number of requests."""
        if self.total_requests == 0:
            return 0.0
        return (100.0 - self.target_pct) / 100.0 * self.total_requests

    @property
    def budget_consumed(self) -> float:
        """Error budget consumed (number of failures)."""
        return float(self.failed_requests)

    @property
    def budget_remaining(self) -> float:
        """Error budget remaining (clamped to zero)."""
        return max(0.0, self.budget_total - self.budget_consumed)

    @property
    def budget_remaining_pct(self) -> float:
        """Error budget remaining as a percentage of total budget."""
        if self.budget_total == 0:
            return 100.0
        return max(0.0, self.budget_remaining / self.budget_total * 100.0)

    @property
    def burn_rate(self) -> float:
        """Burn rate: how fast the budget is being consumed.

        burn_rate = budget_consumed / budget_total
        A burn rate > 1.0 means the budget is being consumed faster than allowed.
        """
        if self.budget_total == 0:
            return 0.0
        return self.budget_consumed / self.budget_total

    @property
    def status(self) -> SLOStatus:
        """Evaluate error budget status."""
        if self.total_requests == 0:
            return SLOStatus.UNKNOWN
        if self.budget_remaining_pct > 50.0:
            return SLOStatus.OK
        if self.budget_remaining_pct > 20.0:
            return SLOStatus.WARNING
        return SLOStatus.VIOLATION

    @property
    def estimated_days_to_exhaustion(self) -> float | None:
        """Estimated days until error budget is exhausted.

        Returns None if budget is not being consumed.
        """
        if self.budget_consumed == 0 or self.total_requests == 0:
            return None
        # Daily burn rate
        daily_burn = self.budget_consumed / self.window_days
        if daily_burn == 0:
            return None
        return self.budget_remaining / daily_burn

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_name": self.slo_name,
            "target_pct": self.target_pct,
            "window_days": self.window_days,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "budget_total": round(self.budget_total, 2),
            "budget_consumed": round(self.budget_consumed, 2),
            "budget_remaining": round(self.budget_remaining, 2),
            "budget_remaining_pct": round(self.budget_remaining_pct, 2),
            "burn_rate": round(self.burn_rate, 4),
            "status": self.status.value,
            "estimated_days_to_exhaustion": round(self.estimated_days_to_exhaustion, 2)
            if self.estimated_days_to_exhaustion is not None
            else None,
        }


@dataclass
class SLATracking:
    """SLA compliance tracking for a service.

    Attributes:
        service_name: Name of the service.
        window_days: Rolling window in days.
        availability_slo: Availability SLO configuration.
        latency_slo: Latency SLO configuration.
        error_budget: Error budget tracking.
    """

    service_name: str
    window_days: int
    availability_slo: AvailabilitySLO
    latency_slo: LatencySLO | None = None
    error_budget: ErrorBudget | None = None

    @property
    def overall_status(self) -> SLOStatus:
        """Overall SLA status (worst of all components)."""
        statuses = [self.availability_slo.status]
        if self.latency_slo:
            statuses.append(self.latency_slo.status)
        if self.error_budget:
            statuses.append(self.error_budget.status)
        if SLOStatus.VIOLATION in statuses:
            return SLOStatus.VIOLATION
        if SLOStatus.WARNING in statuses:
            return SLOStatus.WARNING
        if SLOStatus.UNKNOWN in statuses:
            return SLOStatus.UNKNOWN
        return SLOStatus.OK

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "service_name": self.service_name,
            "window_days": self.window_days,
            "overall_status": self.overall_status.value,
            "availability": self.availability_slo.to_dict(),
        }
        if self.latency_slo:
            result["latency"] = self.latency_slo.to_dict()
        if self.error_budget:
            result["error_budget"] = self.error_budget.to_dict()
        return result


@dataclass
class SLOReport:
    """Complete SLO report for all tracked services.

    Attributes:
        generated_at: ISO timestamp of report generation.
        services: List of SLA tracking entries.
    """

    generated_at: str
    services: list[SLATracking] = field(default_factory=list)

    @property
    def overall_status(self) -> SLOStatus:
        """Overall status across all services."""
        if not self.services:
            return SLOStatus.UNKNOWN
        statuses = [s.overall_status for s in self.services]
        if SLOStatus.VIOLATION in statuses:
            return SLOStatus.VIOLATION
        if SLOStatus.WARNING in statuses:
            return SLOStatus.WARNING
        if SLOStatus.UNKNOWN in statuses:
            return SLOStatus.UNKNOWN
        return SLOStatus.OK

    @property
    def violations(self) -> list[str]:
        """List of services with violations."""
        return [s.service_name for s in self.services if s.overall_status == SLOStatus.VIOLATION]

    @property
    def warnings(self) -> list[str]:
        """List of services with warnings."""
        return [s.service_name for s in self.services if s.overall_status == SLOStatus.WARNING]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall_status": self.overall_status.value,
            "violations": self.violations,
            "warnings": self.warnings,
            "services": [s.to_dict() for s in self.services],
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _percentile(values: Sequence[float], p: float) -> float:
    """Calculate percentile using linear interpolation.

    Args:
        values: Sequence of numeric values.
        p: Percentile to calculate (0-100).

    Returns:
        The value at the given percentile.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    rank = (p / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def slo_status(
    actual_pct: float,
    target_pct: float,
    *,
    warning_threshold: float = 0.5,
) -> SLOStatus:
    """Evaluate SLO status from actual and target percentages.

    Args:
        actual_pct: Actual percentage (0-100).
        target_pct: Target percentage (0-100).
        warning_threshold: How far below target before warning (default 0.5%).

    Returns:
        SLOStatus indicating compliance level.
    """
    if actual_pct >= target_pct:
        return SLOStatus.OK
    if actual_pct >= target_pct - warning_threshold:
        return SLOStatus.WARNING
    return SLOStatus.VIOLATION


def availability_slo(
    name: str,
    target_pct: float,
    window_days: int,
    total_requests: int,
    failed_requests: int,
) -> AvailabilitySLO:
    """Create an AvailabilitySLO instance."""
    return AvailabilitySLO(
        name=name,
        target_pct=target_pct,
        window_days=window_days,
        total_requests=total_requests,
        failed_requests=failed_requests,
    )


def latency_slo(
    name: str,
    target_ms: float,
    percentile: float,
    window_days: int,
    latencies_ms: list[float],
) -> LatencySLO:
    """Create a LatencySLO instance."""
    return LatencySLO(
        name=name,
        target_ms=target_ms,
        percentile=percentile,
        window_days=window_days,
        latencies_ms=latencies_ms,
    )


def error_budget(
    slo_name: str,
    target_pct: float,
    window_days: int,
    total_requests: int,
    failed_requests: int,
) -> ErrorBudget:
    """Create an ErrorBudget instance."""
    return ErrorBudget(
        slo_name=slo_name,
        target_pct=target_pct,
        window_days=window_days,
        total_requests=total_requests,
        failed_requests=failed_requests,
    )


def sla_compliance(
    service_name: str,
    window_days: int,
    *,
    target_availability_pct: float = 99.9,
    target_latency_ms: float = 500.0,
    latency_percentile: float = 95.0,
    total_requests: int = 0,
    failed_requests: int = 0,
    latencies_ms: list[float] | None = None,
) -> SLATracking:
    """Create a complete SLATracking instance with all components.

    Args:
        service_name: Name of the service.
        window_days: Rolling window in days.
        target_availability_pct: Target availability percentage.
        target_latency_ms: Target latency in milliseconds.
        latency_percentile: Target latency percentile.
        total_requests: Total requests in the window.
        failed_requests: Failed requests in the window.
        latencies_ms: List of observed latencies.

    Returns:
        SLATracking with availability, latency, and error budget.
    """
    avail = AvailabilitySLO(
        name=f"{service_name}_availability",
        target_pct=target_availability_pct,
        window_days=window_days,
        total_requests=total_requests,
        failed_requests=failed_requests,
    )
    lat = LatencySLO(
        name=f"{service_name}_latency",
        target_ms=target_latency_ms,
        percentile=latency_percentile,
        window_days=window_days,
        latencies_ms=latencies_ms or [],
    )
    budget = ErrorBudget(
        slo_name=f"{service_name}_error_budget",
        target_pct=target_availability_pct,
        window_days=window_days,
        total_requests=total_requests,
        failed_requests=failed_requests,
    )
    return SLATracking(
        service_name=service_name,
        window_days=window_days,
        availability_slo=avail,
        latency_slo=lat,
        error_budget=budget,
    )


def build_slo_report(services: list[SLATracking]) -> SLOReport:
    """Build a complete SLO report from a list of services.

    Args:
        services: List of SLATracking instances.

    Returns:
        SLOReport with all services and overall status.
    """
    return SLOReport(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        services=services,
    )
