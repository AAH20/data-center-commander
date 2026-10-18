# ADR-004: Adapter Pattern for Source Integrations

## Status
Accepted

## Context
The system must integrate with diverse source systems (utility, BMS, EPMS, CMMS, hypervisor, cloud) without coupling core logic to vendor APIs.

## Decision
Each source integration implements a versioned adapter with declared capabilities, health checks, and rate-limit tracking. The `AdapterRegistry` provides discovery, capability negotiation, and health monitoring. Adapters are read-only and declare identity, endpoint, scopes, and version.

## Consequences
- **Positive:** Pluggable architecture; vendor independence; testable contracts; clear capability negotiation.
- **Negative:** Adapter maintenance overhead; capability gaps when vendors change APIs.
- **Mitigation:** Adapter conformance suite; versioned adapter contracts; health monitoring with circuit breakers.
