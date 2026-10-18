"""Integration tests for Rancher monitoring metrics.

Tests the Rancher adapter's monitoring integration through the vendor-neutral
HTTPS API gateway.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestRancherMonitoringIntegration(unittest.TestCase):
    """Integration tests for Rancher monitoring via the Rancher adapter."""

    def test_fetch_monitoring_metrics_success(self):
        from dcc.containers.rancher.monitoring import fetch_monitoring_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "metric-1",
                    "entity_type": "cluster",
                    "entity_id": "c-abc123",
                    "cpu_usage_percent": 45.5,
                    "memory_usage_percent": 60.2,
                    "cpu_usage_cores": 18.2,
                    "memory_usage_mb": 98765.0,
                    "network_rx_mbps": 100.5,
                    "network_tx_mbps": 50.2,
                    "disk_usage_percent": 35.0,
                    "pod_count": 25,
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
            result = fetch_monitoring_metrics(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "metric-1")
        self.assertEqual(result["metrics"][0]["platform"], "rancher")
        self.assertEqual(result["metrics"][0]["entity_type"], "cluster")

    def test_fetch_monitoring_metrics_with_cluster_filter(self):
        from dcc.containers.rancher.monitoring import fetch_monitoring_metrics
        mock_data = {
            "metrics": [
                {
                    "metric_id": "metric-filtered",
                    "entity_type": "cluster",
                    "entity_id": "c-filtered",
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
            result = fetch_monitoring_metrics(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                cluster_id="c-filtered",
            )
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["metric_id"], "metric-filtered")

    def test_fetch_monitoring_metrics_with_since(self):
        from dcc.containers.rancher.monitoring import fetch_monitoring_metrics
        mock_data = {"metrics": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=Opener()):
            result = fetch_monitoring_metrics(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                since="2026-09-01T00:00:00Z",
            )
        self.assertEqual(len(result["metrics"]), 0)

    def test_fetch_monitoring_metrics_rejects_invalid_since(self):
        from dcc.containers.rancher.monitoring import fetch_monitoring_metrics
        with self.assertRaises(ValueError):
            fetch_monitoring_metrics(
                platform="rancher",
                endpoint="https://rancher.example.com/api",
                since="invalid-date",
            )


if __name__ == "__main__":
    unittest.main()
