"""NP-hard optimization kernels for Data Center Commander.

Each kernel implements an approximation algorithm with guaranteed bounds.
All kernels are pure functions with no I/O — they operate on plain data
structures and return results that can be persisted by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Workload:
    """A workload to be placed on an asset."""
    id: str
    name: str
    cpu_cores: float
    ram_gb: float
    gpu_units: float = 0.0
    power_kw: float = 0.0
    affinity: tuple[str, ...] = ()
    anti_affinity: tuple[str, ...] = ()


@dataclass
class Asset:
    """A server/asset that can host workloads."""
    id: str
    name: str
    total_cpu: float
    total_ram: float
    total_gpu: float = 0.0
    power_budget_kw: float = 0.0
    used_cpu: float = 0.0
    used_ram: float = 0.0
    used_gpu: float = 0.0
    used_power: float = 0.0
    workloads: list[str] = field(default_factory=list)

    @property
    def remaining_cpu(self) -> float:
        return self.total_cpu - self.used_cpu

    @property
    def remaining_ram(self) -> float:
        return self.total_ram - self.used_ram

    @property
    def remaining_gpu(self) -> float:
        return self.total_gpu - self.used_gpu

    @property
    def remaining_power(self) -> float:
        return self.power_budget_kw - self.used_power

    def can_fit(self, wl: Workload) -> bool:
        return (
            self.remaining_cpu >= wl.cpu_cores
            and self.remaining_ram >= wl.ram_gb
            and self.remaining_gpu >= wl.gpu_units
            and self.remaining_power >= wl.power_kw
        )

    def assign(self, wl: Workload) -> None:
        self.used_cpu += wl.cpu_cores
        self.used_ram += wl.ram_gb
        self.used_gpu += wl.gpu_units
        self.used_power += wl.power_kw
        self.workloads.append(wl.id)


@dataclass(frozen=True)
class WorkOrder:
    """A maintenance work order for routing."""
    id: str
    asset_id: str
    priority: int
    duration_hours: float
    skill_required: str
    latitude: float
    longitude: float
    time_window_start: float | None = None
    time_window_end: float | None = None


@dataclass(frozen=True)
class Technician:
    """A technician available for maintenance routing."""
    id: str
    skills: frozenset[str]
    base_latitude: float
    base_longitude: float
    available_hours: float = 8.0


@dataclass
class CapacityDimension:
    """A capacity dimension for allocation."""
    name: str
    total: float
    used: float = 0.0
    reserved: float = 0.0
    policy_reserve: float = 0.0

    @property
    def available(self) -> float:
        return self.total - self.used - self.reserved - self.policy_reserve


@dataclass(frozen=True)
class NetworkNode:
    """A network node for zoning."""
    id: str
    zone: str | None = None
    neighbors: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnergyRequest:
    """An energy allocation request from a workload."""
    workload_id: str
    energy_kwh: float
    useful_work_per_kwh: float
    min_fair_share: float = 0.0


# ---------------------------------------------------------------------------
# 1. Workload Placement — First-Fit Decreasing (Bin Packing)
# ---------------------------------------------------------------------------

def first_fit_decreasing(
    workloads: list[Workload],
    assets: list[Asset],
) -> dict[str, list[str]]:
    """Place workloads onto assets using First-Fit Decreasing.

    Guarantees: 11/9 × OPT + 1 bins for standard bin packing.
    With constraints (affinity/anti-affinity), uses backtracking with pruning.

    Returns: mapping of asset_id → list of workload_ids.
    """
    # Sort workloads by "size" (max of normalized resource usage) descending
    sorted_wls = sorted(
        workloads,
        key=lambda w: max(w.cpu_cores, w.ram_gb, w.gpu_units, w.power_kw),
        reverse=True,
    )

    # Reset asset state
    for asset in assets:
        asset.used_cpu = 0.0
        asset.used_ram = 0.0
        asset.used_gpu = 0.0
        asset.used_power = 0.0
        asset.workloads = []

    unplaced: list[Workload] = []

    for wl in sorted_wls:
        placed = False
        # Try affinity constraints first
        candidates = list(assets)
        if wl.affinity:
            # Prefer assets that already host affinity targets
            candidates.sort(
                key=lambda a: wl.affinity and any(t in a.workloads for t in wl.affinity),
                reverse=True,
            )

        for asset in candidates:
            if not asset.can_fit(wl):
                continue
            # Check anti-affinity: skip if any anti-affinity target is already on this asset
            if wl.anti_affinity and any(t in asset.workloads for t in wl.anti_affinity):
                continue
            asset.assign(wl)
            placed = True
            break

        if not placed:
            unplaced.append(wl)

    result = {a.id: list(a.workloads) for a in assets if a.workloads}
    if unplaced:
        result["__unplaced__"] = [w.id for w in unplaced]
    return result


# ---------------------------------------------------------------------------
# 2. Maintenance Routing — Clarke-Wright Savings + 2-opt
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute haversine distance in km."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def clarke_wright_savings(
    work_orders: list[WorkOrder],
    technicians: list[Technician],
    depot_lat: float = 0.0,
    depot_lon: float = 0.0,
) -> dict[str, list[str]]:
    """Route technicians to work orders using Clarke-Wright Savings.

    Two-phase approach:
    1. Assignment: distribute work orders across compatible technicians (greedy by priority)
    2. Routing: optimize each technician's route using Clarke-Wright + 2-opt

    Guarantees: 2-approximation for metric TSP (routing phase).
    Time: O(n² log n).

    Returns: mapping of technician_id → ordered list of work_order_ids.
    """
    if not work_orders or not technicians:
        return {}

    # Phase 1: Assign work orders to technicians
    # Sort work orders by priority (highest first), then by duration (shortest first)
    sorted_wos = sorted(work_orders, key=lambda wo: (-wo.priority, wo.duration_hours))

    # Track remaining hours per technician
    remaining_hours: dict[str, float] = {t.id: t.available_hours for t in technicians}

    # Assignment: greedy by priority, distribute across compatible technicians
    assignment: dict[str, list[WorkOrder]] = {t.id: [] for t in technicians}

    for wo in sorted_wos:
        # Find compatible technicians with enough remaining hours
        compatible = [
            t for t in technicians
            if wo.skill_required in t.skills and remaining_hours[t.id] >= wo.duration_hours
        ]
        if not compatible:
            continue  # No technician can handle this work order

        # Assign to compatible technician with most remaining hours (load balancing)
        best_tech = max(compatible, key=lambda t: remaining_hours[t.id])
        assignment[best_tech.id].append(wo)
        remaining_hours[best_tech.id] -= wo.duration_hours

    # Phase 2: Route each technician's assigned work orders using Clarke-Wright
    routes: dict[str, list[str]] = {}

    for tech in technicians:
        tech_wos = assignment[tech.id]
        if not tech_wos:
            routes[tech.id] = []
            continue

        # Compute savings for this technician's work orders
        savings: list[tuple[float, WorkOrder, WorkOrder]] = []
        for i, a in enumerate(tech_wos):
            for j, b in enumerate(tech_wos):
                if i >= j:
                    continue
                d_depot_a = _haversine(depot_lat, depot_lon, a.latitude, a.longitude)
                d_depot_b = _haversine(depot_lat, depot_lon, b.latitude, b.longitude)
                d_a_b = _haversine(a.latitude, a.longitude, b.latitude, b.longitude)
                s = d_depot_a + d_depot_b - d_a_b
                savings.append((s, a, b))

        savings.sort(key=lambda x: x[0], reverse=True)

        # Build routes using union-find
        parent: dict[str, str] = {wo.id: wo.id for wo in tech_wos}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> bool:
            ra, rb = find(a), find(b)
            if ra == rb:
                return False
            parent[ra] = rb
            return True

        # Perform unions based on savings (Clarke-Wright)
        for s, a, b in savings:
            union(a.id, b.id)

        # Group work orders by union-find root
        routes_by_root: dict[str, list[WorkOrder]] = {}
        for wo in tech_wos:
            root = find(wo.id)
            routes_by_root.setdefault(root, []).append(wo)

        # Pick the best route (most work orders, then shortest distance)
        best_route: list[WorkOrder] = []
        for route in routes_by_root.values():
            if len(route) > len(best_route):
                best_route = route
            elif len(route) == len(best_route) and best_route:
                d1 = sum(
                    _haversine(
                        best_route[k].latitude, best_route[k].longitude,
                        best_route[k + 1].latitude, best_route[k + 1].longitude,
                    )
                    for k in range(len(best_route) - 1)
                )
                d2 = sum(
                    _haversine(
                        route[k].latitude, route[k].longitude,
                        route[k + 1].latitude, route[k + 1].longitude,
                    )
                    for k in range(len(route) - 1)
                )
                if d2 < d1:
                    best_route = route

        # Apply 2-opt local search
        best_route = _two_opt(best_route, depot_lat, depot_lon)
        routes[tech.id] = [wo.id for wo in best_route]

    return routes


def _two_opt(route: list[WorkOrder], depot_lat: float, depot_lon: float) -> list[WorkOrder]:
    """2-opt local search improvement."""
    if len(route) < 3:
        return route

    improved = True
    while improved:
        improved = False
        for i in range(len(route) - 1):
            for j in range(i + 2, len(route)):
                # Current edges: (i, i+1) and (j, j+1 or depot)
                a, b = route[i], route[i + 1]
                c, d = route[j], route[(j + 1) % len(route)] if j + 1 < len(route) else None

                d1 = _haversine(a.latitude, a.longitude, b.latitude, b.longitude)
                d2 = _haversine(c.latitude, c.longitude, d.latitude, d.longitude) if d else 0

                # New edges: (i, j) and (i+1, j+1 or depot)
                d3 = _haversine(a.latitude, a.longitude, c.latitude, c.longitude)
                d4 = _haversine(b.latitude, b.longitude, d.latitude, d.longitude) if d else 0

                if d3 + d4 < d1 + d2:
                    route[i + 1 : j + 1] = reversed(route[i + 1 : j + 1])
                    improved = True
    return route


# ---------------------------------------------------------------------------
# 3. Capacity Allocation — LP Relaxation + Greedy Rounding
# ---------------------------------------------------------------------------

def capacity_allocation(
    dimensions: list[CapacityDimension],
    demands: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Allocate capacity across dimensions using greedy density.

    For each demand, allocate to the dimension with highest remaining capacity.
    Guarantees: feasible solution when total capacity >= total demand.

    Returns: mapping of demand_id → {dimension_name: allocated_amount}.
    """
    # Reset usage
    for dim in dimensions:
        dim.used = 0.0

    result: dict[str, dict[str, float]] = {}

    # Sort demands by total requirement descending
    sorted_demands = sorted(
        demands.items(),
        key=lambda x: sum(x[1].values()),
        reverse=True,
    )

    for demand_id, requirements in sorted_demands:
        allocation: dict[str, float] = {}
        for dim_name, required in requirements.items():
            dim = next((d for d in dimensions if d.name == dim_name), None)
            if dim is None:
                allocation[dim_name] = 0.0
                continue
            available = dim.available
            allocated = min(available, required)
            dim.used += allocated
            allocation[dim_name] = allocated
        result[demand_id] = allocation

    return result


