"""Integration tests for KVM/libvirt hypervisor adapter.

Tests the hypervisor adapter's KVM/libvirt integration through the
vendor-neutral HTTPS API gateway, covering VM inventory, host inventory,
power metrics, capacity metrics, VM state, and health checks.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock


class TestKVMHypervisorIntegration(unittest.TestCase):
    """Integration tests for KVM/libvirt via the hypervisor adapter."""

    def test_probe_kvm_success(self):
        from dcc.adapters.hypervisor import probe
        mock_data = {
            "version": "1.0",
            "scopes": ["vm_inventory", "host_inventory"],
            "supported_hypervisors": ["kvm_libvirt"],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://hypervisor.example.com/api")
        self.assertTrue(result["probe_success"])
        self.assertEqual(result["adapter_id"], "hypervisor")

    def test_fetch_vm_inventory_kvm_success(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        mock_data = {
            "vms": [
                {
                    "vm_id": "kvm-vm-1",
                    "name": "KVM Web Server",
                    "power_state": "running",
                    "cpu_count": 4,
                    "memory_mb": 8192,
                    "host_id": "kvm-host-1",
                    "guest_os": "Ubuntu 22.04",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertEqual(len(result["vms"]), 1)
        self.assertEqual(result["vms"][0]["vm_id"], "kvm-vm-1")
        self.assertEqual(result["vms"][0]["hypervisor_type"], "kvm_libvirt")
        self.assertEqual(result["vms"][0]["power_state"], "running")

    def test_fetch_vm_inventory_kvm_with_power_state_filter(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        mock_data = {
            "vms": [
                {
                    "vm_id": "kvm-vm-2",
                    "name": "KVM DB Server",
                    "power_state": "running",
                    "cpu_count": 8,
                    "memory_mb": 16384,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                power_state="powered_on",
            )
        self.assertEqual(len(result["vms"]), 1)
        self.assertEqual(result["vms"][0]["vm_id"], "kvm-vm-2")

    def test_fetch_vm_inventory_kvm_with_host_filter(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        mock_data = {
            "vms": [
                {
                    "vm_id": "kvm-vm-3",
                    "name": "KVM App Server",
                    "power_state": "running",
                    "host_id": "kvm-host-2",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                host_id="kvm-host-2",
            )
        self.assertEqual(len(result["vms"]), 1)
        self.assertEqual(result["vms"][0]["host_id"], "kvm-host-2")

    def test_fetch_host_inventory_kvm_success(self):
        from dcc.adapters.hypervisor import fetch_host_inventory
        mock_data = {
            "hosts": [
                {
                    "host_id": "kvm-host-1",
                    "name": "KVM Host 1",
                    "total_cpu_cores": 64,
                    "total_memory_mb": 262144,
                    "libvirt_version": "8.0.0",
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_host_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertEqual(len(result["hosts"]), 1)
        self.assertEqual(result["hosts"][0]["host_id"], "kvm-host-1")
        self.assertEqual(result["hosts"][0]["libvirt_version"], "8.0.0")

    def test_fetch_power_metrics_kvm_success(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "kvm-m1",
                    "entity_type": "vm",
                    "entity_id": "kvm-vm-1",
                    "power_watts": 250.5,
                    "cpu_percent": 45.2,
                    "memory_percent": 60.0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "kvm-m1")
        self.assertEqual(result["metrics"][0]["power_watts"], "250.5")

    def test_fetch_power_metrics_kvm_with_vm_ids(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "kvm-m2",
                    "entity_type": "vm",
                    "entity_id": "kvm-vm-1",
                    "power_watts": 300.0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                vm_ids=["kvm-vm-1"],
            )
        self.assertEqual(len(result["metrics"]), 1)

    def test_fetch_capacity_metrics_kvm_success(self):
        from dcc.adapters.hypervisor import fetch_capacity_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "kvm-c1",
                    "entity_type": "host",
                    "entity_id": "kvm-host-1",
                    "cpu_total_cores": 64,
                    "cpu_used_cores": 32,
                    "cpu_percent": 50.0,
                    "memory_total_mb": 262144,
                    "memory_used_mb": 131072,
                    "memory_percent": 50.0,
                    "vm_count": 10,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["cpu_total_cores"], 64)
        self.assertEqual(result["metrics"][0]["vm_count"], 10)

    def test_fetch_vm_state_kvm_success(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        mock_data = {
            "states": [
                {
                    "vm_id": "kvm-vm-1",
                    "power_state": "running",
                    "uptime_seconds": 86400,
                    "guest_os": "Ubuntu 22.04",
                    "cpu_ready_percent": 2.5,
                    "memory_balloon_percent": 10.0,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_state(
                hypervisor_type="kvm_libvirt",
                vm_ids=["kvm-vm-1"],
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["vm_id"], "kvm-vm-1")
        self.assertEqual(result["states"][0]["uptime_seconds"], 86400)

    def test_health_check_kvm_success(self):
        from dcc.adapters.hypervisor import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_hypervisors": ["kvm_libvirt"]}
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://hypervisor.example.com/api")
        self.assertTrue(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "ok")
        self.assertEqual(result["checks"]["authentication"], "ok")
        self.assertEqual(result["checks"]["schema"], "ok")
        self.assertEqual(result["checks"]["freshness"], "ok")

    def test_health_check_kvm_stale_data(self):
        from dcc.adapters.hypervisor import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_hypervisors": ["kvm_libvirt"]}
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://hypervisor.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "stale")

    def test_health_check_kvm_no_data(self):
        from dcc.adapters.hypervisor import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_hypervisors": ["kvm_libvirt"]}
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://hypervisor.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "no_data")

    def test_kvm_rejects_invalid_power_state(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                power_state="invalid_state",
            )

    def test_kvm_rejects_invalid_vm_id(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                hypervisor_type="kvm_libvirt",
                vm_ids=["invalid vm id!"],
                endpoint="https://hypervisor.example.com/api",
            )

    def test_kvm_rejects_empty_vm_ids(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                hypervisor_type="kvm_libvirt",
                vm_ids=[],
                endpoint="https://hypervisor.example.com/api",
            )

    def test_kvm_rejects_too_many_vm_ids(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                hypervisor_type="kvm_libvirt",
                vm_ids=[f"vm-{i}" for i in range(101)],
                endpoint="https://hypervisor.example.com/api",
            )

    def test_kvm_rejects_http_endpoint(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://hypervisor.example.com/api")

    def test_kvm_rejects_invalid_since_timestamp(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                since="not-a-timestamp",
            )

    def test_kvm_rejects_too_many_vm_ids_for_power_metrics(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                vm_ids=[f"vm-{i}" for i in range(101)],
            )

    def test_kvm_vm_inventory_truncation(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-123")
        self.assertLessEqual(len(result["vms"]), 200)

    def test_kvm_host_inventory_truncation(self):
        from dcc.adapters.hypervisor import fetch_host_inventory
        mock_data = {
            "hosts": [{"host_id": f"host-{i}", "name": f"Host {i}"} for i in range(250)],
            "next_cursor": "cursor-456",
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_host_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-456")

    def test_kvm_power_metrics_truncation(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-789")

    def test_kvm_capacity_metrics_truncation(self):
        from dcc.adapters.hypervisor import fetch_capacity_metrics
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-abc")

    def test_kvm_vm_state_truncation(self):
        from dcc.adapters.hypervisor import fetch_vm_state
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

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_state(
                hypervisor_type="kvm_libvirt",
                vm_ids=[f"vm-{i}" for i in range(100)],
                endpoint="https://hypervisor.example.com/api",
            )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sync_cursor"], "cursor-def")

    def test_kvm_rejects_invalid_host_id(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                host_id="invalid host!",
            )

    def test_kvm_rejects_long_vm_id(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                hypervisor_type="kvm_libvirt",
                vm_ids=["x" * 121],
                endpoint="https://hypervisor.example.com/api",
            )

    def test_kvm_rejects_long_host_id(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(
                hypervisor_type="kvm_libvirt",
                endpoint="https://hypervisor.example.com/api",
                host_id="x" * 121,
            )

    def test_kvm_rejects_invalid_credential_ref(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ValueError):
            probe(
                endpoint="https://hypervisor.example.com/api",
                credential_ref="invalid\r\ncredential",
            )

    def test_kvm_rejects_long_credential_ref(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ValueError):
            probe(
                endpoint="https://hypervisor.example.com/api",
                credential_ref="x" * 257,
            )

    def test_kvm_rejects_long_endpoint(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https://example.com/" + "x" * 512)

    def test_kvm_rejects_empty_endpoint(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ConnectionError):
            probe(endpoint="")

    def test_kvm_rejects_endpoint_without_hostname(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https:///api")

    def test_kvm_connection_error_handling(self):
        from dcc.adapters.hypervisor import probe

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("Connection refused")

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://hypervisor.example.com/api")

    def test_kvm_invalid_json_handling(self):
        from dcc.adapters.hypervisor import probe

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"not json"

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://hypervisor.example.com/api")

    def test_kvm_non_dict_response_handling(self):
        from dcc.adapters.hypervisor import probe

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"[1, 2, 3]"

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://hypervisor.example.com/api")

    def test_kvm_missing_version_handling(self):
        from dcc.adapters.hypervisor import probe
        mock_data = {"scopes": [], "supported_hypervisors": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://hypervisor.example.com/api")

    def test_kvm_invalid_scopes_handling(self):
        from dcc.adapters.hypervisor import probe
        mock_data = {"version": "1.0", "scopes": "not-a-list", "supported_hypervisors": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://hypervisor.example.com/api")

    def test_kvm_invalid_supported_hypervisors_handling(self):
        from dcc.adapters.hypervisor import probe
        mock_data = {"version": "1.0", "scopes": [], "supported_hypervisors": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://hypervisor.example.com/api")

    def test_kvm_vm_inventory_invalid_contract(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        mock_data = {"vms": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_vm_inventory(
                    hypervisor_type="kvm_libvirt",
                    endpoint="https://hypervisor.example.com/api",
                )

    def test_kvm_host_inventory_invalid_contract(self):
        from dcc.adapters.hypervisor import fetch_host_inventory
        mock_data = {"hosts": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_host_inventory(
                    hypervisor_type="kvm_libvirt",
                    endpoint="https://hypervisor.example.com/api",
                )

    def test_kvm_power_metrics_invalid_contract(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        mock_data = {"metrics": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_power_metrics(
                    hypervisor_type="kvm_libvirt",
                    endpoint="https://hypervisor.example.com/api",
                )

    def test_kvm_capacity_metrics_invalid_contract(self):
        from dcc.adapters.hypervisor import fetch_capacity_metrics
        mock_data = {"metrics": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_capacity_metrics(
                    hypervisor_type="kvm_libvirt",
                    endpoint="https://hypervisor.example.com/api",
                )

    def test_kvm_vm_state_invalid_contract(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        mock_data = {"states": "not-a-list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_vm_state(
                    hypervisor_type="kvm_libvirt",
                    vm_ids=["vm-1"],
                    endpoint="https://hypervisor.example.com/api",
                )

    def test_kvm_health_check_connection_error(self):
        from dcc.adapters.hypervisor import health_check

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("Connection refused")

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://hypervisor.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "unavailable")

    def test_kvm_health_check_unexpected_error(self):
        from dcc.adapters.hypervisor import health_check

        class Opener:
            def open(self, request, timeout):
                raise RuntimeError("Unexpected error")

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://hypervisor.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertIn("error", result["details"])

    def test_kvm_supported_hypervisors_constant(self):
        from dcc.adapters.hypervisor import SUPPORTED_HYPERVISORS
        self.assertIn("kvm_libvirt", SUPPORTED_HYPERVISORS)
        self.assertIn("vmware_vcenter", SUPPORTED_HYPERVISORS)
        self.assertIn("hyperv", SUPPORTED_HYPERVISORS)

    def test_kvm_adapter_constants(self):
        from dcc.adapters.hypervisor import (
            ADAPTER_ID,
            ADAPTER_VERSION,
            VENDOR,
            CAPABILITIES,
            SCOPES,
            DATA_CLASSIFICATION,
        )
        self.assertEqual(ADAPTER_ID, "hypervisor")
        self.assertEqual(ADAPTER_VERSION, "0.1.0")
        self.assertEqual(VENDOR, "Multi-Hypervisor Gateway")
        self.assertIn("read_vm_inventory", CAPABILITIES)
        self.assertIn("vm_inventory", SCOPES)
        self.assertEqual(DATA_CLASSIFICATION, "operational_telemetry")

    def test_kvm_max_constants(self):
        from dcc.adapters.hypervisor import (
            MAX_RESPONSE_BYTES,
            MAX_VMS_PER_PAGE,
            MAX_HOSTS_PER_PAGE,
            MAX_ROWS,
            CONNECT_TIMEOUT,
            READ_TIMEOUT,
        )
        self.assertEqual(MAX_RESPONSE_BYTES, 2_000_000)
        self.assertEqual(MAX_VMS_PER_PAGE, 500)
        self.assertEqual(MAX_HOSTS_PER_PAGE, 200)
        self.assertEqual(MAX_ROWS, 200)
        self.assertEqual(CONNECT_TIMEOUT, 8)
        self.assertEqual(READ_TIMEOUT, 15)

    def test_kvm_default_endpoint_constant(self):
        from dcc.adapters.hypervisor import DEFAULT_HYPERVISOR_ENDPOINT
        self.assertEqual(
            DEFAULT_HYPERVISOR_ENDPOINT,
            "https://hypervisor-gateway.example.internal/api/v1",
        )

    def test_kvm_protocols_constant(self):
        from dcc.adapters.hypervisor import PROTOCOLS
        self.assertEqual(PROTOCOLS, ["HTTPS/JSON"])


if __name__ == "__main__":
    unittest.main()
