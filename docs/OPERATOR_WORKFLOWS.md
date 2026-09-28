# Operator workflows and procedures

Every workflow uses a durable record: `workflow_id`, tenant/site/facility,
stage, severity/risk, accountable owner and deputies, opened/updated times,
source observations, procedure ID/version, hazards, preconditions, approvals,
tasks, handoffs, evidence, exit criteria, and closure outcome. The application
coordinates and records; authoritative work execution remains in the designated
CMMS/ITSM/BMS/EPMS and permit systems.

## Shift handover

1. Incoming lead confirms identity, role, site, current restrictions, and
   emergency contacts.
2. Review unresolved incidents, active work permits, planned maintenance,
   facility alarms, load/thermal margins, data-source freshness, and changes.
3. Distinguish actionable alarms from stale, suppressed, test, and unknown
   points; acknowledge the source system only under existing role policy.
4. Assign a named receiving owner and due time. Capture handover summary and
   acknowledgements; do not silently clear another shift's queue.

## Alarm to incident

1. Ingest source event and preserve original ID/time/severity; deduplicate only
   within a source-defined identity/time policy.
2. Correlate topology and dependent workloads with confidence and alternatives;
   keep uncorrelated events visible.
3. Route safety/life-safety alarms to the existing emergency procedure and
   qualified site personnel immediately. The platform never delays or replaces
   the required emergency system.
4. Open incident, assign incident commander/technical leads, capture decisions,
   stakeholders, impact, SLO status, and approved continuity actions.
5. Verify recovery from independent telemetry/source-of-truth evidence; close
   with timeline, root-cause confidence, follow-up work, and lessons.

## Planned maintenance

1. Select asset and approved procedure version; verify identity, ownership,
   dependencies, warranty, last service, calibration, and spares.
2. Evaluate capacity/redundancy under normal, work-in-progress, and one additional
   failure scenarios; expose uncertainty and blocked dependencies.
3. Link CMMS work order and safety permit. Only the authoritative permit system
   can issue clearance, LOTO, hot-work, confined-space, or energization authority.
4. Confirm change window, impacted services, notifications, abort conditions,
   qualified staff, independent verifier, and restoration steps.
5. Record source-system completion, measured postconditions, exceptions, and
   residual risk. Reconcile asset state and update maintenance history.

## Capacity and change assessment

For a proposed compute/rack/service change, aggregate power, cooling, rack
units, network, storage, CPU/GPU, fuel/autonomy, and environmental constraints.
Model the planned maintenance/failure cases and growth forecast. State whether
each number is measured, reserved, estimated, or stale. Produce a non-executable
recommendation containing scope, assumptions, SLO impact, energy/cost/carbon
estimate with uncertainty, rollback/abort criteria, and owners. Human change
control approves and dispatches through existing systems. Compare independent
before/after observations and record the actual outcome.

## Energy review and anomaly follow-up

1. Confirm interval completeness and meter hierarchy; resolve resets, clock
   drift, missing sensors, and double-counted boundaries.
2. Review facility/IT energy balance, PUE/WUE, peak/demand charges, carbon
   factors, workload attribution coverage, thermal margin, and forecast error.
3. Investigate abrupt change with source graph and concurrent incidents/changes;
   do not infer root cause from correlation alone.
4. Create advisory opportunities with baselines, guardrails, workload SLO/fairness,
   constraints and confidence. Route for qualified human review.
5. If an approved external change is made, measure the same boundary and cohort
   after the change; report realized result beside the forecast and uncertainty.

## Predictive-maintenance case

Create a case only when a model is validated for the specific asset family and
site regime. Display predicted failure mode/horizon, calibrated probability or
interval, top evidence/features, sensor gaps, known limitations, and alert
history. A facilities reliability owner accepts, defers, or rejects with a
reason. Acceptance may create a CMMS recommendation—not a device control call.
Record actual findings to measure precision, recall, lead time, avoided outage,
and intervention cost.

## Decommission and asset disposition

Confirm service/workload dependencies and owner signoff; migrate/retire identity
and secrets in the authoritative systems; obtain a safe-isolation and work
permit through the approved process; preserve required evidence; sanitize
media using the organization's approved standard; record chain of custody,
reuse/recycle/vendor certificates, hazardous waste records, contract closure,
and meter/topology removal. A disabled asset is not assumed physically safe or
properly disposed.