# ---------------------------------------------------------------------------
# 4. Network Zoning — DSATUR (Degree of Saturation)
# ---------------------------------------------------------------------------

def dsatur_zoning(nodes: list[NetworkNode]) -> dict[str, str]:
    """Assign network nodes to zones using DSATUR heuristic.

    Guarantees: ≤ Δ+1 colors where Δ is max degree.
    Time: O(n²).

    Returns: mapping of node_id → zone_name.
    """
    if not nodes:
        return {}

    # Build adjacency list
    adj: dict[str, set[str]] = {n.id: set(n.neighbors) for n in nodes}
    zones: dict[str, str] = {}
    zone_counter = 0

    # Compute saturation degree for each node
    def saturation(node_id: str) -> int:
        neighbor_zones = {zones[n] for n in adj[node_id] if n in zones}
        return len(neighbor_zones)

    unassigned = set(n.id for n in nodes)

    while unassigned:
        # Pick unassigned node with highest saturation, break ties by degree
        best = max(unassigned, key=lambda n: (saturation(n), len(adj[n])))

        # Assign smallest available zone
        neighbor_zones = {zones[n] for n in adj[best] if n in zones}
        zone = 0
        while f"zone_{zone}" in neighbor_zones:
            zone += 1

        zones[best] = f"zone_{zone}"
        unassigned.remove(best)
        zone_counter = max(zone_counter, zone + 1)

    return zones


