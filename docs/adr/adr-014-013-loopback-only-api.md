# ADR-014: Loopback-Only API

## Status
Accepted

## Context
The local development API must not be exposed to networks. Production deployments require authentication and authorization.

## Decision
The development API binds only to `127.0.0.1`, `::1`, or `localhost`. Non-loopback binds raise `ValueError`. The API is unauthenticated in local mode. Production deployments must add AuthN/AuthZ (roadmap stage 5). The `/healthz` and `/readyz` endpoints report liveness and readiness without authentication.

## Consequences
- **Positive:** Prevents accidental exposure; clear security boundary for local development.
- **Negative:** No remote access for testing; production requires additional infrastructure.
- **Mitigation:** Explicit loopback enforcement; production IAM on roadmap; security audit.
