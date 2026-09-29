# Tutorial 7: Data Quality & Provenance

## Overview

Every KPI in Data Center Commander is reproducible from named source
observations and a versioned calculation definition. Missing inputs produce
`unknown`, not zero. This tutorial covers the quality vocabulary, quality
scoring engine, freshness SLA monitoring, anomaly detection integration, and
the provenance tracking system.

## Quality Vocabulary

The canonical quality statuses:

| Status | Meaning |
|---|---|
| `good` | Reading passed all quality checks |
| `estimated` | Value is modeled or interpolated, not directly measured |
| `suspect` | Reading may be incorrect; under review |
| `bad` | Reading failed validation; do not use |
| `missing` | Expected reading not received |
| `stale` | Reading is older than the freshness SLA |
| `late` | Reading arrived after the expected window |
| `replayed` | Duplicate reading from a replay |
| `clock_skew` | Source clock differs from system clock beyond tolerance |
| `out_of_range` | Value is outside the expected physical range |
| `uncalibrated` | Sensor calibration has expired or is unknown |
| `superseded` | Reading has been corrected by a newer reading |

A quality rule has a version, threshold, interval, metric, and facility
context. Consumers choose an explicit quality policy; no global implicit
filtering is applied.

## Quality Scoring Engine

The `src/dcc/quality/engine.py` module scores data sources across four
dimensions:

### Completeness (weight: 0.30)

Fraction of required fields present and non-null. Optional fields contribute
half-weight.

```python
from dcc.quality.engine import completeness_score

score = completeness_score(
    records=[{"timestamp": "2024-01-01T00:00:00Z", "value": 150.5}, ...],
    required_fields=["timestamp", "value"],
    optional_fields=["quality_status"],
)
# score.score → 0.0–1.0
# score.passed → count of present required fields
# score.total → total required field slots
```

### Freshness (weight: 0.25)

How recent the newest record is. Linear decay over a week after the SLA
threshold.

```python
from dcc.quality.engine import freshness_score

score = freshness_score(
    timestamps=[datetime(2024, 1, 1), datetime(2024, 1, 2)],
    max_age_hours=24.0,
)
# score.score → 1.0 if within SLA, decaying to 0.0 after 7× SLA
```

### Consistency (weight: 0.25)

Fraction of records passing all validation rules.

```python
from dcc.quality.engine import consistency_score

score = consistency_score(
    records=[{"value": 150.5}, {"value": -1.0}, {"value": 200.0}],
    rules=[lambda r: r["value"] > 0],
    rule_names=["positive_value"],
)
# score.score → 0.667 (2 of 3 pass)
```

### Accuracy (weight: 0.20)

Fraction of records matching reference values within tolerance.

```python
from dcc.quality.engine import accuracy_score

score = accuracy_score(
    records=[{"voltage": 230.1}, {"voltage": 230.5}, {"voltage": 229.8}],
    reference_values={"voltage": 230.0},
    tolerance=1.0,
)
# score.score → 1.0 (all within 1.0 of 230.0)
```

### Overall Score

```python
from dcc.quality.engine import QualityEngine

engine = QualityEngine()
report = engine.score_source(
    source="epms_meter_1",
    records=records,
    required_fields=["timestamp", "value"],
    timestamps=[...],
    consistency_rules=[...],
    reference_values={...},
)
print(f"Overall: {report.overall:.2f}")
for dim, s in report.scores.items():
    print(f"  {dim.value}: {s.score:.2f} (weight {s.weight})")
```

## Freshness SLA Monitoring

The `src/dcc/quality/freshness.py` module tracks data age per source:

```python
from dcc.quality.freshness import check_freshness

report = check_freshness(pool, tenant_id)
print(f"Overall: {report.overall_status}")
for source in report.sources:
    print(f"  {source.source}: {source.status} (age: {source.age_hours}h, SLA: {source.sla_hours}h)")
```

### SLA Thresholds

| Source | SLA (hours) | Description |
|---|---|---|
| telemetry_readings | 1 | Real-time telemetry |
| kpi_observations | 26 | Daily KPIs (~1 day) |
| capacity_snapshots | 26 | Daily capacity (~1 day) |
| price_observations | 72 | Prices (3 days) |
| connectors | 26 | Connector last success (~1 day) |
| assets | 168 | Asset observed_at (7 days) |
| cost_actuals | 720 | Monthly actuals (30 days) |
| energy_allocations | 26 | Daily allocations (~1 day) |

