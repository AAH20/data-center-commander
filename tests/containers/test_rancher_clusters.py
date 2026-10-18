"""Integration tests for Rancher cluster inventory and state.

Tests the Rancher adapter's cluster integration through the vendor-neutral
HTTPS API gateway, covering cluster inventory, cluster state, and health checks.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestRancherClusterIntegration(unittest.TestCase):
    """Integration tests for Rancher clusters via the Rancher adapter."""

    def test_fetch_cluster_inventory_success(self):
        from dcc.containers.rancher.clusters import fetch_cluster_inventory
        mock_data = {
            "clusters": [
                {
                    "cluster_id": "c-abc123",
                    "name": "Production Cluster",
                    "status": "active",
                    "provider": "aws",
                    "version": "v1.28.0",
                    "node_count": 5,
                    "cpu_total_cores": 40,
                    "memory_total_mb": 163840,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=Opener()):
            result = fetch_cluster_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
            )
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(result["clusters"][0]["cluster_id"], "c-abc123")
        self.assertEqual(result["clusters"][0]["platform"], "rancher")
        self.assertEqual(result["clusters"][0]["status"], "active")

    def test_fetch_cluster_inventory_with_filter(self):
        from dcc.containers.rancher.clusters import fetch_cluster_inventory
        mock_data = {
            "clusters": [
                {
                    "cluster_id": "c-filtered",
                    "name": "Filtered Cluster",
                    "status": "active",
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=Opener()):
            result = fetch_cluster_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                cluster_id="c-filtered",
            )
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(result["clusters"][0]["cluster_id"], "c-filtered")

    def test_fetch_cluster_state_success(self):
        from dcc.containers.rancher.clusters import fetch_cluster_state
        mock_data = {
            "states": [
                {
                    "cluster_id": "c-abc123",
                    "status": "active",
                    "phase": "running",
                    "message": "Cluster is ready",
                    "node_count": 5,
                }
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=Opener()):
            result = fetch_cluster_state(
                platform="rancher",
                cluster_ids=["c-abc123"],
                endpoint="https://rancher.example.com/api",
            )
        self.assertEqual(len(result["states"]), 1)
        self.assertEqual(result["states"][0]["cluster_id"], "c-abc123")
        self.assertEqual(result["states"][0]["phase"], "running")

    def test_fetch_cluster_state_requires_ids(self):
        from dcc.containers.rancher.clusters import fetch_cluster_state
        with self.assertRaises(ValueError):
            fetch_cluster_state(
                platform="rancher",
                cluster_ids=[],
                endpoint="https://rancher.example.com/api",
            )

    def test_fetch_cluster_state_rejects_too_many_ids(self):
        from dcc.containers.rancher.clusters import fetch_cluster_state
        with self.assertRaises(ValueError):
            fetch_cluster_state(
                platform="rancher",
                cluster_ids=[f"c-{i}" for i in range(101)],
                endpoint="https://rancher.example.com/api",
            )


if __name__ == "__main__":
    unittest.main()
