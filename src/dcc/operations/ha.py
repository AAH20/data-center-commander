"""High availability manager: failover, load balancing, health-based routing.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import enum
import random
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeState(str, enum.Enum):
    """Operational state of a node in the cluster."""
    ACTIVE = "active"
    DRAINING = "draining"
    DRAINED = "drained"
    FAILED = "failed"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class FailoverStrategy(str, enum.Enum):
    """Strategy for selecting failover targets."""
    PRIORITY = "priority"
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    GEOGRAPHIC = "geographic"
    HEALTH_SCORE = "health_score"


class LoadBalancingStrategy(str, enum.Enum):
    """Strategy for distributing load across nodes."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    IP_HASH = "ip_hash"
    RANDOM = "random"


class HealthStatus(str, enum.Enum):
    """Health status of a node or service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class HealthSnapshot:
    """Point-in-time health data for a node."""
    node_id: str
    timestamp: float
    latency_ms: float = 0.0
    error_rate: float = 0.0
    active_connections: int = 0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    disk_utilization: float = 0.0
    last_success_at: float | None = None
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0


@dataclass(slots=True)
class NodeHealth:
    """Aggregated health information for a node."""
    node_id: str
    state: NodeState = NodeState.UNKNOWN
    region: str = "default"
    priority: int = 0
    weight: float = 1.0
    current_snapshot: HealthSnapshot | None = None
    history: list[HealthSnapshot] = field(default_factory=list)
    max_history: int = 100
    labels: dict[str, str] = field(default_factory=dict)
    drained_at: float | None = None
    failed_at: float | None = None
    recovered_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def availability_pct(self) -> float:
        """Calculate availability percentage from history."""
        if not self.current_snapshot:
            return 0.0
        total = self.current_snapshot.total_requests
        if total == 0:
            return 100.0
        failed = self.current_snapshot.failed_requests
        return max(0.0, (total - failed) / total * 100.0)

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency from history."""
        if not self.history:
            return 0.0
        return statistics.fmean(s.latency_ms for s in self.history)

    @property
    def avg_error_rate(self) -> float:
        """Calculate average error rate from history."""
        if not self.history:
            return 0.0
        return statistics.fmean(s.error_rate for s in self.history)

    @property
    def is_healthy(self) -> bool:
        """Determine if node is healthy based on state and metrics."""
        if self.state not in (NodeState.ACTIVE, NodeState.DRAINING):
            return False
        if self.current_snapshot is None:
            return False
        snap = self.current_snapshot
        if snap.error_rate > 0.5:
            return False
        if snap.consecutive_failures > 3:
            return False
        return True

    @property
    def health_status(self) -> HealthStatus:
        """Get health status."""
        if not self.is_healthy:
            if self.current_snapshot and self.current_snapshot.error_rate > 0.8:
                return HealthStatus.UNHEALTHY
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


@dataclass(slots=True)
class NodeWeight:
    """Dynamic weight configuration for a node."""
    node_id: str
    base_weight: float = 1.0
    health_multiplier: float = 1.0
    load_multiplier: float = 1.0
    custom_multiplier: float = 1.0

    @property
    def effective_weight(self) -> float:
        """Calculate effective weight."""
        return max(0.0, self.base_weight * self.health_multiplier * self.load_multiplier * self.custom_multiplier)


@dataclass(slots=True)
class WeightedNode:
    """A node with computed weight for load balancing."""
    node_id: str
    effective_weight: float
    current_weight: float = 0.0
    connections: int = 0
    avg_response_time_ms: float = 0.0


