"""Integration tests for Rancher namespace inventory.

Tests the Rancher adapter's namespace integration through the vendor-neutral
HTTPS API gateway.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestRancherNamespaceIntegration(unittest.TestCase):
    """Integration tests for Rancher namespaces via the Rancher adapter."""

    def test_fetch_namespace_inventory_success(self):
        from dcc.containers.rancher.namespaces import fetch_namespace_inventory
        mock_data = {
            "namespaces": [
                {
                    "namespace_id": "ns-abc123",
                    "name": "default",
                    "project_id": "p-abc123",
                    "cluster_id": "c-abc123",
                    "status": "active",
                    "workload_count": 5,
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
            result = fetch_namespace_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
            )
        self.assertEqual(len(result["namespaces"]), 1)
        self.assertEqual(result["namespaces"][0]["namespace_id"], "ns-abc123")
        self.assertEqual(result["namespaces"][0]["platform"], "rancher")
        self.assertEqual(result["namespaces"][0]["project_id"], "p-abc123")

    def test_fetch_namespace_inventory_with_project_filter(self):
        from dcc.containers.rancher.namespaces import fetch_namespace_inventory
        mock_data = {
            "namespaces": [
                {
                    "namespace_id": "ns-filtered",
                    "name": "filtered-ns",
                    "project_id": "p-filtered",
                    "cluster_id": "c-filtered",
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
            result = fetch_namespace_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                project_id="p-filtered",
            )
        self.assertEqual(len(result["namespaces"]), 1)
        self.assertEqual(result["namespaces"][0]["namespace_id"], "ns-filtered")


if __name__ == "__main__":
    unittest.main()
