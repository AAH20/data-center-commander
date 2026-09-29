# ADR-032: Change Management

## Status
Accepted

## Context
Changes to infrastructure must be controlled with risk assessment, blast radius analysis, rollback plans, and verification.

## Decision
Change records capture: change window, risk class, blast radius, plan, rollback plan, approval state, before/after state, and verification. Changes link to workflows and require approval. The change window uses PostgreSQL `tstzrange` for temporal queries. Verification confirms the change achieved its intended outcome.

## Consequences
- **Positive:** Controlled changes; risk awareness; rollback capability; verification.
- **Negative:** Process overhead; requires discipline in change recording.
- **Mitigation:** Risk class assessment; approval requirements; verification tracking.
