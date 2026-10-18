"""Tests for GCP Cloud Run integration."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from dcc.autoscaling.cloud_run import (
    CloudRunAdapter,
    CloudRunCPUAllocation,
    CloudRunError,
    CloudRunIngress,
    CloudRunNotFoundError,
    CloudRunScalingRecommendation,
    CloudRunServiceConfig,
    CloudRunServiceStatus,
    CloudRunStatus,
    CloudRunValidationError,
    get_adapter,
)


class CloudRunServiceConfigTests(unittest.TestCase):
    def test_valid_config(self):
        config = CloudRunServiceConfig(
            name="my-service",
            region="us-central1",
            image="gcr.io/project/image:latest",
            min_instances=1,
            max_instances=10,
            concurrency=50,
        )
        self.assertEqual(config.name, "my-service")
        self.assertEqual(config.region, "us-central1")
        self.assertEqual(config.min_instances, 1)
        self.assertEqual(config.max_instances, 10)
        self.assertEqual(config.concurrency, 50)

    def test_default_values(self):
        config = CloudRunServiceConfig(
            name="my-service",
            region="us-central1",
            image="gcr.io/project/image:latest",
        )
        self.assertEqual(config.min_instances, 0)
        self.assertEqual(config.max_instances, 100)
        self.assertEqual(config.concurrency, 80)
        self.assertEqual(config.cpu, "1")
        self.assertEqual(config.memory, "512Mi")
        self.assertEqual(config.timeout_seconds, 300)

    def test_invalid_name_empty(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="",
                region="us-central1",
                image="gcr.io/project/image:latest",
            )

    def test_invalid_name_too_long(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="a" * 64,
                region="us-central1",
                image="gcr.io/project/image:latest",
            )

    def test_invalid_name_uppercase(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="MyService",
                region="us-central1",
                image="gcr.io/project/image:latest",
            )

    def test_invalid_name_starts_with_hyphen(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="-my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
            )

    def test_invalid_region_empty(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="",
                image="gcr.io/project/image:latest",
            )

    def test_invalid_image_empty(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="",
            )

    def test_invalid_min_instances_negative(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                min_instances=-1,
            )

    def test_invalid_max_instances_zero(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                max_instances=0,
            )

    def test_invalid_min_greater_than_max(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                min_instances=10,
                max_instances=5,
            )

    def test_invalid_concurrency_zero(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                concurrency=0,
            )

    def test_invalid_concurrency_too_high(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                concurrency=1001,
            )

    def test_invalid_timeout_zero(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                timeout_seconds=0,
            )

    def test_invalid_timeout_too_high(self):
        with self.assertRaises(ValueError):
            CloudRunServiceConfig(
                name="my-service",
                region="us-central1",
                image="gcr.io/project/image:latest",
                timeout_seconds=3601,
            )

    def test_env_vars(self):
        config = CloudRunServiceConfig(
            name="my-service",
            region="us-central1",
            image="gcr.io/project/image:latest",
            env_vars={"KEY1": "value1", "KEY2": "value2"},
        )
        self.assertEqual(config.env_vars, {"KEY1": "value1", "KEY2": "value2"})

    def test_labels(self):
        config = CloudRunServiceConfig(
            name="my-service",
            region="us-central1",
            image="gcr.io/project/image:latest",
            labels={"env": "prod", "team": "backend"},
        )
        self.assertEqual(config.labels, {"env": "prod", "team": "backend"})

    def test_ingress_enum(self):
        config = CloudRunServiceConfig(
            name="my-service",
            region="us-central1",
            image="gcr.io/project/image:latest",
            ingress=CloudRunIngress.INTERNAL,
        )
        self.assertEqual(config.ingress, CloudRunIngress.INTERNAL)

    def test_cpu_allocation_enum(self):
        config = CloudRunServiceConfig(
            name="my-service",
            region="us-central1",
            image="gcr.io/project/image:latest",
            cpu_allocation=CloudRunCPUAllocation.CPU_ALLOCATION_ONLY_DURING_REQUESTS,
        )
        self.assertEqual(
            config.cpu_allocation,
            CloudRunCPUAllocation.CPU_ALLOCATION_ONLY_DURING_REQUESTS,
        )


class CloudRunServiceStatusTests(unittest.TestCase):
    def test_status_creation(self):
        status = CloudRunServiceStatus(
            name="my-service",
            region="us-central1",
            status=CloudRunStatus.READY,
            url="https://my-service-abc123-uc.a.run.app",
            ready=True,
            active_instances=3,
            desired_instances=3,
        )
        self.assertEqual(status.name, "my-service")
        self.assertEqual(status.status, CloudRunStatus.READY)
        self.assertTrue(status.ready)
        self.assertEqual(status.active_instances, 3)

    def test_status_error(self):
        status = CloudRunServiceStatus(
            name="my-service",
            region="us-central1",
            status=CloudRunStatus.ERROR,
            error_message="Container failed to start",
        )
        self.assertEqual(status.status, CloudRunStatus.ERROR)
        self.assertFalse(status.ready)
        self.assertEqual(status.error_message, "Container failed to start")


class CloudRunScalingRecommendationTests(unittest.TestCase):
    def test_recommendation_creation(self):
        rec = CloudRunScalingRecommendation(
            service_name="my-service",
            region="us-central1",
            current_min_instances=0,
            current_max_instances=100,
            current_concurrency=80,
            recommended_min_instances=1,
            recommended_max_instances=50,
            recommended_concurrency=100,
            reason="High traffic detected",
            confidence=0.85,
            estimated_cost_impact=-25.50,
            risk_level="low",
        )
        self.assertEqual(rec.service_name, "my-service")
        self.assertEqual(rec.recommended_min_instances, 1)
        self.assertEqual(rec.recommended_max_instances, 50)
        self.assertEqual(rec.recommended_concurrency, 100)
        self.assertEqual(rec.confidence, 0.85)
        self.assertEqual(rec.risk_level, "low")


class CloudRunAdapterTests(unittest.TestCase):
    def test_adapter_creation(self):
        adapter = CloudRunAdapter(project_id="my-project-123")
        self.assertEqual(adapter.project_id, "my-project-123")

    def test_adapter_creation_from_env(self):
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "env-project"}):
            adapter = CloudRunAdapter()
            self.assertEqual(adapter.project_id, "env-project")

    def test_adapter_missing_project(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(CloudRunError):
                CloudRunAdapter()

    def test_adapter_invalid_project(self):
        with self.assertRaises(CloudRunError):
            CloudRunAdapter(project_id="Invalid_Project")

    def test_validate_service_name_valid(self):
        adapter = CloudRunAdapter(project_id="my-project")
        result = adapter._validate_service_name("my-service-123")
        self.assertEqual(result, "my-service-123")

    def test_validate_service_name_invalid(self):
        adapter = CloudRunAdapter(project_id="my-project")
        with self.assertRaises(CloudRunValidationError):
            adapter._validate_service_name("MyService")

    def test_validate_region_valid(self):
        adapter = CloudRunAdapter(project_id="my-project")
        result = adapter._validate_region("us-central1")
        self.assertEqual(result, "us-central1")

    def test_validate_region_invalid(self):
        adapter = CloudRunAdapter(project_id="my-project")
        with self.assertRaises(CloudRunValidationError):
            adapter._validate_region("invalid_region_format")

    def test_parse_status_ready(self):
        adapter = CloudRunAdapter(project_id="my-project")
        status = adapter._parse_status("READY")
        self.assertEqual(status, CloudRunStatus.READY)

    def test_parse_status_deploying(self):
        adapter = CloudRunAdapter(project_id="my-project")
        status = adapter._parse_status("DEPLOYING")
        self.assertEqual(status, CloudRunStatus.DEPLOYING)

    def test_parse_status_error(self):
        adapter = CloudRunAdapter(project_id="my-project")
        status = adapter._parse_status("ERROR")
        self.assertEqual(status, CloudRunStatus.ERROR)

    def test_parse_status_unknown(self):
        adapter = CloudRunAdapter(project_id="my-project")
        status = adapter._parse_status("SOMETHING_ELSE")
        self.assertEqual(status, CloudRunStatus.UNKNOWN)

    def test_parse_service_status_ready(self):
        adapter = CloudRunAdapter(project_id="my-project")
        payload = {
            "name": "projects/my-project/locations/us-central1/services/my-service",
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "True"},
                ],
                "url": "https://my-service-abc123-uc.a.run.app",
                "latestRevision": "my-service-00001-abc",
            },
            "createTime": "2024-01-01T00:00:00Z",
            "updateTime": "2024-01-02T00:00:00Z",
        }
        status = adapter._parse_service_status(payload, "us-central1")
        self.assertEqual(status.name, "my-service")
        self.assertEqual(status.status, CloudRunStatus.READY)
        self.assertTrue(status.ready)
        self.assertEqual(status.url, "https://my-service-abc123-uc.a.run.app")

    def test_parse_service_status_error(self):
        adapter = CloudRunAdapter(project_id="my-project")
        payload = {
            "name": "projects/my-project/locations/us-central1/services/my-service",
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "False", "message": "Container failed"},
                ],
            },
        }
        status = adapter._parse_service_status(payload, "us-central1")
        self.assertEqual(status.status, CloudRunStatus.ERROR)
        self.assertFalse(status.ready)
        self.assertEqual(status.error_message, "Container failed")

    def test_build_recommendation_reason_error(self):
        adapter = CloudRunAdapter(project_id="my-project")
        service = CloudRunServiceStatus(
            name="my-service",
            region="us-central1",
            status=CloudRunStatus.ERROR,
        )
        reason = adapter._build_recommendation_reason(service, [], 0, 100, 80)
        self.assertIn("ERROR", reason)

    def test_build_recommendation_reason_no_metrics(self):
        adapter = CloudRunAdapter(project_id="my-project")
        service = CloudRunServiceStatus(
            name="my-service",
            region="us-central1",
            status=CloudRunStatus.READY,
        )
        reason = adapter._build_recommendation_reason(service, [], 0, 100, 80)
        self.assertIn("No metrics available", reason)

    def test_build_recommendation_reason_with_metrics(self):
        adapter = CloudRunAdapter(project_id="my-project")
        service = CloudRunServiceStatus(
            name="my-service",
            region="us-central1",
            status=CloudRunStatus.READY,
            active_instances=5,
        )
        from dcc.autoscaling.cloud_run import CloudRunMetrics
        metrics = CloudRunMetrics(
            service_name="my-service",
            region="us-central1",
            timestamp="2024-01-01T00:00:00Z",
            active_instances=5,
            average_concurrency=42.5,
        )
        reason = adapter._build_recommendation_reason(service, [metrics], 2, 10, 51)
        self.assertIn("5 active instance", reason)
        self.assertIn("42.5", reason)

    def test_health_check_success(self):
        adapter = CloudRunAdapter(project_id="my-project")
        with patch.object(adapter, "list_services", return_value=[]):
            self.assertTrue(adapter.health_check())

    def test_health_check_failure(self):
        adapter = CloudRunAdapter(project_id="my-project")
        with patch.object(adapter, "list_services", side_effect=CloudRunError("fail")):
            self.assertFalse(adapter.health_check())

    def test_get_scaling_recommendation_invalid_cpu(self):
        adapter = CloudRunAdapter(project_id="my-project")
        with self.assertRaises(CloudRunValidationError):
            adapter.get_scaling_recommendation(
                "my-service", "us-central1", target_cpu_utilization=0.05
            )

    def test_get_scaling_recommendation_invalid_memory(self):
        adapter = CloudRunAdapter(project_id="my-project")
        with self.assertRaises(CloudRunValidationError):
            adapter.get_scaling_recommendation(
                "my-service", "us-central1", target_memory_utilization=1.5
            )


class CloudRunAdapterSingletonTests(unittest.TestCase):
    def test_get_adapter_singleton(self):
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            a1 = get_adapter()
            a2 = get_adapter()
            self.assertIs(a1, a2)

    def test_get_adapter_with_project_id(self):
        from dcc.autoscaling.cloud_run import adapter as adapter_module
        old_adapter = adapter_module._default_adapter
        adapter_module._default_adapter = None
        try:
            adapter = get_adapter(project_id="custom-project")
            self.assertEqual(adapter.project_id, "custom-project")
        finally:
            adapter_module._default_adapter = old_adapter


class CloudRunMetricsTests(unittest.TestCase):
    def test_metrics_creation(self):
        from dcc.autoscaling.cloud_run import CloudRunMetrics
        metrics = CloudRunMetrics(
            service_name="my-service",
            region="us-central1",
            timestamp="2024-01-01T00:00:00Z",
            active_instances=3,
            idle_instances=2,
            request_count=1000,
            request_latency_ms=150.5,
            average_concurrency=42.0,
            error_count=5,
            error_rate=0.005,
            cpu_utilization=0.65,
            memory_utilization=0.72,
        )
        self.assertEqual(metrics.service_name, "my-service")
        self.assertEqual(metrics.active_instances, 3)
        self.assertEqual(metrics.request_count, 1000)
        self.assertAlmostEqual(metrics.cpu_utilization, 0.65)


if __name__ == "__main__":
    unittest.main()
