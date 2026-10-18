# ADR-030: Data Flow Pipeline

## Status
Accepted

## Context
Data moves from source systems through multiple transformation stages to operator views and analytics. Each stage must preserve quality and provenance.

## Decision
Pipeline: `source envelope → validated raw observation → normalized measurement → asset/topology link → quality decision → derived metric → operator review → work record → observed outcome → evidence closeout`. Raw source facts are immutable or versioned; corrections append superseding records. Derived records name formula version, source IDs/time ranges, meter boundary, allocation method, quality gates, and uncertainty.

## Consequences
- **Positive:** Clear data lineage; quality at each stage; evidence-backed decisions.
- **Negative:** Pipeline complexity; latency from multiple stages.
- **Mitigation:** Stage-specific quality gates; provenance tracking; idempotent consumers.
