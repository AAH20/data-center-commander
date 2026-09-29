"""Cost allocation engine for shared cost distribution across workloads.

This module provides pure computation for allocating shared costs (energy, facilities,
operations) across workloads using various allocation bases. It does not access the
database directly; the caller fetches raw data and persists results.

Allocation methods:
- direct_meter: Based on metered energy consumption (energy_allocations)
- measured_usage: Based on measured usage (generalization of direct_meter)
- capacity_share: Based on capacity consumption (capacity_snapshots)
- floor_area: Based on floor area occupation (spaces.floor_area_m2)
- rack_units: Based on rack unit occupation (spaces.rack_units)
- headcount: Based on headcount (workload attributes or external)
- equal_share: Equal division among all workloads
- manual_approved: Pre-approved manual fractions
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from enum import Enum
from typing import Any

METHOD_VERSION = "1.0"
ALLOCATION_PRECISION = Decimal("0.000001")  # 6 decimal places


class AllocationMethod(str, Enum):
    """Supported cost allocation methods."""
    DIRECT_METER = "direct_meter"
    MEASURED_USAGE = "measured_usage"
    CAPACITY_SHARE = "capacity_share"
    FLOOR_AREA = "floor_area"
    RACK_UNITS = "rack_units"
    HEADCOUNT = "headcount"
    EQUAL_SHARE = "equal_share"
    MANUAL_APPROVED = "manual_approved"


@dataclass(frozen=True)
class WorkloadShare:
    """A workload's measured share for allocation purposes."""
    workload_id: str
    share_value: Decimal
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationResult:
    """Result of allocating cost to a single workload."""
    workload_id: str
    allocated_amount: Decimal
    allocation_fraction: Decimal
    basis: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationReport:
    """Complete report of a cost allocation run."""
    cost_actual_id: str
    total_amount: Decimal
    allocated_total: Decimal
    unallocated_amount: Decimal
    currency: str
    method: str
    method_version: str
    results: list[AllocationResult]
    reconciliation: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _validate_inputs(
    total_amount: Decimal,
    currency: str,
    workload_ids: list[str],
    shares: list[WorkloadShare] | None,
    custom_weights: dict[str, Decimal] | None,
) -> None:
    """Validate allocation inputs."""
    if total_amount < 0:
        raise ValueError("total_amount must be non-negative")
    if not currency or len(currency) != 3:
        raise ValueError("currency must be a 3-letter ISO code")
    if not workload_ids:
        raise ValueError("at least one workload is required")
    if len(set(workload_ids)) != len(workload_ids):
        raise ValueError("workload_ids must be unique")
    if shares is not None:
        share_ids = [s.workload_id for s in shares]
        if set(share_ids) != set(workload_ids):
            raise ValueError("shares must cover exactly the provided workload_ids")
        for s in shares:
            if s.share_value < 0:
                raise ValueError(f"share_value for workload {s.workload_id} must be non-negative")
    if custom_weights is not None:
        if set(custom_weights.keys()) != set(workload_ids):
            raise ValueError("custom_weights must cover exactly the provided workload_ids")
        for wid, w in custom_weights.items():
            if w < 0:
                raise ValueError(f"weight for workload {wid} must be non-negative")
        total_weight = sum(custom_weights.values())
        if total_weight == 0:
            raise ValueError("custom_weights must have a positive total")


def _round_amount(amount: Decimal) -> Decimal:
    """Round to allocation precision."""
    return amount.quantize(ALLOCATION_PRECISION, rounding=ROUND_HALF_UP)


def _allocate_equal_shares(
    total_amount: Decimal,
    workload_ids: list[str],
) -> list[AllocationResult]:
    """Divide total_amount equally among workloads using largest remainder."""
    n = len(workload_ids)
    if n == 0:
        return []

    # Compute exact equal share
    exact_share = total_amount / Decimal(n)
    rounded_share = _round_amount(exact_share)

    # Initial allocation
    results: list[AllocationResult] = []
    total_allocated = Decimal("0")
    for wid in workload_ids:
        results.append(AllocationResult(
            workload_id=wid,
            allocated_amount=rounded_share,
            allocation_fraction=_round_amount(Decimal(1) / Decimal(n)),
            basis="equal_share",
            evidence={"equal_division": True, "workload_count": n},
        ))
        total_allocated += rounded_share

    # Adjust for rounding residual
    residual = total_amount - total_allocated
    if residual != 0:
        # Add residual to first workload
        first = results[0]
        new_amount = _round_amount(first.allocated_amount + residual)
        new_fraction = _round_amount(
            first.allocation_fraction + (residual / total_amount if total_amount > 0 else Decimal("0"))
        )
        results[0] = AllocationResult(
            workload_id=first.workload_id,
            allocated_amount=new_amount,
            allocation_fraction=new_fraction,
            basis="equal_share",
            evidence={"equal_division": True, "workload_count": n, "rounding_adjustment": str(residual)},
        )

    return results


