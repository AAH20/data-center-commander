"""Tests for the Rancher adapter."""
import json
import unittest
from unittest.mock import patch, MagicMock

from dcc.containers.rancher.adapter import (
    RancherConfig,
    RancherAdapter,
    create_rancher_adapter,
    _validate_cluster_id,
    _validate_project_id,
    _validate_namespace_id,
    _validate_catalog_id,
    _validate_platform,
    _parse_timestamp,
    _safe_int,
    _safe_float,
    MAX_CLUSTERS_PER_PAGE,
    MAX_PROJECTS_PER_PAGE,
    MAX_NAMESPACES_PER_PAGE,
    MAX_CATALOGS_PER_PAGE,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return json.dumps(self.payload).encode()


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        if not self.responses:
            raise RuntimeError("no more fake responses")
        return FakeResponse(self.responses.pop(0))


class RancherFactoryTests(unittest.TestCase):
    def test_create_adapter_with_valid_config(self):
        adapter = create_rancher_adapter(
            endpoint="https://rancher.example.com/api",
            api_version="v1",
            vendor="Rancher",
            product="Rancher",
        )
        self.assertEqual(adapter.config.endpoint, "https://rancher.example.com/api")
        self.assertEqual(adapter.config.api_version, "v1")
        self.assertEqual(adapter.config.vendor, "Rancher")
        self.assertEqual(adapter.config.product, "Rancher")

    def test_rejects_non_https_endpoint(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            create_rancher_adapter(endpoint="http://rancher.example.com")

    def test_rejects_invalid_api_version(self):
        with self.assertRaisesRegex(ValueError, "api_version"):
            create_rancher_adapter(
                endpoint="https://rancher.example.com",
                api_version="v1; DROP TABLE",
            )

    def test_rejects_invalid_rate_limit(self):
        with self.assertRaisesRegex(ValueError, "rate_limit"):
            create_rancher_adapter(
                endpoint="https://rancher.example.com",
                rate_limit_per_minute=0,
            )

    def test_rejects_invalid_timeout(self):
        with self.assertRaisesRegex(ValueError, "timeout"):
            create_rancher_adapter(
                endpoint="https://rancher.example.com",
                timeout_s=0.1,
            )

    def test_rejects_long_endpoint(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            create_rancher_adapter(endpoint="https://example.com/" + "a" * 3000)


class RancherValidationTests(unittest.TestCase):
    def test_validate_platform_accepts_valid(self):
        self.assertEqual(_validate_platform("rancher"), "rancher")
        self.assertEqual(_validate_platform("Rancher"), "rancher")
        self.assertEqual(_validate_platform("  rancher  "), "rancher")

    def test_validate_platform_rejects_invalid(self):
        for bad in ("", "docker", "kubernetes", "openshift"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_platform(bad)

    def test_validate_cluster_id_accepts_valid(self):
        self.assertEqual(_validate_cluster_id("c-abc123"), "c-abc123")
        self.assertEqual(_validate_cluster_id("cluster-1"), "cluster-1")

    def test_validate_cluster_id_rejects_invalid(self):
        for bad in ("", "a" * 121, "cluster id", "cluster;id", "cluster'id"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_cluster_id(bad)

    def test_validate_project_id_accepts_valid(self):
        self.assertEqual(_validate_project_id("p-abc123"), "p-abc123")
        self.assertEqual(_validate_project_id("project-1"), "project-1")

    def test_validate_project_id_rejects_invalid(self):
        for bad in ("", "a" * 121, "project id", "project;id"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_project_id(bad)

    def test_validate_namespace_id_accepts_valid(self):
        self.assertEqual(_validate_namespace_id("ns-abc123"), "ns-abc123")
        self.assertEqual(_validate_namespace_id("default"), "default")

    def test_validate_namespace_id_rejects_invalid(self):
        for bad in ("", "a" * 121, "namespace id", "namespace;id"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_namespace_id(bad)

    def test_validate_catalog_id_accepts_valid(self):
        self.assertEqual(_validate_catalog_id("cat-abc123"), "cat-abc123")
        self.assertEqual(_validate_catalog_id("library"), "library")

    def test_validate_catalog_id_rejects_invalid(self):
        for bad in ("", "a" * 121, "catalog id", "catalog;id"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_catalog_id(bad)

    def test_parse_timestamp_accepts_valid(self):
        self.assertEqual(
            _parse_timestamp("2026-09-29T10:00:00Z"),
            "2026-09-29T10:00:00Z",
        )
        self.assertEqual(
            _parse_timestamp("2026-09-29T10:00:00+03:00"),
            "2026-09-29T10:00:00+03:00",
        )

    def test_parse_timestamp_rejects_invalid(self):
        for bad in ("", "yesterday", "2026-13-01", "not-a-date", None, 123):
            with self.subTest(bad=bad):
                self.assertIsNone(_parse_timestamp(bad))

    def test_safe_int(self):
        self.assertEqual(_safe_int(42), 42)
        self.assertEqual(_safe_int("42"), 42)
        self.assertIsNone(_safe_int(None))
        self.assertIsNone(_safe_int("abc"))

    def test_safe_float(self):
        self.assertEqual(_safe_float(42), 42.0)
        self.assertEqual(_safe_float("3.14"), 3.14)
        self.assertIsNone(_safe_float(None))
        self.assertIsNone(_safe_float("abc"))
        self.assertIsNone(_safe_float(float("nan")))
        self.assertIsNone(_safe_float(float("inf")))


class RancherAdapterHealthTests(unittest.TestCase):
    def test_health_check_success(self):
        opener = FakeOpener([
            {"version": "2.8.0", "scopes": ["cluster_inventory"], "supported_platforms": ["rancher"]},
            {"clusters": [{"cluster_id": "c-1", "observed_at": "2026-09-29T10:00:00Z"}]},
        ])
        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=opener):
            adapter = create_rancher_adapter(endpoint="https://rancher.example.com/api")
            self.assertTrue(adapter.health_check())
        self.assertEqual(len(opener.calls), 2)

    def test_health_check_failure(self):
        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            adapter = create_rancher_adapter(endpoint="https://rancher.example.com/api")
            self.assertFalse(adapter.health_check())


class RancherAdapterSupportsTests(unittest.TestCase):
    def test_supports_known_capabilities(self):
        adapter = create_rancher_adapter(endpoint="https://rancher.example.com/api")
        self.assertTrue(adapter.supports("read_cluster_inventory"))
        self.assertTrue(adapter.supports("read_project_inventory"))
        self.assertTrue(adapter.supports("read_namespace_inventory"))
        self.assertTrue(adapter.supports("read_catalog_inventory"))
        self.assertTrue(adapter.supports("read_monitoring_metrics"))
        self.assertTrue(adapter.supports("read_cluster_state"))

    def test_rejects_unknown_capability(self):
        adapter = create_rancher_adapter(endpoint="https://rancher.example.com/api")
        self.assertFalse(adapter.supports("unknown_capability"))
        self.assertFalse(adapter.supports("write_cluster"))


class RancherProbeTests(unittest.TestCase):
    def test_probe_success(self):
        from dcc.containers.rancher.adapter import probe
        mock_data = {
            "version": "2.8.0",
            "scopes": ["cluster_inventory", "project_inventory"],
            "supported_platforms": ["rancher"],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://rancher.example.com/api")
        self.assertTrue(result["probe_success"])
        self.assertEqual(result["adapter_id"], "rancher")
        self.assertEqual(result["server_version"], "2.8.0")

    def test_probe_rejects_http(self):
        from dcc.containers.rancher.adapter import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://rancher.example.com/api")


class RancherHealthCheckTests(unittest.TestCase):
    def test_health_check_success(self):
        from dcc.containers.rancher.adapter import health_check
        info_data = {
            "version": "2.8.0",
            "scopes": ["cluster_inventory"],
            "supported_platforms": ["rancher"],
        }
        clusters_data = {
            "clusters": [{"cluster_id": "c-1", "observed_at": "2026-09-29T10:00:00Z"}]
        }

        class Response:
            def __init__(self, payload):
                self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(self.payload).encode()

        class Opener:
            def __init__(self):
                self.responses = [Response(info_data), Response(clusters_data)]
            def open(self, request, timeout): return self.responses.pop(0)

        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://rancher.example.com/api")
        self.assertTrue(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "ok")
        self.assertEqual(result["checks"]["authentication"], "ok")
        self.assertEqual(result["checks"]["schema"], "ok")
        self.assertEqual(result["checks"]["freshness"], "ok")

    def test_health_check_connection_error(self):
        from dcc.containers.rancher.adapter import health_check
        with patch("dcc.containers.rancher.adapter.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            result = health_check(endpoint="https://rancher.example.com/api")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "unavailable")


if __name__ == "__main__":
    unittest.main()
