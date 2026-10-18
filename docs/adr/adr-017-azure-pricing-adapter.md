# ADR-017: Azure Pricing Adapter

## Status
Accepted

## Context
Cloud TCO comparisons require current Azure retail prices. The adapter must be read-only, bounded, and never persist data.

## Decision
The Azure pricing adapter fetches from the public Retail Prices API with bounded requests (1 MB max, 100 rows max, 8s timeout). It never follows provider-supplied next links. Input is validated with regex filters. Output includes commercial basis disclaimer (retail list rates only). No authentication required; no data is persisted.

## Consequences
- **Positive:** No credentials needed; bounded resource usage; clear commercial basis.
- **Negative:** Public API may change; no negotiated pricing; rate limits apply.
- **Mitigation:** Versioned API endpoint; input validation; error handling with clear messages.
