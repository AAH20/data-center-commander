"""Tests for the OpenShift adapter."""
import json
import unittest
from unittest.mock import patch, MagicMock

from dcc.containers.openshift.adapter import (
    OpenShiftAdapter,
    OpenShiftConfig,
    create_openshift_adapter,
    _validate_platform,
    _validate_project_name,
    _validate_resource_name,
    _validate_scc_name,
    _parse_timestamp,
    _safe_decimal,
    _safe_int,
    _resolve_endpoint,
    _resolve_credential,
    MAX_PROJECTS_PER_PAGE,
    MAX_DEPLOYMENTS_PER_PAGE,
    MAX_ROUTES_PER_PAGE,
    MAX_BUILDS_PER_PAGE,
    MAX_TEMPLATES_PER_PAGE,
    MAX_SCCS_PER_PAGE,
    MAX_ROWS,
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


class OpenShiftFactoryTests(unittest.TestCase):
    def test_create_adapter_with_valid_config(self):
        adapter = create_openshift_adapter(
            endpoint="https://openshift.example.com/api",
            api_version="v1",
            vendor="OpenShift",
            product="OpenShift Container Platform",
        )
        self.assertEqual(adapter.config.endpoint, "https://openshift.example.com/api")
        self.assertEqual(adapter.config.api_version, "v1")
        self.assertEqual(adapter.config.vendor, "OpenShift")
        self.assertEqual(adapter.config.product, "OpenShift Container Platform")

    def test_rejects_non_https_endpoint(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            create_openshift_adapter(endpoint="http://openshift.example.com")

    def test_rejects_invalid_api_version(self):
        with self.assertRaisesRegex(ValueError, "api_version"):
            create_openshift_adapter(
                endpoint="https://openshift.example.com",
                api_version="v1; DROP TABLE",
            )

    def test_rejects_invalid_rate_limit(self):
        with self.assertRaisesRegex(ValueError, "rate_limit"):
            create_openshift_adapter(
                endpoint="https://openshift.example.com",
                rate_limit_per_minute=0,
            )

    def test_rejects_invalid_timeout(self):
        with self.assertRaisesRegex(ValueError, "timeout"):
            create_openshift_adapter(
                endpoint="https://openshift.example.com",
                timeout_s=0.1,
            )

    def test_rejects_long_endpoint(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            create_openshift_adapter(endpoint="https://example.com/" + "a" * 3000)

    def test_rejects_missing_hostname(self):
        with self.assertRaisesRegex(ValueError, "hostname"):
            create_openshift_adapter(endpoint="https://")

    def test_rejects_negative_max_retries(self):
        with self.assertRaisesRegex(ValueError, "max_retries"):
            create_openshift_adapter(
                endpoint="https://openshift.example.com",
                max_retries=-1,
            )


class OpenShiftValidationTests(unittest.TestCase):
    def test_validate_platform_accepts_valid(self):
        self.assertEqual(_validate_platform("openshift"), "openshift")
        self.assertEqual(_validate_platform("OpenShift"), "openshift")

    def test_validate_platform_rejects_invalid(self):
        with self.assertRaisesRegex(ValueError, "platform"):
            _validate_platform("kubernetes")

    def test_validate_project_name_accepts_valid(self):
        self.assertEqual(_validate_project_name("my-project"), "my-project")
        self.assertEqual(_validate_project_name("a"), "a")
        self.assertEqual(_validate_project_name("project123"), "project123")

    def test_validate_project_name_rejects_invalid(self):
        with self.assertRaisesRegex(ValueError, "project name"):
            _validate_project_name("")
        with self.assertRaisesRegex(ValueError, "project name"):
            _validate_project_name("-invalid")
        with self.assertRaisesRegex(ValueError, "project name"):
            _validate_project_name("invalid-")
        with self.assertRaisesRegex(ValueError, "project name"):
            _validate_project_name("a" * 64)
        with self.assertRaisesRegex(ValueError, "project name"):
            _validate_project_name("Invalid_Name")

    def test_validate_resource_name_accepts_valid(self):
        self.assertEqual(_validate_resource_name("my-deployment"), "my-deployment")
        self.assertEqual(_validate_resource_name("a"), "a")

    def test_validate_resource_name_rejects_invalid(self):
        with self.assertRaisesRegex(ValueError, "resource name"):
            _validate_resource_name("")
        with self.assertRaisesRegex(ValueError, "resource name"):
            _validate_resource_name("-invalid")
        with self.assertRaisesRegex(ValueError, "resource name"):
            _validate_resource_name("a" * 254)

    def test_validate_scc_name_accepts_valid(self):
        self.assertEqual(_validate_scc_name("privileged"), "privileged")
        self.assertEqual(_validate_scc_name("anyuid"), "anyuid")
        self.assertEqual(_validate_scc_name("system:openshift:scc:anyuid"), "system:openshift:scc:anyuid")

    def test_validate_scc_name_rejects_invalid(self):
        with self.assertRaisesRegex(ValueError, "SCC name"):
            _validate_scc_name("")
        with self.assertRaisesRegex(ValueError, "SCC name"):
            _validate_scc_name("a" * 254)
        with self.assertRaisesRegex(ValueError, "SCC name"):
            _validate_scc_name("invalid name with spaces")


class OpenShiftParseTests(unittest.TestCase):
    def test_parse_timestamp_valid(self):
        self.assertEqual(_parse_timestamp("2024-01-15T10:30:00Z"), "2024-01-15T10:30:00Z")
        self.assertEqual(_parse_timestamp("2024-01-15T10:30:00+00:00"), "2024-01-15T10:30:00+00:00")

    def test_parse_timestamp_invalid(self):
        self.assertIsNone(_parse_timestamp("not-a-timestamp"))
        self.assertIsNone(_parse_timestamp(12345))
        self.assertIsNone(_parse_timestamp(None))

    def test_safe_decimal_valid(self):
        self.assertEqual(_safe_decimal("42.5"), 42.5)
        self.assertEqual(_safe_decimal(100), 100)

    def test_safe_decimal_invalid(self):
        self.assertIsNone(_safe_decimal("not-a-number"))
        self.assertIsNone(_safe_decimal(None))
        self.assertIsNone(_safe_decimal(float("inf")))

    def test_safe_int_valid(self):
        self.assertEqual(_safe_int("42"), 42)
        self.assertEqual(_safe_int(100), 100)

    def test_safe_int_invalid(self):
        self.assertIsNone(_safe_int("not-a-number"))
        self.assertIsNone(_safe_int(None))


class OpenShiftResolveTests(unittest.TestCase):
    def test_resolve_endpoint_from_param(self):
        self.assertEqual(
            _resolve_endpoint("https://openshift.example.com/api"),
            "https://openshift.example.com/api",
        )

    def test_resolve_endpoint_strips_trailing_slash(self):
        self.assertEqual(
            _resolve_endpoint("https://openshift.example.com/api/"),
            "https://openshift.example.com/api",
        )

    def test_resolve_endpoint_rejects_http(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            _resolve_endpoint("http://openshift.example.com")

    def test_resolve_endpoint_rejects_missing_hostname(self):
        with self.assertRaisesRegex(ValueError, "hostname"):
            _resolve_endpoint("https://")

    def test_resolve_endpoint_rejects_long_url(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            _resolve_endpoint("https://example.com/" + "a" * 600)

    def test_resolve_credential_from_param(self):
        self.assertEqual(_resolve_credential("my-cred-ref"), "my-cred-ref")

    def test_resolve_credential_empty(self):
        self.assertIsNone(_resolve_credential(""))
        self.assertIsNone(_resolve_credential(None))

    def test_resolve_credential_rejects_invalid(self):
        with self.assertRaisesRegex(ValueError, "credential"):
            _resolve_credential("cred\r\ninjection")
        with self.assertRaisesRegex(ValueError, "credential"):
            _resolve_credential("a" * 300)


class OpenShiftAdapterProbeTests(unittest.TestCase):
    def test_probe_success(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        info_response = {
            "version": "4.14.0",
            "scopes": ["projects", "deployments"],
            "supported_platforms": ["openshift"],
        }
        opener = FakeOpener([info_response])
        with patch("urllib.request.build_opener", return_value=opener):
            result = adapter.probe()
        self.assertTrue(result["probe_success"])
        self.assertEqual(result["adapter_id"], "openshift")
        self.assertEqual(result["server_version"], "4.14.0")

    def test_probe_missing_version(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        opener = FakeOpener([{}])
        with patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ConnectionError, "version"):
                adapter.probe()

    def test_probe_invalid_scopes(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        opener = FakeOpener([{"version": "4.14.0", "scopes": "not-a-list"}])
        with patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ConnectionError, "scopes"):
                adapter.probe()


class OpenShiftAdapterHealthTests(unittest.TestCase):
    def test_health_check_healthy(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        info_response = {"version": "4.14.0"}
        projects_response = {
            "projects": [{"name": "default", "observed_at": "2024-01-15T10:30:00Z"}]
        }
        opener = FakeOpener([info_response, projects_response])
        with patch("urllib.request.build_opener", return_value=opener):
            result = adapter.health_check()
        self.assertTrue(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "ok")
        self.assertEqual(result["checks"]["authentication"], "ok")
        self.assertEqual(result["checks"]["schema"], "ok")
        self.assertEqual(result["checks"]["freshness"], "ok")

    def test_health_check_stale(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        info_response = {"version": "4.14.0"}
        projects_response = {"projects": [{"name": "default"}]}
        opener = FakeOpener([info_response, projects_response])
        with patch("urllib.request.build_opener", return_value=opener):
            result = adapter.health_check()
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "stale")

    def test_health_check_no_data(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        info_response = {"version": "4.14.0"}
        projects_response = {"projects": []}
        opener = FakeOpener([info_response, projects_response])
        with patch("urllib.request.build_opener", return_value=opener):
            result = adapter.health_check()
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["freshness"], "no_data")

    def test_health_check_connection_error(self):
        adapter = create_openshift_adapter(endpoint="https://openshift.example.com")
        opener = FakeOpener([])
        with patch("urllib.request.build_opener", return_value=opener):
            result = adapter.health_check()
        self.assertFalse(result["healthy"])
        self.assertEqual(result["checks"]["endpoint"], "unavailable")


if __name__ == "__main__":
    unittest.main()
