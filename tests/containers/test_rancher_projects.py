"""Integration tests for Rancher project inventory.

Tests the Rancher adapter's project integration through the vendor-neutral
HTTPS API gateway.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestRancherProjectIntegration(unittest.TestCase):
    """Integration tests for Rancher projects via the Rancher adapter."""

    def test_fetch_project_inventory_success(self):
        from dcc.containers.rancher.projects import fetch_project_inventory
        mock_data = {
            "projects": [
                {
                    "project_id": "p-abc123",
                    "name": "Production Project",
                    "cluster_id": "c-abc123",
                    "namespace_count": 10,
                    "workload_count": 25,
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
            result = fetch_project_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
            )
        self.assertEqual(len(result["projects"]), 1)
        self.assertEqual(result["projects"][0]["project_id"], "p-abc123")
        self.assertEqual(result["projects"][0]["platform"], "rancher")
        self.assertEqual(result["projects"][0]["cluster_id"], "c-abc123")

    def test_fetch_project_inventory_with_cluster_filter(self):
        from dcc.containers.rancher.projects import fetch_project_inventory
        mock_data = {
            "projects": [
                {
                    "project_id": "p-filtered",
                    "name": "Filtered Project",
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
            result = fetch_project_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                cluster_id="c-filtered",
            )
        self.assertEqual(len(result["projects"]), 1)
        self.assertEqual(result["projects"][0]["project_id"], "p-filtered")


if __name__ == "__main__":
    unittest.main()
