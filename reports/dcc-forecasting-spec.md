# Predictive Maintenance Specification

**Project:** Data Center Commander  
**Status:** Specification (Stage 3 roadmap target)  
**Date:** 2026-09-29  
**Author:** DCC Architecture Review  

---

## 1. Scope and Purpose

This document specifies the predictive maintenance (PdM) subsystem for Data Center Commander. It defines the ML models, feature engineering pipeline, training data requirements, evaluation metrics, and operational governance needed to deliver advisory failure predictions for data-center assets.

The PdM subsystem is **advisory only**. It produces human-reviewed recommendations, never automatic control actions. All predictions carry uncertainty, provenance, and model version metadata.

### 1.1 In Scope

- Failure prediction for critical asset families: UPS, PDU, cooling units (CRAH/CRAC/CDU), generators, ATS, transformers, switchgear, pumps, servers, storage
- Remaining useful life (RUL) estimation for wear-out components (batteries, fans, capacitors, bearings)
- Anomaly detection for early fault indication
- Maintenance timing optimization

### 1.2 Out of Scope

- Automatic shutdown, setpoint changes, or breaker commands
- Safety system actuation (fire suppression, emergency ventilation)
- Work order auto-creation without human approval
- Replacement procurement decisions

---

## 2. Architecture Context

### 2.1 Bounded Context

The PdM subsystem lives within the **Maintenance & reliability** bounded context, which owns:

- Asset history and condition indicators
- Work orders and failure analysis
- Maintenance procedures and spares

It consumes from:

- **Telemetry & provenance** — sensor readings with quality flags
- **Organization & estate** — asset topology and relationships
- **Operations & governance** — incidents, changes, approvals

### 22.2 Data Flow

```
Telemetry readings ──► Feature engineering ──► Model inference ──► Prediction
Asset history      ──►                         │                    │
Work orders        ──►                         ▼                    ▼
                                        Confidence + uncertainty  Advisory case
                                                                   │
                                                                   ▼
                                                          Human review (accept/defer/reject)
                                                                   │
                                                                   ▼
                                                          CMMS recommendation (not command)
```

### 2.3 Trust Boundary

Model output must be traceable to:
- Input watermark (source data freshness)
- Feature/model/formula version
- Training/validation scope
- Confidence and drift state
- Human disposition (accept/defer/reject with reason)

---

## 3. Required ML Models

### 3.1 Model Inventory

| Model ID | Name | Purpose | Asset Families | Output |
|----------|------|---------|----------------|--------|
| `PdM-FAIL-01` | Binary failure classifier | Predict probability of failure within horizon | All critical assets | P(failure) + confidence interval |
| `PdM-RUL-01` | Remaining useful life regressor | Estimate days until end-of-life | Batteries, fans, capacitors, bearings | RUL in days + prediction interval |
| `PdM-ANOM-01` | Anomaly detector | Detect anomalous behavior patterns | All instrumented assets | Anomaly score + contributing features |
| `PdM-MAINT-01` | Maintenance timing optimizer | Recommend optimal maintenance window | All maintainable assets | Recommended date + cost/risk tradeoff |

### 3.2 Model Details

#### 3.2.1 Binary Failure Classifier (`PdM-FAIL-01`)

- **Algorithm:** Gradient-boosted trees (XGBoost/LightGBM) or logistic regression with calibrated probabilities
- **Output:** Probability of failure within configurable horizon (default: 30 days)
- **Calibration:** Platt scaling or isotonic regression on held-out validation set
- **Threshold:** Configurable per asset family; default 0.5 with cost-sensitive adjustment
- **Class imbalance:** Handle via SMOTE, class weights, or threshold tuning; report precision-recall tradeoff

#### 3.2.2 RUL Regressor (`PdM-RUL-01`)

- **Algorithm:** Random forest regression or Weibull survival analysis
- **Output:** Predicted remaining useful life in days with 80% and 95% prediction intervals
- **Censoring:** Handle right-censored data (assets still operating) via survival analysis methods
- **Degradation modeling:** Fit degradation trajectory from condition indicators

#### 3.2.3 Anomaly Detector (`PdM-ANOM-01`)

- **Algorithm:** Isolation Forest, autoencoder, or statistical process control (SPC)
- **Output:** Anomaly score (0-1) with top contributing features
- **Baseline:** Per-asset or per-asset-family baseline with seasonal adjustment
- **Online update:** Support incremental learning for concept drift

#### 3.2.4 Maintenance Timing Optimizer (`PdM-MAINT-01`)