def _allocate_by_weights(
    total_amount: Decimal,
    shares: list[WorkloadShare],
) -> list[AllocationResult]:
    """Allocate proportionally based on share values using largest remainder."""
    if not shares:
        return []

    total_share = sum(s.share_value for s in shares)
    if total_share == 0:
        # All shares are zero - fall back to equal division
        return _allocate_equal_shares(total_amount, [s.workload_id for s in shares])

    # Compute exact amounts
    exact_amounts: list[tuple[WorkloadShare, Decimal, Decimal]] = []
    for s in shares:
        fraction = s.share_value / total_share
        exact = total_amount * fraction
        exact_amounts.append((s, exact, fraction))

    # Round down and track remainders
    rounded_results: list[tuple[WorkloadShare, Decimal, Decimal]] = []
    total_rounded = Decimal("0")
    remainders: list[tuple[int, Decimal]] = []
    for i, (s, exact, fraction) in enumerate(exact_amounts):
        rounded = exact.quantize(ALLOCATION_PRECISION, rounding=ROUND_DOWN)
        remainder = exact - rounded
        rounded_results.append((s, rounded, fraction))
        total_rounded += rounded
        remainders.append((i, remainder))

    # Distribute residual to largest remainders
    residual = total_amount - total_rounded
    # Convert residual to number of precision units
    residual_units = int(residual / ALLOCATION_PRECISION)

    # Sort by remainder descending
    remainders.sort(key=lambda x: x[1], reverse=True)

    adjustments = [Decimal("0")] * len(shares)
    for i in range(residual_units):
        idx = remainders[i % len(remainders)][0]
        adjustments[idx] += ALLOCATION_PRECISION

    results: list[AllocationResult] = []
    for i, (s, rounded, fraction) in enumerate(rounded_results):
        final_amount = rounded + adjustments[i]
        final_fraction = final_amount / total_amount if total_amount > 0 else Decimal("0")
        results.append(AllocationResult(
            workload_id=s.workload_id,
            allocated_amount=_round_amount(final_amount),
            allocation_fraction=_round_amount(final_fraction),
            basis="measured_share",
            evidence={
                "share_value": str(s.share_value),
                "total_share": str(total_share),
                "fraction": str(fraction),
                **s.evidence,
            },
        ))

    return results


def allocate_cost(
    cost_actual_id: str,
    total_amount: Decimal,
    currency: str,
    method: AllocationMethod | str,
    workload_ids: list[str],
    shares: list[WorkloadShare] | None = None,
    custom_weights: dict[str, Decimal] | None = None,
) -> AllocationReport:
    """Allocate a shared cost across workloads.

    Args:
        cost_actual_id: The cost actual being allocated.
        total_amount: The total amount to allocate.
        currency: 3-letter ISO currency code.
        method: Allocation method to use.
        workload_ids: IDs of workloads to allocate to.
        shares: Measured shares for each workload (required for direct_meter,
            measured_usage, capacity_share, floor_area, rack_units, headcount).
        custom_weights: Pre-approved weights (required for manual_approved).

    Returns:
        AllocationReport with full allocation results and reconciliation.

    Raises:
        ValueError: If inputs are invalid or required data is missing.
    """
    if isinstance(method, str):
        method = AllocationMethod(method)

    _validate_inputs(total_amount, currency, workload_ids, shares, custom_weights)

    # Compute allocations based on method
    if method == AllocationMethod.EQUAL_SHARE:
        results = _allocate_equal_shares(total_amount, workload_ids)
    elif method == AllocationMethod.MANUAL_APPROVED:
        if custom_weights is None:
            raise ValueError("custom_weights required for manual_approved method")
        weight_shares = [
            WorkloadShare(
                workload_id=wid,
                share_value=custom_weights[wid],
                evidence={"manual_weight": str(custom_weights[wid])},
            )
            for wid in workload_ids
        ]
        results = _allocate_by_weights(total_amount, weight_shares)
    else:
        if shares is None:
            raise ValueError(f"shares required for {method.value} method")
        results = _allocate_by_weights(total_amount, shares)

    # Compute reconciliation
    allocated_total = sum((r.allocated_amount for r in results), Decimal("0"))
    unallocated = total_amount - allocated_total

    reconciliation = {
        "total_amount": str(total_amount),
        "allocated_total": str(allocated_total),
        "unallocated_amount": str(unallocated),
        "fully_allocated": unallocated == 0,
        "workload_count": len(results),
    }

    return AllocationReport(
        cost_actual_id=cost_actual_id,
        total_amount=total_amount,
        allocated_total=allocated_total,
        unallocated_amount=unallocated,
        currency=currency,
        method=method.value,
        method_version=METHOD_VERSION,
        results=results,
        reconciliation=reconciliation,
    )


