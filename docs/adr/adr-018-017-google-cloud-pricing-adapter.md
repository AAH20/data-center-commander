# ADR-018: Google Cloud Pricing Adapter

## Status
Accepted

## Context
Cloud TCO comparisons require Google Cloud pricing. The adapter uses the Cloud Billing API with API key authentication.

## Decision
The Google Cloud pricing adapter fetches from the Cloud Billing API using an API key (`GOOGLE_CLOUD_BILLING_API_KEY`). It is read-only, bounded, and never persists data. Missing API key returns 503. Input is validated. Output includes commercial basis disclaimer.

## Consequences
- **Positive:** Access to Google Cloud pricing; bounded requests; clear error handling.
- **Negative:** Requires API key management; API may change; rate limits apply.
- **Mitigation:** Environment-based key configuration; input validation; clear error messages.
