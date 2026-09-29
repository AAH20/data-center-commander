# Tutorial 8: Capacity & Resilience

## Overview

Data Center Commander models capacity across multiple dimensions — power,
cooling, rack, network, storage, CPU/GPU — with explicit reserves, policy
scenarios, and failure domains. This tutorial covers the capacity API,
scenario modeling, headroom calculation, and the resilience workflow.

## Capacity API

```
GET /v1/capacity?tenant_id=<uuid>
```

Returns capacity snapshots with:

| Field | Description |
|---|---|
| `facility_id` | Facility UUID |
| `dimension` | Power, cooling, rack, network, storage, CPU, GPU |
| `scenario` | Normal, maintenance, failure, or growth scenario |
| `usable` | Validated usable capacity |
| `reserved` | Reserved for existing commitments |
| `policy_reserve` | Policy-mandated reserve (N+1, 2N, etc.) |
| `forecast_peak` | Forecast peak demand |
| `unit` | kW, racks, Gbps, TB, cores, GPUs |
| `quality_status` | Quality of the underlying data |
| `observed_at` | When the snapshot was taken |

The API uses `DISTINCT ON (facility_id, dimension, scenario)` to return the
latest snapshot per dimension/scenario combination.

## Capacity Calculation

### Free Capacity

```
free = validated_usable - reservations - policy_reserve
```

### Scenario Capacity

Scenario capacity additionally evaluates:

- **Planned maintenance** — capacity reduced during maintenance windows
- **Failure domains** — capacity reduced by one or more failure scenarios
- **Growth forecast** — capacity reduced by forecast growth

### Dimensions

| Dimension | Unit | Sources |
|---|---|---|
| Power | kW | Electrical meters, UPS capacity, generator capacity |
| Cooling | kW | Chiller capacity, CRAH/CRAC capacity, cooling tower capacity |
| Rack | racks | Physical rack inventory |
| Network | Gbps | Switch port capacity, fiber capacity |
| Storage | TB | Storage array capacity |
| CPU | cores | Server CPU inventory |
| GPU | GPUs | Accelerator inventory |

## Capacity Snapshots

The `capacity_snapshots` table stores point-in-time capacity evaluations:

```sql
SELECT DISTINCT ON (facility_id, dimension, scenario)
    facility_id, dimension, scenario,
    usable, reserved, policy_reserve, forecast_peak,
    unit, quality_status, observed_at
FROM dcc.capacity_snapshots
WHERE tenant_id = '<uuid>'
ORDER BY facility_id, dimension, scenario, observed_at DESC
```

Each snapshot carries a `quality_status` indicating whether the underlying
data is measured, estimated, or stale.

## Headroom Calculation

The UI computes capacity headroom as:

```
headroom_pct = (free - forecast_peak) / usable × 100
```

A negative headroom indicates that forecast peak demand exceeds free
capacity, triggering a review workflow.

## Resilience Scenarios

### Normal Scenario

All systems operational. Capacity = usable - reserved - policy_reserve.

### Maintenance Scenario

One or more systems are in planned maintenance. Capacity is reduced by the
maintenance impact. The maintenance window and impacted systems are
explicitly modeled.

### Failure Scenario

One or more systems have failed. Capacity is reduced by the failure impact.
The failure domain (N+1, 2N) determines how much capacity is lost.

### Growth Scenario

Forecast growth is applied to the demand side. Capacity headroom is
recalculated with the growth forecast.

## Capacity and Change Assessment

For a proposed compute/rack/service change:

1. **Aggregate constraints** — power, cooling, rack units, network, storage,
   CPU/GPU, fuel/autonomy, environmental constraints
2. **Model scenarios** — planned maintenance, failure cases, growth forecast
3. **Classify numbers** — measured, reserved, estimated, or stale
4. **Produce recommendation** — scope, assumptions, SLO impact,
   energy/cost/carbon estimate with uncertainty, rollback/abort criteria,
   owners
5. **Human approval** — change control approves and dispatches through
   existing systems
6. **Post-change validation** — compare independent before/after observations
   and record the actual outcome

The recommendation is **non-executable**. It does not create infrastructure
commands.

## The Capacity UI

The **Capacity & resilience** section shows:

- Usable, reserved, and policy reserve by dimension
- Forecast peak demand
- Free capacity and headroom percentage
- Quality status for each snapshot
- Scenario comparison (normal vs. maintenance vs. failure)

## Energy-to-Compute Accounting

An energy claim is meaningful only for an explicit:

- **Site** — which facility
- **Meter boundary** — utility, facility, IT, or sub-meter
- **Interval** — time window with aligned start/end
- **Source quality** — good, estimated, suspect, bad, missing
- **Workload cohort** — which workloads are included
- **Allocation tier** — direct meter, device telemetry model, capacity-share
  model, or unallocated
- **Formula version** — versioned calculation definition

### Allocation Tiers

| Tier | Description | Error bound |
|---|---|---|
| Direct meter | Submeter directly measures the workload | Lowest |
| Device telemetry model | Power draw modeled from device telemetry | Medium |
| Capacity-share model | Shared overhead allocated by capacity share | Higher |
| Unallocated | Not allocated; remains in shared pool | N/A |

Never distribute shared overhead as if directly metered. Reject comparisons
with misaligned intervals, meter resets, uncalibrated sources, gaps above
policy, or incompatible facility/IT boundaries.

## KPI Catalog

| KPI family | Examples | Required dimensions |
|---|---|---|
| Energy | Facility/IT kWh, peak demand, PUE | Boundary, interval, meter coverage, calibration |
| Compute efficiency | Useful work/kWh, GPU-hours/kWh | Workload cohort, SLO class, allocation tier |
| Cooling & water | Cooling kW/IT kW, WUE, thermal margin | Climate, cooling topology, sensor quality |
| Cost | Tariff cost, demand charge exposure | Tariff version, timezone, currency |
| Carbon | kgCO2e by interval, location/market-based | Factor source/time/geography, accounting method |
| Capacity | Usable/reserved/free by dimension | Redundancy, maintenance cases, peak forecast |
| Reliability | Availability, MTTR, repeat failure | Service boundary, incident definition |
| Operations | Change success, work backlog, stale telemetry | Source lineage, denominator, exclusions |

## Continuous BI and Forecast Lifecycle

Every report records:

- **As-of watermark** — when the data was current
- **Source completeness** — coverage denominator
- **Calculation/model version** — formula or model version
- **Dimensions** — site, boundary, interval, cohort
- **Figure type** — observed, allocated, estimated, or forecast

Corrections never rewrite prior operator decisions. They create a new version
and recalculate a linked view. The audit view must reproduce the number
shown at the time a decision was made.

## Next Steps

- [Tutorial 4: Economics & Cost Estimation](04-economics.md) — cost per kW-year and unit economics
- [Tutorial 9: Lifecycle Operations](09-lifecycle-operations.md) — the 15-stage lifecycle
