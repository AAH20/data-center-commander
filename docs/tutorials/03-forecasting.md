# Tutorial 3: Forecasting & Analytics

## Overview

Data Center Commander provides decision-grade KPIs trends, short-horizon
forecasts, anomaly detection, and model readiness scoring. This tutorial
covers the analytics API, the forecasting pipeline, anomaly detection methods,
and the minimum-history gates that prevent unreliable predictions.

## The Analytics API

```
GET /v1/analytics?tenant_id=<uuid>&window_days=30
```

The `window_days` parameter accepts 1–90. The response includes:

| Field | Description |
|---|---|
| `kpi_series` | Daily-bucketed KPI observations with value, coverage, uncertainty, sample count, synthetic flag |
| `kpi_quality` | Per-metric quality: observation count, usable count, mean coverage, mean uncertainty, latest window end, synthetic count |
| `telemetry_quality` | Quality status distribution: sample count, metric count, asset count, latest observed timestamp |
| `workflow_health` | Workflow queue health: type, status, priority, item count, overdue count, mean age in days |
| `model_policy` | Forecast thresholds and model enablement flags |

## KPI Series Structure

Each KPI series point contains:

- `metric_key` — stable identifier (e.g., `facility_energy_kwh`, `pue`)
- `name` — human-readable label
- `unit` — canonical SI unit
- `bucket` — day-truncated window end timestamp
- `value` — averaged numeric value
- `coverage` — fraction of expected samples present (0.0–1.0)
- `uncertainty` — mean uncertainty across samples
- `samples` — number of observations in the bucket
- `synthetic` — boolean, true if any sample is synthetic

## Trend Forecasting

The UI renders trend charts for up to 6 KPI metrics. For each metric:

1. **Filter**: only non-synthetic daily points with finite values
2. **Threshold**: minimum 7 clean daily points required
3. **Fit**: ordinary least squares (OLS) linear regression on the clean series
4. **Project**: 3-step advisory projection beyond the last observation
5. **Display**: observed polyline (teal) + forecast dashed polyline (amber)

The forecast is **advisory only**. It is not a command, not a procurement
signal, and not a capacity commitment. The UI labels it "OLS trend · 3-step
advisory projection".

### Minimum History Gates

| Model | Minimum Daily Points | Purpose |
|---|---|---|
| Trend forecast | 7 | Basic linear trend |
| Anomaly detection | 14 | Statistical baseline |
| Maintenance failure labels | Required | Failure-probability model |

If clean history is below the threshold, the UI displays "Forecast withheld ·
N clean points; M required". No forecast is fabricated.

## Anomaly Detection

The `src/dcc/quality/anomaly.py` module provides three methods:

### Z-Score Detection

```python
from dcc.quality.anomaly import zscore_detect

report = zscore_detect(values, timestamps, threshold=3.0, window=None)
```

- **Global z-score**: computes mean and standard deviation across the entire
  series; flags points where `|z| > threshold`
- **Rolling z-score**: uses a sliding window for local mean/std; useful for
  non-stationary series
- **Severity**: `low` (deviation ratio ≥ 1), `medium` (≥ 2), `high` (≥ 4)

### IQR Detection

```python
from dcc.quality.anomaly import iqr_detect

report = iqr_detect(values, timestamps, k=1.5)
```

- Values outside `[Q1 - k*IQR, Q3 + k*IQR]` are flagged
- Default `k=1.5` is Tukey's standard for outlier detection
- Use `k=3.0` for "extreme" outliers only

### Seasonal Decomposition

```python
from dcc.quality.anomaly import seasonal_decompose_detect

report = seasonal_decompose_detect(values, timestamps, period=24, threshold=3.0)
```

- Decomposes series into trend + seasonal + residual (additive model)
- Applies z-score detection on the residual component
- Requires at least 2 full periods of data (e.g., 48 points for `period=24`)
- `period=24` for hourly data with daily seasonality; `period=7` for daily
  data with weekly seasonality

### Running All Methods

```python
from dcc.quality.anomaly import detect_all

results = detect_all(values, timestamps)
# Returns {"zscore": AnomalyReport, "iqr": AnomalyReport, "seasonal": AnomalyReport}
```

## Model Readiness

The analytics API returns a `model_policy` object:

```json
{
  "trend_forecast_min_daily_points": 7,
  "anomaly_min_daily_points": 14,
  "maintenance_failure_labels_required": true,
  "note": "Forecasts and anomalies require adequate non-synthetic history; no failure-probability model is enabled by this read model."
}
```

The UI computes a readiness score:

- Count of KPI series with at least one non-synthetic observation
- Whether any series meets the 7-point forecast threshold
- Whether any series meets the 14-point anomaly threshold
- Whether synthetic provenance is present (interpreted as demo only)

## Data Quality Engine

The `src/dcc/quality/engine.py` module scores data sources across four
dimensions:

| Dimension | Weight | What it measures |
|---|---|---|
| Completeness | 0.30 | Fraction of required fields present and non-null |
| Freshness | 0.25 | Age of newest record vs. SLA threshold |
| Consistency | 0.25 | Fraction of records passing validation rules |
| Accuracy | 0.20 | Fraction of records matching reference values |

Each dimension produces a `QualityScore` with a 0.0–1.0 score, weight, passed
count, total count, and details. The overall score is the weighted sum.

### Using the Quality Engine

```python
from dcc.quality.engine import QualityEngine

engine = QualityEngine()
report = engine.score_source(
    source="epms_meter_1",
    records=[{"timestamp": "2024-01-01T00:00:00Z", "value": 150.5}, ...],
    required_fields=["timestamp", "value"],
    optional_fields=["quality_status"],
    timestamps=[datetime(2024, 1, 1), ...],
    max_age_hours=24.0,
    consistency_rules=[lambda r: r["value"] > 0],
    rule_names=["positive_value"],
)
print(report.overall)  # 0.0–1.0
```

## Freshness SLA Monitoring

The `src/dcc/quality/freshness.py` module tracks data age per source:

| Source | SLA (hours) | Override by source_kind |
|---|---|---|
| telemetry_readings | 1 | — |
| kpi_observations | 26 | — |
| capacity_snapshots | 26 | — |
| price_observations | 72 | vendor_api: 24, vendor_quote: 168, contract: 720, utility_tariff: 168, public_benchmark: 72, manual: 168, synthetic_demo: ∞ |
| connectors | 26 | — |
| assets | 168 | — |
| cost_actuals | 720 | — |
| energy_allocations | 26 | — |

Status levels: `ok` (age ≤ 80% of SLA), `warning` (age > 80% of SLA),
`violation` (age > SLA), `no_data` (no rows).

## Continuous BI Lifecycle

Every report records:

- **As-of watermark** — when the data was current
- **Source completeness** — coverage denominator
- **Calculation/model version** — formula or model version used
- **Dimensions** — site, boundary, interval, cohort
- **Figure type** — observed, allocated, estimated, or forecast

Corrections never rewrite prior operator decisions. They create a new version
and recalculate a linked view. The audit view must reproduce the number shown
at the time a decision was made.

## Next Steps

- [Tutorial 4: Economics & Cost Estimation](04-economics.md) — bottom-up estimation and unit economics
- [Tutorial 7: Data Quality & Provenance](07-data-quality.md) — quality engine and lineage tracking
