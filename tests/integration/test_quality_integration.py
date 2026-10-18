"""Integration tests for quality modules.

Tests anomaly detection, quality engine, and freshness monitoring.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone


class TestAnomalyDetectionIntegration(unittest.TestCase):
    """Integration tests for anomaly detection."""

    def test_detect_anomalies_zscore(self):
        from dcc.quality.anomaly import detect_anomalies
        result = detect_anomalies([1, 2, 3, 4, 5, 100], method="zscore")
        self.assertIsNotNone(result)

    def test_detect_anomalies_iqr(self):
        from dcc.quality.anomaly import detect_anomalies
        result = detect_anomalies([1, 2, 3, 4, 5, 100], method="iqr")
        self.assertIsNotNone(result)

    def test_detect_anomalies_rejects_empty(self):
        from dcc.quality.anomaly import detect_anomalies
        with self.assertRaises(ValueError):
            detect_anomalies([], method="zscore")

    def test_detect_anomalies_rejects_invalid_method(self):
        from dcc.quality.anomaly import detect_anomalies
        with self.assertRaises(ValueError):
            detect_anomalies([1, 2, 3], method="invalid")

    def test_anomaly_report_to_dict(self):
        from dcc.quality.anomaly import AnomalyReport, Anomaly
        report = AnomalyReport(
            method="zscore",
            total_points=10,
            anomalies=[Anomaly(index=0, timestamp=None, value=100.0, expected=3.0, deviation=97.0, method="zscore", severity="high")],
        )
        d = report.to_dict()
        self.assertIn("method", d)
        self.assertIn("anomaly_count", d)

    def test_anomaly_report_properties(self):
        from dcc.quality.anomaly import AnomalyReport, Anomaly
        report = AnomalyReport(
            method="zscore",
            total_points=10,
            anomalies=[Anomaly(index=0, timestamp=None, value=100.0, expected=3.0, deviation=97.0, method="zscore", severity="high")],
        )
        self.assertEqual(report.anomaly_count, 1)
        self.assertAlmostEqual(report.anomaly_rate, 0.1)


class TestQualityEngineIntegration(unittest.TestCase):
    """Integration tests for the quality engine."""

    def test_score_source(self):
        from dcc.quality.engine import score_source
        result = score_source(
            source="test",
            records=[{"id": "1", "name": "Test"}],
            required_fields=["id", "name"],
        )
        self.assertIsNotNone(result)

    def test_quality_engine(self):
        from dcc.quality.engine import QualityEngine
        engine = QualityEngine()
        self.assertIsNotNone(engine)

    def test_quality_report_to_dict(self):
        from dcc.quality.engine import QualityReport, QualityScore, QualityDimension
        report = QualityReport(
            source="test",
            scores={
                QualityDimension.COMPLETENESS: QualityScore(
                    dimension=QualityDimension.COMPLETENESS,
                    score=0.9,
                    weight=0.3,
                ),
            },
            overall=0.9,
            graded_at="2026-01-01T00:00:00Z",
        )
        d = report.to_dict()
        self.assertIn("source", d)
        self.assertIn("overall", d)

    def test_default_weights(self):
        from dcc.quality.engine import DEFAULT_WEIGHTS, QualityDimension
        self.assertIn(QualityDimension.COMPLETENESS, DEFAULT_WEIGHTS)
        self.assertIn(QualityDimension.FRESHNESS, DEFAULT_WEIGHTS)
        self.assertIn(QualityDimension.CONSISTENCY, DEFAULT_WEIGHTS)
        self.assertIn(QualityDimension.ACCURACY, DEFAULT_WEIGHTS)

    def test_completeness_score(self):
        from dcc.quality.engine import completeness_score
        result = completeness_score(
            records=[{"id": "1", "name": "Test", "value": 100}],
            required_fields=["id", "name"],
        )
        self.assertIsNotNone(result)

    def test_freshness_score(self):
        from dcc.quality.engine import freshness_score
        result = freshness_score(
            records=[{"id": "1", "observed_at": datetime.now(timezone.utc).isoformat()}],
            timestamp_field="observed_at",
            max_age_hours=24,
        )
        self.assertIsNotNone(result)

    def test_consistency_score(self):
        from dcc.quality.engine import consistency_score
        result = consistency_score(
            records=[{"id": "1", "value": 100}],
            field="value",
        )
        self.assertIsNotNone(result)

    def test_accuracy_score(self):
        from dcc.quality.engine import accuracy_score
        result = accuracy_score(
            records=[{"id": "1", "value": 100}],
            field="value",
            min_val=0,
            max_val=200,
        )
        self.assertIsNotNone(result)


class TestFreshnessIntegration(unittest.TestCase):
    """Integration tests for freshness monitoring."""

    def test_evaluate_sla_ok(self):
        from dcc.quality.freshness import evaluate_sla
        result = evaluate_sla(age_hours=0.5, sla_hours=1)
        self.assertEqual(result, "ok")

    def test_evaluate_sla_warning(self):
        from dcc.quality.freshness import evaluate_sla
        result = evaluate_sla(age_hours=0.8, sla_hours=1)
        self.assertEqual(result, "warning")

    def test_evaluate_sla_violation(self):
        from dcc.quality.freshness import evaluate_sla
        result = evaluate_sla(age_hours=2.0, sla_hours=1)
        self.assertEqual(result, "violation")

    def test_evaluate_sla_no_data(self):
        from dcc.quality.freshness import evaluate_sla
        result = evaluate_sla(age_hours=None, sla_hours=1, row_count=0)
        self.assertEqual(result, "no_data")

    def test_hours_since(self):
        from dcc.quality.freshness import _hours_since
        now = datetime.now(timezone.utc)
        result = _hours_since(now - timedelta(hours=2))
        self.assertAlmostEqual(result, 2.0, places=1)

    def test_hours_since_none(self):
        from dcc.quality.freshness import _hours_since
        result = _hours_since(None)
        self.assertIsNone(result)

    def test_default_sla_hours(self):
        from dcc.quality.freshness import DEFAULT_SLA_HOURS
        self.assertIn("telemetry_readings", DEFAULT_SLA_HOURS)
        self.assertIn("kpi_observations", DEFAULT_SLA_HOURS)

    def test_price_source_kind_sla(self):
        from dcc.quality.freshness import PRICE_SOURCE_KIND_SLA_HOURS
        self.assertIn("vendor_api", PRICE_SOURCE_KIND_SLA_HOURS)
        self.assertIn("synthetic_demo", PRICE_SOURCE_KIND_SLA_HOURS)

    def test_source_freshness_creation(self):
        from dcc.quality.freshness import SourceFreshness
        source = SourceFreshness(
            source="test",
            table="test_table",
            latest_timestamp="2026-01-01T00:00:00Z",
            age_hours=1.0,
            sla_hours=24,
            status="ok",
        )
        self.assertEqual(source.status, "ok")

    def test_freshness_report_creation(self):
        from dcc.quality.freshness import FreshnessReport
        report = FreshnessReport(
            tenant_id="t1",
            checked_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(report.overall_status, "ok")

    def test_freshness_report_with_violations(self):
        from dcc.quality.freshness import FreshnessReport, SourceFreshness
        report = FreshnessReport(
            tenant_id="t1",
            checked_at="2026-01-01T00:00:00Z",
            sources=[
                SourceFreshness(
                    source="test",
                    table="test_table",
                    latest_timestamp="2026-01-01T00:00:00Z",
                    age_hours=48.0,
                    sla_hours=24,
                    status="violation",
                ),
            ],
            violations=["test"],
        )
        self.assertEqual(report.overall_status, "violation")


if __name__ == "__main__":
    unittest.main()