- **Algorithm:** Cost-benefit optimization or reinforcement learning
- **Output:** Recommended maintenance window with expected cost savings
- **Constraints:** Spare parts availability, staff schedule, change windows, SLO impact
- **Objective:** Minimize total cost = maintenance cost + expected failure cost + opportunity cost

### 3.3 Model Selection Criteria

For each asset family, select the model that minimizes:
- **Primary:** Expected cost of misclassification (false positive + false negative costs)
- **Secondary:** Calibration error, interpretability, inference latency
- **Tertiary:** Training data efficiency, maintenance overhead

---

## 4. Feature Engineering

### 4.1 Feature Categories

#### 4.1.1 Time-Series Features (from telemetry)

| Feature | Description | Source Metrics |
|---------|-------------|----------------|
| Rolling mean (1h, 24h, 7d) | Short/medium/long-term average | All continuous metrics |
| Rolling std (1h, 24h, 7d) | Variability indicator | All continuous metrics |
| Rolling min/max (24h, 7d) | Extreme values | Temperature, pressure, current |
| Trend slope (7d, 30d) | Linear regression slope | All continuous metrics |
| Rate of change | First difference | All continuous metrics |
| Exponentially weighted moving average | Recent-weighted average | All continuous metrics |
| Time since last peak | Hours since maximum observed | All continuous metrics |
| Spectral features | Frequency domain characteristics | Vibration, current |
| Cross-metric correlations | Pearson correlation between metrics | Temperature × load, pressure × flow |

#### 4.1.2 Asset Static Features

| Feature | Description | Source |
|---------|-------------|--------|
| Asset age | Days since in_service_at | `assets.in_service_at` |
| Asset type | Categorical | `assets.asset_type` |
| Manufacturer | Categorical | `assets.manufacturer` |
| Model | Categorical | `assets.model` |
| Criticality | Ordinal (low/medium/high/critical) | `assets.criticality` |
| Warranty status | Days until warranty expiry | `assets.warranty_until` |
| Support status | Days until support expiry | `assets.support_until` |
| Rated capacity | Nameplate rating | `assets.attributes` |
| Operating envelope | Min/max observed values | Telemetry history |

#### 4.1.3 Maintenance History Features

| Feature | Description | Source |
|---------|-------------|--------|
| Days since last maintenance | Days since last completed work order | `work_orders` |
| Maintenance frequency | Work orders per year | `work_orders` |
| Days since last failure | Days since last failure work order | `work_orders` |
| Failure count (1y, 3y, lifetime) | Historical failure count | `work_orders` |
| Mean time between failures | Average days between failures | `work_orders` |
| Last failure mode | Categorical failure code | `work_orders.failure_code` |
| Repair duration | Hours from open to close | `work_orders` |
| Recurring failure indicator | Same failure mode repeated | `work_orders` |

#### 4.1.4 Operational Context Features

| Feature | Description | Source |
|---------|-------------|--------|
| Current load | Latest load percentage | Telemetry |
| Load variability | Std dev of load (7d) | Telemetry |
| Ambient conditions | Temperature, humidity | Environmental sensors |
| Time of day | Hour of day (cyclical encoding) | Timestamp |
| Day of week | Day of week (cyclical encoding) | Timestamp |
| Season | Seasonal indicator | Timestamp |
| Concurrent incidents | Active incident count | `incidents` |
| Recent changes | Change records in last 7 days | `change_records` |
| Alarm frequency | Alarms per day (7d) | `incidents` |

#### 4.1.5 Topology Features

| Feature | Description | Source |
|---------|-------------|--------|
| Redundancy status | N, N+1, 2N based on topology | `asset_relationships` |
| Dependency depth | Number of downstream assets | `asset_relationships` |
| Shared risk assets | Assets sharing power/cooling path | `asset_relationships` |
| Critical path indicator | On critical path for service | `asset_relationships` |

### 4.2 Feature Pipeline

```
Raw telemetry ──► Quality filter ──► Imputation ──► Normalization ──► Feature extraction ──► Feature store
                  │                  │              │                  │
                  ▼                  ▼              ▼                  ▼
              quality_status    missing value   z-score or         rolling stats,
              filter            indicator       min-max           trends, spectral
```

#### 4.2.1 Quality Filtering

- Only use readings with `quality_status IN ('good', 'estimated')`
- Reject readings with `quality_status IN ('bad', 'suspect', 'uncalibrated')`
- Flag features derived from low-coverage windows
- Minimum coverage threshold: 80% of expected readings in feature window

#### 4.2.2 Imputation

- **Short gaps (< 1h):** Linear interpolation
- **Medium gaps (1h - 24h):** Forward fill with uncertainty flag
- **Long gaps (> 24h):** Mark feature as missing; do not impute
- **Missing indicator:** Add binary feature indicating imputation

