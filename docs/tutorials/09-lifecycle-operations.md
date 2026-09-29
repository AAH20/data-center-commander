# Tutorial 9: Lifecycle Operations

## Overview

Data Center Commander models the full data-center lifecycle from demand and
site strategy through decommissioning, plus the continuous
operate/maintain/optimize loop. This tutorial covers the 15-stage lifecycle,
the workflow API, operational procedures, and the estate & topology view.

## The 15-Stage Lifecycle

| Stage | Core work | Gate/evidence |
|---|---|---|
| 1. Demand & service strategy | Service demand, latency/availability, geography, sovereignty, growth bands, workload energy budgets | Approved demand envelope, assumptions, risk and cost range |
| 2. Site/utility diligence | Utility capacity, interconnect, tariff, carbon, water, climate, land, fiber, hazards, permits | Independently verified site constraints and utility commitments |
| 3. Concept & design | Topology, N/N+1/2N, electrical one-line, cooling, fire/life safety, security zones, rack density, liquid loop | Stamped design approvals; model traceability |
| 4. Procurement & supply chain | Long-lead transformers, switchgear, UPS, generators, chillers/CDUs, racks, servers, GPUs, software, spares | Approved BOM, vendor assurance, lead-time and obsolescence risk |
| 5. Build & install | Civils, utility entrance, electrical rooms, plant, white space, cabling, grounding, rack, asset receipt | Permit-to-work, inspections, serial/lot provenance, as-built revisions |
| 6. Commission & integrated systems tests | Factory/site acceptance, protection, transfer, load-bank, cooling modes, leak detection, alarms, failover | Witnessed test scripts/results, corrective actions, safe energization sign-off |
| 7. Service onboarding | Service owner, workload class, SLO, dependencies, target zone, resource reservation, energy/cost policy | Service record, placement limits, rollback/continuity plan |
| 8. Operate | Shift handover, alarm triage, daily checks, access review, data-quality review, service capacity review | Time-stamped checklists, owner acknowledgement, unresolved-risk queue |
| 9. Capacity & change | Power/thermal/network/storage/GPU headroom; reserve, maintenance, failover and growth scenarios | Approved change window and post-change validation |
| 10. Maintain & reliability | Condition monitoring, planned work, spares, OEM advisories, calibration, failure mode analysis | CMMS work order, safety permit, tested restoration |
| 11. Incident & continuity | Classify, protect people, notify qualified owner, bound impact, continuity and restoration coordination | Timeline, decision log, verified service/facility state, lessons learned |
| 12. Optimize energy-to-compute | Meter reconciliation, workload attribution, idle analysis, cooling and scheduling advisories | Shadow-mode evidence with uncertainty, SLO and fairness impacts |
| 13. Compliance & assurance | Access, safety, environmental, resilience, asset, change, supplier, and evidence audits | Traceable control evidence, gap owner, due date, closure proof |
| 14. Refresh & migration | Lifecycle risk, vendor end-of-support, workload migration, capacity bridge, data sanitization | Approved migration, validated service continuity, chain of custody |
| 15. Decommission & reuse | Isolate, drain, disconnect under authority, remove media, hazardous materials, reuse/recycle, contract closeout | Verified zero service dependency, media disposition certificate, energy baseline update |

## Workflow API

```
GET /v1/workflows?tenant_id=<uuid>
```

Returns operational workflows with:

| Field | Description |
|---|---|
| `id` | Workflow UUID |
| `workflow_type` | Domain (incident, change, maintenance, etc.) |
| `stage` | Lifecycle stage |
| `status` | open, in_progress, closed, cancelled |
| `priority` | Priority level |
| `title` | Work item title |
| `accountable_owner` | Named owner |
| `opened_at` | When the workflow was opened |
| `due_at` | Deadline |
| `closed_at` | When the workflow was closed |

The API orders by status (open first), priority, due date, and opened
timestamp.

## Workflow Structure

Every workflow uses a durable record:

- `workflow_id` — unique identifier
- `tenant/site/facility` — scope
- `stage` — lifecycle stage
- `severity/risk` — classification
- `accountable_owner` and `deputies` — named responsibility
- `opened_at` / `updated_at` — timestamps
- `source_observations` — what triggered the workflow
- `procedure_id` / `procedure_version` — approved procedure
- `hazards` — identified hazards
- `preconditions` — what must be true before starting
- `approvals` — who approved what
- `tasks` — work items
- `handoffs` — shift or team handoffs
- `evidence` — supporting evidence
- `exit_criteria` — what must be true to close
- `closure_outcome` — how it ended

