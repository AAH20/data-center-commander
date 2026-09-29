"""Equipment failure prediction from telemetry patterns.

Read-only statistical model that scores failure risk per asset using
telemetry anomaly detection, degradation trend analysis, and criticality
weighting. No external ML dependencies — pure stdlib implementation.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TelemetryPoint:
    """A single telemetry reading."""
    observed_at: datetime
    value: float
    quality_status: str = "good"
    metric_key: str = ""


@dataclass
class AssetRiskProfile:
    """Failure risk assessment for one asset."""
    asset_id: str
    asset_name: str
    asset_type: str
    criticality: str
    lifecycle_state: str
    risk_score: float  # 0.0 - 1.0
    risk_level: str  # "low", "medium", "high", "critical"
    contributing_factors: list[str] = field(default_factory=list)
    metric_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    anomaly_count: int = 0
    trend_degradation: bool = False
    days_since_last_reading: int | None = None
    recommended_action: str = "none"


@dataclass
class FailurePredictionResult:
    """Complete prediction result for a tenant."""
    tenant_id: str
    generated_at: datetime
    window_days: int
    total_assets: int
    assets_with_telemetry: int
    risk_profiles: list[AssetRiskProfile] = field(default_factory=list)
    model_version: str = "1.0.0"
    model_policy: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _parse_telemetry_rows(rows: list[dict]) -> dict[str, list[TelemetryPoint]]:
    """Group telemetry rows by asset_id, sorted by time."""
    by_asset: dict[str, list[TelemetryPoint]] = {}
    for row in rows:
        asset_id = str(row.get("asset_id", ""))
        if not asset_id:
            continue
        value = row.get("value_numeric")
        if value is None:
            continue
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(val):
            continue
        observed_at = row.get("observed_at")
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
        elif not isinstance(observed_at, datetime):
            continue
        point = TelemetryPoint(
            observed_at=observed_at,
            value=val,
            quality_status=str(row.get("quality_status", "good")),
            metric_key=str(row.get("metric_key", "")),
        )
        by_asset.setdefault(asset_id, []).append(point)
    for points in by_asset.values():
        points.sort(key=lambda p: p.observed_at)
    return by_asset


def _compute_metric_keyed_series(
    points: list[TelemetryPoint],
) -> dict[str, list[TelemetryPoint]]:
    """Group points by metric_key for per-metric analysis."""
    by_metric: dict[str, list[TelemetryPoint]] = {}
    for p in points:
        key = p.metric_key or "unknown"
        by_metric.setdefault(key, []).append(p)
    return by_metric


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def _detect_anomalies_zscore(
    values: list[float], threshold: float = 3.0
) -> list[int]:
    """Return indices of values exceeding z-score threshold."""
    if len(values) < 3:
        return []
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    if stdev == 0:
        return []
    anomalies = []
    for i, v in enumerate(values):
        z = abs(v - mean) / stdev
        if z > threshold:
            anomalies.append(i)
    return anomalies


def _detect_anomalies_iqr(values: list[float]) -> list[int]:
    """Return indices of values outside 1.5*IQR bounds."""
    if len(values) < 4:
        return []
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    if iqr == 0:
        return []
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [i for i, v in enumerate(values) if v < lower or v > upper]


def _detect_anomalies_ewma(
    values: list[float], alpha: float = 0.3, threshold: float = 3.0
) -> list[int]:
    """EWMA-based anomaly detection using first half as baseline.

    Uses the first half of the data to establish a baseline mean and
    standard deviation, then flags points in the second half that
    exceed the threshold. Also requires the shift to be significant
    relative to the baseline mean to avoid false positives on small trends.
    """
    if len(values) < 10:
        return []
    mid = len(values) // 2
    baseline = values[:mid]
    baseline_mean = statistics.mean(baseline)
    baseline_stdev = statistics.stdev(baseline) if len(baseline) > 1 else 0
    if baseline_stdev == 0:
        return [i for i in range(mid, len(values)) if values[i] != baseline_mean]
    anomalies = []
    for i in range(mid, len(values)):
        z = abs(values[i] - baseline_mean) / baseline_stdev
        if z > threshold and abs(values[i] - baseline_mean) > 0.1 * abs(baseline_mean):
            anomalies.append(i)
    return anomalies


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

def _compute_trend_slope(values: list[float]) -> float:
    """Simple linear regression slope."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = statistics.mean(values)
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _detect_degradation(values: list[float], window: int = 5) -> bool:
    """Detect sustained degradation: second half significantly shifted from first half."""
    if len(values) < window * 2:
        return False
    mid = len(values) // 2
    baseline = values[:mid]
    recent = values[mid:]
    if not baseline or not recent:
        return False
    recent_mean = statistics.mean(recent)
    baseline_mean = statistics.mean(baseline)
    baseline_stdev = statistics.stdev(baseline) if len(baseline) > 1 else 0
    shift = abs(recent_mean - baseline_mean)
    if baseline_stdev == 0:
        # No variance in baseline: flag if shift is > 10% of baseline mean
        return shift > 0.1 * abs(baseline_mean) if baseline_mean != 0 else shift > 0
    # Degradation = shift is statistically significant AND practically significant
    return shift > 1.5 * baseline_stdev and shift > 0.05 * abs(baseline_mean)