@dataclass(slots=True)
class FailoverDecision:
    """Result of a failover evaluation."""
    should_failover: bool
    reason: str
    source_node: str | None = None
    target_node: str | None = None
    strategy_used: FailoverStrategy | None = None
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FailoverOutcome:
    """Outcome of a single node-pair failover attempt in the HA manager.

    Deliberately NOT named ``FailoverResult``: ``dcc.dr.failover.FailoverResult``
    is a different, richer shape (an execution record with ``execution_id``,
    step counters, and a ``FailoverStatus``). Two classes sharing the name meant
    an import typo silently produced the wrong one and the attributes only
    surfaced at the call site.

    This one answers "did the VIP/route move from source to target, and how
    long did it take". It carries no step detail -- the DR orchestrator's
    ``FailoverExecution`` does.

    Attributes:
        success: Whether the source-to-target move completed.
        source_node: Node the failover moved away from.
        target_node: Node now serving, or None if no target was selected.
        duration_ms: Wall-clock duration of the attempt, in milliseconds.
        timestamp: Unix epoch seconds when the attempt finished.
        error: Failure reason, or None on success.
        metadata: Strategy-specific detail (strategy used, confidence, ...).
    """

    success: bool
    source_node: str
    target_node: str | None
    duration_ms: float
    timestamp: float
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LoadBalancingResult:
    """Result of a load balancing decision."""
    selected_node: str | None
    strategy_used: LoadBalancingStrategy
    candidates_considered: int
    selection_time_ms: float
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RouteTarget:
    """A target for health-based routing."""
    node_id: str
    weight: float = 1.0
    priority: int = 0
    region: str = "default"
    healthy: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RoutingDecision:
    """Result of a routing decision."""
    target: RouteTarget | None
    reason: str
    alternatives: list[RouteTarget] = field(default_factory=list)
    routing_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_node_score(
    node: NodeHealth,
    *,
    latency_weight: float = 0.3,
    error_weight: float = 0.3,
    connection_weight: float = 0.2,
    resource_weight: float = 0.2,
) -> float:
    """Compute a composite health score for a node (0.0-1.0, higher is better).

    Combines latency, error rate, connection count, and resource utilization
    into a single score for ranking nodes.
    """
    if node.current_snapshot is None:
        return 0.0

    snap = node.current_snapshot

    # Latency score: lower is better, normalize to 0-1
    latency_score = max(0.0, 1.0 - (snap.latency_ms / 1000.0))

    # Error rate score: lower is better
    error_score = max(0.0, 1.0 - snap.error_rate)

    # Connection score: fewer connections is better (normalize to 100)
    connection_score = max(0.0, 1.0 - (snap.active_connections / 100.0))

    # Resource score: average of CPU, memory, disk (lower is better)
    resource_score = max(0.0, 1.0 - (
        snap.cpu_utilization + snap.memory_utilization + snap.disk_utilization
    ) / 3.0)

    score = (
        latency_score * latency_weight
        + error_score * error_weight
        + connection_score * connection_weight
        + resource_score * resource_weight
    )

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Failover logic
# ---------------------------------------------------------------------------

def evaluate_failover(
    source_node: NodeHealth,
    candidates: Sequence[NodeHealth],
    *,
    strategy: FailoverStrategy = FailoverStrategy.HEALTH_SCORE,
    failure_threshold: float = 0.5,
    min_candidates: int = 1,
) -> FailoverDecision:
    """Evaluate whether a failover is needed and select the best target.

    Args:
        source_node: The node that may need to fail over.
        candidates: Available target nodes.
        strategy: Failover strategy to use.
        failure_threshold: Error rate threshold to trigger failover.
        min_candidates: Minimum healthy candidates required.

    Returns:
        FailoverDecision with the result.
    """
    # Check if source is healthy enough to keep running
    if source_node.is_healthy:
        if source_node.current_snapshot and source_node.current_snapshot.error_rate < failure_threshold:
            return FailoverDecision(
                should_failover=False,
                reason="source_node_healthy",
                source_node=source_node.node_id,
            )

    # Filter to healthy candidates
    healthy_candidates = [c for c in candidates if c.is_healthy and c.node_id != source_node.node_id]

    if len(healthy_candidates) < min_candidates:
        return FailoverDecision(
            should_failover=True,
            reason="insufficient_healthy_candidates",
            source_node=source_node.node_id,
            metadata={"healthy_candidates": len(healthy_candidates), "min_required": min_candidates},
        )

    # Select target based on strategy
    target = select_failover_target(healthy_candidates, strategy=strategy)

    if target is None:
        return FailoverDecision(
            should_failover=True,
            reason="no_suitable_target",
            source_node=source_node.node_id,
        )

    return FailoverDecision(
        should_failover=True,
        reason="source_unhealthy",
        source_node=source_node.node_id,
        target_node=target.node_id,
        strategy_used=strategy,
        confidence=compute_node_score(target),
    )