The application coordinates and records. Authoritative work execution remains
in the designated CMMS/ITSM/BMS/EPMS and permit systems.

## Operational Procedures

### Shift Handover

1. Incoming lead confirms identity, role, site, current restrictions,
   emergency contacts
2. Review unresolved incidents, active work permits, planned maintenance,
   facility alarms, load/thermal margins, data-source freshness, changes
3. Distinguish actionable alarms from stale, suppressed, test, and unknown
   points
4. Assign a named receiving owner and due time
5. Capture handover summary and acknowledgements

### Alarm to Incident

1. Ingest source event, preserve original ID/time/severity
2. Correlate topology and dependent workloads with confidence
3. Route safety/life-safety alarms to existing emergency procedure
4. Open incident, assign incident commander/technical leads
5. Verify recovery from independent telemetry/source-of-truth evidence
6. Close with timeline, root-cause confidence, follow-up work, lessons

### Planned Maintenance

1. Select asset and approved procedure version
2. Evaluate capacity/redundancy under normal, work-in-progress, and one
   additional failure scenarios
3. Link CMMS work order and safety permit
4. Confirm change window, impacted services, notifications, abort conditions
5. Record source-system completion, measured postconditions, exceptions

### Energy Review and Anomaly Follow-up

1. Confirm interval completeness and meter hierarchy
2. Review facility/IT energy balance, PUE/WUE, peak/demand charges, carbon
   factors, workload attribution coverage, thermal margin, forecast error
3. Investigate abrupt change with source graph and concurrent incidents/changes
4. Create advisory opportunities with baselines, guardrails, constraints,
   confidence
5. If an approved external change is made, measure the same boundary and
   cohort after the change

### Predictive Maintenance Case

1. Create a case only when a model is validated for the specific asset family
   and site regime
2. Display predicted failure mode/horizon, calibrated probability or interval,
   top evidence/features, sensor gaps, known limitations, alert history
3. A facilities reliability owner accepts, defers, or rejects with a reason
4. Acceptance may create a CMMS recommendation — not a device control call
5. Record actual findings to measure precision, recall, lead time, avoided
   outage, and intervention cost

### Decommission and Asset Disposition

1. Confirm service/workload dependencies and owner signoff
2. Migrate/retire identity and secrets in the authoritative systems
3. Obtain a safe-isolation and work permit through the approved process
4. Preserve required evidence
5. Sanitize media using the organization's approved standard
6. Record chain of custody, reuse/recycle/vendor certificates, hazardous
   waste records, contract closure, and meter/topology removal

## Estate & Lifecycle UI

The **Estate & lifecycle** section shows:

1. **Facilities** — sites, facilities, status, type
2. **Assets** — asset inventory with type, manufacturer, model, lifecycle
   state, criticality, facility, space
3. **Dependency graph** — topology visualization

### Topology API

```
GET /v1/topology?tenant_id=<uuid>
```

Returns nodes (assets) and edges (relationships):

- **Nodes**: id, kind, label, type, lifecycle state, criticality, external
  ID, facility name
- **Edges**: source asset, target asset, relation type, confidence, valid
  from, provenance

The client uses bounded layered layout and adjacency-list breadth-first
traversal, caps the display to 200 nodes / 400 edges, and labels the source.
This is dependency context, not proof of network reachability or actuation
capability.

## Operations Queue UI

The **Operations queue** section shows all lifecycle workflows with:

- **Search** — filter by title, type, stage, status, priority, owner
- **Status filter** — all, open, in_progress, closed, cancelled
- **CSV export** — download the filtered queue
- **Summary** — count of displayed records, client-side filter note

## Reliability UI

The **Reliability** section shows work-order and condition records linked to
the authoritative CMMS and approved site procedures. It does not execute
work orders or issue permits.

## Next Steps

- [Tutorial 6: Deployment & Operations](06-deployment.md) — operational runbooks
- [Tutorial 10: Evidence & Audit](10-evidence-audit.md) — evidence ledger and audit trail