def _compute_volatility(values: list[float]) -> float:
    """Coefficient of variation as volatility measure."""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    return statistics.stdev(values) / abs(mean)


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

_CRITICALITY_WEIGHTS = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}

_LIFECYCLE_RISK = {
    "active": 0.0,
    "commissioning": 0.15,
    "maintenance": 0.3,
    "impaired": 0.5,
    "retiring": 0.2,
    "installed": 0.05,
    "procured": 0.0,
    "planned": 0.0,
    "retired": 0.0,
    "disposed": 0.0,
    "unknown": 0.1,
}


def _score_asset_risk(
    asset: dict[str, Any],
    points: list[TelemetryPoint],
    now: datetime,
) -> AssetRiskProfile:
    """Compute failure risk score for a single asset."""
    asset_id = str(asset.get("id", ""))
    asset_name = str(asset.get("name", ""))
    asset_type = str(asset.get("asset_type", ""))
    criticality = str(asset.get("criticality", "medium"))
    lifecycle_state = str(asset.get("lifecycle_state", "active"))

    factors: list[str] = []
    metric_summaries: dict[str, dict[str, Any]] = {}
    total_anomalies = 0
    any_degradation = False

    by_metric = _compute_metric_keyed_series(points)

    for metric_key, metric_points in by_metric.items():
        values = [p.value for p in metric_points]
        if not values:
            continue

        # Anomaly detection (combine methods)
        zscore_anomalies = set(_detect_anomalies_zscore(values))
        iqr_anomalies = set(_detect_anomalies_iqr(values))
        ewma_anomalies = set(_detect_anomalies_ewma(values))
        combined_anomalies = zscore_anomalies | iqr_anomalies | ewma_anomalies
        total_anomalies += len(combined_anomalies)

        # Trend analysis
        slope = _compute_trend_slope(values)
        degradation = _detect_degradation(values)
        volatility = _compute_volatility(values)
        if degradation:
            any_degradation = True

        # Quality check
        bad_quality = sum(1 for p in metric_points if p.quality_status in ("bad", "suspect", "missing"))

        metric_summaries[metric_key] = {
            "count": len(values),
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "slope": slope,
            "volatility": volatility,
            "anomaly_count": len(combined_anomalies),
            "bad_quality_count": bad_quality,
            "degradation_detected": degradation,
        }

        if len(combined_anomalies) > 0:
            factors.append(f"{metric_key}: {len(combined_anomalies)} anomalies detected")
        if degradation:
            factors.append(f"{metric_key}: degradation trend detected")
        if volatility > 0.5:
            factors.append(f"{metric_key}: high volatility ({volatility:.2f})")
        if bad_quality > len(values) * 0.2:
            factors.append(f"{metric_key}: {bad_quality} low-quality readings")

    # Compute composite risk score
    crit_weight = _CRITICALITY_WEIGHTS.get(criticality, 0.5)
    lifecycle_risk = _LIFECYCLE_RISK.get(lifecycle_state, 0.1)

    # Anomaly contribution (more anomalies = higher risk, capped)
    # Each anomaly contributes meaningfully; 5+ anomalies is high risk
    anomaly_score = min(total_anomalies / 5.0, 1.0) * 0.35

    # Degradation contribution
    degradation_score = 0.3 if any_degradation else 0.0

    # Data staleness contribution
    days_since = None
    staleness_score = 0.0
    if points:
        last_reading = max(p.observed_at for p in points)
        if last_reading.tzinfo is None:
            last_reading = last_reading.replace(tzinfo=timezone.utc)
        delta = now - last_reading
        days_since = max(0, delta.days)
        if days_since > 7:
            staleness_score = min(days_since / 30.0, 1.0) * 0.15
            factors.append(f"no telemetry for {days_since} days")
    else:
        # No telemetry at all — treat as stale
        days_since = 999
        staleness_score = 0.15
        factors.append("no telemetry data available")

    # Combine scores
    base_risk = lifecycle_risk
    telemetry_risk = anomaly_score + degradation_score + staleness_score
    risk_score = min(1.0, base_risk + telemetry_risk * crit_weight)

    # Determine risk level
    if risk_score >= 0.75:
        risk_level = "critical"
    elif risk_score >= 0.5:
        risk_level = "high"
    elif risk_score >= 0.25:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Recommended action
    if risk_level == "critical":
        action = "immediate_inspection"
    elif risk_level == "high":
        action = "schedule_maintenance"
    elif risk_level == "medium":
        action = "increase_monitoring"
    else:
        action = "none"

    if not factors and risk_level == "low":
        factors.append("no significant risk indicators")

    return AssetRiskProfile(
        asset_id=asset_id,
        asset_name=asset_name,
        asset_type=asset_type,
        criticality=criticality,
        lifecycle_state=lifecycle_state,
        risk_score=round(risk_score, 4),
        risk_level=risk_level,
        contributing_factors=factors,
        metric_summaries=metric_summaries,
        anomaly_count=total_anomalies,
        trend_degradation=any_degradation,
        days_since_last_reading=days_since,
        recommended_action=action,
    )


