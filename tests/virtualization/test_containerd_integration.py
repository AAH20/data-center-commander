"""Integration tests for containerd container platform adapter.

Tests the container adapter's containerd integration through the vendor-neutral
HTTPS API gateway, covering container inventory, node inventory, power
metrics, capacity metrics, container state, and health checks.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestContainerdContainerIntegration(unittest.TestCase):
    """Integration tests for containerd via the container adapter."""

    def test_probe_containerd_success(self):
        from dcc.adapters.container import probe
        mock_data = {
            "version": "1.0",
            "scopes": ["container_inventory", "node_inventory"],
            "supported_platforms": ["containerd"],
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

    def test_fetch_container_inventory_containerd_success(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [
                {
                    "container_id": "containerd-c1",
                    "name": "containerd-web",
                    "image": "docker.io/library/nginx:latest",
                    "status": "running",
                    "node_id": "containerd-node-1",
                    "cpu_limit_millicores": 1000,
                    "memory_limit_mb": 2048,
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
            result = fetch_container_inventory(
                platform="containerd",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(result["containers"][0]["container_id"], "containerd-c1")
        self.assertEqual(result["containers"][0]["platform"], "containerd")

    def test_fetch_container_inventory_containerd_with_node_filter(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [
                {
                    "container_id": "containerd-c2",
                    "name": "containerd-db",
                    "image": "docker.io/library/postgres:15",
                    "status": "running",
                    "node_id": "containerd-node-2",
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
                platform="containerd",
                endpoint="https://container.example.com/api",
                node_id="containerd-node-2",
            )
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(result["containers"][0]["node_id"], "containerd-node-2")

    def test_fetch_node_inventory_containerd_success(self):
        from dcc.adapters.container import fetch_node_inventory
        mock_data = {
            "nodes": [
                {
                    "node_id": "containerd-node-1",
                    "name": "containerd Node 1",
                    "total_cpu_cores": 16,
                    "total_memory_mb": 65536,
                    "container_runtime": "containerd",
                    "runtime_version": "1.7.11",
                    "status": "ready",
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
                platform="containerd",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["node_id"], "containerd-node-1")
        self.assertEqual(result["nodes"][0]["container_runtime"], "containerd")

    def test_fetch_power_metrics_containerd_success(self):
        from dcc.adapters.container import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "containerd-m1",
                    "entity_type": "container",
                    "entity_id": "containerd-c1",
                    "power_watts": 30.5,
                    "cpu_percent": 18.2,
                    "memory_percent": 28.0,
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
                platform="containerd",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "containerd-m1")
        self.assertEqual(result["metrics"][0]["power_watts"], "30.5")

    def test_fetch_capacity_metrics_containerd_success(self):
        from dcc.adapters.container import fetch_capacity_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "containerd-c1",
                    "entity_type": "node",
                    "entity_id": "containerd-node-1",
                    "cpu_total_cores": 16,
                    "cpu_used_cores": 10,
                    "cpu_percent": 62.5,
                    "memory_total_mb": 65536,
                    "memory_used_mb": 39322,
                    "memory_percent": 60.0,
                    "container_count": 15,
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
                platform="containerd",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["cpu_total_cores"], 16)
        self.assertEqual(result["metrics"][0]["container_count"], 15)

    def test_fetch_container_state_containerd_success(self):
        from dcc.adapters.container import fetch_container_state
        mock_data = {
            "states": [
                {
                    "container_id": "containerd-c1",
                    "status": "running",
                    "uptime_seconds": 5400,
                    "restart_count": 0,
                    "image": "docker.io/library/nginx:latest",
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
                platform="containerd",
                container_ids=["containerd-c1"],
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["container_id"], "containerd-c1")
        self.assertEqual(result["states"][0]["uptime_seconds"], 5400)

    def test_health_check_containerd_success(self):
        from dcc.adapters.container import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["containerd"]}
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

    def test_containerd_rejects_invalid_platform(self):
        from dcc.adapters.container import fetch_container_inventory
        with self.assertRaises(ValueError):
            fetch_container_inventory(
                platform="invalid_platform",
                endpoint="https://container.example.com/api",
            )

    def test_containerd_rejects_invalid_container_id(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="containerd",
                container_ids=["invalid container id!"],
                endpoint="https://container.example.com/api",
            )

    def test_containerd_rejects_empty_container_ids(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="containerd",
                container_ids=[],
                endpoint="https://container.example.com/api",
            )

    def test_containerd_rejects_too_many_container_ids(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="containerd",
                container_ids=[f"c-{i}" for i in range(101)],
                endpoint="https://container.example.com/api",
            )

    def test_containerd_container_inventory_truncation(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [{"container_id": f"c-{i}", "name": f"Container {i}"} for i in range(250)],
            "next_cursor": "cursor-123",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_container_inventory(
                platform="containerd",
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-123")
        self.assertLessEqual(len(result["containers"]), 200)

    def test_containerd_rejects_long_container_id(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="containerd",
                container_ids=["x" * 121],
                endpoint="https://container.example.com/api",
            )

    def test_containerd_rejects_long_node_id(self):
        from dcc.adapters.container import fetch_container_inventory
        with self.assertRaises(ValueError):
            fetch_container_inventory(
                platform="containerd",
                endpoint="https://container.example.com/api",
                node_id="x" * 121,
            )

    def test_containerd_supported_platforms_constant(self):
        from dcc.adapters.container import SUPPORTED_PLATFORMS
        self.assertIn("containerd", SUPPORTED_PLATFORMS)

    def test_containerd_adapter_constants(self):
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
        self.assertIn("read_container_inventory", CAPABILITIES)
        self.assertIn("container_inventory", SCOPES)
        self.assertEqual(DATA_CLASSIFICATION, "operational_telemetry")


if __name__ == "__main__":
    unittest.main()
