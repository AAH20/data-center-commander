"""Integration tests for Docker container platform adapter.

Tests the container adapter's Docker integration through the vendor-neutral
HTTPS API gateway, covering container inventory, node inventory, power
metrics, capacity metrics, container state, and health checks.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestDockerContainerIntegration(unittest.TestCase):
    """Integration tests for Docker via the container adapter."""

    def test_probe_docker_success(self):
        from dcc.adapters.container import probe
        mock_data = {
            "version": "1.0",
            "scopes": ["container_inventory", "node_inventory"],
            "supported_platforms": ["docker"],
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

    def test_probe_docker_rejects_http(self):
        from dcc.adapters.container import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://container.example.com/api")

    def test_fetch_container_inventory_docker_success(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [
                {
                    "container_id": "docker-c1",
                    "name": "docker-web",
                    "image": "nginx:latest",
                    "status": "running",
                    "node_id": "docker-node-1",
                    "cpu_limit_millicores": 2000,
                    "memory_limit_mb": 4096,
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
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(result["containers"][0]["container_id"], "docker-c1")
        self.assertEqual(result["containers"][0]["platform"], "docker")
        self.assertEqual(result["containers"][0]["image"], "nginx:latest")

    def test_fetch_container_inventory_docker_with_namespace_filter(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [
                {
                    "container_id": "docker-c2",
                    "name": "docker-app",
                    "image": "myapp:v1",
                    "status": "running",
                    "namespace": "production",
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
                platform="docker",
                endpoint="https://container.example.com/api",
                namespace="production",
            )
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(result["containers"][0]["namespace"], "production")

    def test_fetch_container_inventory_docker_with_node_filter(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {
            "containers": [
                {
                    "container_id": "docker-c3",
                    "name": "docker-db",
                    "image": "postgres:15",
                    "status": "running",
                    "node_id": "docker-node-2",
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
                platform="docker",
                endpoint="https://container.example.com/api",
                node_id="docker-node-2",
            )
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(result["containers"][0]["node_id"], "docker-node-2")

    def test_fetch_node_inventory_docker_success(self):
        from dcc.adapters.container import fetch_node_inventory
        mock_data = {
            "nodes": [
                {
                    "node_id": "docker-node-1",
                    "name": "Docker Node 1",
                    "total_cpu_cores": 32,
                    "total_memory_mb": 131072,
                    "container_runtime": "docker",
                    "runtime_version": "24.0.7",
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
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["node_id"], "docker-node-1")
        self.assertEqual(result["nodes"][0]["container_runtime"], "docker")

    def test_fetch_power_metrics_docker_success(self):
        from dcc.adapters.container import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "docker-m1",
                    "entity_type": "container",
                    "entity_id": "docker-c1",
                    "power_watts": 45.5,
                    "cpu_percent": 25.2,
                    "memory_percent": 40.0,
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
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "docker-m1")
        self.assertEqual(result["metrics"][0]["power_watts"], "45.5")

    def test_fetch_power_metrics_docker_with_container_ids(self):
        from dcc.adapters.container import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "docker-m2",
                    "entity_type": "container",
                    "entity_id": "docker-c1",
                    "power_watts": 50.0,
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
                platform="docker",
                endpoint="https://container.example.com/api",
                container_ids=["docker-c1"],
            )
        self.assertEqual(len(result["metrics"]), 1)

    def test_fetch_capacity_metrics_docker_success(self):
        from dcc.adapters.container import fetch_capacity_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "docker-c1",
                    "entity_type": "node",
                    "entity_id": "docker-node-1",
                    "cpu_total_cores": 32,
                    "cpu_used_cores": 16,
                    "cpu_percent": 50.0,
                    "memory_total_mb": 131072,
                    "memory_used_mb": 65536,
                    "memory_percent": 50.0,
                    "container_count": 20,
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
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["cpu_total_cores"], 32)
        self.assertEqual(result["metrics"][0]["container_count"], 20)

    def test_fetch_container_state_docker_success(self):
        from dcc.adapters.container import fetch_container_state
        mock_data = {
            "states": [
                {
                    "container_id": "docker-c1",
                    "status": "running",
                    "uptime_seconds": 43200,
                    "restart_count": 0,
                    "image": "nginx:latest",
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
                platform="docker",
                container_ids=["docker-c1"],
                endpoint="https://container.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["container_id"], "docker-c1")
        self.assertEqual(result["states"][0]["uptime_seconds"], 43200)

    def test_health_check_docker_success(self):
        from dcc.adapters.container import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["docker"]}
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

    def test_health_check_docker_stale_data(self):
        from dcc.adapters.container import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["docker"]}
        mock_containers = {"containers": [{"observed_at": None}]}

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
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "stale")

    def test_health_check_docker_no_data(self):
        from dcc.adapters.container import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["docker"]}
        mock_containers = {"containers": []}

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
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "no_data")

    def test_docker_rejects_invalid_platform(self):
        from dcc.adapters.container import fetch_container_inventory
        with self.assertRaises(ValueError):
            fetch_container_inventory(
                platform="invalid_platform",
                endpoint="https://container.example.com/api",
            )

    def test_docker_rejects_invalid_container_id(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="docker",
                container_ids=["invalid container id!"],
                endpoint="https://container.example.com/api",
            )

    def test_docker_rejects_empty_container_ids(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="docker",
                container_ids=[],
                endpoint="https://container.example.com/api",
            )

    def test_docker_rejects_too_many_container_ids(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="docker",
                container_ids=[f"c-{i}" for i in range(101)],
                endpoint="https://container.example.com/api",
            )

    def test_docker_rejects_invalid_since_timestamp(self):
        from dcc.adapters.container import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                platform="docker",
                endpoint="https://container.example.com/api",
                since="not-a-timestamp",
            )

    def test_docker_rejects_too_many_container_ids_for_power_metrics(self):
        from dcc.adapters.container import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                platform="docker",
                endpoint="https://container.example.com/api",
                container_ids=[f"c-{i}" for i in range(101)],
            )

    def test_docker_container_inventory_truncation(self):
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
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-123")
        self.assertLessEqual(len(result["containers"]), 200)

    def test_docker_node_inventory_truncation(self):
        from dcc.adapters.container import fetch_node_inventory
        mock_data = {
            "nodes": [{"node_id": f"node-{i}", "name": f"Node {i}"} for i in range(250)],
            "next_cursor": "cursor-456",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_node_inventory(
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-456")

    def test_docker_power_metrics_truncation(self):
        from dcc.adapters.container import fetch_power_metrics
        mock_data = {
            "metrics": [{"metric_id": f"m-{i}"} for i in range(250)],
            "next_cursor": "cursor-789",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-789")

    def test_docker_capacity_metrics_truncation(self):
        from dcc.adapters.container import fetch_capacity_metrics
        mock_data = {
            "metrics": [{"metric_id": f"c-{i}"} for i in range(250)],
            "next_cursor": "cursor-abc",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(
                platform="docker",
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-abc")

    def test_docker_container_state_truncation(self):
        from dcc.adapters.container import fetch_container_state
        mock_data = {
            "states": [{"container_id": f"c-{i}"} for i in range(250)],
            "next_cursor": "cursor-def",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = fetch_container_state(
                platform="docker",
                container_ids=[f"c-{i}" for i in range(100)],
                endpoint="https://container.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-def")

    def test_docker_rejects_invalid_node_id(self):
        from dcc.adapters.container import fetch_container_inventory
        with self.assertRaises(ValueError):
            fetch_container_inventory(
                platform="docker",
                endpoint="https://container.example.com/api",
                node_id="invalid node!",
            )

    def test_docker_rejects_long_container_id(self):
        from dcc.adapters.container import fetch_container_state
        with self.assertRaises(ValueError):
            fetch_container_state(
                platform="docker",
                container_ids=["x" * 121],
                endpoint="https://container.example.com/api",
            )

    def test_docker_rejects_long_node_id(self):
        from dcc.adapters.container import fetch_container_inventory
        with self.assertRaises(ValueError):
            fetch_container_inventory(
                platform="docker",
                endpoint="https://container.example.com/api",
                node_id="x" * 121,
            )

    def test_docker_rejects_invalid_credential_ref(self):
        from dcc.adapters.container import probe
        with self.assertRaises(ValueError):
            probe(
                endpoint="https://container.example.com/api",
                credential_ref="invalid\r\ncredential",
            )

    def test_docker_rejects_long_credential_ref(self):
        from dcc.adapters.container import probe
        with self.assertRaises(ValueError):
            probe(
                endpoint="https://container.example.com/api",
                credential_ref="x" * 257,
            )

    def test_docker_rejects_long_endpoint(self):
        from dcc.adapters.container import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https://example.com/" + "x" * 512)

    def test_docker_rejects_empty_endpoint(self):
        from dcc.adapters.container import probe
        with self.assertRaises(ConnectionError):
            probe(endpoint="")

    def test_docker_rejects_endpoint_without_hostname(self):
        from dcc.adapters.container import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https:///api")

    def test_docker_connection_error_handling(self):
        from dcc.adapters.container import probe

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("Connection refused")

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://container.example.com/api")

    def test_docker_invalid_json_handling(self):
        from dcc.adapters.container import probe

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"not json"

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://container.example.com/api")

    def test_docker_non_dict_response_handling(self):
        from dcc.adapters.container import probe

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"[1, 2, 3]"

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://container.example.com/api")

    def test_docker_missing_version_handling(self):
        from dcc.adapters.container import probe
        mock_data = {"scopes": [], "supported_platforms": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://container.example.com/api")

    def test_docker_invalid_scopes_handling(self):
        from dcc.adapters.container import probe
        mock_data = {"version": "1.0", "scopes": "not-a-list", "supported_platforms": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://container.example.com/api")

    def test_docker_invalid_supported_platforms_handling(self):
        from dcc.adapters.container import probe
        mock_data = {"version": "1.0", "scopes": [], "supported_platforms": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://container.example.com/api")

    def test_docker_container_inventory_invalid_contract(self):
        from dcc.adapters.container import fetch_container_inventory
        mock_data = {"containers": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_container_inventory(
                    platform="docker",
                    endpoint="https://container.example.com/api",
                )

    def test_docker_node_inventory_invalid_contract(self):
        from dcc.adapters.container import fetch_node_inventory
        mock_data = {"nodes": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_node_inventory(
                    platform="docker",
                    endpoint="https://container.example.com/api",
                )

    def test_docker_power_metrics_invalid_contract(self):
        from dcc.adapters.container import fetch_power_metrics
        mock_data = {"metrics": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_power_metrics(
                    platform="docker",
                    endpoint="https://container.example.com/api",
                )

    def test_docker_capacity_metrics_invalid_contract(self):
        from dcc.adapters.container import fetch_capacity_metrics
        mock_data = {"metrics": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_capacity_metrics(
                    platform="docker",
                    endpoint="https://container.example.com/api",
                )

    def test_docker_container_state_invalid_contract(self):
        from dcc.adapters.container import fetch_container_state
        mock_data = {"states": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_container_state(
                    platform="docker",
                    container_ids=["c-1"],
                    endpoint="https://container.example.com/api",
                )

    def test_docker_health_check_connection_error(self):
        from dcc.adapters.container import health_check

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("Connection refused")

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://container.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "unavailable")

    def test_docker_health_check_unexpected_error(self):
        from dcc.adapters.container import health_check

        class Opener:
            def open(self, request, timeout):
                raise RuntimeError("Unexpected error")

        with patch("dcc.adapters.container.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://container.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertIn("error", result["details"])

    def test_docker_supported_platforms_constant(self):
        from dcc.adapters.container import SUPPORTED_PLATFORMS
        self.assertIn("docker", SUPPORTED_PLATFORMS)
        self.assertIn("kubernetes", SUPPORTED_PLATFORMS)
        self.assertIn("podman", SUPPORTED_PLATFORMS)
        self.assertIn("containerd", SUPPORTED_PLATFORMS)
        self.assertIn("openshift", SUPPORTED_PLATFORMS)

    def test_docker_adapter_constants(self):
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

    def test_docker_max_constants(self):
        from dcc.adapters.container import (
            MAX_RESPONSE_BYTES,
            MAX_CONTAINERS_PER_PAGE,
            MAX_PODS_PER_PAGE,
            MAX_NODES_PER_PAGE,
            MAX_ROWS,
            CONNECT_TIMEOUT,
            READ_TIMEOUT,
        )
        self.assertEqual(MAX_RESPONSE_BYTES, 2_000_000)
        self.assertEqual(MAX_CONTAINERS_PER_PAGE, 500)
        self.assertEqual(MAX_PODS_PER_PAGE, 500)
        self.assertEqual(MAX_NODES_PER_PAGE, 200)
        self.assertEqual(MAX_ROWS, 200)
        self.assertEqual(CONNECT_TIMEOUT, 8)
        self.assertEqual(READ_TIMEOUT, 15)

    def test_docker_default_endpoint_constant(self):
        from dcc.adapters.container import DEFAULT_CONTAINER_ENDPOINT
        self.assertEqual(
            DEFAULT_CONTAINER_ENDPOINT,
            "https://container-gateway.example.internal/api/v1",
        )

    def test_docker_protocols_constant(self):
        from dcc.adapters.container import PROTOCOLS
        self.assertEqual(PROTOCOLS, ["HTTPS/JSON"])


if __name__ == "__main__":
    unittest.main()