#### 4.2.3 Normalization

- **Z-score:** For normally distributed features
- **Min-max:** For bounded features (percentages, ratios)
- **Log transform:** For heavy-tailed distributions (failure counts, durations)
- **Cyclical encoding:** For time features (hour, day of week, season)

### 4.3 Feature Store

Features are stored in a versioned feature store with:
- Feature definition version
- Computation timestamp
- Source data watermark
- Coverage statistics
- Missingness indicators

---

## 5. Training Data Requirements

### 5.1 Data Sources

| Source | Data | Minimum History | Update Frequency |
|--------|------|-----------------|------------------|
| `telemetry_readings` | Sensor time-series | 12 months | Real-time |
| `work_orders` | Maintenance and failure records | 24 months | Daily |
| `assets` | Asset metadata and lifecycle | Full history | On change |
| `incidents` | Incident records | 24 months | Real-time |
| `asset_relationships` | Topology and dependencies | Full history | On change |
| `change_records` | Change history | 12 months | Real-time |

### 5.2 Label Definition

#### 5.2.1 Failure Labels

A **failure** is defined as:
- A work order with `work_type = 'failure'` or `failure_code IS NOT NULL`
- An incident with `severity IN ('SEV-1', 'SEV-2')` that resulted in asset unavailability
- A condition where the asset entered `lifecycle_state = 'impaired'` or `maintenance`

**Label timing:** The failure label is assigned to the time window *before* the failure event, not at the failure time. This prevents data leakage.

#### 5.2.2 Censoring

- Assets that have not failed are **right-censored** at the last observation time
- Assets that were retired or decommissioned before failing are **competing risks**
- Handle via survival analysis or exclude from binary classification

#### 5.2.3 Label Validation

- **Do not** infer failure labels from closure codes without validation
- **Do not** use `work_type = 'inspection'` as a negative label (absence of failure ≠ negative)
- Validate labels against independent sources (incident records, downtime logs)

### 5.3 Data Quality Gates

Before training, verify:
- [ ] Minimum 100 failure events per asset family (or use transfer learning)
- [ ] Minimum 12 months of telemetry history
- [ ] Telemetry coverage > 80% for critical metrics
- [ ] No systematic gaps in failure reporting
- [ ] Failure labels validated against independent sources
- [ ] No data leakage (future information in features)

### 5.4 Data Splitting

| Split | Purpose | Method | Ratio |
|-------|---------|--------|-------|
| Training | Model fitting | Time-based split | 60% |
| Validation | Hyperparameter tuning | Time-based split | 20% |
| Testing | Final evaluation | Time-based split | 20% |

**Critical:** Use time-based splits, not random splits, to prevent leakage. The test set must be chronologically after the training set.

For asset-family-specific models:
- Stratify by asset family
- Ensure each family has sufficient representation in all splits
- Use grouped cross-validation by asset ID

---

## 6. Evaluation Metrics

### 6.1 Classification Metrics (Failure Prediction)

| Metric | Description | Target |
|--------|-------------|--------|
| Precision | TP / (TP + FP) | > 0.70 |
| Recall | TP / (TP + FN) | > 0.80 |
| F1-score | Harmonic mean of precision and recall | > 0.75 |
| AUC-ROC | Area under ROC curve | > 0.85 |
| AUC-PR | Area under precision-recall curve | > 0.70 |
| Calibration error | Expected calibration error (ECE) | < 0.05 |
| Brier score | Mean squared error of probability | < 0.15 |

### 6.2 Regression Metrics (RUL Estimation)

| Metric | Description | Target |
|--------|-------------|--------|
| MAE | Mean absolute error in days | < 14 days |
| RMSE | Root mean squared error in days | < 21 days |
| MAPE | Mean absolute percentage error | < 30% |
| Coverage | % of true values within prediction interval | > 80% |
| Pinball loss | Quantile loss for prediction intervals | Minimize |

### 6.3 Anomaly Detection Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Precision@K | Precision at top K anomalies | > 0.60 |
| Recall@K | Recall at top K anomalies | > 0.70 |
| False positive rate | FP / (FP + TN) | < 0.05 |
| Detection delay | Time from fault onset to detection | < 24h |

### 6.4 Business Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Lead time | Time from prediction to actual failure | > 7 days |
| False alarm rate | False positives per asset per month | < 0.5 |
| Maintenance cost savings | Reduction in unplanned downtime cost | > 20% |
| Avoided outages | Failures prevented by early intervention | Track and report |
| Operator acceptance rate | % of predictions accepted by operators | > 60% |

