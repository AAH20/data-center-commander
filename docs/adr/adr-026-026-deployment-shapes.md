# ADR-026: Deployment Shapes

## Status
Accepted

## Context
The system must support different deployment scenarios from local development to multi-site production.

## Decision
Supported shapes: (1) Local single-node PostgreSQL for engineering and demos; (2) Site-edge collectors with durable local spool during WAN loss; (3) Regional services aggregating approved site data; (4) Central control view joining regions where residency and policy permit; (5) Supabase as a managed Postgres/Auth/Realtime/Storage option. Multi-site failure must not disable local facility controls.

## Consequences
- **Positive:** Flexible deployment; supports various operational scales; clear upgrade path.
- **Negative:** Complexity in multi-site scenarios; data residency constraints.
- **Mitigation:** Clear deployment documentation; residency policy enforcement; local autonomy.