def select_failover_target(
    candidates: Sequence[NodeHealth],
    *,
    strategy: FailoverStrategy = FailoverStrategy.HEALTH_SCORE,
) -> NodeHealth | None:
    """Select the best failover target from candidates.

    Args:
        candidates: Healthy candidate nodes.
        strategy: Selection strategy.

    Returns:
        The best target node, or None if no candidates.
    """
    if not candidates:
        return None

    if strategy == FailoverStrategy.PRIORITY:
        return max(candidates, key=lambda n: (n.priority, compute_node_score(n)))

    if strategy == FailoverStrategy.LEAST_LOADED:
        return min(candidates, key=lambda n: (
            n.current_snapshot.active_connections if n.current_snapshot else 0
        ))

    if strategy == FailoverStrategy.HEALTH_SCORE:
        return max(candidates, key=lambda n: compute_node_score(n))

    if strategy == FailoverStrategy.ROUND_ROBIN:
        # Pick the one with lowest total requests (simple round-robin proxy)
        return min(candidates, key=lambda n: (
            n.current_snapshot.total_requests if n.current_snapshot else 0
        ))

    if strategy == FailoverStrategy.GEOGRAPHIC:
        # Prefer highest priority, then health score
        return max(candidates, key=lambda n: (n.priority, compute_node_score(n)))

    return None


# ---------------------------------------------------------------------------
# Load balancing
# ---------------------------------------------------------------------------

def weighted_round_robin(
    nodes: Sequence[WeightedNode],
) -> WeightedNode | None:
    """Select a node using weighted round-robin.

    Uses the smooth weighted round-robin algorithm (nginx-style).
    """
    if not nodes:
        return None

    active = [n for n in nodes if n.effective_weight > 0]
    if not active:
        return None

    total_weight = sum(n.effective_weight for n in active)
    if total_weight <= 0:
        return None

    # Smooth weighted round-robin
    for node in active:
        node.current_weight += node.effective_weight

    selected = max(active, key=lambda n: n.current_weight)
    selected.current_weight -= total_weight

    return selected


# ---------------------------------------------------------------------------
# Load balancer
# ---------------------------------------------------------------------------

