# Video Script: Data Center Commander — Forecasting & Predictive Analytics

**Target length:** 5–6 minutes  
**Audience:** Data center reliability engineers, data scientists, operations managers  
**Goal:** Explain how forecasts are produced, what gates them, why they're advisory, and how predictive maintenance works.

---

## Scene 1 — The Forecasting Problem (0:00–0:40)

**Visual:** Screen recording of the "Data science & BI" view. Show a KPI trend sparkline with a dashed forecast projection. Then show a series with "Forecast withheld" tag.

**Narration:**
> "Every operator wants to know: what's going to break, and when? Data Center Commander approaches forecasting with a simple principle — if the evidence isn't there, the system says so. Let me show you how that works in practice."

**On-screen text:** "Advisory only · No automatic action · Human review required"

---

## Scene 2 — The Model Gate (0:40–1:45)

**Visual:** Animated flowchart: Data → Quality check → History check → Label check → Coverage check → {Pass: advisory forecast | Fail: "Unknown; no forecast"}.

**Narration:**
> "Before any forecast is produced, the data passes through a model gate. First, quality: are the readings good, estimated, or suspect? Second, history: is there enough clean, non-synthetic data? The system requires a minimum of seven daily points per metric. Third, labels: for predictive maintenance, are there validated failure labels? Fourth, coverage: is the telemetry complete enough for the interval? If any check fails, the system returns 'Unknown' with reason codes. It never guesses."

**Action:** Show a metric with 5 clean points — forecast withheld. Then show the same metric with 10 points — forecast appears.

---

## Scene 3 — Trend & Short-Horizon Forecast (1:45–2:45)

**Visual:** Close-up of the trend charts in the analytics view. Show observed values as a solid teal line, forecast as a dashed amber line. Point out the metadata: "OLS trend · 3-step advisory projection · N non-synthetic daily points".

**Narration:**
> "When the gate passes, the system fits an ordinary least squares trend to the observed data and projects three steps forward. The projection is explicitly labeled as advisory. The metadata tells you exactly what was computed: the method, the number of clean points, and the latest observation timestamp. You can see at a glance whether the forecast is based on 30 days of data or 7."

**Action:** Toggle between 7-day and 30-day analysis windows. Show how the forecast changes.

---

## Scene 4 — Data Quality & Model Readiness (2:45–3:45)

**Visual:** Show the "Data quality & model readiness" card and the "Telemetry quality distribution" table. Highlight quality classes: good, estimated, suspect, bad, missing, stale, late, replayed, clock_skew, out_of_range, uncalibrated, superseded.

**Narration:**
> "Forecasting is only as good as its inputs. The telemetry quality distribution shows you exactly how many samples fall into each quality class. A metric with 40% suspect readings won't produce a reliable forecast — and the system won't pretend it does. The model readiness indicator tells you how many clean daily points exist versus how many are required. This is the data quality vocabulary that makes the difference between a forecast you can act on and one you should ignore."

---

## Scene 5 — Predictive Maintenance (3:45–5:00)

**Visual:** Animated diagram showing the predictive maintenance workflow: Condition features → Model → Validated for asset family? → {Yes: predicted failure mode/horizon, calibrated probability, top evidence} → Human review → {Accept: CMMS recommendation | Defer: record reason | Reject: record reason}.

**Narration:**
> "Predictive maintenance follows a strict protocol. A model is only used when it's validated for the specific asset family and site regime. The prediction shows the failure mode, the horizon, a calibrated probability or interval, the top evidence features, sensor gaps, and known limitations. A facilities reliability owner then accepts, defers, or rejects with a reason. Acceptance may create a CMMS recommendation — not a device control call. The actual outcome is recorded to measure precision, recall, lead time, and avoided cost."

**Action:** Show a sample prediction card. Walk through the accept/defer/reject buttons.

---

## Scene 6 — Capacity Forecasting (5:00–5:30)

**Visual:** Navigate to "Capacity & resilience" view. Show capacity snapshots with scenario evaluation: normal, planned maintenance, and failure domain scenarios.

**Narration:**
> "Capacity forecasting evaluates usable capacity under normal operations, planned maintenance, and failure scenarios. It's not just nameplate ratings — it's what you actually have available when you need it. The system models growth forecasts, reserve policy, and maintenance windows to give you a realistic picture of headroom."

---

## Scene 7 — Close (5:30–6:00)

**Visual:** Return to the analytics view. Fade to the `docs/LIFECYCLE_OPERATIONS.md` section on predictive maintenance.

**Narration:**
> "Every forecast in Data Center Commander is advisory, gated by evidence quality, and designed for human review. The system doesn't replace operator judgment — it gives operators better information to exercise that judgment. Full details are in the lifecycle operations documentation."

---

## Production notes

- Use screen recordings from the synthetic demo for UI scenes.
- Animated diagrams for the model gate and predictive maintenance workflow.
- Emphasize the "foreheld" state — this is a key differentiator.
- Caption all narration.
