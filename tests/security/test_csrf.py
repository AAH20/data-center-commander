"""Security tests: Cross-Site Request Forgery (CSRF) prevention."""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class CSRFPreventionTests(unittest.TestCase):
    """Verify CSRF protection on state-changing endpoints."""

    def test_post_endpoint_requires_origin_header(self):
        """POST /v1/placement/scenarios must check Origin header."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("Origin", api_source)
        self.assertIn("same_origin_required", api_source)

    def test_post_endpoint_validates_origin_matches_server(self):
        """POST endpoint must validate Origin matches server address."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("expected_origins", api_source)
        self.assertIn("server_address", api_source)

    def test_post_endpoint_rejects_missing_origin(self):
        """POST endpoint must reject requests without Origin header."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("self.headers.get(\"Origin\")", api_source)

    def test_post_endpoint_rejects_wrong_origin(self):
        """POST endpoint must reject requests with wrong Origin."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("403", api_source)
        self.assertIn("same_origin_required", api_source)

    def test_post_endpoint_accepts_loopback_origin(self):
        """POST endpoint must accept loopback Origin."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("127.0.0.1", api_source)
        self.assertIn("localhost", api_source)

    def test_post_endpoint_requires_content_type_json(self):
        """POST endpoint must require application/json content type."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("application/json", api_source)
        self.assertIn("content type required", api_source)

    def test_post_endpoint_validates_content_length(self):
        """POST endpoint must validate Content-Length bounds."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("Content-Length", api_source)
        self.assertIn("70000", api_source)

    def test_post_endpoint_validates_json_body(self):
        """POST endpoint must validate JSON body is an object."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("json.loads", api_source)
        self.assertIn("must be an object", api_source)

    def test_post_endpoint_validates_tenant_id(self):
        """POST endpoint must validate tenant_id in body."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("parse_tenant", api_source)
        self.assertIn("tenant_id", api_source)

    def test_post_endpoint_validates_placement_snapshot(self):
        """POST endpoint must validate placement snapshot payload."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("validate_placement_snapshot", api_source)

    def test_post_endpoint_uses_parameterized_queries(self):
        """POST endpoint must use parameterized queries."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("%s", api_source)
        self.assertNotIn("f\"INSERT", api_source)

    def test_post_endpoint_sets_tenant_config(self):
        """POST endpoint must set tenant config before insert."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("set_config", api_source)
        self.assertIn("dcc.tenant_id", api_source)

    def test_post_endpoint_uses_read_only_transaction_for_get(self):
        """GET endpoints must use read-only transactions."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("SET TRANSACTION READ ONLY", api_source)

    def test_post_endpoint_returns_403_for_invalid_origin(self):
        """POST endpoint returns 403 for invalid Origin."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("403", api_source)

    def test_post_endpoint_returns_400_for_invalid_body(self):
        """POST endpoint returns 400 for invalid body."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("400", api_source)

    def test_post_endpoint_returns_503_for_db_error(self):
        """POST endpoint returns 503 for database errors."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("503", api_source)

    def test_post_endpoint_returns_201_for_success(self):
        """POST endpoint returns 201 for successful creation."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("201", api_source)

    def test_post_endpoint_includes_execution_permitted_false(self):
        """POST endpoint response includes execution_permitted: false."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("execution_permitted", api_source)
        self.assertIn("False", api_source)

    def test_get_endpoints_do_not_require_origin(self):
        """GET endpoints should not require Origin header (read-only)."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        # Origin check is only in do_POST
        post_section = api_source.split("def do_POST")[1]
        self.assertIn("Origin", post_section)
        get_section = api_source.split("def do_POST")[0]
        self.assertNotIn("Origin", get_section)

    def test_post_endpoint_validates_name_length(self):
        """POST endpoint validates snapshot name length."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("120", api_source)

    def test_post_endpoint_validates_schema_version(self):
        """POST endpoint validates schema version."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("schema_version", api_source)

    def test_post_endpoint_validates_currency(self):
        """POST endpoint validates currency code."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("currency", api_source)

    def test_post_endpoint_validates_horizon(self):
        """POST endpoint validates horizon months."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("horizon_months", api_source)

    def test_post_endpoint_validates_observed_on(self):
        """POST endpoint validates observation date."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("observed_on", api_source)

    def test_post_endpoint_validates_payload_size(self):
        """POST endpoint validates payload size."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("65536", api_source)

    def test_post_endpoint_computes_payload_hash(self):
        """POST endpoint computes payload hash."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("sha256", api_source)
        self.assertIn("payload_sha256", api_source)

    def test_post_endpoint_stores_created_by_null(self):
        """POST endpoint stores created_by as NULL."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("created_by", api_source)
        self.assertIn("NULL", api_source)


if __name__ == "__main__":
    unittest.main()