class HALoadBalancer:
    """Thread-safe load balancer with multiple strategies.

    Supports round-robin, weighted round-robin, least-connections,
    least-response-time, IP-hash, and random strategies.
    """

    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
    ) -> None:
        self._strategy = strategy
        self._nodes: dict[str, NodeHealth] = {}
        self._weights: dict[str, NodeWeight] = {}
        self._weighted_nodes: dict[str, WeightedNode] = {}
        self._lock = threading.RLock()
        self._rr_index = 0

    @property
    def strategy(self) -> LoadBalancingStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, value: LoadBalancingStrategy) -> None:
        with self._lock:
            self._strategy = value

    def register_node(self, node: NodeHealth, weight: NodeWeight | None = None) -> None:
        """Register a node for load balancing."""
        with self._lock:
            self._nodes[node.node_id] = node
            if weight:
                self._weights[node.node_id] = weight
            elif node.node_id not in self._weights:
                self._weights[node.node_id] = NodeWeight(
                    node_id=node.node_id,
                    base_weight=node.weight,
                )
            self._weighted_nodes[node.node_id] = WeightedNode(
                node_id=node.node_id,
                effective_weight=self._weights[node.node_id].effective_weight,
            )

    def unregister_node(self, node_id: str) -> bool:
        """Remove a node from load balancing."""
        with self._lock:
            existed = node_id in self._nodes
            self._nodes.pop(node_id, None)
            self._weights.pop(node_id, None)
            self._weighted_nodes.pop(node_id, None)
            return existed

    def update_node_health(self, snapshot: HealthSnapshot) -> None:
        """Update health data for a node."""
        with self._lock:
            node = self._nodes.get(snapshot.node_id)
            if node is None:
                return
            node.current_snapshot = snapshot
            node.history.append(snapshot)
            if len(node.history) > node.max_history:
                node.history = node.history[-node.max_history:]
            # Update weighted node
            wn = self._weighted_nodes.get(snapshot.node_id)
            if wn:
                wn.connections = snapshot.active_connections
                wn.avg_response_time_ms = snapshot.latency_ms
                weight = self._weights.get(snapshot.node_id)
                if weight:
                    wn.effective_weight = weight.effective_weight

    def select_node(
        self,
        *,
        client_ip: str | None = None,
        key: str | None = None,
    ) -> LoadBalancingResult:
        """Select a node for a new request.

        Args:
            client_ip: Client IP for IP-hash strategy.
            key: Custom key for consistent hashing.

        Returns:
            LoadBalancingResult with the selected node.
        """
        start = time.monotonic()
        with self._lock:
            healthy = {
                nid: n for nid, n in self._nodes.items()
                if n.is_healthy
            }
            if not healthy:
                elapsed = (time.monotonic() - start) * 1000
                return LoadBalancingResult(
                    selected_node=None,
                    strategy_used=self._strategy,
                    candidates_considered=0,
                    selection_time_ms=elapsed,
                    reason="no_healthy_nodes",
                )

            selected_id: str | None = None

            if self._strategy == LoadBalancingStrategy.ROUND_ROBIN:
                selected_id = self._round_robin_select(list(healthy))
            elif self._strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                selected_id = self._weighted_round_robin_select(list(healthy))
            elif self._strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                selected_id = self._least_connections_select(list(healthy))
            elif self._strategy == LoadBalancingStrategy.LEAST_RESPONSE_TIME:
                selected_id = self._least_response_time_select(list(healthy))
            elif self._strategy == LoadBalancingStrategy.IP_HASH:
                selected_id = self._ip_hash_select(list(healthy), client_ip or key or "")
            elif self._strategy == LoadBalancingStrategy.RANDOM:
                selected_id = random.choice(list(healthy))
            else:
                selected_id = self._round_robin_select(list(healthy))

            elapsed = (time.monotonic() - start) * 1000
            return LoadBalancingResult(
                selected_node=selected_id,
                strategy_used=self._strategy,
                candidates_considered=len(healthy),
                selection_time_ms=elapsed,
            )

    def _round_robin_select(self, node_ids: list[str]) -> str | None:
        if not node_ids:
            return None
        idx = self._rr_index % len(node_ids)
        self._rr_index += 1
        return node_ids[idx]

    def _weighted_round_robin_select(self, node_ids: list[str]) -> str | None:
        wnodes = [self._weighted_nodes[nid] for nid in node_ids if nid in self._weighted_nodes]
        selected = weighted_round_robin(wnodes)
        return selected.node_id if selected else None

    def _least_connections_select(self, node_ids: list[str]) -> str | None:
        return min(node_ids, key=lambda nid: (
            self._nodes[nid].current_snapshot.active_connections
            if self._nodes[nid].current_snapshot is not None else 0
        ))

    def _least_response_time_select(self, node_ids: list[str]) -> str | None:
        return min(node_ids, key=lambda nid: (
            self._nodes[nid].current_snapshot.latency_ms
            if self._nodes[nid].current_snapshot is not None else float("inf")
        ))

    def _ip_hash_select(self, node_ids: list[str], key: str) -> str | None:
        if not node_ids:
            return None
        hash_val = hash(key) % len(node_ids)
        return node_ids[abs(hash_val) % len(node_ids)]

    def get_stats(self) -> dict[str, Any]:
        """Get current load balancer statistics."""
        with self._lock:
            return {
                "strategy": self._strategy.value,
                "total_nodes": len(self._nodes),
                "healthy_nodes": sum(1 for n in self._nodes.values() if n.is_healthy),
                "nodes": {
                    nid: {
                        "state": n.state.value,
                        "healthy": n.is_healthy,
                        "availability_pct": round(n.availability_pct, 2),
                        "avg_latency_ms": round(n.avg_latency_ms, 2),
                        "connections": n.current_snapshot.active_connections if n.current_snapshot else 0,
                    }
                    for nid, n in self._nodes.items()
                },
            }


# ---------------------------------------------------------------------------
# Health-based router
# ---------------------------------------------------------------------------

