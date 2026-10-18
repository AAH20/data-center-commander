"""Integration tests for Kubernetes container platform adapter.

Tests the container adapter's Kubernetes integration through the vendor-neutral
HTTPS API gateway, covering pod inventory, container inventory, node inventory,
power metrics, capacity metrics, pod state, container state, and health checks.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestKubernetesContainerIntegration(unittest.TestCase):
    """Integration tests for Kubernetes via the container adapter."""

    def test_probe_kubernetes_success(self):
        from dcc.adapters.container import probe
        mock_data = {
            "version": "1.0",
            "scopes": ["pod_inventory", "container_inventory", "node_inventory"],
            "supported_platforms": ["kubernetes"],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://container.example.com/api")
        self.assertTrue(result["probe_success"])
        self.assertEqual(result["adapter_id"], "container")

    def test_fetch_pod_inventory_kubernetes_success(self):
        from dcc.adapters.container import fetch_pod_inventory
        mock_data = {
            "pods": [
                {
                    "pod_id": "k8s-pod-1",
                    "name": "web-deployment-abc12",
                    "namespace": "default",
                    "status": "Running",
                    "phase": "Running",
                    "node_id": "k8s-node-1",
                    "container_count": 2,
                    "restart_count": 0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_pod_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["pods"]), 1)
        self.assertEqual(result["pods"][0]["pod_id"], "k8s-pod-1")
        self.assertEqual(result["pods"][0]["platform"], "kubernetes")
        self.assertEqual(result["pods"][0]["phase"], "Running")

    def test_fetch_pod_inventory_kubernetes_with_namespace_filter(self):
        from dcc.adapters.container import fetch_pod_inventory
        mock_data = {
            "pods": [
                {
                    "pod_id": "k8s-pod-2",
                    "name": "api-deployment-def34",
                    "namespace": "production",
                    "status": "Running",
                    "phase": "Running",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_pod_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
                namespace="production",
            )
        self.assertEqual(len(result["pods"]), 1)
        self.assertEqual(result["pods"][0]["namespace"], "production")

    def test_fetch_pod_inventory_kubernetes_with_node_filter(self):
        from dcc.adapters.container import fetch_pod_inventory
        mock_data = {
            "pods": [
                {
                    "pod_id": "k8s-pod-3",
                    "name": "worker-pod",
                    "namespace": "default",
                    "status": "Running",
                    "node_id": "k8s-node-2",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_pod_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
                node_id="k8s-node-2",
            )
        self.assertEqual(len(result["pods"]), 1)
        self.assertEqual(result["pods"][0]["node_id"], "k8s-node-2")

    def test_fetch_container_inventory_kubernetes_success(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [
                {
                    "container_id": "k8s-c1",
                    "name": "web-container",
                    "image": "nginx:1.25",
                    "status": "running",
                    "namespace": "default",
                    "pod_id": "k8s-pod-1",
                    "node_id": "k8s-node-1",
                    "cpu_limit_millicores": 500,
                    "memory_limit_mb": 512,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_container_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(result["containers"][0]["container_id"], "k8s-c1")
        self.assertEqual(result["containers"][0]["pod_id"], "k8s-pod-1")

    def test_fetch_node_inventory_kubernetes_success(self):
        from dcc.adapters.container import fetch_node_inventory
        mock_data = {
            "nodes": [
                {
                    "node_id": "k8s-node-1",
                    "name": "k8s-worker-1",
                    "total_cpu_cores": 16,
                    "total_memory_mb": 65536,
                    "container_runtime": "containerd",
                    "runtime_version": "1.7.11",
                    "role": "worker",
                    "status": "Ready",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_node_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["node_id"], "k8s-node-1")
        self.assertEqual(result["nodes"][0]["container_runtime"], "containerd")

    def test_fetch_power_metrics_kubernetes_success(self):
        from dcc.adapters.container import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "k8s-m1",
                    "entity_type": "pod",
                    "entity_id": "k8s-pod-1",
                    "power_watts": 15.5,
                    "cpu_percent": 12.2,
                    "memory_percent": 30.0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "k8s-m1")
        self.assertEqual(result["metrics"][0]["power_watts"], "15.5")

    def test_fetch_capacity_metrics_kubernetes_success(self):
        from dcc.adapters.container import fetch_capacity_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "k8s-c1",
                    "entity_type": "node",
                    "entity_id": "k8s-node-1",
                    "cpu_total_cores": 16,
                    "cpu_used_cores": 8,
                    "cpu_percent": 50.0,
                    "memory_total_mb": 65536,
                    "memory_used_mb": 32768,
                    "memory_percent": 50.0,
                    "container_count": 25,
                    "pod_count": 20,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["cpu_total_cores"], 16)
        self.assertEqual(result["metrics"][0]["pod_count"], 20)

    def test_fetch_pod_state_kubernetes_success(self):
        from dcc.adapters.container import fetch_pod_state
        mock_data = {
            "states": [
                {
                    "pod_id": "k8s-pod-1",
                    "status": "Running",
                    "phase": "Running",
                    "namespace": "default",
                    "node_id": "k8s-node-1",
                    "container_count": 2,
                    "restart_count": 0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_pod_state(
                platform="kubernetes",
                pod_ids=["k8s-pod-1"],
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["pod_id"], "k8s-pod-1")
        self.assertEqual(result["states"][0]["phase"], "Running")

    def test_fetch_container_state_kubernetes_success(self):
        from dcc.adapters.container import fetch_container_state
        mock_data = {
            "states": [
                {
                    "container_id": "k8s-c1",
                    "status": "running",
                    "uptime_seconds": 7200,
                    "restart_count": 0,
                    "image": "nginx:1.25",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_container_state(
                platform="kubernetes",
                container_ids=["k8s-c1"],
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["container_id"], "k8s-c1")
        self.assertEqual(result["states"][0]["uptime_seconds"], 7200)

    def test_health_check_kubernetes_success(self):
        from dcc.adapters.container import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["kubernetes"]}
        mock_containers = {"containers": [{"observed_at": "2026-01-01T00:00:00Z"}]}

        class InfoResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_info).encode()

        class ContainersResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_containers).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return InfoResponse()
                return ContainersResponse()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://container.example.com/api")
        self.assertTrue(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "ok")
        self.assertEqual(result["checks"]["authentication"], "ok")
        self.assertEqual(result["checks"]["schema"], "ok")
        self.assertEqual(result["checks"]["freshness"], "ok")

    def test_kubernetes_rejects_pod_inventory_for_docker(self):
        from dcc.adapters.container import fetch_pod_inventory
        with self.assertRaises(ValueError):
            fetch_pod_inventory(
                platform="docker",
                endpoint="https://container.example.com/api",
            )

    def test_kubernetes_rejects_pod_state_for_docker(self):
        from dcc.adapters.container import fetch_pod_state
        with self.assertRaises(ValueError):
            fetch_pod_state(
                platform="docker",
                pod_ids=["pod-1"],
                endpoint="https://container.example.com/api",
            )

    def test_kubernetes_rejects_invalid_pod_id(self):
        from dcc.adapters.container import fetch_pod_state
        with self.assertRaises(ValueError):
            fetch_pod_state(
                platform="kubernetes",
                pod_ids=["invalid pod id!"],
                endpoint="https://container.example.com/api",
            )

    def test_kubernetes_rejects_empty_pod_ids(self):
        from dcc.adapters.container import fetch_pod_state
        with self.assertRaises(ValueError):
            fetch_pod_state(
                platform="kubernetes",
                pod_ids=[],
                endpoint="https://container.example.com/api",
            )

    def test_kubernetes_rejects_too_many_pod_ids(self):
        from dcc.adapters.container import fetch_pod_state
        with self.assertRaises(ValueError):
            fetch_pod_state(
                platform="kubernetes",
                pod_ids=[f"pod-{i}" for i in range(101)],
                endpoint="https://container.example.com/api",
            )

    def test_kubernetes_pod_inventory_truncation(self):
        from dcc.adapters.container import fetch_pod_inventory
        mock_data = {
            "pods": [{"pod_id": f"pod-{i}", "name": f"Pod {i}"} for i in range(250)],
            "next_cursor": "cursor-123",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_pod_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-123")
        self.assertLessEqual(len(result["pods"]), 200)

    def test_kubernetes_pod_state_truncation(self):
        from dcc.adapters.container import fetch_pod_state
        mock_data = {
            "states": [{"pod_id": f"pod-{i}"} for i in range(250)],
            "next_cursor": "cursor-def",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_pod_state(
                platform="kubernetes",
                pod_ids=[f"pod-{i}" for i in range(100)],
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-def")

    def test_kubernetes_rejects_long_pod_id(self):
        from dcc.adapters.container import fetch_pod_state
        with self.assertRaises(ValueError):
            fetch_pod_state(
                platform="kubernetes",
                pod_ids=["x" * 121],
                endpoint="https://container.example.com/api",
            )

    def test_kubernetes_rejects_long_namespace(self):
        from dcc.adapters.container import fetch_pod_inventory
        with self.assertRaises(ValueError):
            fetch_pod_inventory(
                platform="kubernetes",
                endpoint="https://container.example.com/api",
                namespace="x" * 201,
            )

    def test_kubernetes_supported_platforms_constant(self):
        from dcc.adapters.container import SUPPORTED_PLATFORMS
        self.assertIn("kubernetes", SUPPORTED_PLATFORMS)

    def test_kubernetes_adapter_constants(self):
        from dcc.adapters.container import (
            ADAPTER_ID,
            ADAPTER_VERSION,
            VENDOR,
            CAPABILITIES,
            SCOPES,
            DATA_CLASSIFICATION,
        )
        self.assertEqual(ADAPTER_ID, "container")
        self.assertEqual(ADAPTER_VERSION, "0.1.0")
        self.assertEqual(VENDOR, "Multi-Container Gateway")
        self.assertIn("read_pod_inventory", CAPABILITIES)
        self.assertIn("pod_inventory", SCOPES)
        self.assertEqual(DATA_CLASSIFICATION, "operational_telemetry")


if __name__ == "__main__":
    unittest.main()