### 6.5 Evaluation Protocol

1. **Backtesting:** Evaluate on historical data with time-based splits
2. **Shadow mode:** Run predictions without operator visibility; compare to actual outcomes
3. **A/B testing:** Compare model recommendations to standard maintenance schedules
4. **Calibration monitoring:** Track calibration drift over time
5. **Fairness audit:** Evaluate performance across asset families, sites, and time periods

---

## 7. Model Governance

### 7.1 Model Registry

Each model version must record:
- Model ID and version
- Training data range and scope
- Feature definitions and versions
- Hyperparameters
- Evaluation metrics (validation and test)
- Calibration method and parameters
- Approval status and approver
- Deployment date
- Retirement date (if applicable)

### 7.2 Model Validation Gate

Before deployment, a model must pass:
- [ ] Minimum performance thresholds (Section 6)
- [ ] Calibration validation on held-out set
- [ ] Leakage audit (no future information in features)
- [ ] Robustness tests (missing data, sensor drift, adversarial inputs)
- [ ] Fairness audit (no disparate performance across asset families)
- [ ] Interpretability review (feature importance is physically meaningful)
- [ ] Operator review (domain expert signoff)

### 7.3 Drift Detection

Monitor for:
- **Data drift:** Distribution shift in input features
- **Concept drift:** Change in feature-target relationship
- **Performance drift:** Degradation in prediction quality

Trigger retraining when:
- Data drift exceeds threshold (KL divergence > 0.1)
- Calibration error exceeds 0.10
- Performance drops below minimum thresholds
- Significant change in asset population or operating conditions

### 7.4 Explainability

Every prediction must include:
- **Top contributing features:** SHAP values or feature importance
- **Prediction interval:** Confidence range, not just point estimate
- **Similar historical cases:** Analogous past failures
- **Known limitations:** Sensor gaps, data quality issues, model uncertainty

### 7.5 Human-in-the-Loop

The predictive maintenance workflow (from `OPERATOR_WORKFLOWS.md`):

1. System creates a case when model predicts failure with sufficient confidence
2. Case displays: predicted failure mode/horizon, calibrated probability, top evidence/features, sensor gaps, known limitations, alert history
3. Facilities reliability owner reviews and accepts, defers, or rejects with reason
4. Acceptance may create a CMMS recommendation (not a device control call)
5. Actual findings recorded to measure precision, recall, lead time, avoided outage, and intervention cost

---

## 8. Implementation Requirements

### 8.1 Data Pipeline

- **Feature computation:** Scheduled batch (hourly) + on-demand for new predictions
- **Feature storage:** Versioned feature store with lineage
- **Model serving:** REST API endpoint for real-time inference
- **Prediction storage:** Append-only prediction log with model version and input hash

### 8.2 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/predictions` | GET | List predictions for tenant |
| `/v1/predictions/{id}` | GET | Get prediction details with explanation |
| `/v1/predictions/{id}/disposition` | POST | Record operator disposition |
| `/v1/models` | GET | List deployed models and status |
| `/v1/models/{id}/metrics` | GET | Get model performance metrics |

### 8.3 Database Schema Extensions

```sql
-- Predictions table
CREATE TABLE dcc.predictions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id uuid NOT NULL REFERENCES assets(tenant_id,id),
    model_id text NOT NULL,
    model_version text NOT NULL,
    prediction_type text NOT NULL CHECK(prediction_type IN ('failure', 'rul', 'anomaly', 'maintenance')),
    predicted_at timestamptz NOT NULL DEFAULT now(),
    horizon_days integer NOT NULL,
    probability numeric(5,4) CHECK(probability BETWEEN 0 AND 1),
    rul_days numeric(8,2),
    anomaly_score numeric(5,4) CHECK(anomaly_score BETWEEN 0 AND 1),
    confidence_interval_lower numeric(5,4),
    confidence_interval_upper numeric(5,4),
    top_features jsonb NOT NULL DEFAULT '[]',
    sensor_gaps jsonb NOT NULL DEFAULT '[]',
    known_limitations jsonb NOT NULL DEFAULT '[]',
    input_watermark timestamptz NOT NULL,
    feature_version text NOT NULL,
    calculation_hash text NOT NULL,
    provenance jsonb NOT NULL DEFAULT '{}',
    UNIQUE(tenant_id, id)
);

-- Operator dispositions
CREATE TABLE dcc.prediction_dispositions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    prediction_id uuid NOT NULL REFERENCES dcc.predictions(tenant_id,id),
    operator_ref text NOT NULL,
    decision text NOT NULL CHECK(decision IN ('accepted', 'deferred', 'rejected')),
    reason text NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    outcome text CHECK(outcome IN ('true_positive', 'false_positive', 'true_negative', 'false_negative', 'pending')),
    actual_failure_at timestamptz,
    notes jsonb NOT NULL DEFAULT '{}',
    UNIQUE(tenant_id, id)
);

-- Model registry
CREATE TABLE dcc.model_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    model_id text NOT NULL,
    model_version text NOT NULL,
    model_type text NOT NULL,
    training_data_start timestamptz NOT NULL,
    training_data_end timestamptz NOT NULL,
    feature_version text NOT NULL,
    hyperparameters jsonb NOT NULL DEFAULT '{}',
    validation_metrics jsonb NOT NULL DEFAULT '{}',
    test_metrics jsonb NOT NULL DEFAULT '{}',
    calibration_method text,
    approval_status text NOT NULL CHECK(approval_status IN ('draft', 'validated', 'approved', 'rejected', 'retired')),
    approved_by text,
    approved_at timestamptz,
    deployed_at timestamptz,
    retired_at timestamptz,
    provenance jsonb NOT NULL DEFAULT '{}',
    UNIQUE(tenant_id, model_id, model_version)
);
```