class HealthBasedRouter:
    """Routes requests based on node health status.

    Considers health, priority, and region when making routing decisions.
    """

    def __init__(self) -> None:
        self._targets: dict[str, RouteTarget] = {}
        self._lock = threading.RLock()

    def add_target(self, target: RouteTarget) -> None:
        """Add a routing target."""
        with self._lock:
            self._targets[target.node_id] = target

    def remove_target(self, node_id: str) -> bool:
        """Remove a routing target."""
        with self._lock:
            existed = node_id in self._targets
            self._targets.pop(node_id, None)
            return existed

    def update_health(self, node_id: str, healthy: bool) -> None:
        """Update health status of a target."""
        with self._lock:
            target = self._targets.get(node_id)
            if target:
                target.healthy = healthy

    def route(
        self,
        *,
        preferred_region: str | None = None,
        required_labels: dict[str, str] | None = None,
    ) -> RoutingDecision:
        """Select the best target for routing.

        Args:
            preferred_region: Prefer targets in this region.
            required_labels: Targets must have these labels.

        Returns:
            RoutingDecision with the selected target.
        """
        start = time.monotonic()
        with self._lock:
            candidates = [t for t in self._targets.values() if t.healthy]

            if required_labels:
                candidates = [
                    t for t in candidates
                    if all(t.metadata.get(k) == v for k, v in required_labels.items())
                ]

            if not candidates:
                elapsed = (time.monotonic() - start) * 1000
                return RoutingDecision(
                    target=None,
                    reason="no_healthy_targets",
                    routing_time_ms=elapsed,
                )

            # Score candidates
            def score_target(t: RouteTarget) -> tuple:
                region_bonus = 1 if preferred_region and t.region == preferred_region else 0
                return (region_bonus, t.priority, t.weight)

            candidates.sort(key=score_target, reverse=True)
            selected = candidates[0]
            alternatives = candidates[1:]

            elapsed = (time.monotonic() - start) * 1000
            return RoutingDecision(
                target=selected,
                reason="health_based_selection",
                alternatives=alternatives,
                routing_time_ms=elapsed,
                metadata={
                    "candidates_considered": len(candidates),
                    "preferred_region": preferred_region,
                },
            )


# ---------------------------------------------------------------------------
# HA Manager (facade)
# ---------------------------------------------------------------------------