### Price Source Kind Overrides

| Source kind | SLA (hours) |
|---|---|
| vendor_api | 24 |
| vendor_quote | 168 |
| contract | 720 |
| utility_tariff | 168 |
| public_benchmark | 72 |
| manual | 168 |
| synthetic_demo | ∞ (no SLA) |

### Status Levels

- `ok` — age ≤ 80% of SLA
- `warning` — age > 80% of SLA but ≤ 100%
- `violation` — age > SLA
- `no_data` — no rows in the table

## Anomaly Detection Integration

The `src/dcc/quality/anomaly.py` module provides three detection methods
that feed into the quality pipeline:

### Z-Score

```python
from dcc.quality.anomaly import zscore_detect

report = zscore_detect(values, timestamps, threshold=3.0, window=None)
for a in report.anomalies:
    print(f"  Index {a.index}: value={a.value}, expected={a.expected}, severity={a.severity}")
```

### IQR

```python
from dcc.quality.anomaly import iqr_detect

report = iqr_detect(values, timestamps, k=1.5)
```

### Seasonal Decomposition

```python
from dcc.quality.anomaly import seasonal_decompose_detect

report = seasonal_decompose_detect(values, timestamps, period=24, threshold=3.0)
```

### Combined

```python
from dcc.quality.anomaly import detect_all

results = detect_all(values, timestamps)
# Returns {"zscore": ..., "iqr": ..., "seasonal": ...}
```

## Provenance Tracking

The `src/dcc/provenance/tracker.py` module tracks data lineage from source
through transformations to outputs. Every step is hash-chained and
tenant-isolated.

### Lineage Nodes

```python
from dcc.provenance.tracker import LineageTracker, SourceType

tracker = LineageTracker()
node = tracker.register_source(
    tenant_id="dcc00000-0000-4000-8000-000000000001",
    node_type="connector_reading",
    label="UPS-1 power reading",
    source_type=SourceType.CONNECTOR,
    content={"voltage": 230.1, "current": 45.2},
)
```

### Transformation Steps

```python
from dcc.provenance.tracker import TransformationType

step = tracker.record_transformation(
    tenant_id="dcc00000-0000-4000-8000-000000000001",
    operation="kwh_calculation",
    transformation_type=TransformationType.CALCULATION,
    input_node_ids=[node.node_id],
    output_node_id=output_node_id,
    output_content={"energy_kwh": 10.4},
    actor_ref="system",
)
```

### Chain Verification

```python
result = tracker.verify_chain(tenant_id="dcc00000-0000-4000-8000-00000000001")
# result["valid"] → True/False
# result["steps_checked"] → number of steps verified
# result["broken_at"] → step_id where chain broke (if invalid)
```

### Lineage Query

```python
lineage = tracker.get_lineage(
    tenant_id="dcc00000-0000-4000-8000-000000000001",
    artifact_id="kpi_123",
    direction="upstream",
    max_depth=10,
)
# Returns nodes and edges walking upstream from the artifact
```

## Telemetry Envelope

Minimum normalized reading fields:

- `tenant` — tenant UUID
- `source_connector` and `source_version` — connector identity
- `source_event_id` — immutable source event identifier
- `external_asset_id` / `external_meter_id` — source system identity
- `metric_id` — canonical metric identifier
- `observed_at` — source timestamp (UTC)
- `ingested_at` — system ingestion timestamp (UTC)
- `value_numeric` — canonical numeric value
- `unit` — canonical SI unit
- `quality_status` — quality vocabulary status
- `sample_interval` — seconds between samples
- `calibration_reference` — calibration identifier
- `source_cursor` — pagination/checkpoint cursor
- `provenance_digest` — hash of source payload

Deduplicate by `(tenant, connector, source_event_id)`. Keep corrections as
superseded readings. Store UTC instants while retaining source timezone and
clock offset.

## Data Retention

- **Raw readings** — policy-defined hot retention
- **Derived rollups** — agreed operational/audit horizons
- **Evidence digests/decision records** — legal retention

Partition by time and tenant only after measured scale requires it. Avoid
partitioning that destroys useful uniqueness or RLS. Retention and export are
per-tenant policy.

## Next Steps

- [Tutorial 3: Forecasting & Analytics](03-forecasting.md) — KPI trends and model readiness
- [Tutorial 10: Evidence & Audit](10-evidence-audit.md) — evidence ledger and audit trail
