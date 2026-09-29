"""Example: Data lineage tracking.

Tracks data from source through transformations to final output.
"""
from dcc.provenance.tracker import (
    LineageTracker, LineageNode, LineageEdge, SourceType, TransformationType,
)

tracker = LineageTracker(tenant_id="tenant-1")
# Create source node
source = LineageNode(
    node_id="src-1", node_type="table", tenant_id="tenant-1",
    label="telemetry_readings", source_type=SourceType.CONNECTOR,
)
tracker.add_node(source)
# Create transformation node
transform = LineageNode(
    node_id="calc-1", node_type="kpi", tenant_id="tenant-1",
    label="PUE Calculation", source_type=SourceType.CALCULATED,
)
tracker.add_node(transform)
# Link them
edge = LineageEdge(
    edge_id="edge-1", source_node_id="src-1", target_node_id="calc-1",
    tenant_id="tenant-1", transformation=TransformationType.CALCULATION,
)
tracker.add_edge(edge)
print(f"Nodes: {len(tracker.nodes)}")
print(f"Edges: {len(tracker.edges)}")