def build_evidence(
    method: AllocationMethod | str,
    window_start: datetime,
    window_end: datetime,
    source_data: dict[str, Any],
) -> dict[str, Any]:
    """Build evidence JSON for an allocation run."""
    if isinstance(method, str):
        method = AllocationMethod(method)
    return {
        "method": method.value,
        "method_version": METHOD_VERSION,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "source_data": source_data,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_allocation_hash(report: AllocationReport) -> str:
    """Compute a deterministic hash of an allocation report for audit."""
    data = {
        "cost_actual_id": report.cost_actual_id,
        "total_amount": str(report.total_amount),
        "currency": report.currency,
        "method": report.method,
        "method_version": report.method_version,
        "results": [
            {
                "workload_id": r.workload_id,
                "allocated_amount": str(r.allocated_amount),
                "allocation_fraction": str(r.allocation_fraction),
            }
            for r in report.results
        ],
    }
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def validate_allocation(report: AllocationReport) -> bool:
    """Validate that an allocation report is internally consistent."""
    total = sum(r.allocated_amount for r in report.results)
    return total == report.total_amount


def allocation_rows_for_insert(
    report: AllocationReport,
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    """Convert allocation report to rows ready for cost_allocations INSERT.

    Returns list of dicts with keys matching cost_allocations columns:
    tenant_id (added by caller), cost_actual_id, workload_id, allocation_basis,
    allocated_amount, currency, allocation_fraction, window_start, window_end,
    method_version, evidence.
    """
    rows = []
    for r in report.results:
        rows.append({
            "cost_actual_id": report.cost_actual_id,
            "workload_id": r.workload_id,
            "allocation_basis": report.method,
            "allocated_amount": r.allocated_amount,
            "currency": report.currency,
            "allocation_fraction": r.allocation_fraction,
            "window_start": window_start,
            "window_end": window_end,
            "method_version": report.method_version,
            "evidence": {
                **r.evidence,
                "allocation_hash": compute_allocation_hash(report),
                "computed_at": report.created_at.isoformat(),
            },
        })
    return rows


# ---------------------------------------------------------------------------
# Helper functions for building WorkloadShare lists from common data patterns
# ---------------------------------------------------------------------------


def shares_from_energy_allocations(
    energy_allocations: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> list[WorkloadShare]:
    """Build WorkloadShare list from energy_allocations rows.

    Args:
        energy_allocations: Rows from dcc.energy_allocations with keys:
            workload_id, energy_kwh, allocation_method, coverage, provenance
        window_start: Start of allocation window
        window_end: End of allocation window

    Returns:
        List of WorkloadShare with energy_kwh as the share value.
    """
    shares = []
    for row in energy_allocations:
        wid = row.get("workload_id")
        energy = row.get("energy_kwh")
        if wid is None or energy is None:
            continue
        energy_dec = Decimal(str(energy))
        if energy_dec <= 0:
            continue
        shares.append(WorkloadShare(
            workload_id=str(wid),
            share_value=energy_dec,
            evidence={
                "source": "energy_allocations",
                "energy_kwh": str(energy_dec),
                "allocation_method": row.get("allocation_method"),
                "coverage": row.get("coverage"),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            },
        ))
    return shares


def shares_from_floor_areas(
    workload_areas: dict[str, Decimal],
) -> list[WorkloadShare]:
    """Build WorkloadShare list from floor areas per workload.

    Args:
        workload_areas: Mapping of workload_id to floor area in m².

    Returns:
        List of WorkloadShare with floor area as the share value.
    """
    return [
        WorkloadShare(
            workload_id=wid,
            share_value=area,
            evidence={"source": "spaces.floor_area_m2", "floor_area_m2": str(area)},
        )
        for wid, area in workload_areas.items()
        if area > 0
    ]


def shares_from_rack_units(
    workload_racks: dict[str, Decimal],
) -> list[WorkloadShare]:
    """Build WorkloadShare list from rack units per workload.

    Args:
        workload_racks: Mapping of workload_id to rack units.

    Returns:
        List of WorkloadShare with rack units as the share value.
    """
    return [
        WorkloadShare(
            workload_id=wid,
            share_value=racks,
            evidence={"source": "spaces.rack_units", "rack_units": str(racks)},
        )
        for wid, racks in workload_racks.items()
        if racks > 0
    ]


def shares_from_headcount(
    workload_headcounts: dict[str, Decimal],
) -> list[WorkloadShare]:
    """Build WorkloadShare list from headcount per workload.

    Args:
        workload_headcounts: Mapping of workload_id to headcount.

    Returns:
        List of WorkloadShare with headcount as the share value.
    """
    return [
        WorkloadShare(
            workload_id=wid,
            share_value=hc,
            evidence={"source": "headcount", "headcount": str(hc)},
        )
        for wid, hc in workload_headcounts.items()
        if hc > 0
    ]


def shares_from_capacity(
    workload_capacities: dict[str, Decimal],
) -> list[WorkloadShare]:
    """Build WorkloadShare list from capacity values per workload.

    Args:
        workload_capacities: Mapping of workload_id to capacity (e.g., kW).

    Returns:
        List of WorkloadShare with capacity as the share value.
    """
    return [
        WorkloadShare(
            workload_id=wid,
            share_value=cap,
            evidence={"source": "capacity_snapshots", "capacity": str(cap)},
        )
        for wid, cap in workload_capacities.items()
        if cap > 0
    ]
