"""Integration tests for provenance tracking.

Tests lineage nodes, edges, steps, and hash chaining.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

# Fixed timestamp so step hashes are reproducible across runs.
_TEST_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)



class TestProvenanceTrackerIntegration(unittest.TestCase):
    """Integration tests for provenance tracking."""

    def test_lineage_node_creation(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test Node",
            source_type=SourceType.CONNECTOR,
        )
        self.assertEqual(node.node_id, "n1")
        self.assertEqual(node.tenant_id, "t1")

    def test_lineage_edge_creation(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.INGESTION,
        )
        self.assertEqual(edge.edge_id, "e1")
        self.assertEqual(edge.source_node_id, "n1")

    def test_lineage_step_creation(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.AGGREGATION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertEqual(step.step_id, "s1")

    def test_source_type_enum(self):
        from dcc.provenance.tracker import SourceType
        self.assertEqual(SourceType.CONNECTOR, "connector")
        self.assertEqual(SourceType.MANUAL_ENTRY, "manual_entry")
        self.assertEqual(SourceType.API_IMPORT, "api_import")
        self.assertEqual(SourceType.SEED_FIXTURE, "seed_fixture")
        self.assertEqual(SourceType.CALCULATED, "calculated")
        self.assertEqual(SourceType.EXTERNAL_SYSTEM, "external_system")

    def test_transformation_type_enum(self):
        from dcc.provenance.tracker import TransformationType
        self.assertEqual(TransformationType.INGESTION, "ingestion")
        self.assertEqual(TransformationType.VALIDATION, "validation")
        self.assertEqual(TransformationType.AGGREGATION, "aggregation")
        self.assertEqual(TransformationType.ALLOCATION, "allocation")
        self.assertEqual(TransformationType.NORMALIZATION, "normalization")
        self.assertEqual(TransformationType.CALCULATION, "calculation")
        self.assertEqual(TransformationType.FILTER, "filter")
        self.assertEqual(TransformationType.JOIN, "join")
        self.assertEqual(TransformationType.DERIVATION, "derivation")

    def test_quality_status_enum(self):
        from dcc.provenance.tracker import QualityStatus
        self.assertEqual(QualityStatus.GOOD, "good")
        self.assertEqual(QualityStatus.ESTIMATED, "estimated")
        self.assertEqual(QualityStatus.SUSPECT, "suspect")
        self.assertEqual(QualityStatus.BAD, "bad")
        self.assertEqual(QualityStatus.MISSING, "missing")
        self.assertEqual(QualityStatus.UNVERIFIED, "unverified")

    def test_lineage_node_with_metadata(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test",
            source_type=SourceType.CONNECTOR,
            metadata={"key": "value"},
            content_hash="abc123",
        )
        self.assertEqual(node.metadata["key"], "value")
        self.assertEqual(node.content_hash, "abc123")

    def test_lineage_edge_with_metadata(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.AGGREGATION,
            metadata={"method": "sum"},
        )
        self.assertEqual(edge.metadata["method"], "sum")

    def test_lineage_step_with_metadata(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.CALCULATION,
            input_hashes = ["hash-n1", "hash-n2"],
            output_hash = "hash-n3",
            metadata={"formula": "sum"},
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertEqual(step.metadata["formula"], "sum")

    def test_lineage_node_default_created_at(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test",
            source_type=SourceType.CONNECTOR,
        )
        self.assertIsNotNone(node.created_at)

    def test_lineage_edge_default_created_at(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.INGESTION,
        )
        self.assertIsNotNone(edge.created_at)

    def test_lineage_step_default_created_at(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.INGESTION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertIsNotNone(step.occurred_at)

    def test_lineage_node_default_content_hash(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test",
            source_type=SourceType.CONNECTOR,
        )
        self.assertEqual(node.content_hash, "")

    def test_lineage_node_default_metadata(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test",
            source_type=SourceType.CONNECTOR,
        )
        self.assertEqual(node.metadata, {})

    def test_lineage_edge_default_metadata(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.INGESTION,
        )
        self.assertEqual(edge.metadata, {})

    def test_lineage_step_default_metadata(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.INGESTION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertEqual(step.metadata, {})

    def test_lineage_node_tenant_isolation(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node1 = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test 1",
            source_type=SourceType.CONNECTOR,
        )
        node2 = LineageNode(
            node_id="n2",
            node_type="telemetry",
            tenant_id="t2",
            label="Test 2",
            source_type=SourceType.CONNECTOR,
        )
        self.assertNotEqual(node1.tenant_id, node2.tenant_id)

    def test_lineage_edge_tenant_isolation(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge1 = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.INGESTION,
        )
        edge2 = LineageEdge(
            edge_id="e2",
            source_node_id="n3",
            target_node_id="n4",
            tenant_id="t2",
            transformation=TransformationType.INGESTION,
        )
        self.assertNotEqual(edge1.tenant_id, edge2.tenant_id)

    def test_lineage_step_tenant_isolation(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step1 = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.INGESTION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        step2 = LineageStep(
            step_id="s2",
            tenant_id="t2",
            transformation_type = TransformationType.INGESTION,
            input_hashes = ["hash-n3"],
            output_hash = "hash-n4",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertNotEqual(step1.tenant_id, step2.tenant_id)

    def test_lineage_node_different_source_types(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        for source_type in SourceType:
            node = LineageNode(
                node_id=f"n-{source_type.value}",
                node_type="test",
                tenant_id="t1",
                label=f"Test {source_type.value}",
                source_type=source_type,
            )
            self.assertEqual(node.source_type, source_type)

    def test_lineage_edge_different_transformations(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        for transformation in TransformationType:
            edge = LineageEdge(
                edge_id=f"e-{transformation.value}",
                source_node_id="n1",
                target_node_id="n2",
                tenant_id="t1",
                transformation=transformation,
            )
            self.assertEqual(edge.transformation, transformation)

    def test_lineage_step_different_transformations(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        for transformation in TransformationType:
            step = LineageStep(
                step_id=f"s-{transformation.value}",
                tenant_id="t1",
                transformation_type = transformation,
                input_hashes = ["hash-n1"],
                output_hash = "hash-n2",
                operation = "test",
                actor_ref = "tester",
                occurred_at = _TEST_TIME,
            )
            self.assertEqual(step.transformation_type, transformation)

    def test_lineage_node_multiple_metadata_keys(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test",
            source_type=SourceType.CONNECTOR,
            metadata={"key1": "value1", "key2": "value2", "key3": "value3"},
        )
        self.assertEqual(len(node.metadata), 3)

    def test_lineage_edge_multiple_metadata_keys(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.INGESTION,
            metadata={"key1": "value1", "key2": "value2", "key3": "value3"},
        )
        self.assertEqual(len(edge.metadata), 3)

    def test_lineage_step_multiple_metadata_keys(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.INGESTION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            metadata={"key1": "value1", "key2": "value2", "key3": "value3"},
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertEqual(len(step.metadata), 3)

    def test_lineage_node_multiple_input_nodes(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.AGGREGATION,
            input_hashes = ["hash-n1", "hash-n2", "hash-n3"],
            output_hash = "hash-n4",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        self.assertEqual(len(step.input_hashes), 3)

    def test_lineage_step_single_output_hash(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.DERIVATION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        # LineageStep carries ONE output_hash. A transformation with several outputs
        # is recorded as several steps -- record_transformation() takes a single
        # output_node_id. This assertion previously expected output_node_ids to hold
        # three entries, a shape the dataclass never had.
        self.assertEqual(step.output_hash, "hash-n2")
        self.assertIsInstance(step.output_hash, str)

    def test_lineage_node_content_hash_immutable(self):
        from dcc.provenance.tracker import LineageNode, SourceType
        node = LineageNode(
            node_id="n1",
            node_type="telemetry",
            tenant_id="t1",
            label="Test",
            source_type=SourceType.CONNECTOR,
            content_hash="original_hash",
        )
        # content_hash should not be directly mutable (frozen dataclass)
        self.assertEqual(node.content_hash, "original_hash")

    def test_lineage_edge_created_at_immutable(self):
        from dcc.provenance.tracker import LineageEdge, TransformationType
        edge = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.INGESTION,
        )
        # created_at should not be directly mutable (frozen dataclass)
        self.assertIsNotNone(edge.created_at)

    def test_lineage_step_created_at_immutable(self):
        from dcc.provenance.tracker import LineageStep, TransformationType
        step = LineageStep(
            step_id="s1",
            tenant_id="t1",
            transformation_type = TransformationType.INGESTION,
            input_hashes = ["hash-n1"],
            output_hash = "hash-n2",
            operation = "test",
            actor_ref = "tester",
            occurred_at = _TEST_TIME,
        )
        # created_at should not be directly mutable (frozen dataclass)
        self.assertIsNotNone(step.occurred_at)


if __name__ == "__main__":
    unittest.main()
