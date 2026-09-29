"""Example: Data quality scoring.

Scores a data source on completeness, freshness, consistency, and accuracy.
"""
from dcc.quality.engine import QualityEngine, QualityDimension

engine = QualityEngine()
records = [
    {"id": "1", "name": "UPS-1", "status": "active", "observed_at": "2026-01-01"},
    {"id": "2", "name": "CRAC-1", "status": "active", "observed_at": "2026-01-02"},
    {"id": "3", "name": None, "status": "maintenance", "observed_at": "2026-01-03"},
]
report = engine.score_source(
    source="telemetry_readings",
    records=records,
    required_fields=["id", "name", "status"],
    optional_fields=["observed_at"],
)
print(f"Overall: {report.overall:.2f}")
for dim, score in report.scores.items():
    print(f"  {dim.value}: {score.score:.2f} (weight: {score.weight})")
