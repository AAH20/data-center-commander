"""Example: Data lineage tracking.

Tracks data from source through transformations to final output.
"""
from dcc.provenance.tracker import (
    LineageTracker, LineageNode, LineageEdge, SourceType, TransformationType,
)

tracker = LineageTracker()
source = tracker.register_source(
    tenant_id="tenant-1",
    node_type="table",
    label="telemetry_readings",
    source_type=SourceType.CONNECTOR,
)
step = tracker.record_transformation(
    tenant_id="tenant-1",
    operation="calculate_pue",
    transformation_type=TransformationType.CALCULATION,
    input_node_ids=[source.node_id],
    output_node_id="kpi-pue-1",
)
print(f"Source node: {source.node_id}")
print(f"Transformation step: {step.step_id}")
lineage = tracker.get_lineage(tenant_id="tenant-1", artifact_id="kpi-pue-1")
print(f"Lineage: {lineage}")