### 8.4 Minimum History Gates

The system must enforce minimum history requirements before producing predictions:

| Asset Family | Minimum Telemetry History | Minimum Failure Events | Minimum Total Assets |
|--------------|--------------------------|----------------------|---------------------|
| UPS | 12 months | 20 | 10 |
| Cooling units | 12 months | 15 | 10 |
| Generators | 6 months | 10 | 5 |
| Servers | 6 months | 30 | 50 |
| PDU | 12 months | 10 | 10 |

If minimum history is not met, the system reports `insufficient_data` and does not produce predictions.

---

## 9. Security and Compliance

### 9.1 Data Protection

- Training data must be tenant-isolated
- Model inference must be tenant-scoped
- Prediction logs must be retained per tenant policy
- Sensitive features (exact locations, serial numbers) must be hashed or tokenized

### 9.2 Model Security

- Model artifacts must be signed and verified before deployment
- Adversarial input detection for prediction API
- Rate limiting on prediction endpoints
- Audit log for all model updates and predictions

### 9.3 Operational Safety

- Predictions must never trigger automatic control actions
- All predictions must be reviewed by qualified human operator
- System must clearly distinguish between prediction and confirmed fault
- False positives must not lead to unnecessary maintenance actions

---

## 10. Roadmap Alignment

This specification aligns with **Stage 3** of the DCC roadmap:

| Roadmap Item | Specification Section |
|--------------|----------------------|
| Condition features | Section 4: Feature Engineering |
| Work-order/failure labels | Section 5.2: Label Definition |
| Maintenance history | Section 4.1.3: Maintenance History Features |
| Interpretable forecasting | Section 7.4: Explainability |
| Drift detection | Section 7.3: Drift Detection |
| Time-split backtests | Section 5.4: Data Splitting |
| Calibration/error analysis | Section 6: Evaluation Metrics |
| Leakage checks | Section 5.3: Data Quality Gates |
| Minimum-history gates | Section 8.4: Minimum History Gates |
| Human disposition | Section 7.5: Human-in-the-Loop |

---

## 11. Open Questions

1. **Compute infrastructure:** Will model training happen on-premises, in the cloud, or hybrid?
2. **Real-time requirements:** What is the maximum acceptable latency for predictions?
3. **Model update frequency:** How often should models be retrained (weekly, monthly, on-drift)?
4. **Multi-tenant models:** Should models be shared across tenants or tenant-specific?
5. **Integration with CMMS:** What is the approved mechanism for creating work order recommendations?
6. **Cost model:** What are the relative costs of false positives vs. false negatives for each asset family?
7. **Regulatory requirements:** Are there industry-specific regulations (e.g., Uptime Institute, TIA-942) that affect model requirements?

---

## 12. References

- `docs/ARCHITECTURE.md` — System architecture and bounded contexts
- `docs/DATA_MODEL_AND_KPIS.md` — Data model and quality vocabulary
- `docs/OPERATOR_WORKFLOWS.md` — Predictive maintenance workflow
- `docs/LIFECYCLE_OPERATIONS.md` — Predictive maintenance and analytics requirements
- `docs/SECURITY_AND_GOVERNANCE.md` — AI and analytics governance
- `docs/INTEGRATIONS.md` — Source system integration contracts
- `database/schema.sql` — Current database schema
- `src/dcc/api.py` — Current API implementation (model_policy section)
