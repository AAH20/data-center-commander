"""Integration tests for Rancher catalog inventory.

Tests the Rancher adapter's catalog integration through the vendor-neutral
HTTPS API gateway.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestRancherCatalogIntegration(unittest.TestCase):
    """Integration tests for Rancher catalogs via the Rancher adapter."""

    def test_fetch_catalog_inventory_success(self):
        from dcc.containers.rancher.catalogs import fetch_catalog_inventory
        mock_data = {
            "catalogs": [
                {
                    "catalog_id": "cat-abc123",
                    "name": "Helm Library",
                    "url": "https://charts.example.com",
                    "scope": "global",
                    "branch": "main",
                    "commit": "abc123",
                    "version": "1.0.0",
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
            result = fetch_catalog_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
            )
        self.assertEqual(len(result["catalogs"]), 1)
        self.assertEqual(result["catalogs"][0]["catalog_id"], "cat-abc123")
        self.assertEqual(result["catalogs"][0]["platform"], "rancher")
        self.assertEqual(result["catalogs"][0]["url"], "https://charts.example.com")

    def test_fetch_catalog_inventory_with_cluster_filter(self):
        from dcc.containers.rancher.catalogs import fetch_catalog_inventory
        mock_data = {
            "catalogs": [
                {
                    "catalog_id": "cat-filtered",
                    "name": "Filtered Catalog",
                    "url": "https://filtered.example.com",
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
            result = fetch_catalog_inventory(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                cluster_id="c-filtered",
            )
        self.assertEqual(len(result["catalogs"]), 1)
        self.assertEqual(result["catalogs"][0]["catalog_id"], "cat-filtered")


if __name__ == "__main__":
    unittest.main()
