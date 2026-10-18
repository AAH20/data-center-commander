"""Unit tests for dcc.iac_observability.drift module."""
import unittest

from dcc.iac_observability.drift import (
    DriftDetector,
    DriftResult,
    DriftSeverity,
    DriftType,
    ResourceDrift,
    detect_drift,
    summarize_drift,
)


class TestDriftType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DriftType.ADDED.value, "added")
        self.assertEqual(DriftType.REMOVED.value, "removed")
        self.assertEqual(DriftType.MODIFIED.value, "modified")
        self.assertEqual(DriftType.TAG_DRIFT.value, "tag_drift")
        self.assertEqual(DriftType.SIZE_DRIFT.value, "size_drift")
        self.assertEqual(DriftType.NETWORK_DRIFT.value, "network_drift")
        self.assertEqual(DriftType.CREDENTIAL_DRIFT.value, "credential_drift")


class TestDriftSeverity(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DriftSeverity.NONE.value, "none")
        self.assertEqual(DriftSeverity.LOW.value, "low")
        self.assertEqual(DriftSeverity.MEDIUM.value, "medium")
        self.assertEqual(DriftSeverity.HIGH.value, "high")
        self.assertEqual(DriftSeverity.CRITICAL.value, "critical")


class TestResourceDrift(unittest.TestCase):
    def test_creation(self):
        d = ResourceDrift(
            resource_type="aws_instance",
            resource_id="i-123",
            resource_name="web-1",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.MEDIUM,
            changed_attributes=["instance_type"],
        )
        self.assertEqual(d.resource_id, "i-123")
        self.assertEqual(d.drift_type, DriftType.MODIFIED)
        self.assertTrue(d.to_dict())


class TestDriftResult(unittest.TestCase):
    def test_empty(self):
        r = DriftResult()
        self.assertFalse(r.has_drift)
        self.assertEqual(r.drift_rate, 0.0)
        self.assertEqual(r.total_drifted, 0)

    def test_with_drifts(self):
        d = ResourceDrift(
            resource_type="aws_instance",
            resource_id="i-123",
            resource_name="web-1",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.MEDIUM,
        )
        r = DriftResult(total_desired=10, total_actual=10, total_drifted=1, drifts=[d])
        self.assertTrue(r.has_drift)
        self.assertAlmostEqual(r.drift_rate, 0.05)


class TestDriftDetector(unittest.TestCase):
    def test_no_drift(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertFalse(result.has_drift)
        self.assertEqual(result.total_drifted, 0)

    def test_added_resource(self):
        desired = {}
        actual = {
            "i-456": {"resource_type": "aws_instance", "name": "rogue", "instance_type": "t3.large"},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertTrue(result.has_drift)
        self.assertEqual(result.total_drifted, 1)
        self.assertEqual(result.drifts[0].drift_type, DriftType.ADDED)

    def test_removed_resource(self):
        desired = {
            "i-789": {"resource_type": "aws_instance", "name": "old", "instance_type": "t3.micro"},
        }
        actual = {}
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertTrue(result.has_drift)
        self.assertEqual(result.drifts[0].drift_type, DriftType.REMOVED)

    def test_modified_resource(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.large"},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertTrue(result.has_drift)
        self.assertEqual(result.drifts[0].drift_type, DriftType.SIZE_DRIFT)
        self.assertIn("instance_type", result.drifts[0].changed_attributes)

    def test_tag_drift(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "prod"}},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "dev"}},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertTrue(result.has_drift)
        self.assertEqual(result.drifts[0].drift_type, DriftType.TAG_DRIFT)

    def test_network_drift(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "vpc": "vpc-123"},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "vpc": "vpc-456"},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertTrue(result.has_drift)
        self.assertEqual(result.drifts[0].drift_type, DriftType.NETWORK_DRIFT)
        self.assertEqual(result.drifts[0].severity, DriftSeverity.CRITICAL)

    def test_credential_drift(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "key": "old-key"},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "key": "new-key"},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertTrue(result.has_drift)
        self.assertEqual(result.drifts[0].drift_type, DriftType.CREDENTIAL_DRIFT)
        self.assertEqual(result.drifts[0].severity, DriftSeverity.CRITICAL)

    def test_ignored_attributes(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "id": "i-123", "created_at": "2024-01-01"},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "id": "i-123", "created_at": "2024-06-01"},
        }
        detector = DriftDetector()
        result = detector.detect(desired, actual)
        self.assertFalse(result.has_drift)

    def test_custom_ignored_attributes(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "metadata": "old"},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "metadata": "new"},
        }
        detector = DriftDetector(ignored_attributes={"id", "metadata"})
        result = detector.detect(desired, actual)
        self.assertFalse(result.has_drift)

    def test_severity_override(self):
        desired = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "prod"}},
        }
        actual = {
            "i-123": {"resource_type": "aws_instance", "name": "web-1", "tags": {"env": "dev"}},
        }
        detector = DriftDetector(
            severity_overrides={DriftType.TAG_DRIFT: DriftSeverity.HIGH}
        )
        result = detector.detect(desired, actual)
        self.assertEqual(result.drifts[0].severity, DriftSeverity.HIGH)


class TestDetectDrift(unittest.TestCase):
    def test_convenience_function(self):
        desired = {"i-1": {"resource_type": "aws_instance", "name": "web", "instance_type": "t3.micro"}}
        actual = {"i-1": {"resource_type": "aws_instance", "name": "web", "instance_type": "t3.large"}}
        result = detect_drift(desired, actual)
        self.assertIsInstance(result, DriftResult)
        self.assertTrue(result.has_drift)


class TestSummarizeDrift(unittest.TestCase):
    def test_empty(self):
        result = DriftResult()
        summary = summarize_drift(result)
        self.assertEqual(summary["total_drifted"], 0)
        self.assertFalse(summary["has_drift"])

    def test_with_drifts(self):
        d = ResourceDrift(
            resource_type="aws_instance",
            resource_id="i-123",
            resource_name="web-1",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.HIGH,
        )
        result = DriftResult(total_desired=5, total_actual=5, total_drifted=1, drifts=[d])
        summary = summarize_drift(result)
        self.assertEqual(summary["total_drifted"], 1)
        self.assertTrue(summary["has_drift"])
        self.assertEqual(len(summary["top_drifts"]), 1)


if __name__ == "__main__":
    unittest.main()