# ---------------------------------------------------------------------------
# Main prediction function
# ---------------------------------------------------------------------------

def predict_equipment_failures(
    *,
    tenant_id: str,
    assets: list[dict[str, Any]],
    telemetry_rows: list[dict[str, Any]],
    window_days: int = 30,
    now: datetime | None = None,
) -> FailurePredictionResult:
    """Predict equipment failure risk from telemetry patterns.

    Args:
        tenant_id: Tenant UUID for scoping.
        assets: List of asset dicts from dcc.assets.
        telemetry_rows: List of telemetry reading dicts from dcc.telemetry_readings.
        window_days: Analysis window in days.
        now: Reference time (defaults to UTC now).

    Returns:
        FailurePredictionResult with per-asset risk profiles.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Parse and group telemetry by asset
    telemetry_by_asset = _parse_telemetry_rows(telemetry_rows)

    # Score each asset
    profiles: list[AssetRiskProfile] = []
    for asset in assets:
        asset_id = str(asset.get("id", ""))
        points = telemetry_by_asset.get(asset_id, [])
        if not points:
            # No telemetry — still create a profile with lifecycle-based risk
            profile = _score_asset_risk(asset, [], now)
            profiles.append(profile)
            continue
        profile = _score_asset_risk(asset, points, now)
        profiles.append(profile)

    # Sort by risk score descending
    profiles.sort(key=lambda p: p.risk_score, reverse=True)

    assets_with_telemetry = sum(1 for p in profiles if p.metric_summaries)

    return FailurePredictionResult(
        tenant_id=tenant_id,
        generated_at=now,
        window_days=window_days,
        total_assets=len(assets),
        assets_with_telemetry=assets_with_telemetry,
        risk_profiles=profiles,
        model_version="1.0.0",
        model_policy={
            "anomaly_methods": ["zscore", "iqr", "ewma"],
            "zscore_threshold": 3.0,
            "ewma_alpha": 0.3,
            "degradation_window": 5,
            "degradation_stdev_threshold": 1.5,
            "staleness_threshold_days": 7,
            "criticality_weights": _CRITICALITY_WEIGHTS,
            "lifecycle_risk": _LIFECYCLE_RISK,
            "note": "Statistical baseline model; not a trained ML classifier. Scores indicate relative risk for prioritization, not absolute failure probability.",
        },
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def result_to_dict(result: FailurePredictionResult) -> dict[str, Any]:
    """Convert prediction result to a JSON-serializable dict."""
    return {
        "tenant_id": result.tenant_id,
        "generated_at": result.generated_at.isoformat(),
        "window_days": result.window_days,
        "total_assets": result.total_assets,
        "assets_with_telemetry": result.assets_with_telemetry,
        "model_version": result.model_version,
        "model_policy": result.model_policy,
        "risk_profiles": [
            {
                "asset_id": p.asset_id,
                "asset_name": p.asset_name,
                "asset_type": p.asset_type,
                "criticality": p.criticality,
                "lifecycle_state": p.lifecycle_state,
                "risk_score": p.risk_score,
                "risk_level": p.risk_level,
                "contributing_factors": p.contributing_factors,
                "metric_summaries": p.metric_summaries,
                "anomaly_count": p.anomaly_count,
                "trend_degradation": p.trend_degradation,
                "days_since_last_reading": p.days_since_last_reading,
                "recommended_action": p.recommended_action,
            }
            for p in result.risk_profiles
        ],
        "summary": {
            "critical_count": sum(1 for p in result.risk_profiles if p.risk_level == "critical"),
            "high_count": sum(1 for p in result.risk_profiles if p.risk_level == "high"),
            "medium_count": sum(1 for p in result.risk_profiles if p.risk_level == "medium"),
            "low_count": sum(1 for p in result.risk_profiles if p.risk_level == "low"),
            "total_anomalies": sum(p.anomaly_count for p in result.risk_profiles),
            "assets_with_degradation": sum(1 for p in result.risk_profiles if p.trend_degradation),
        },
        "read_only": True,
        "execution_permitted": False,
    }
