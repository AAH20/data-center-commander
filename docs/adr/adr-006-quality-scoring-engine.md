# ADR-006: Quality Scoring Engine

## Status
Accepted

## Context
Data from multiple sources varies in completeness, freshness, consistency, and accuracy. KPIs and decisions must carry quality metadata.

## Decision
The `QualityEngine` scores sources across four dimensions: completeness (0.30), freshness (0.25), consistency (0.25), accuracy (0.20). Scores are weighted and aggregated. Missing inputs produce `unknown`, not zero. Quality status flows through to KPI observations and forecasts.

## Consequences
- **Positive:** Objective quality assessment; configurable weights; clear quality gates for forecasts.
- **Negative:** Subjective weight tuning; requires reference values for accuracy scoring.
- **Mitigation:** Default weights based on operational experience; quality policies per metric definition.
