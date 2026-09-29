"""Data lineage and provenance tracking for Data Center Commander.

Tracks data from source systems through transformations to KPI observations,
cost estimates, and operational decisions. Every step is hash-chained and
tenant-isolated.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class SourceType(str, Enum):
    """Origin classification for data entering the system."""
    CONNECTOR = "connector"
    MANUAL_ENTRY = "manual_entry"
    API_IMPORT = "api_import"
    SEED_FIXTURE = "seed_fixture"
    CALCULATED = "calculated"
    EXTERNAL_SYSTEM = "external_system"


class TransformationType(str, Enum):
    """How data was derived from its inputs."""
    INGESTION = "ingestion"
    VALIDATION = "validation"
    AGGREGATION = "aggregation"
    ALLOCATION = "allocation"
    NORMALIZATION = "normalization"
    CALCULATION = "calculation"
    FILTER = "filter"
    JOIN = "join"
    DERIVATION = "derivation"


class QualityStatus(str, Enum):
    """Data quality classification."""
    GOOD = "good"
    ESTIMATED = "estimated"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class LineageNode:
    """A node in the lineage graph representing a data artifact."""
    node_id: str
    node_type: str
    tenant_id: str
    label: str
    source_type: SourceType
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""


@dataclass(frozen=True)
class LineageEdge:
    """A directed edge showing data flow from source to target."""
    edge_id: str
    source_node_id: str
    target_node_id: str
    tenant_id: str
    transformation: TransformationType
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageStep:
    """A single transformation step in the lineage chain."""
    step_id: str
    tenant_id: str
    operation: str
    transformation_type: TransformationType
    input_hashes: list[str]
    output_hash: str
    actor_ref: str
    occurred_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    previous_step_hash: str = ""
    step_hash: str = ""


@dataclass
class ProvenanceRecord:
    """Complete provenance for a single data artifact."""
    record_id: str
    tenant_id: str
    artifact_type: str
    artifact_id: str
    source_type: SourceType
    quality_status: QualityStatus
    lineage_steps: list[LineageStep]
    source_refs: list[str]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    record_hash: str = ""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


class LineageTracker:
    """Tracks data lineage from source through transformations to outputs.

    Maintains an in-memory lineage graph with hash-chained steps. Designed
    to be backed by the dcc.evidence_events table for persistence.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, LineageNode] = {}
        self._edges: dict[str, LineageEdge] = {}
        self._steps: dict[str, LineageStep] = {}
        self._records: dict[str, ProvenanceRecord] = {}
        self._tenant_chains: dict[str, list[str]] = {}

    def register_source(
        self,
        *,
        tenant_id: str,
        node_type: str,
        label: str,
        source_type: SourceType,
        content: Any = None,
        metadata: dict[str, Any] | None = None,
        node_id: str | None = None,
    ) -> LineageNode:
        """Register a data source node (connector reading, manual entry, etc.)."""
        nid = node_id or str(uuid4())
        content_hash = _sha256(_canonical_json(content)) if content is not None else ""
        node = LineageNode(
            node_id=nid,
            node_type=node_type,
            tenant_id=str(tenant_id),
            label=label,
            source_type=source_type,
            created_at=_utcnow(),
            metadata=metadata or {},
            content_hash=content_hash,
        )
        self._nodes[nid] = node
        return node

    def record_transformation(
        self,
        *,
        tenant_id: str,
        operation: str,
        transformation_type: TransformationType,
        input_node_ids: list[str],
        output_node_id: str,
        output_content: Any = None,
        actor_ref: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> LineageStep:
        """Record a transformation step linking inputs to an output node."""
        step_id = str(uuid4())
        input_hashes = [self._nodes[nid].content_hash for nid in input_node_ids if nid in self._nodes]
        output_hash = _sha256(_canonical_json(output_content)) if output_content is not None else ""

        tenant_chain = self._tenant_chains.get(str(tenant_id), [])
        previous_hash = tenant_chain[-1] if tenant_chain else ""

        step = LineageStep(
            step_id=step_id,
            tenant_id=str(tenant_id),
            operation=operation,
            transformation_type=transformation_type,
            input_hashes=input_hashes,
            output_hash=output_hash,
            actor_ref=actor_ref,
            occurred_at=_utcnow(),
            metadata=metadata or {},
            previous_step_hash=previous_hash,
        )
        step.step_hash = _compute_step_hash(step)
        self._steps[step_id] = step
        tenant_chain.append(step.step_hash)
        self._tenant_chains[str(tenant_id)] = tenant_chain

        for input_nid in input_node_ids:
            if input_nid in self._nodes:
                edge = LineageEdge(
                    edge_id=str(uuid4()),
                    source_node_id=input_nid,
                    target_node_id=output_node_id,
                    tenant_id=str(tenant_id),
                    transformation=transformation_type,
                    created_at=_utcnow(),
                )
                self._edges[edge.edge_id] = edge

        return step

    def create_record(
        self,
        *,
        tenant_id: str,
        artifact_type: str,
        artifact_id: str,
        source_type: SourceType,
        quality_status: QualityStatus,
        lineage_steps: list[LineageStep],
        source_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        content: Any = None,
    ) -> ProvenanceRecord:
        """Create a complete provenance record for a data artifact."""
        record_id = str(uuid4())
        content_hash = _sha256(_canonical_json(content)) if content is not None else ""
        record = ProvenanceRecord(
            record_id=record_id,
            tenant_id=str(tenant_id),
            artifact_type=artifact_type,
            artifact_id=str(artifact_id),
            source_type=source_type,
            quality_status=quality_status,
            lineage_steps=lineage_steps,
            source_refs=source_refs or [],
            created_at=_utcnow(),
            metadata=metadata or {},
            content_hash=content_hash,
        )
        record.record_hash = _compute_record_hash(record)
        self._records[record_id] = record
        return record

    def get_lineage(
        self,
        *,
        tenant_id: str,
        artifact_id: str,
        direction: str = "upstream",
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Trace lineage for an artifact, walking upstream or downstream."""
        record = self._find_record(str(tenant_id), str(artifact_id))
        if record is None:
            return {"artifact_id": artifact_id, "found": False, "nodes": [], "edges": []}

        visited_nodes: set[str] = set()
        visited_edges: set[str] = set()
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        if direction == "upstream":
            self._walk_upstream(record, visited_nodes, visited_edges, nodes, edges, max_depth)
        else:
            self._walk_downstream(record, visited_nodes, visited_edges, nodes, edges, max_depth)

        return {
            "artifact_id": artifact_id,
            "found": True,
            "record_id": record.record_id,
            "record_hash": record.record_hash,
            "source_type": record.source_type.value,
            "quality_status": record.quality_status.value,
            "nodes": nodes,
            "edges": edges,
        }

    def verify_chain(self, *, tenant_id: str) -> dict[str, Any]:
        """Verify hash-chain integrity for all steps belonging to a tenant."""
        chain = self._tenant_chains.get(str(tenant_id), [])
        if not chain:
            return {"tenant_id": tenant_id, "valid": True, "steps_checked": 0, "broken_at": None}

        steps_in_order = [
            s for s in self._steps.values() if s.tenant_id == str(tenant_id)
        ]
        steps_in_order.sort(key=lambda s: s.occurred_at)

        previous_hash = ""
        for i, step in enumerate(steps_in_order):
            expected_hash = _compute_step_hash(step)
            if step.step_hash != expected_hash:
                return {
                    "tenant_id": tenant_id,
                    "valid": False,
                    "steps_checked": i,
                    "broken_at": step.step_id,
                    "reason": "step_hash_mismatch",
                }
            if step.previous_step_hash != previous_hash:
                return {
                    "tenant_id": tenant_id,
                    "valid": False,
                    "steps_checked": i,
                    "broken_at": step.step_id,
                    "reason": "chain_link_mismatch",
                }
            previous_hash = step.step_hash

        return {
            "tenant_id": tenant_id,
            "valid": True,
            "steps_checked": len(steps_in_order),
            "broken_at": None,
        }

    def get_tenant_summary(self, *, tenant_id: str) -> dict[str, Any]:
        """Summarize lineage coverage for a tenant."""
        tenant_nodes = [n for n in self._nodes.values() if n.tenant_id == str(tenant_id)]
        tenant_records = [r for r in self._records.values() if r.tenant_id == str(tenant_id)]
        tenant_steps = [s for s in self._steps.values() if s.tenant_id == str(tenant_id)]

        source_type_counts: dict[str, int] = {}
        for n in tenant_nodes:
            key = n.source_type.value
            source_type_counts[key] = source_type_counts.get(key, 0) + 1

        quality_counts: dict[str, int] = {}
        for r in tenant_records:
            key = r.quality_status.value
            quality_counts[key] = quality_counts.get(key, 0) + 1

        return {
            "tenant_id": tenant_id,
            "total_nodes": len(tenant_nodes),
            "total_records": len(tenant_records),
            "total_steps": len(tenant_steps),
            "source_type_counts": source_type_counts,
            "quality_counts": quality_counts,
            "chain_valid": self.verify_chain(tenant_id=str(tenant_id))["valid"],
        }

    def _find_record(self, tenant_id: str, artifact_id: str) -> ProvenanceRecord | None:
        for record in self._records.values():
            if record.tenant_id == tenant_id and record.artifact_id == artifact_id:
                return record
        return None

    def _walk_upstream(
        self,
        record: ProvenanceRecord,
        visited_nodes: set[str],
        visited_edges: set[str],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        max_depth: int,
    ) -> None:
        if max_depth <= 0:
            return
        for step in record.lineage_steps:
            for input_hash in step.input_hashes:
                for node in self._nodes.values():
                    if node.content_hash == input_hash and node.node_id not in visited_nodes:
                        visited_nodes.add(node.node_id)
                        nodes.append(_node_to_dict(node))
                        self._walk_upstream_node(
                            node.node_id, visited_nodes, visited_edges, nodes, edges, max_depth - 1
                        )

    def _walk_upstream_node(
        self,
        node_id: str,
        visited_nodes: set[str],
        visited_edges: set[str],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        depth: int,
    ) -> None:
        if depth <= 0:
            return
        for edge in self._edges.values():
            if edge.target_node_id == node_id and edge.edge_id not in visited_edges:
                visited_edges.add(edge.edge_id)
                edges.append(_edge_to_dict(edge))
                source_node = self._nodes.get(edge.source_node_id)
                if source_node and source_node.node_id not in visited_nodes:
                    visited_nodes.add(source_node.node_id)
                    nodes.append(_node_to_dict(source_node))
                    self._walk_upstream_node(
                        source_node.node_id, visited_nodes, visited_edges, nodes, edges, depth - 1
                    )

    def _walk_downstream(
        self,
        record: ProvenanceRecord,
        visited_nodes: set[str],
        visited_edges: set[str],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        max_depth: int,
    ) -> None:
        if max_depth <= 0:
            return
        for step in record.lineage_steps:
            for edge in self._edges.values():
                if edge.source_node_id in visited_nodes and edge.edge_id not in visited_edges:
                    visited_edges.add(edge.edge_id)
                    edges.append(_edge_to_dict(edge))
                    target_node = self._nodes.get(edge.target_node_id)
                    if target_node and target_node.node_id not in visited_nodes:
                        visited_nodes.add(target_node.node_id)
                        nodes.append(_node_to_dict(target_node))


def _compute_step_hash(step: LineageStep) -> str:
    payload = _canonical_json({
        "step_id": step.step_id,
        "tenant_id": step.tenant_id,
        "operation": step.operation,
        "transformation_type": step.transformation_type.value,
        "input_hashes": step.input_hashes,
        "output_hash": step.output_hash,
        "actor_ref": step.actor_ref,
        "occurred_at": step.occurred_at.isoformat(),
        "metadata": step.metadata,
        "previous_step_hash": step.previous_step_hash,
    })
    return _sha256(payload)


def _compute_record_hash(record: ProvenanceRecord) -> str:
    payload = _canonical_json({
        "record_id": record.record_id,
        "tenant_id": record.tenant_id,
        "artifact_type": record.artifact_type,
        "artifact_id": record.artifact_id,
        "source_type": record.source_type.value,
        "quality_status": record.quality_status.value,
        "lineage_steps": [s.step_hash for s in record.lineage_steps],
        "source_refs": record.source_refs,
        "created_at": record.created_at.isoformat(),
        "metadata": record.metadata,
        "content_hash": record.content_hash,
    })
    return _sha256(payload)


def _node_to_dict(node: LineageNode) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "label": node.label,
        "source_type": node.source_type.value,
        "created_at": node.created_at.isoformat(),
        "content_hash": node.content_hash,
        "metadata": node.metadata,
    }


def _edge_to_dict(edge: LineageEdge) -> dict[str, Any]:
    return {
        "edge_id": edge.edge_id,
        "source_node_id": edge.source_node_id,
        "target_node_id": edge.target_node_id,
        "transformation": edge.transformation.value,
        "created_at": edge.created_at.isoformat(),
    }
