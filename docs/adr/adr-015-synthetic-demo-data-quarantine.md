# ADR-015: Synthetic Demo Data Quarantine

## Status
Accepted

## Context
Synthetic demo data must never appear as live operational data. Operators need to distinguish real observations from fixtures.

## Decision
Synthetic data is tagged with `provenance.synthetic = true` or `source_kind = 'synthetic_demo'`. The API quarantines synthetic data unless `demo=synthetic` query parameter is explicitly provided. The UI displays a persistent "SYNTHETIC DEMO · NOT LIVE" banner. Demo mode is presentation-only and never enables actuation.

## Consequences
- **Positive:** Clear separation of real and synthetic data; prevents confusion; safe demo environment.
- **Negative:** Requires discipline in tagging; demo mode could be misused.
- **Mitigation:** Database constraints enforce synthetic tagging; UI banners; audit logging.
