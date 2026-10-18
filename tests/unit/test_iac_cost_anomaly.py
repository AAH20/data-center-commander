"""Unit tests for dcc.iac_observability.cost_anomaly module."""
import unittest

from dcc.iac_observability.cost_anomaly import (
    CostAnomaly,
    CostAnomalyDetector,
    CostAnomalyReport,
    CostAnomalySeverity,
    CostAnomalyType,
    detect_cost_anomalies,
    build_cost_dashboard,
)


class TestCostAnomalyType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(CostAnomalyType.SPIKE.value, "spike")
        self.assertEqual(CostAnomalyType.DROP.value, "drop")
        self.assertEqual(CostAnomalyType.BUDGET_EXCEEDED.value, "budget_exceeded")
        self.assertEqual(CostAnomalyType.BUDGET_VARIANCE.value, "budget_variance")
        self.assertEqual(CostAnomalyType.TREND_INCREASE.value, "trend_increase")
        self.assertEqual(CostAnomalyType.TREND_DECREASE.value, "trend_decrease")
        self.assertEqual(CostAnomalyType.IDLE_RESOURCE.value, "idle_resource")


class TestCostAnomalySeverity(unittest.TestCase):
    def test_values(self):
        self.assertEqual(CostAnomalySeverity.INFO.value, "info")
        self.assertEqual(CostAnomalySeverity.LOW.value, "low")
        self.assertEqual(CostAnomalySeverity.MEDIUM.value, "medium")
        self.assertEqual(CostAnomalySeverity.HIGH.value, "high")
        self.assertEqual(CostAnomalySeverity.CRITICAL.value, "critical")


class TestCostAnomaly(unittest.TestCase):
    def test_creation(self):
        a = CostAnomaly(
            anomaly_type=CostAnomalyType.SPIKE,
            severity=CostAnomalySeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Cost spike detected",
            expected_cost=100.0,
            actual_cost=200.0,
            deviation_pct=100.0,
        )
        self.assertEqual(a.resource_id, "i-123")
        self.assertTrue(a.to_dict())


class TestCostAnomalyReport(unittest.TestCase):
    def test_empty(self):
        r = CostAnomalyReport()
        self.assertFalse(r.has_anomalies)
        self.assertEqual(r.total_variance, 0.0)

    def test_with_anomalies(self):
        a = CostAnomaly(
            anomaly_type=CostAnomalyType.SPIKE,
            severity=CostAnomalySeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Spike",
        )
        r = CostAnomalyReport(
            total_anomalies=1,
            anomalies=[a],
            total_expected_cost=100.0,
            total_actual_cost=150.0,
        )
        self.assertTrue(r.has_anomalies)
        self.assertEqual(r.total_variance, 50.0)
        self.assertAlmostEqual(r.variance_pct, 50.0)


class TestCostAnomalyDetector(unittest.TestCase):
    def test_no_anomalies(self):
        cost_data = [
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-01", "cost": 100.0, "expected_cost": 100.0},
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-02", "cost": 101.0, "expected_cost": 100.0},
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-03", "cost": 99.0, "expected_cost": 100.0},
        ]
        detector = CostAnomalyDetector()
        report = detector.detect(cost_data)
        self.assertFalse(report.has_anomalies)

    def test_spike_detection(self):
        cost_data = [
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 100.0}
            for d in range(1, 15)
        ]
        # Add a spike
        cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-15", "cost": 500.0, "expected_cost": 100.0})
        detector = CostAnomalyDetector(zscore_threshold=2.0)
        report = detector.detect(cost_data)
        self.assertTrue(report.has_anomalies)
        spike_found = any(a.anomaly_type == CostAnomalyType.SPIKE for a in report.anomalies)
        self.assertTrue(spike_found)

    def test_budget_variance(self):
        cost_data = [
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-01", "cost": 150.0, "expected_cost": 100.0},
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-02", "cost": 160.0, "expected_cost": 100.0},
        ]
        budget_data = {"i-1": 100.0}
        detector = CostAnomalyDetector(budget_variance_threshold=0.10)
        report = detector.detect(cost_data, budget_data)
        self.assertTrue(report.has_anomalies)
        variance_found = any(a.anomaly_type == CostAnomalyType.BUDGET_VARIANCE for a in report.anomalies)
        self.assertTrue(variance_found)

    def test_trend_increase(self):
        # Create data with clear increasing trend
        cost_data = []
        for d in range(1, 15):
            cost = 100.0 + d * 2  # Slowly increasing
            cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": f"2024-01-{d:02d}", "cost": cost, "expected_cost": 100.0})
        for d in range(15, 29):
            cost = 200.0 + d * 2  # Step up
            cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": f"2024-01-{d:02d}", "cost": cost, "expected_cost": 100.0})
        detector = CostAnomalyDetector(spike_threshold=0.20, trend_window=7)
        report = detector.detect(cost_data)
        trend_found = any(a.anomaly_type == CostAnomalyType.TREND_INCREASE for a in report.anomalies)
        self.assertTrue(trend_found)

    def test_idle_resource(self):
        cost_data = [
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-01", "cost": 100.0, "expected_cost": 100.0, "utilization": 0.02},
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-02", "cost": 100.0, "expected_cost": 100.0, "utilization": 0.01},
        ]
        detector = CostAnomalyDetector()
        report = detector.detect(cost_data)
        idle_found = any(a.anomaly_type == CostAnomalyType.IDLE_RESOURCE for a in report.anomalies)
        self.assertTrue(idle_found)


class TestDetectCostAnomalies(unittest.TestCase):
    def test_convenience_function(self):
        cost_data = [
            {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance", "timestamp": "2024-01-01", "cost": 100.0, "expected_cost": 100.0},
        ]
        report = detect_cost_anomalies(cost_data)
        self.assertIsInstance(report, CostAnomalyReport)


class TestBuildCostDashboard(unittest.TestCase):
    def test_dashboard(self):
        a = CostAnomaly(
            anomaly_type=CostAnomalyType.SPIKE,
            severity=CostAnomalySeverity.HIGH,
            resource_id="i-123",
            resource_name="web-1",
            resource_type="aws_instance",
            description="Spike detected",
        )
        report = CostAnomalyReport(
            total_anomalies=1,
            anomalies=[a],
            total_expected_cost=100.0,
            total_actual_cost=150.0,
        )
        dashboard = build_cost_dashboard(report)
        self.assertIn("total_anomalies", dashboard)
        self.assertIn("total_variance", dashboard)
        self.assertIn("top_anomalies", dashboard)


if __name__ == "__main__":
    unittest.main()
