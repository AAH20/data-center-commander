"""Integration tests for Proxmox VE adapter.

Tests the Proxmox adapter's integration through the vendor-neutral HTTPS API
gateway, covering VM inventory, node inventory, power metrics, capacity
metrics, VM state, and health checks.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestProxmoxAdapterIntegration(unittest.TestCase):
    """Integration tests for Proxmox VE via the Proxmox adapter."""

    def test_probe_proxmox_success(self):
        from dcc.adapters.proxmox import probe
        mock_data = {
            "version": "1.0",
            "scopes": ["vm_inventory", "node_inventory"],
            "supported_platforms": ["proxmox_ve"],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://proxmox.example.com/api")
        self.assertTrue(result["probe_success"])
        self.assertEqual(result["adapter_id"], "proxmox")

    def test_probe_proxmox_rejects_http(self):
        from dcc.adapters.proxmox import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://proxmox.example.com/api")

    def test_fetch_vm_inventory_proxmox_success(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        mock_data = {
            "vms": [
                {
                    "vm_id": "proxmox-vm-1",
                    "name": "Proxmox Web Server",
                    "vm_type": "qemu",
                    "status": "running",
                    "cpu_count": 4,
                    "memory_mb": 8192,
                    "node_id": "proxmox-node-1",
                    "disk_gb": 100,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertEqual(len(result["vms"]), 1)
        self.assertEqual(result["vms"][0]["vm_id"], "proxmox-vm-1")
        self.assertEqual(result["vms"][0]["platform"], "proxmox_ve")
        self.assertEqual(result["vms"][0]["vm_type"], "qemu")

    def test_fetch_vm_inventory_proxmox_lxc(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        mock_data = {
            "vms": [
                {
                    "vm_id": "proxmox-vm-2",
                    "name": "Proxmox Container",
                    "vm_type": "lxc",
                    "status": "running",
                    "cpu_count": 2,
                    "memory_mb": 4096,
                    "node_id": "proxmox-node-1",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                vm_type="lxc",
            )
        self.assertEqual(len(result["vms"]), 1)
        self.assertEqual(result["vms"][0]["vm_type"], "lxc")

    def test_fetch_vm_inventory_proxmox_with_node_filter(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        mock_data = {
            "vms": [
                {
                    "vm_id": "proxmox-vm-3",
                    "name": "Proxmox App Server",
                    "vm_type": "qemu",
                    "status": "running",
                    "node_id": "proxmox-node-2",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                node_id="proxmox-node-2",
            )
        self.assertEqual(len(result["vms"]), 1)
        self.assertEqual(result["vms"][0]["node_id"], "proxmox-node-2")

    def test_fetch_node_inventory_proxmox_success(self):
        from dcc.adapters.proxmox import fetch_node_inventory
        mock_data = {
            "nodes": [
                {
                    "node_id": "proxmox-node-1",
                    "name": "Proxmox Node 1",
                    "total_cpu_cores": 64,
                    "total_memory_mb": 262144,
                    "proxmox_version": "8.1",
                    "status": "online",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_node_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["node_id"], "proxmox-node-1")
        self.assertEqual(result["nodes"][0]["proxmox_version"], "8.1")

    def test_fetch_power_metrics_proxmox_success(self):
        from dcc.adapters.proxmox import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "proxmox-m1",
                    "entity_type": "vm",
                    "entity_id": "proxmox-vm-1",
                    "power_watts": 280.5,
                    "cpu_percent": 50.2,
                    "memory_percent": 62.0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "proxmox-m1")
        self.assertEqual(result["metrics"][0]["power_watts"], "280.5")

    def test_fetch_power_metrics_proxmox_with_vm_ids(self):
        from dcc.adapters.proxmox import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "proxmox-m2",
                    "entity_type": "vm",
                    "entity_id": "proxmox-vm-1",
                    "power_watts": 310.0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                vm_ids=["proxmox-vm-1"],
            )
        self.assertEqual(len(result["metrics"]), 1)

    def test_fetch_capacity_metrics_proxmox_success(self):
        from dcc.adapters.proxmox import fetch_capacity_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "proxmox-c1",
                    "entity_type": "node",
                    "entity_id": "proxmox-node-1",
                    "cpu_total_cores": 64,
                    "cpu_used_cores": 38,
                    "cpu_percent": 59.4,
                    "memory_total_mb": 262144,
                    "memory_used_mb": 157286,
                    "memory_percent": 60.0,
                    "vm_count": 14,
                    "container_count": 8,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["cpu_total_cores"], 64)
        self.assertEqual(result["metrics"][0]["vm_count"], 14)
        self.assertEqual(result["metrics"][0]["container_count"], 8)

    def test_fetch_vm_state_proxmox_success(self):
        from dcc.adapters.proxmox import fetch_vm_state
        mock_data = {
            "states": [
                {
                    "vm_id": "proxmox-vm-1",
                    "status": "running",
                    "uptime_seconds": 345600,
                    "vm_type": "qemu",
                    "cpu_ready_percent": 2.0,
                    "memory_balloon_percent": 7.5,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_state(
                platform="proxmox_ve",
                vm_ids=["proxmox-vm-1"],
                endpoint="https://proxmox.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["vm_id"], "proxmox-vm-1")
        self.assertEqual(result["states"][0]["uptime_seconds"], 345600)

    def test_health_check_proxmox_success(self):
        from dcc.adapters.proxmox import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["proxmox_ve"]}
        mock_vms = {"vms": [{"observed_at": "2026-01-01T00:00:00Z"}]}

        class InfoResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_info).encode()

        class VmsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_vms).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return InfoResponse()
                return VmsResponse()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://proxmox.example.com/api")
        self.assertTrue(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "ok")
        self.assertEqual(result["checks"]["authentication"], "ok")
        self.assertEqual(result["checks"]["schema"], "ok")
        self.assertEqual(result["checks"]["freshness"], "ok")

    def test_health_check_proxmox_stale_data(self):
        from dcc.adapters.proxmox import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["proxmox_ve"]}
        mock_vms = {"vms": [{"observed_at": None}]}

        class InfoResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_info).encode()

        class VmsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_vms).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return InfoResponse()
                return VmsResponse()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://proxmox.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "stale")

    def test_health_check_proxmox_no_data(self):
        from dcc.adapters.proxmox import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_platforms": ["proxmox_ve"]}
        mock_vms = {"vms": []}

        class InfoResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_info).encode()

        class VmsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_vms).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return InfoResponse()
                return VmsResponse()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://proxmox.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "no_data")

    def test_proxmox_rejects_invalid_platform(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                platform="invalid_platform",
                endpoint="https://proxmox.example.com/api",
            )

    def test_proxmox_rejects_invalid_vm_type(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                vm_type="invalid_type",
            )

    def test_proxmox_rejects_invalid_vm_id(self):
        from dcc.adapters.proxmox import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                platform="proxmox_ve",
                vm_ids=["invalid vm id!"],
                endpoint="https://proxmox.example.com/api",
            )

    def test_proxmox_rejects_empty_vm_ids(self):
        from dcc.adapters.proxmox import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                platform="proxmox_ve",
                vm_ids=[],
                endpoint="https://proxmox.example.com/api",
            )

    def test_proxmox_rejects_too_many_vm_ids(self):
        from dcc.adapters.proxmox import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                platform="proxmox_ve",
                vm_ids=[f"vm-{i}" for i in range(101)],
                endpoint="https://proxmox.example.com/api",
            )

    def test_proxmox_rejects_invalid_since_timestamp(self):
        from dcc.adapters.proxmox import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                since="not-a-timestamp",
            )

    def test_proxmox_rejects_too_many_vm_ids_for_power_metrics(self):
        from dcc.adapters.proxmox import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                vm_ids=[f"vm-{i}" for i in range(101)],
            )

    def test_proxmox_vm_inventory_truncation(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        mock_data = {
            "vms": [{"vm_id": f"vm-{i}", "name": f"VM {i}"} for i in range(250)],
            "next_cursor": "cursor-123",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-123")
        self.assertLessEqual(len(result["vms"]), 200)

    def test_proxmox_node_inventory_truncation(self):
        from dcc.adapters.proxmox import fetch_node_inventory
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

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_node_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-456")

    def test_proxmox_power_metrics_truncation(self):
        from dcc.adapters.proxmox import fetch_power_metrics
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

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-789")

    def test_proxmox_capacity_metrics_truncation(self):
        from dcc.adapters.proxmox import fetch_capacity_metrics
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

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-abc")

    def test_proxmox_vm_state_truncation(self):
        from dcc.adapters.proxmox import fetch_vm_state
        mock_data = {
            "states": [{"vm_id": f"vm-{i}"} for i in range(250)],
            "next_cursor": "cursor-def",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_state(
                platform="proxmox_ve",
                vm_ids=[f"vm-{i}" for i in range(100)],
                endpoint="https://proxmox.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-def")

    def test_proxmox_rejects_invalid_node_id(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                node_id="invalid node!",
            )

    def test_proxmox_rejects_long_vm_id(self):
        from dcc.adapters.proxmox import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                platform="proxmox_ve",
                vm_ids=["x" * 121],
                endpoint="https://proxmox.example.com/api",
            )

    def test_proxmox_rejects_long_node_id(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                platform="proxmox_ve",
                endpoint="https://proxmox.example.com/api",
                node_id="x" * 121,
            )

    def test_proxmox_rejects_invalid_credential_ref(self):
        from dcc.adapters.proxmox import probe
        with self.assertRaises(ValueError):
            probe(
                endpoint="https://proxmox.example.com/api",
                credential_ref="invalid\r\ncredential",
            )

    def test_proxmox_rejects_long_credential_ref(self):
        from dcc.adapters.proxmox import probe
        with self.assertRaises(ValueError):
            probe(
                endpoint="https://proxmox.example.com/api",
                credential_ref="x" * 257,
            )

    def test_proxmox_rejects_long_endpoint(self):
        from dcc.adapters.proxmox import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https://example.com/" + "x" * 512)

    def test_proxmox_rejects_empty_endpoint(self):
        from dcc.adapters.proxmox import probe
        with self.assertRaises(ConnectionError):
            probe(endpoint="")

    def test_proxmox_rejects_endpoint_without_hostname(self):
        from dcc.adapters.proxmox import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https:///api")

    def test_proxmox_connection_error_handling(self):
        from dcc.adapters.proxmox import probe

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("Connection refused")

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://proxmox.example.com/api")

    def test_proxmox_invalid_json_handling(self):
        from dcc.adapters.proxmox import probe

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"not json"

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://proxmox.example.com/api")

    def test_proxmox_non_dict_response_handling(self):
        from dcc.adapters.proxmox import probe

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"[1, 2, 3]"

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://proxmox.example.com/api")

    def test_proxmox_missing_version_handling(self):
        from dcc.adapters.proxmox import probe
        mock_data = {"scopes": [], "supported_platforms": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://proxmox.example.com/api")

    def test_proxmox_invalid_scopes_handling(self):
        from dcc.adapters.proxmox import probe
        mock_data = {"version": "1.0", "scopes": "not-a-list", "supported_platforms": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://proxmox.example.com/api")

    def test_proxmox_invalid_supported_platforms_handling(self):
        from dcc.adapters.proxmox import probe
        mock_data = {"version": "1.0", "scopes": [], "supported_platforms": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://proxmox.example.com/api")

    def test_proxmox_vm_inventory_invalid_contract(self):
        from dcc.adapters.proxmox import fetch_vm_inventory
        mock_data = {"vms": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_vm_inventory(
                    platform="proxmox_ve",
                    endpoint="https://proxmox.example.com/api",
                )

    def test_proxmox_node_inventory_invalid_contract(self):
        from dcc.adapters.proxmox import fetch_node_inventory
        mock_data = {"nodes": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_node_inventory(
                    platform="proxmox_ve",
                    endpoint="https://proxmox.example.com/api",
                )

    def test_proxmox_power_metrics_invalid_contract(self):
        from dcc.adapters.proxmox import fetch_power_metrics
        mock_data = {"metrics": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_power_metrics(
                    platform="proxmox_ve",
                    endpoint="https://proxmox.example.com/api",
                )

    def test_proxmox_capacity_metrics_invalid_contract(self):
        from dcc.adapters.proxmox import fetch_capacity_metrics
        mock_data = {"metrics": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_capacity_metrics(
                    platform="proxmox_ve",
                    endpoint="https://proxmox.example.com/api",
                )

    def test_proxmox_vm_state_invalid_contract(self):
        from dcc.adapters.proxmox import fetch_vm_state
        mock_data = {"states": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_vm_state(
                    platform="proxmox_ve",
                    vm_ids=["vm-1"],
                    endpoint="https://proxmox.example.com/api",
                )

    def test_proxmox_health_check_connection_error(self):
        from dcc.adapters.proxmox import health_check

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("Connection refused")

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://proxmox.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "unavailable")

    def test_proxmox_health_check_unexpected_error(self):
        from dcc.adapters.proxmox import health_check

        class Opener:
            def open(self, request, timeout):
                raise RuntimeError("Unexpected error")

        with patch("dcc.adapters.proxmox.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://proxmox.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertIn("error", result["details"])

    def test_proxmox_supported_platforms_constant(self):
        from dcc.adapters.proxmox import SUPPORTED_PLATFORMS
        self.assertIn("proxmox_ve", SUPPORTED_PLATFORMS)

    def test_proxmox_adapter_constants(self):
        from dcc.adapters.proxmox import (
            ADAPTER_ID,
            ADAPTER_VERSION,
            VENDOR,
            CAPABILITIES,
            SCOPES,
            DATA_CLASSIFICATION,
        )
        self.assertEqual(ADAPTER_ID, "proxmox")
        self.assertEqual(ADAPTER_VERSION, "0.1.0")
        self.assertEqual(VENDOR, "Proxmox VE Gateway")
        self.assertIn("read_vm_inventory", CAPABILITIES)
        self.assertIn("vm_inventory", SCOPES)
        self.assertEqual(DATA_CLASSIFICATION, "operational_telemetry")

    def test_proxmox_max_constants(self):
        from dcc.adapters.proxmox import (
            MAX_RESPONSE_BYTES,
            MAX_VMS_PER_PAGE,
            MAX_NODES_PER_PAGE,
            MAX_ROWS,
            CONNECT_TIMEOUT,
            READ_TIMEOUT,
        )
        self.assertEqual(MAX_RESPONSE_BYTES, 2_000_000)
        self.assertEqual(MAX_VMS_PER_PAGE, 500)
        self.assertEqual(MAX_NODES_PER_PAGE, 200)
        self.assertEqual(MAX_ROWS, 200)
        self.assertEqual(CONNECT_TIMEOUT, 8)
        self.assertEqual(READ_TIMEOUT, 15)

    def test_proxmox_default_endpoint_constant(self):
        from dcc.adapters.proxmox import DEFAULT_PROXMOX_ENDPOINT
        self.assertEqual(
            DEFAULT_PROXMOX_ENDPOINT,
            "https://proxmox-gateway.example.internal/api/v1",
        )

    def test_proxmox_protocols_constant(self):
        from dcc.adapters.proxmox import PROTOCOLS
        self.assertEqual(PROTOCOLS, ["HTTPS/JSON"])


if __name__ == "__main__":
    unittest.main()
