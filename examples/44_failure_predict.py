"""Example: Equipment failure prediction from telemetry.

Scores failure risk per asset using anomaly detection and trend analysis.
"""
from dcc.forecasting.failure import predict_equipment_failures

telemetry_rows = [
    {"asset_id": "UPS-1", "metric_key": "battery_temp", "value_numeric": 45, "quality_status": "good", "observed_at": "2026-01-01T00:00:00Z"},
    {"asset_id": "UPS-1", "metric_key": "battery_temp", "value_numeric": 48, "quality_status": "good", "observed_at": "2026-01-02T00:00:00Z"},
    {"asset_id": "UPS-1", "metric_key": "battery_temp", "value_numeric": 52, "quality_status": "suspect", "observed_at": "2026-01-03T00:00:00Z"},
    {"asset_id": "CRAC-1", "metric_key": "supply_temp", "value_numeric": 18, "quality_status": "good", "observed_at": "2026-01-01T00:00:00Z"},
]
result = predict_equipment_failures(
    tenant_id="tenant-1",
    telemetry_rows=telemetry_rows,
    asset_info={"UPS-1": {"name": "UPS Unit 1", "asset_type": "ups", "criticality": "critical", "lifecycle_state": "operational"}},
    window_days=7,
)
for profile in result.risk_profiles:
    print(f"  {profile.asset_name}: risk={profile.risk_score:.2f} ({profile.risk_level})")
    if profile.contributing_factors:
        print(f"    Factors: {profile.contributing_factors}")
