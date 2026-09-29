"""Maintenance scheduling optimization based on load forecasts.

Advisory module: recommends optimal maintenance windows by correlating
equipment failure risk with predicted load minima. All outputs are
recommendations for qualified human review — no work orders, permits,
or physical actions are created or executed.

Pure stdlib implementation: no numpy / pandas / sklearn required.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from .failure import AssetRiskProfile
from .load import ForecastPoint, LoadObservation


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceConstraint:
    """Constraints that bound feasible maintenance windows."""
    min_notice_hours: float = 24.0
    max_consecutive_hours: float = 8.0
    preferred_start_hour: int = 0  # 0-23, local time preference
    preferred_end_hour: int = 6    # 0-23, local time preference
    min_gap_between_windows_hours: float = 4.0
    max_windows_per_day: int = 2
    blackout_weekdays: frozenset[int] = frozenset()  # 0=Mon, 6=Sun
    require_low_load: bool = True
    low_load_threshold_pct: float = 0.60  # fraction of peak below which is "low"


@dataclass
class MaintenanceWindow:
    """A recommended maintenance window."""
    asset_id: str
    asset_name: str
    start: datetime
    end: datetime
    duration_hours: float
    predicted_load_kw: float
    load_pct_of_peak: float
    risk_score: float
    risk_level: str
    confidence: str  # "high", "medium", "low"
    rationale: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class MaintenanceSchedule:
    """Complete maintenance schedule for a planning horizon."""
    tenant_id: str
    generated_at: datetime
    horizon_days: int
    windows: list[MaintenanceWindow] = field(default_factory=list)
    unscheduled: list[dict[str, Any]] = field(default_factory=list)
    model_version: str = "1.0.0"
    model_policy: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Load profile analysis
# ---------------------------------------------------------------------------


def _compute_load_profile(
    forecast_points: Sequence[ForecastPoint],
) -> dict[str, Any]:
    """Compute summary statistics from a load forecast."""
    if not forecast_points:
        return {
            "peak_kw": 0.0,
            "mean_kw": 0.0,
            "min_kw": 0.0,
            "min_timestamp": None,
            "values": [],
        }
    values = [p.predicted for p in forecast_points]
    peak = max(values)
    mean_val = statistics.fmean(values)
    min_val = min(values)
    min_idx = values.index(min_val)
    return {
        "peak_kw": peak,
        "mean_kw": mean_val,
        "min_kw": min_val,
        "min_timestamp": forecast_points[min_idx].timestamp,
        "values": values,
    }


def _find_low_load_periods(
    forecast_points: Sequence[ForecastPoint],
    threshold_pct: float,
    min_duration_hours: float = 2.0,
    interval_minutes: int = 60,
) -> list[tuple[datetime, datetime, float]]:
    """Find contiguous periods where predicted load is below threshold.

    Returns list of (start, end, mean_load_kw) tuples.
    """
    if not forecast_points:
        return []
    values = [p.predicted for p in forecast_points]
    peak = max(values)
    if peak <= 0:
        return []
    threshold = peak * threshold_pct

    periods: list[tuple[datetime, datetime, float]] = []
    current_start: datetime | None = None
    current_values: list[float] = []

    for i, point in enumerate(forecast_points):
        if point.predicted <= threshold:
            if current_start is None:
                current_start = point.timestamp
                current_values = [point.predicted]
            else:
                current_values.append(point.predicted)
        else:
            if current_start is not None and current_values:
                end = forecast_points[i - 1].timestamp
                duration = (end - current_start).total_seconds() / 3600.0
                if duration >= min_duration_hours:
                    periods.append((current_start, end, statistics.fmean(current_values)))
            current_start = None
            current_values = []

    # Handle period extending to end of forecast
    if current_start is not None and current_values:
        end = forecast_points[-1].timestamp
        duration = (end - current_start).total_seconds() / 3600.0
        if duration >= min_duration_hours:
            periods.append((current_start, end, statistics.fmean(current_values)))

    return periods


# ---------------------------------------------------------------------------
# Window scoring
# ---------------------------------------------------------------------------


def _score_window(
    start: datetime,
    end: datetime,
    mean_load_kw: float,
    peak_kw: float,
    risk_profile: AssetRiskProfile,
    constraints: MaintenanceConstraint,
    now: datetime,
) -> tuple[float, list[str]]:
    """Score a candidate maintenance window. Higher is better.

    Returns (score, rationale).
    """
    rationale: list[str] = []
    score = 0.0

    # Load factor: lower load = higher score (0-40 points)
    if peak_kw > 0:
        load_pct = mean_load_kw / peak_kw
        load_score = (1.0 - load_pct) * 40.0
        score += load_score
        rationale.append(
            f"predicted load {mean_load_kw:.1f} kW ({load_pct:.0%} of peak)"
        )
    else:
        score += 40.0
        rationale.append("no load forecast available")

    # Risk urgency: higher risk = more urgent = schedule sooner (0-30 points)
    risk_score = risk_profile.risk_score * 30.0
    score += risk_score
    rationale.append(
        f"asset risk {risk_profile.risk_score:.2f} ({risk_profile.risk_level})"
    )

    # Time preference: preferred hours get bonus (0-15 points)
    start_hour = start.hour
    if constraints.preferred_start_hour <= start_hour < constraints.preferred_end_hour:
        score += 15.0
        rationale.append("within preferred maintenance hours")
    elif start_hour < constraints.preferred_start_hour:
        score += 5.0
        rationale.append("early morning start")

    # Notice period: windows too soon get penalty
    hours_until = (start - now).total_seconds() / 3600.0
    if hours_until < constraints.min_notice_hours:
        score -= 20.0
        rationale.append(
            f"insufficient notice ({hours_until:.1f}h < {constraints.min_notice_hours:.0f}h)"
        )
    elif hours_until < constraints.min_notice_hours * 2:
        score -= 5.0
        rationale.append("short notice period")

    # Duration fit: prefer windows that fit well within low-load period
    window_duration = (end - start).total_seconds() / 3600.0
    if window_duration <= constraints.max_consecutive_hours:
        score += 10.0
        rationale.append(f"duration {window_duration:.1f}h within limit")
    else:
        score -= 10.0
        rationale.append(f"duration {window_duration:.1f}h exceeds preferred limit")

    # Criticality bonus: critical assets get priority scheduling
    if risk_profile.criticality == "critical":
        score += 5.0
        rationale.append("critical asset priority")
    elif risk_profile.criticality == "high":
        score += 2.0

    return score, rationale


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _check_conflicts(
    start: datetime,
    end: datetime,
    asset_id: str,
    existing_windows: Sequence[MaintenanceWindow],
    constraints: MaintenanceConstraint,
) -> list[str]:
    """Check for scheduling conflicts with existing windows."""
    conflicts: list[str] = []
    for w in existing_windows:
        if w.asset_id == asset_id:
            continue  # Same asset can have sequential windows
        # Check temporal overlap
        if start < w.end and end > w.start:
            conflicts.append(
                f"overlaps with {w.asset_name} window "
                f"({w.start.isoformat()} to {w.end.isoformat()})"
            )
    return conflicts


# ---------------------------------------------------------------------------
# Core scheduling algorithm
# ---------------------------------------------------------------------------


def _select_best_window(
    risk_profile: AssetRiskProfile,
    low_load_periods: Sequence[tuple[datetime, datetime, float]],
    peak_kw: float,
    constraints: MaintenanceConstraint,
    existing_windows: Sequence[MaintenanceWindow],
    now: datetime,
    interval_minutes: int = 60,
) -> MaintenanceWindow | None:
    """Select the best maintenance window for a single asset."""
    if not low_load_periods:
        return None

    best_window: MaintenanceWindow | None = None
    best_score = float("-inf")

    for period_start, period_end, mean_load in low_load_periods:
        # Generate candidate windows within this low-load period
        # Use adaptive duration: min of max_consecutive_hours and period length
        period_duration_hours = (period_end - period_start).total_seconds() / 3600.0
        duration = min(constraints.max_consecutive_hours, period_duration_hours)
        if duration < 1.0:
            continue
        candidate_start = period_start
        while candidate_start + timedelta(hours=duration) <= period_end:
            candidate_end = candidate_start + timedelta(hours=duration)

            # Skip if in the past
            if candidate_end <= now:
                candidate_start += timedelta(minutes=interval_minutes)
                continue

            # Check conflicts
            conflicts = _check_conflicts(
                candidate_start, candidate_end,
                risk_profile.asset_id, existing_windows, constraints,
            )

            # Score this candidate
            score, rationale = _score_window(
                candidate_start, candidate_end,
                mean_load, peak_kw,
                risk_profile, constraints, now,
            )

            # Penalize conflicts
            if conflicts:
                score -= 15.0 * len(conflicts)

            if score > best_score:
                best_score = score
                # Determine confidence based on data quality
                if risk_profile.metric_summaries and peak_kw > 0:
                    confidence = "high"
                elif risk_profile.metric_summaries or peak_kw > 0:
                    confidence = "medium"
                else:
                    confidence = "low"

                best_window = MaintenanceWindow(
                    asset_id=risk_profile.asset_id,
                    asset_name=risk_profile.asset_name,
                    start=candidate_start,
                    end=candidate_end,
                    duration_hours=duration,
                    predicted_load_kw=round(mean_load, 2),
                    load_pct_of_peak=round(mean_load / peak_kw, 4) if peak_kw > 0 else 0.0,
                    risk_score=risk_profile.risk_score,
                    risk_level=risk_profile.risk_level,
                    confidence=confidence,
                    rationale=rationale,
                    conflicts=conflicts,
                )

            candidate_start += timedelta(minutes=interval_minutes)

    return best_window


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def optimize_maintenance_windows(
    *,
    tenant_id: str,
    risk_profiles: Sequence[AssetRiskProfile],
    forecast_points: Sequence[ForecastPoint],
    constraints: MaintenanceConstraint | None = None,
    existing_windows: Sequence[MaintenanceWindow] = (),
    horizon_days: int = 14,
    now: datetime | None = None,
    interval_minutes: int = 60,
) -> MaintenanceSchedule:
    """Optimize maintenance windows based on load forecasts and asset risk.

    This is an advisory function. It recommends optimal maintenance windows
    by correlating equipment failure risk with predicted load minima.
    All outputs require qualified human review and approval.

    Args:
        tenant_id: Tenant UUID for scoping.
        risk_profiles: Asset risk profiles from failure prediction.
        forecast_points: Load forecast points from a forecaster.
        constraints: Scheduling constraints (uses defaults if None).
        existing_windows: Already-scheduled maintenance windows to avoid.
        horizon_days: Planning horizon in days.
        now: Reference time (defaults to UTC now).
        interval_minutes: Time resolution for window placement.

    Returns:
        MaintenanceSchedule with recommended windows and unscheduled assets.
    """
    if constraints is None:
        constraints = MaintenanceConstraint()
    if now is None:
        now = datetime.now(timezone.utc)

    # Compute load profile
    load_profile = _compute_load_profile(forecast_points)
    peak_kw = load_profile["peak_kw"]

    # Find low-load periods
    low_load_periods = _find_low_load_periods(
        forecast_points,
        constraints.low_load_threshold_pct,
        min_duration_hours=min(2.0, constraints.max_consecutive_hours),
        interval_minutes=interval_minutes,
    )

    # Sort risk profiles by urgency (risk score descending, criticality first)
    def sort_key(p: AssetRiskProfile) -> tuple[float, float, int]:
        crit_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return (
            -p.risk_score,
            crit_order.get(p.criticality, 2),
            -p.anomaly_count,
        )

    sorted_profiles = sorted(risk_profiles, key=sort_key)

    # Track assets that already have windows (from existing_windows)
    scheduled_asset_ids: set[str] = {w.asset_id for w in existing_windows}

    # Greedy assignment: schedule highest-risk assets first
    windows: list[MaintenanceWindow] = list(existing_windows)
    unscheduled: list[dict[str, Any]] = []

    for profile in sorted_profiles:
        # Skip assets that already have a scheduled window
        if profile.asset_id in scheduled_asset_ids:
            continue
        # Skip very low risk assets if no low-load periods exist
        if profile.risk_level == "low" and not low_load_periods:
            unscheduled.append({
                "asset_id": profile.asset_id,
                "asset_name": profile.asset_name,
                "risk_score": profile.risk_score,
                "risk_level": profile.risk_level,
                "reason": "low risk and no suitable low-load window found",
            })
            continue

        window = _select_best_window(
            profile,
            low_load_periods,
            peak_kw,
            constraints,
            windows,
            now,
            interval_minutes,
        )

        if window is not None:
            windows.append(window)
            scheduled_asset_ids.add(profile.asset_id)
        else:
            unscheduled.append({
                "asset_id": profile.asset_id,
                "asset_name": profile.asset_name,
                "risk_score": profile.risk_score,
                "risk_level": profile.risk_level,
                "reason": "no feasible window found within constraints",
            })

    # Sort windows by risk priority (highest risk first)
    crit_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    windows.sort(key=lambda w: (-w.risk_score, crit_order.get(w.risk_level, 2)))

    return MaintenanceSchedule(
        tenant_id=tenant_id,
        generated_at=now,
        horizon_days=horizon_days,
        windows=windows,
        unscheduled=unscheduled,
        model_version="1.0.0",
        model_policy={
            "algorithm": "greedy-risk-priority",
            "load_threshold_pct": constraints.low_load_threshold_pct,
            "max_consecutive_hours": constraints.max_consecutive_hours,
            "min_notice_hours": constraints.min_notice_hours,
            "note": (
                "Advisory recommendation only. "
                "All windows require qualified human review, "
                "approved procedures, and valid permits before execution."
            ),
        },
    )


def schedule_to_dict(schedule: MaintenanceSchedule) -> dict[str, Any]:
    """Convert a MaintenanceSchedule to a JSON-serializable dict."""
    return {
        "tenant_id": schedule.tenant_id,
        "generated_at": schedule.generated_at.isoformat(),
        "horizon_days": schedule.horizon_days,
        "model_version": schedule.model_version,
        "model_policy": schedule.model_policy,
        "windows": [
            {
                "asset_id": w.asset_id,
                "asset_name": w.asset_name,
                "start": w.start.isoformat(),
                "end": w.end.isoformat(),
                "duration_hours": w.duration_hours,
                "predicted_load_kw": w.predicted_load_kw,
                "load_pct_of_peak": w.load_pct_of_peak,
                "risk_score": w.risk_score,
                "risk_level": w.risk_level,
                "confidence": w.confidence,
                "rationale": w.rationale,
                "conflicts": w.conflicts,
            }
            for w in schedule.windows
        ],
        "unscheduled": schedule.unscheduled,
        "summary": {
            "total_windows": len(schedule.windows),
            "total_unscheduled": len(schedule.unscheduled),
            "high_risk_scheduled": sum(
                1 for w in schedule.windows if w.risk_level in ("high", "critical")
            ),
            "mean_load_pct_of_peak": (
                statistics.fmean(w.load_pct_of_peak for w in schedule.windows)
                if schedule.windows else 0.0
            ),
        },
        "read_only": True,
        "execution_permitted": False,
    }


# ---------------------------------------------------------------------------
# Convenience: build forecast from observations
# ---------------------------------------------------------------------------


def build_forecast_from_observations(
    observations: Sequence[LoadObservation],
    horizon_hours: int = 168,
    interval_minutes: int = 60,
) -> list[ForecastPoint]:
    """Build a simple forecast from historical observations.

    Uses the best available model from the load forecasting module.
    This is a convenience wrapper — production callers should use
    the full model selection pipeline.
    """
    if not observations:
        return []

    from .load import select_best_model

    try:
        _, result = select_best_model(
            observations,
            validation_split=0.2,
            interval_minutes=interval_minutes,
        )
        # Extend or trim to requested horizon
        points = result.points[:horizon_hours]
        return points
    except ValueError:
        # Not enough data for model selection — use simple average
        from .load import MovingAverageForecaster

        forecaster = MovingAverageForecaster(window=min(24, len(observations)))
        result = forecaster.forecast(observations, horizon_hours, interval_minutes)
        return result.points