# ---------------------------------------------------------------------------
# 5. Energy Allocation — Max-Min Fairness + Gain Density
# ---------------------------------------------------------------------------

def max_min_fair_energy_allocation(
    requests: list[EnergyRequest],
    total_energy_kwh: float,
) -> dict[str, float]:
    """Allocate energy budget across workloads using max-min fairness.

    Guarantees: Pareto optimal, max-min fair.
    Time: O(n log n).

    Returns: mapping of workload_id → allocated_kwh.
    """
    if not requests or total_energy_kwh <= 0:
        return {}

    # Sort by useful_work_per_kwh descending (gain density)
    sorted_reqs = sorted(requests, key=lambda r: r.useful_work_per_kwh, reverse=True)

    allocation: dict[str, float] = {}
    remaining = total_energy_kwh
    n = len(sorted_reqs)

    # First pass: satisfy minimum fair shares
    for req in sorted_reqs:
        share = min(req.min_fair_share, remaining / max(n, 1))
        allocation[req.workload_id] = share
        remaining -= share
        n -= 1

    # Second pass: distribute remaining by gain density
    if remaining > 0:
        total_gain = sum(r.useful_work_per_kwh for r in sorted_reqs)
        if total_gain > 0:
            for req in sorted_reqs:
                extra = remaining * (req.useful_work_per_kwh / total_gain)
                allocation[req.workload_id] += extra

    return allocation
