# ADR-023: Cost Book Versioning

## Status
Accepted

## Context
Price observations must be organized into versioned cost books with clear status (draft, approved, superseded, archived) and validity periods.

## Decision
Cost books have name, version, status, currency, geography, price basis (budgetary, quoted, contracted, actual, benchmark), and validity dates. Approved books require `approved_by` and `approved_at`. Price observations reference a cost book. The `estimate_cost_rollup` view aggregates line items by phase and currency.

## Consequences
- **Positive:** Organized price data; clear approval workflow; validity period enforcement.
- **Negative:** Version management complexity; requires approval discipline.
- **Mitigation:** Status constraints; approval tracking; source policy metadata.
