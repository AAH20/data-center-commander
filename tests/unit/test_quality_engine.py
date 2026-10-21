"""Unit tests for dcc.quality.engine module."""
import unittest
import datetime as dt

from dcc.quality.engine import (
    QualityDimension,
    QualityScore,
    QualityReport,
    QualityEngine,
    DEFAULT_WEIGHTS,
    completeness_score,
    freshness_score,
    consistency_score,
    accuracy_score,
    score_source,
)


class TestQualityDimension(unittest.TestCase):
    def test_dimension_values(self):
        self.assertEqual(QualityDimension.COMPLETENESS.value, "completeness")
        self.assertEqual(QualityDimension.FRESHNESS.value, "freshness")
        self.assertEqual(QualityDimension.CONSISTENCY.value, "consistency")
        self.assertEqual(QualityDimension.ACCURACY.value, "accuracy")

    def test_dimension_enum_members(self):
        self.assertEqual(len(QualityDimension), 4)


class TestDefaultWeights(unittest.TestCase):
    def test_weights_sum(self):
        total = sum(DEFAULT_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0)

    def test_all_dimensions_present(self):
        for dim in QualityDimension:
            self.assertIn(dim, DEFAULT_WEIGHTS)


class TestQualityScore(unittest.TestCase):
    def test_creation(self):
        s = QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=0.9,
            weight=0.3,
        )
        self.assertEqual(s.dimension, QualityDimension.COMPLETENESS)
        self.assertEqual(s.score, 0.9)
        self.assertEqual(s.weight, 0.3)
        self.assertAlmostEqual(s.weighted, 0.27)

    def test_weighted(self):
        s = QualityScore(
            dimension=QualityDimension.FRESHNESS,
            score=0.8,
            weight=0.25,
        )
        self.assertAlmostEqual(s.weighted, 0.2)


class TestQualityReport(unittest.TestCase):
    def test_creation(self):
        scores = {
            QualityDimension.COMPLETENESS: QualityScore(
                dimension=QualityDimension.COMPLETENESS, score=0.9, weight=0.3
            ),
        }
        r = QualityReport(source="test", scores=scores, overall=0.9, graded_at="2024-01-01")
        self.assertEqual(r.source, "test")
        self.assertEqual(r.overall, 0.9)

    def test_to_dict(self):
        scores = {
            QualityDimension.COMPLETENESS: QualityScore(
                dimension=QualityDimension.COMPLETENESS, score=0.9, weight=0.3
            ),
        }
        r = QualityReport(source="test", scores=scores, overall=0.9, graded_at="2024-01-01")
        d = r.to_dict()
        self.assertEqual(d["source"], "test")
        self.assertEqual(d["overall"], 0.9)


class TestCompletenessScore(unittest.TestCase):
    def test_complete(self):
        records = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = completeness_score(records, ["a", "b"])
        self.assertEqual(result.score, 1.0)

    def test_incomplete(self):
        records = [{"a": 1}, {"a": 3, "b": 4}]
        result = completeness_score(records, ["a", "b"])
        self.assertLess(result.score, 1.0)

    def test_empty_records(self):
        result = completeness_score([], ["a", "b"])
        self.assertEqual(result.score, 0.0)

    def test_with_optional_fields(self):
        records = [{"a": 1, "b": 2, "c": 3}]
        result = completeness_score(records, ["a", "b"], ["c"])
        self.assertEqual(result.score, 1.0)


class TestFreshnessScore(unittest.TestCase):
    def test_fresh(self):
        now = dt.datetime.now(dt.timezone.utc)
        timestamps = [now]
        result = freshness_score(timestamps, max_age_hours=24)
        self.assertGreater(result.score, 0.8)

    def test_stale(self):
        old = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
        timestamps = [old]
        result = freshness_score(timestamps, max_age_hours=24)
        self.assertLess(result.score, 0.5)


class TestConsistencyScore(unittest.TestCase):
    def test_consistent(self):
        records = [{"a": 1, "b": 1}, {"a": 2, "b": 2}]
        rules = [lambda r: r["a"] == r["b"]]
        result = consistency_score(records, rules)
        self.assertGreater(result.score, 0.5)


class TestAccuracyScore(unittest.TestCase):
    def test_accurate(self):
        # reference_values is keyed by FIELD NAME, not by record id. Keying it by id
        # made every record miss every field and scored a perfectly accurate payload
        # at 0.
        records = [{"id": 1, "value": 100.0}]
        reference = {"value": 100.0}
        result = accuracy_score(records, reference)
        self.assertGreater(result.score, 0.9)


class TestScoreSource(unittest.TestCase):
    def test_score_source(self):
        records = [{"a": 1, "b": 2}]
        result = score_source("test", records, required_fields=["a", "b"])
        self.assertIsInstance(result, QualityReport)


class TestQualityEngine(unittest.TestCase):
    def test_engine_creation(self):
        engine = QualityEngine()
        self.assertIsNotNone(engine)

    def test_engine_with_custom_weights(self):
        weights = {QualityDimension.COMPLETENESS: 0.5, QualityDimension.FRESHNESS: 0.5, QualityDimension.CONSISTENCY: 0.0, QualityDimension.ACCURACY: 0.0}
        engine = QualityEngine(weights=weights)
        self.assertIsNotNone(engine)


if __name__ == "__main__":
    unittest.main()
