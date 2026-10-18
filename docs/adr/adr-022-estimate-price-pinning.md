# ADR-022: Estimate Price Pinning

## Status
Accepted

## Context
Cost estimates must reference specific, approved price observations to ensure reproducibility and auditability. Prices must be current and normalized to the estimate currency.

## Decision
Estimate line items with `pricing_status = 'sourced'` must reference a `price_observation_id`. A database trigger validates that the price observation is approved, the cost book is approved, units match, currency matches, geography matches, and the price is current relative to the estimate's `price_as_of` date. Prices are normalized to the book currency with FX rates.

## Consequences
- **Positive:** Reproducible estimates; price integrity; currency consistency; audit trail.
- **Negative:** Requires approved price observations; FX rate management; price freshness monitoring.
- **Mitigation:** Price freshness validation; cost book approval workflow; source digest tracking.