class HAManager:
    """High-level facade for HA operations.

    Coordinates failover, load balancing, and health-based routing
    into a single management interface.
    """

    def __init__(
        self,
        *,
        failover_strategy: FailoverStrategy = FailoverStrategy.HEALTH_SCORE,
        lb_strategy: LoadBalancingStrategy = LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
    ) -> None:
        self._failover_strategy = failover_strategy
        self._load_balancer = HALoadBalancer(strategy=lb_strategy)
        self._router = HealthBasedRouter()
        self._nodes: dict[str, NodeHealth] = {}
        self._lock = threading.RLock()
        self._failover_history: list[FailoverOutcome] = []
        self._max_history = 100

    @property
    def failover_strategy(self) -> FailoverStrategy:
        return self._failover_strategy

    @property
    def load_balancer(self) -> HALoadBalancer:
        return self._load_balancer

    @property
    def router(self) -> HealthBasedRouter:
        return self._router

    def register_node(self, node: NodeHealth, weight: NodeWeight | None = None) -> None:
        """Register a node for HA management."""
        with self._lock:
            self._nodes[node.node_id] = node
            self._load_balancer.register_node(node, weight)
            self._router.add_target(RouteTarget(
                node_id=node.node_id,
                weight=node.weight,
                priority=node.priority,
                region=node.region,
                healthy=node.is_healthy,
                metadata=dict(node.labels),
            ))

    def unregister_node(self, node_id: str) -> bool:
        """Remove a node from HA management."""
        with self._lock:
            existed = node_id in self._nodes
            self._nodes.pop(node_id, None)
            self._load_balancer.unregister_node(node_id)
            self._router.remove_target(node_id)
            return existed

    def update_health(self, snapshot: HealthSnapshot) -> None:
        """Update health data for a node across all subsystems."""
        with self._lock:
            node = self._nodes.get(snapshot.node_id)
            if node is None:
                return
            node.current_snapshot = snapshot
            node.history.append(snapshot)
            if len(node.history) > node.max_history:
                node.history = node.history[-node.max_history:]
            self._load_balancer.update_node_health(snapshot)
            self._router.update_health(snapshot.node_id, node.is_healthy)

    def check_failover(self, node_id: str) -> FailoverDecision:
        """Check if a node needs to fail over."""
        with self._lock:
            source = self._nodes.get(node_id)
            if source is None:
                return FailoverDecision(
                    should_failover=False,
                    reason="node_not_found",
                    source_node=node_id,
                )
            candidates = [n for nid, n in self._nodes.items() if nid != node_id]
            return evaluate_failover(
                source,
                candidates,
                strategy=self._failover_strategy,
            )

    def execute_failover(self, source_node_id: str, target_node_id: str | None = None) -> FailoverOutcome:
        """Execute a failover from source to target.

        If target_node_id is None, the best target is selected automatically.
        """
        start = time.monotonic()
        with self._lock:
            source = self._nodes.get(source_node_id)
            if source is None:
                return FailoverOutcome(
                    success=False,
                    source_node=source_node_id,
                    target_node=None,
                    duration_ms=0.0,
                    timestamp=time.time(),
                    error="source_node_not_found",
                )

            if target_node_id is None:
                decision = self.check_failover(source_node_id)
                if not decision.should_failover or decision.target_node is None:
                    return FailoverOutcome(
                        success=False,
                        source_node=source_node_id,
                        target_node=None,
                        duration_ms=(time.monotonic() - start) * 1000,
                        timestamp=time.time(),
                        error=f"failover_not_needed: {decision.reason}",
                    )
                target_node_id = decision.target_node

            target = self._nodes.get(target_node_id)
            if target is None:
                return FailoverOutcome(
                    success=False,
                    source_node=source_node_id,
                    target_node=target_node_id,
                    duration_ms=(time.monotonic() - start) * 1000,
                    timestamp=time.time(),
                    error="target_node_not_found",
                )

            # Perform failover
            source.state = NodeState.FAILED
            source.failed_at = time.time()
            target.state = NodeState.ACTIVE

            result = FailoverOutcome(
                success=True,
                source_node=source_node_id,
                target_node=target_node_id,
                duration_ms=(time.monotonic() - start) * 1000,
                timestamp=time.time(),
            )
            self._failover_history.append(result)
            if len(self._failover_history) > self._max_history:
                self._failover_history = self._failover_history[-self._max_history:]
            return result

    def get_node(self, node_id: str) -> NodeHealth | None:
        """Get a node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def get_all_nodes(self) -> dict[str, NodeHealth]:
        """Get all registered nodes."""
        with self._lock:
            return dict(self._nodes)

    def get_healthy_nodes(self) -> list[NodeHealth]:
        """Get all healthy nodes."""
        with self._lock:
            return [n for n in self._nodes.values() if n.is_healthy]

    def get_failover_history(self) -> list[FailoverOutcome]:
        """Get failover history."""
        with self._lock:
            return list(self._failover_history)

    def get_status(self) -> dict[str, Any]:
        """Get overall HA status."""
        with self._lock:
            total = len(self._nodes)
            healthy = sum(1 for n in self._nodes.values() if n.is_healthy)
            failed = sum(1 for n in self._nodes.values() if n.state == NodeState.FAILED)
            draining = sum(1 for n in self._nodes.values() if n.state == NodeState.DRAINING)
            return {
                "total_nodes": total,
                "healthy_nodes": healthy,
                "failed_nodes": failed,
                "draining_nodes": draining,
                "failover_count": len(self._failover_history),
                "failover_strategy": self._failover_strategy.value,
                "lb_strategy": self._load_balancer.strategy.value,
                "nodes": {
                    nid: {
                        "state": n.state.value,
                        "healthy": n.is_healthy,
                        "health_status": n.health_status.value,
                        "availability_pct": round(n.availability_pct, 2),
                        "avg_latency_ms": round(n.avg_latency_ms, 2),
                        "score": round(compute_node_score(n), 4),
                    }
                    for nid, n in self._nodes.items()
                },
            }
