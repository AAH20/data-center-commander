# Tutorial 10: Evidence & Audit

## Overview

Every number in Data Center Commander must be traceable to its source. The
evidence ledger is append-only, tenant-scoped, and hash-chained. This
tutorial covers the evidence API, the provenance system, the audit workflow,
and how to reproduce any historical number.

## Evidence API

```
GET /v1/evidence?tenant_id=<uuid>
```

Returns the last 100 evidence events per tenant, ordered by sequence
descending:

| Field | Description |
|---|---|
| `sequence` | Monotonically increasing per tenant |
| `event_type` | Classification (reading, calculation, decision, etc.) |
| `occurred_at` | When the event happened |
| `actor_ref` | Who or what caused the event |
| `subject_type` | What the event is about (asset, KPI, workflow, etc.) |
| `subject_id` | UUID of the subject |
| `event_hash` | SHA-256 hash for integrity verification |

The evidence ledger is **append-only**. Events are never updated or deleted.
Corrections create a new event that supersedes the original.

## Evidence Event Types

| Type | Description |
|---|---|
| `reading` | Raw telemetry reading ingested from a connector |
| `calculation` | KPI or cost calculation performed |
| `allocation` | Energy or cost allocation to a workload |
| `decision` | Human or automated decision recorded |
| `approval` | Workflow approval granted |
| `rejection` | Workflow rejected with reason |
| `correction` | Superseding correction to a prior event |
| `workflow` | Workflow stage transition |
| `evidence` | External evidence attached to a record |

## Provenance System

The `src/dcc/provenance/tracker.py` module provides hash-chained lineage
tracking:

### Source Registration

```python
from dcc.provenance.tracker import LineageTracker, SourceType

tracker = LineageTracker()
node = tracker.register_source(
    tenant_id="dcc00000-0000-4000-8000-000000000001",
    node_type="connector_reading",
    label="UPS-1 power reading",
    source_type=SourceType.CONNECTOR,
    content={"voltage": 230.1, "current": 45.2},
)
```

### Transformation Recording

```python
from dcc.provenance.tracker import TransformationType

step = tracker.record_transformation(
    tenant_id="dcc00000-0000-4000-8000-000000000001",
    operation="kwh_calculation",
    transformation_type=TransformationType.CALCULATION,
    input_node_ids=[node.node_id],
    output_node_id=output_node_id,
    output_content={"energy_kwh": 10.4},
    actor_ref="system",
)
```

### Chain Verification

```python
result = tracker.verify_chain(tenant_id="dcc00000-0000-4000-8000-000000000001")
# result = {
#     "tenant_id": "...",
#     "valid": True,
#     "steps_checked": 42,
#     "broken_at": None,
# }
```

### Lineage Query

```python
lineage = tracker.get_lineage(
    tenant_id="dcc00000-0000-4000-8000-000000000001",
    artifact_id="kpi_123",
    direction="upstream",
    max_depth=10,
)
# Returns nodes and edges walking upstream from the artifact
```

## Source Types

| Type | Description |
|---|---|
| `connector` | Data ingested from an external system via a connector |
| `manual_entry` | Human-entered data |
| `api_import` | Data imported via an API |
| `seed_fixture` | Synthetic demo data (visibly tagged) |
| `calculated` | Derived from other data via a calculation |
| `external_system` | Data from an external system of record |

## Transformation Types

| Type | Description |
|---|---|
| `ingestion` | Raw data received from a source |
| `validation` | Data validated against quality rules |
| `aggregation` | Data aggregated over time or across sources |
| `allocation` | Energy or cost allocated to a workload |
| `normalization` | Units or intervals normalized |
| `calculation` | KPI or cost calculated |
| `filter` | Data filtered by quality or scope |
| `join` | Data joined across sources |
| `derivation` | Data derived from a formula |

## Quality Statuses

| Status | Description |
|---|---|
| `good` | Passed all quality checks |
| `estimated` | Modeled or interpolated, not directly measured |
| `suspect` | May be incorrect; under review |
| `bad` | Failed validation; do not use |
| `missing` | Expected data not received |
| `unverified` | Not yet validated |

## Audit Workflow

### Reproducing a Historical Number

To reproduce any number shown at the time a decision was made:

1. **Identify the artifact** — KPI observation, cost estimate, capacity snapshot
2. **Query the evidence ledger** — find the calculation event for that artifact
3. **Walk the lineage** — trace upstream to source readings
4. **Verify the chain** — confirm hash-chain integrity
5. **Check quality** — verify quality status of each input
6. **Reproduce the calculation** — apply the versioned formula to the source data

### The Audit View

The **Evidence & audit** section shows:

- Append-only event references (sequence, type, timestamp, actor, subject, hash)
- Full payload access belongs in the authorized audit workflow
- The audit view must reproduce the number shown at the time a decision was made

## Data Lineage and Scale

### Retention Policy

| Data type | Retention |
|---|---|
| Raw readings | Policy-defined hot retention |
| Derived rollups | Agreed operational/audit horizons |
| Evidence digests/decision records | Legal retention |

### Partitioning

Partition by time and tenant only after measured scale requires it. Avoid
partitioning that destroys useful uniqueness or RLS. Supabase migration must
verify RLS on partitions, views, functions, and service-role routes.

### Export

Retention and export are per-tenant policy. Export verification ensures data
integrity during transfer.

## The Evidence UI

The **Evidence & audit** section displays:

- Last 100 evidence events per tenant
- Event sequence, type, timestamp, actor reference, subject type/ID, event hash
- Append-only guarantee (no edit or delete)
- Tenant-scoped visibility (RLS enforced)

Full payload access belongs in the authorized audit workflow. The UI does not
display raw payloads, credentials, or sensitive operational details.

## Continuous BI and Forecast Lifecycle

Every report records:

- **As-of watermark** — when the data was current
- **Source completeness** — coverage denominator
- **Calculation/model version** — formula or model version used
- **Dimensions** — site, boundary, interval, cohort
- **Figure type** — observed, allocated, estimated, or forecast

Corrections never rewrite prior operator decisions. They create a new version
and recalculate a linked view. The audit view must reproduce the number
shown at the time a decision was made.

## KPI Lineage

Each KPI observation carries:

- `calculation_hash` — hash of the formula and inputs
- `source_watermark` — timestamp of the newest source reading used
- `window_start` / `window_end` — the interval the KPI covers
- `numerator` / `denominator` — the values used in the calculation
- `coverage` — fraction of expected samples present
- `uncertainty` — calculated uncertainty
- `status` / `reason_codes` — quality status and reason codes if not `good`

## Cost Lineage

Each cost estimate carries:

- `calculation_version` — version of the estimation engine
- `price_as_of` — the date prices were observed
- `assumptions` — explicit assumptions (PUE, redundancy, escalation, etc.)
- `line_items` — each with quantity, unit cost, extended cost, pricing status
- `lifecycle_pv` / `low_pv` / `high_pv` — present values
- `unpriced_lines` — count of lines without a price
- `synthetic_lines` — count of synthetic lines (visibly tagged)

## Next Steps

- [Tutorial 1: Getting Started](01-getting-started.md) — return to the basics
- [Tutorial 7: Data Quality & Provenance](07-data-quality.md) — quality engine details
- [Tutorial 5: Security & Governance](05-security.md) — production readiness
