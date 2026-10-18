"""Unit tests for dcc.provenance.tracker module."""
import unittest
from datetime import datetime, timezone

from dcc.provenance.tracker import (
    SourceType,
    TransformationType,
    QualityStatus,
    LineageNode,
    LineageEdge,
    LineageStep,
    ProvenanceRecord,
    LineageTracker,
)


class TestSourceType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SourceType.CONNECTOR.value, "connector")
        self.assertEqual(SourceType.MANUAL_ENTRY.value, "manual_entry")
        self.assertEqual(SourceType.API_IMPORT.value, "api_import")
        self.assertEqual(SourceType.SEED_FIXTURE.value, "seed_fixture")
        self.assertEqual(SourceType.CALCULATED.value, "calculated")
        self.assertEqual(SourceType.EXTERNAL_SYSTEM.value, "external_system")


class TestTransformationType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(TransformationType.INGESTION.value, "ingestion")
        self.assertEqual(TransformationType.VALIDATION.value, "validation")
        self.assertEqual(TransformationType.AGGREGATION.value, "aggregation")
        self.assertEqual(TransformationType.ALLOCATION.value, "allocation")
        self.assertEqual(TransformationType.NORMALIZATION.value, "normalization")
        self.assertEqual(TransformationType.CALCULATION.value, "calculation")


class TestQualityStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(QualityStatus.GOOD.value, "good")
        self.assertEqual(QualityStatus.ESTIMATED.value, "estimated")
        self.assertEqual(QualityStatus.SUSPECT.value, "suspect")
        self.assertEqual(QualityStatus.BAD.value, "bad")
        self.assertEqual(QualityStatus.MISSING.value, "missing")
        self.assertEqual(QualityStatus.UNVERIFIED.value, "unverified")


class TestLineageNode(unittest.TestCase):
    def test_creation(self):
        n = LineageNode(
            node_id="n1",
            node_type="kpi",
            tenant_id="t1",
            label="Test KPI",
            source_type=SourceType.CALCULATED,
        )
        self.assertEqual(n.node_id, "n1")
        self.assertEqual(n.node_type, "kpi")

    def test_with_metadata(self):
        n = LineageNode(
            node_id="n1",
            node_type="kpi",
            tenant_id="t1",
            label="Test KPI",
            source_type=SourceType.CALCULATED,
            metadata={"key": "value"},
        )
        self.assertEqual(n.metadata["key"], "value")


class TestLineageEdge(unittest.TestCase):
    def test_creation(self):
        e = LineageEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            tenant_id="t1",
            transformation=TransformationType.CALCULATION,
        )
        self.assertEqual(e.edge_id, "e1")
        self.assertEqual(e.source_node_id, "n1")


class TestLineageStep(unittest.TestCase):
    def test_creation(self):
        s = LineageStep(
            step_id="s1",
            tenant_id="t1",
            operation="test",
            transformation_type=TransformationType.CALCULATION,
        )
        self.assertEqual(s.step_id, "s1")


class TestProvenanceRecord(unittest.TestCase):
    def test_creation(self):
        r = ProvenanceRecord(
            record_id="r1",
            tenant_id="t1",
            node_id="n1",
        )
        self.assertEqual(r.record_id, "r1")


class TestLineageTracker(unittest.TestCase):
    def test_creation(self):
        t = LineageTracker()
        self.assertIsNotNone(t)

    def test_register_source(self):
        t = LineageTracker()
        result = t.register_source(
            tenant_id="t1",
            node_type="kpi",
            label="Test KPI",
            source_type=SourceType.CALCULATED,
        )
        self.assertIsInstance(result, LineageNode)

    def test_record_transformation(self):
        t = LineageTracker()
        result = t.record_transformation(
            tenant_id="t1",
            operation="calculate",
            transformation_type=TransformationType.CALCULATION,
            input_node_ids=["n1"],
            output_node_id="n2",
        )
        self.assertIsInstance(result, LineageStep)

    def test_create_record(self):
        t = LineageTracker()
        result = t.create_record(
            tenant_id="t1",
            artifact_type="kpi",
            artifact_id="a1",
            source_type=SourceType.CALCULATED,
            quality_status=QualityStatus.GOOD,
            lineage_steps=[],
        )
        self.assertIsInstance(result, ProvenanceRecord)

    def test_get_lineage(self):
        t = LineageTracker()
        result = t.get_lineage(tenant_id="t1", artifact_id="a1")
        self.assertIsNotNone(result)

    def test_verify_chain(self):
        t = LineageTracker()
        result = t.verify_chain(tenant_id="t1")
        self.assertIsInstance(result, dict)

    def test_get_tenant_summary(self):
        t = LineageTracker()
        result = t.get_tenant_summary(tenant_id="t1")
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
