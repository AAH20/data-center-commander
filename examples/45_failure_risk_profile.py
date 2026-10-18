"""Example: Asset risk profile interpretation.

Examines the risk profile output for a single asset.
"""
from dcc.forecasting.failure import predict_equipment_failures

telemetry_rows = [
    {"asset_id": "GEN-1", "metric_key": "oil_pressure", "value_numeric": 42, "quality_status": "good", "observed_at": "2026-01-01T00:00:00Z"},
    {"asset_id": "GEN-1", "metric_key": "oil_pressure", "value_numeric": 38, "quality_status": "suspect", "observed_at": "2026-01-02T00:00:00Z"},
    {"asset_id": "GEN-1", "metric_key": "oil_pressure", "value_numeric": 35, "quality_status": "bad", "observed_at": "2026-01-03T00:00:00Z"},
]
assets = [
    {"id": "GEN-1", "name": "Generator 1", "asset_type": "generator", "criticality": "critical", "lifecycle_state": "operational"},
]
result = predict_equipment_failures(
    tenant_id="tenant-1",
    assets=assets,
    telemetry_rows=telemetry_rows,
    window_days=7,
)
profile = result.risk_profiles[0]
print(f"Asset: {profile.asset_name}")
print(f"Risk score: {profile.risk_score:.2f}")
print(f"Risk level: {profile.risk_level}")
print(f"Anomalies: {profile.anomaly_count}")
print(f"Trend degradation: {profile.trend_degradation}")
print(f"Recommended action: {profile.recommended_action}")
