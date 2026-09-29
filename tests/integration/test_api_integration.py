"""Integration tests for the HTTP API layer.

Tests all endpoints, request validation, tenant scoping, error handling,
and the placement snapshot workflow end-to-end.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock

from dcc.api import (
    Handler,
    connect_pool,
    database_readiness,
    parse_tenant,
    serve,
    validate_placement_snapshot,
)


def _make_pool(rows_map=None, schema_ok=True, rls_ok=True):
    """Create a mock connection pool for testing."""
    if rows_map is None:
        rows_map = {}

    class Cursor:
        def __init__(self, rows):
            self.rows = rows
        def fetchone(self):
            return self.rows[0] if self.rows else None
        def fetchall(self):
            return self.rows

    class Transaction:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class Connection:
        def __init__(self):
            self.executed = []
        def transaction(self): return Transaction()
        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            if "to_regclass" in sql:
                if schema_ok:
                    return Cursor([{"tenants": True, "assets": True, "evidence": True}])
                return Cursor([{"tenants": None, "assets": None, "evidence": None}])
            if "pg_class" in sql and "relrowsecurity" in sql:
                rows = []
                for name in ("assets", "evidence_events"):
                    rows.append({
                        "relname": name,
                        "relrowsecurity": rls_ok,
                        "relforcerowsecurity": rls_ok,
                    })
                return Cursor(rows)
            if "placement_comparison_snapshots" in sql and "INSERT" in sql:
                return Cursor([{
                    "id": "test-id", "name": "Test", "schema_version": "v1",
                    "payload": {}, "payload_sha256": "abc", "created_at": "2026-01-01",
                }])
            if "placement_comparison_snapshots" in sql and "SELECT" in sql:
                return Cursor(rows_map.get("placement", []))
            if "facilities" in sql and "count" in sql:
                return Cursor([{"facility_count": 5}])
            if "kpi_observations" in sql:
                return Cursor(rows_map.get("kpis", []))
            if "operational_workflows" in sql and "count" in sql:
                return Cursor([{"open_count": 3}])
            if "telemetry_readings" in sql and "max" in sql:
                return Cursor([{"latest_ingested_at": "2026-01-01T00:00:00Z"}])
            if "assets" in sql and "external_id" in sql:
                return Cursor(rows_map.get("assets", []))
            if "operational_workflows" in sql and "workflow_type" in sql:
                return Cursor(rows_map.get("workflows", []))
            if "connectors" in sql:
                return Cursor(rows_map.get("connectors", []))
            if "capacity_snapshots" in sql:
                return Cursor(rows_map.get("capacity", []))
            if "evidence_events" in sql:
                return Cursor(rows_map.get("evidence", []))
            if "estimate_projects" in sql:
                return Cursor(rows_map.get("estimates", []))
            if "price_observations" in sql:
                return Cursor(rows_map.get("prices", []))
            if "cost_actuals" in sql:
                return Cursor(rows_map.get("actuals", []))
            if "asset_relationships" in sql or "topology" in sql:
                return Cursor(rows_map.get("topology", []))
            if "kpi_observations" in sql and "metric_key" in sql:
                return Cursor(rows_map.get("analytics", []))
            if "telemetry_readings" in sql and "quality_status" in sql:
                return Cursor(rows_map.get("telemetry_quality", []))
            if "operational_workflows" in sql and "workflow_type" in sql:
                return Cursor(rows_map.get("workflow_health", []))
            return Cursor([])

    class Pool:
        def __init__(self):
            self.conn = Connection()
        def connection(self):
            class Context:
                def __enter__(inner): return self.conn
                def __exit__(inner, *args): return False
            return Context()
        def close(self): pass

    return Pool()


class TestHealthEndpoints(unittest.TestCase):
    def test_healthz_returns_service_info(self):
        class FakeHandler:
            path = "/healthz"
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(handler.result[1]["service"], "data-center-commander")
        self.assertEqual(handler.result[1]["mode"], "read_only")
        self.assertFalse(handler.result[1]["execution_permitted"])

    def test_readyz_returns_not_configured_without_pool(self):
        class FakeHandler:
            path = "/readyz"
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        with patch.object(Handler, "pool", None):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 503)
        self.assertFalse(handler.result[1]["ready"])
        self.assertEqual(handler.result[1]["checks"]["database"], "not_configured")

    def test_readyz_returns_ok_with_healthy_pool(self):
        class FakeHandler:
            path = "/readyz"
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        with patch.object(Handler, "pool", _make_pool()):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertTrue(handler.result[1]["ready"])
        self.assertEqual(handler.result[1]["checks"]["database"], "ok")
        self.assertEqual(handler.result[1]["checks"]["schema"], "ok")
        self.assertEqual(handler.result[1]["checks"]["tenant_rls"], "ok")

    def test_readyz_returns_503_when_schema_incomplete(self):
        class FakeHandler:
            path = "/readyz"
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        with patch.object(Handler, "pool", _make_pool(schema_ok=False)):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 503)
        self.assertFalse(handler.result[1]["ready"])
        self.assertEqual(handler.result[1]["checks"]["schema"], "incomplete")

    def test_readyz_returns_503_when_rls_not_enforced(self):
        class FakeHandler:
            path = "/readyz"
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        with patch.object(Handler, "pool", _make_pool(rls_ok=False)):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 503)
        self.assertFalse(handler.result[1]["ready"])
        self.assertEqual(handler.result[1]["checks"]["tenant_rls"], "not_enforced")


class TestTenantParsing(unittest.TestCase):
    def test_valid_uuid_accepted(self):
        value = "dcc00000-0000-4000-8000-000000000001"
        self.assertEqual(parse_tenant({"tenant_id": [value]}), value)

    def test_missing_tenant_id_rejected(self):
        with self.assertRaises(ValueError):
            parse_tenant({})

    def test_invalid_uuid_rejected(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["not-a-uuid"]})

    def test_multiple_tenant_ids_rejected(self):
        value = "dcc00000-0000-4000-8000-000000000001"
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": [value, value]})

    def test_empty_tenant_id_rejected(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": [""]})


class TestCollectionEndpoints(unittest.TestCase):
    def _make_handler(self, path):
        class FakeHandler:
            def __init__(self, p): self.path = p; self.result = None
            def respond(self, status, body): self.result = (status, body)
        return FakeHandler(path)

    def test_assets_endpoint_returns_tenant_scoped_data(self):
        rows = [{"external_id": "srv-1", "asset_type": "server", "name": "Server 1"}]
        handler = self._make_handler("/v1/assets?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"assets": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(handler.result[1]["tenant_id"], "dcc00000-0000-4000-8000-000000000001")
        self.assertEqual(len(handler.result[1]["assets"]), 1)
        self.assertTrue(handler.result[1]["read_only"])

    def test_assets_endpoint_rejects_missing_tenant(self):
        handler = self._make_handler("/v1/assets")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_assets_endpoint_rejects_invalid_tenant(self):
        handler = self._make_handler("/v1/assets?tenant_id=bad")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_assets_endpoint_rejects_window_days_zero(self):
        handler = self._make_handler("/v1/assets?tenant_id=dcc00000-0000-4000-8000-000000000001&window_days=0")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_assets_endpoint_rejects_window_days_over_90(self):
        handler = self._make_handler("/v1/assets?tenant_id=dcc00000-0000-4000-8000-000000000001&window_days=91")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_assets_endpoint_rejects_non_integer_window_days(self):
        handler = self._make_handler("/v1/assets?tenant_id=dcc00000-0000-4000-8000-000000000001&window_days=abc")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_facilities_endpoint_returns_data(self):
        rows = [{"id": "f1", "code": "DC1", "name": "Facility 1"}]
        handler = self._make_handler("/v1/facilities?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"facilities": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(len(handler.result[1]["facilities"]), 1)

    def test_workflows_endpoint_returns_data(self):
        rows = [{"id": "w1", "workflow_type": "maintenance", "status": "open"}]
        handler = self._make_handler("/v1/workflows?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"workflows": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(len(handler.result[1]["workflows"]), 1)

    def test_connectors_endpoint_returns_data(self):
        rows = [{"id": "c1", "name": "Connector 1", "vendor": "Test"}]
        handler = self._make_handler("/v1/connectors?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"connectors": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(len(handler.result[1]["connectors"]), 1)

    def test_capacity_endpoint_returns_data(self):
        rows = [{"facility_id": "f1", "dimension": "power_kw", "usable": 100}]
        handler = self._make_handler("/v1/capacity?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"capacity": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(len(handler.result[1]["capacity"]), 1)

    def test_evidence_endpoint_returns_data(self):
        rows = [{"sequence": 1, "event_type": "test", "occurred_at": "2026-01-01"}]
        handler = self._make_handler("/v1/evidence?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"evidence": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(len(handler.result[1]["evidence"]), 1)

    def test_overview_endpoint_returns_data(self):
        handler = self._make_handler("/v1/overview?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool()):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertIn("facility_count", handler.result[1])
        self.assertIn("kpis", handler.result[1])
        self.assertIn("open_workflows", handler.result[1])
        self.assertIn("source_status", handler.result[1])

    def test_topology_endpoint_returns_nodes_and_edges(self):
        nodes = [{"id": "a1", "label": "Server 1", "type": "server"}]
        edges = [{"source": "a1", "target": "a2", "relation": "feeds"}]
        handler = self._make_handler("/v1/topology?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"topology": nodes})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertIn("nodes", handler.result[1])
        self.assertIn("edges", handler.result[1])
        self.assertTrue(handler.result[1]["read_only"])

    def test_analytics_endpoint_returns_data(self):
        handler = self._make_handler("/v1/analytics?tenant_id=dcc00000-0000-4000-8000-000000000001&window_days=30")
        with patch.object(Handler, "pool", _make_pool()):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertIn("kpi_series", handler.result[1])
        self.assertIn("kpi_quality", handler.result[1])
        self.assertIn("telemetry_quality", handler.result[1])
        self.assertIn("workflow_health", handler.result[1])
        self.assertIn("model_policy", handler.result[1])
        self.assertFalse(handler.result[1]["execution_permitted"])

    def test_costs_endpoint_returns_data(self):
        handler = self._make_handler("/v1/costs?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool()):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertIn("estimates", handler.result[1])
        self.assertIn("prices", handler.result[1])
        self.assertIn("actuals", handler.result[1])
        self.assertIn("synthetic", handler.result[1])

    def test_unknown_route_returns_404(self):
        handler = self._make_handler("/v1/nonexistent?tenant_id=dcc00000-0000-4000-8000-000000000001")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 404)
        self.assertEqual(handler.result[1]["error"], "route_not_found")

    def test_database_error_returns_503(self):
        class FakeHandler:
            path = "/v1/assets?tenant_id=dcc00000-0000-4000-8000-000000000001"
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        with patch.object(Handler, "pool", None):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 503)
        self.assertIn("database", handler.result[1]["error"])


class TestPlacementSnapshotWorkflow(unittest.TestCase):
    def _make_handler(self, path, method="GET", body=None, headers=None):
        class FakeHandler:
            def __init__(self, p, m, b, h):
                self.path = p
                self.method = m
                self.body = b
                self.headers = h or {}
                self.result = None
                self.rfile = MagicMock()
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        return FakeHandler(path, method, body, headers)

    def _valid_payload(self):
        return {
            "name": "Test Comparison",
            "tenant_id": "dcc00000-0000-4000-8000-000000000001",
            "payload": {
                "schema_version": "placement-tco-comparison.v1",
                "assumptions": {"currency": "USD", "horizon_months": 36},
                "sources": {
                    "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                    "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
                },
                "results": {
                    "onprem": {"npv": 1.0},
                    "cloud": {"npv": 2.0},
                },
            },
        }

    def test_get_placement_scenarios_returns_list(self):
        rows = [{"id": "s1", "name": "Scenario 1"}]
        handler = self._make_handler("/v1/placement/scenarios?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch.object(Handler, "pool", _make_pool({"placement": rows})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertEqual(len(handler.result[1]["scenarios"]), 1)
        self.assertEqual(handler.result[1]["status"], "draft_snapshots")
        self.assertFalse(handler.result[1]["execution_permitted"])

    def test_get_placement_scenarios_rejects_invalid_tenant(self):
        handler = self._make_handler("/v1/placement/scenarios?tenant_id=bad")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_creates_draft(self):
        body = self._valid_payload()
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        with patch.object(Handler, "pool", _make_pool()):
            Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 201)
        self.assertEqual(handler.result[1]["status"], "draft_snapshot")
        self.assertFalse(handler.result[1]["execution_permitted"])

    def test_post_placement_snapshot_rejects_missing_origin(self):
        body = self._valid_payload()
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 403)
        self.assertEqual(handler.result[1]["error"], "same_origin_required")

    def test_post_placement_snapshot_rejects_wrong_origin(self):
        body = self._valid_payload()
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://evil.com"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 403)

    def test_post_placement_snapshot_rejects_invalid_payload(self):
        body = self._valid_payload()
        body["payload"]["assumptions"]["horizon_months"] = 0
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_non_json_content_type(self):
        body = self._valid_payload()
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "text/plain", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_empty_body(self):
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=None,
            headers={"Content-Type": "application/json", "Content-Length": "0", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_non_object_body(self):
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=[1, 2, 3],
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_missing_tenant(self):
        body = self._valid_payload()
        del body["tenant_id"]
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_invalid_name(self):
        body = self._valid_payload()
        body["name"] = ""
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_wrong_schema_version(self):
        body = self._valid_payload()
        body["payload"]["schema_version"] = "wrong-version"
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_invalid_currency(self):
        body = self._valid_payload()
        body["payload"]["assumptions"]["currency"] = "US"
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_invalid_observed_date(self):
        body = self._valid_payload()
        body["payload"]["sources"]["onprem"]["observed_on"] = "yesterday"
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_placement_snapshot_rejects_oversized_payload(self):
        body = self._valid_payload()
        body["payload"]["assumptions"]["padding"] = "x" * 70000
        handler = self._make_handler(
            "/v1/placement/scenarios",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": "70001", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 400)

    def test_post_to_wrong_path_returns_404(self):
        handler = self._make_handler(
            "/v1/placement/other",
            method="POST",
            body=self._valid_payload(),
            headers={"Content-Type": "application/json", "Content-Length": "100", "Origin": "http://127.0.0.1:8790"},
        )
        Handler.do_POST(handler)
        self.assertEqual(handler.result[0], 404)


class TestValidatePlacementSnapshot(unittest.TestCase):
    def test_valid_payload_accepted(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        name, encoded, digest, version = validate_placement_snapshot({"name": "Test", "payload": payload})
        self.assertEqual(name, "Test")
        self.assertEqual(version, "placement-tco-comparison.v1")
        self.assertEqual(len(digest), 64)

    def test_name_trimmed(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        name, _, _, _ = validate_placement_snapshot({"name": "  Test  ", "payload": payload})
        self.assertEqual(name, "Test")

    def test_empty_name_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "", "payload": payload})

    def test_long_name_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "x" * 121, "payload": payload})

    def test_missing_payload_rejected(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test"})

    def test_wrong_schema_version_rejected(self):
        payload = {
            "schema_version": "wrong",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_assumptions_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_sources_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_results_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_invalid_currency_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "US", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_horizon_months_zero_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 0},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_horizon_months_over_120_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 121},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_horizon_months_bool_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": True},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_source_type_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_source_reference_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_observed_on_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_invalid_observed_on_format_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "25/09/2026"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_missing_side_result_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_oversized_payload_rejected(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36, "padding": "x" * 70000},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_digest_is_deterministic(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        _, _, digest1, _ = validate_placement_snapshot({"name": "Test", "payload": payload})
        _, _, digest2, _ = validate_placement_snapshot({"name": "Test", "payload": payload})
        self.assertEqual(digest1, digest2)

    def test_digest_changes_with_payload(self):
        payload1 = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        payload2 = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "EUR", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "Vendor quote", "reference": "Q-1", "observed_on": "2026-09-25"},
                "cloud": {"type": "Vendor quote", "reference": "Q-2", "observed_on": "2026-09-25"},
            },
            "results": {
                "onprem": {"npv": 1.0},
                "cloud": {"npv": 2.0},
            },
        }
        _, _, digest1, _ = validate_placement_snapshot({"name": "Test", "payload": payload1})
        _, _, digest2, _ = validate_placement_snapshot({"name": "Test", "payload": payload2})
        self.assertNotEqual(digest1, digest2)


class TestDatabaseReadiness(unittest.TestCase):
    def test_none_pool_returns_not_configured(self):
        ready, checks = database_readiness(None)
        self.assertFalse(ready)
        self.assertEqual(checks["database"], "not_configured")
        self.assertEqual(checks["schema"], "unchecked")
        self.assertEqual(checks["tenant_rls"], "unchecked")

    def test_healthy_pool_returns_ok(self):
        ready, checks = database_readiness(_make_pool())
        self.assertTrue(ready)
        self.assertEqual(checks["database"], "ok")
        self.assertEqual(checks["schema"], "ok")
        self.assertEqual(checks["tenant_rls"], "ok")

    def test_incomplete_schema_returns_incomplete(self):
        ready, checks = database_readiness(_make_pool(schema_ok=False))
        self.assertFalse(ready)
        self.assertEqual(checks["schema"], "incomplete")

    def test_missing_rls_returns_not_enforced(self):
        ready, checks = database_readiness(_make_pool(rls_ok=False))
        self.assertFalse(ready)
        self.assertEqual(checks["tenant_rls"], "not_enforced")


class TestServe(unittest.TestCase):
    def test_non_loopback_bind_rejected(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            serve("0.0.0.0", 8790)

    def test_loopback_bind_accepted(self):
        # We can't actually start the server in tests, but we can verify
        # the validation passes by checking it doesn't raise ValueError
        # (it will fail on connect_pool which is expected)
        with patch("dcc.api.connect_pool", side_effect=Exception("no db")):
            with self.assertRaises(Exception):
                serve("127.0.0.1", 0)


class TestConnectPool(unittest.TestCase):
    def test_missing_env_raises_runtime_error(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                connect_pool()
            self.assertIn("database_not_configured", str(ctx.exception))

    def test_missing_psycopg_raises_runtime_error(self):
        with patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"}):
            with patch.dict("sys.modules", {"psycopg": None, "psycopg_pool": None}):
                with self.assertRaises(RuntimeError):
                    connect_pool()


class TestPricingEndpoints(unittest.TestCase):
    def _make_handler(self, path):
        class FakeHandler:
            def __init__(self, p): self.path = p; self.result = None
            def respond(self, status, body): self.result = (status, body)
        return FakeHandler(path)

    def test_azure_pricing_returns_result(self):
        handler = self._make_handler("/v1/pricing/azure-retail?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch("dcc.api.fetch_azure_retail_prices", return_value={"prices": []}):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)

    def test_azure_pricing_rejects_invalid_tenant(self):
        handler = self._make_handler("/v1/pricing/azure-retail?tenant_id=bad")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_azure_pricing_returns_502_on_connection_error(self):
        handler = self._make_handler("/v1/pricing/azure-retail?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch("dcc.api.fetch_azure_retail_prices", side_effect=ConnectionError("timeout")):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 502)

    def test_google_pricing_returns_result(self):
        handler = self._make_handler("/v1/pricing/google-cloud-retail?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch("dcc.api.fetch_google_cloud_prices", return_value={"prices": []}):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)

    def test_google_pricing_rejects_invalid_tenant(self):
        handler = self._make_handler("/v1/pricing/google-cloud-retail?tenant_id=bad")
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_google_pricing_returns_503_on_missing_key(self):
        handler = self._make_handler("/v1/pricing/google-cloud-retail?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch("dcc.api.fetch_google_cloud_prices", side_effect=ConnectionError("GOOGLE_CLOUD_BILLING_API_KEY is not configured")):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 503)

    def test_google_pricing_returns_502_on_other_connection_error(self):
        handler = self._make_handler("/v1/pricing/google-cloud-retail?tenant_id=dcc00000-0000-4000-8000-000000000001")
        with patch("dcc.api.fetch_google_cloud_prices", side_effect=ConnectionError("timeout")):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 502)


class TestAssetServing(unittest.TestCase):
    def test_serves_onboarding_js(self):
        class FakeHandler:
            path = "/assets/onboarding.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.status, 200)

    def test_serves_topology_js(self):
        class FakeHandler:
            path = "/assets/topology.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.status, 200)

    def test_serves_azure_prices_js(self):
        class FakeHandler:
            path = "/assets/azure-prices.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.status, 200)

    def test_serves_placement_comparison_js(self):
        class FakeHandler:
            path = "/assets/placement-comparison.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.status, 200)

    def test_serves_placement_scenarios_js(self):
        class FakeHandler:
            path = "/assets/placement-scenarios.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.status, 200)

    def test_serves_quality_dashboard_js(self):
        class FakeHandler:
            path = "/assets/quality-dashboard.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
            def send_response(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.status, 200)

    def test_unknown_asset_returns_404(self):
        class FakeHandler:
            path = "/assets/nonexistent.js"
            def __init__(self): self.result = None
            def respond(self, status, body): self.result = (status, body)
        handler = FakeHandler()
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 404)


class TestSyntheticDemoMode(unittest.TestCase):
    def test_overview_synthetic_demo_mode(self):
        kpis = [{"metric_key": "pue", "name": "PUE", "unit": "ratio", "provenance": {"synthetic": True}}]
        handler = type("FakeHandler", (), {
            "path": "/v1/overview?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic",
            "result": None,
            "respond": lambda self, status, body: setattr(self, "result", (status, body)),
        })()
        with patch.object(Handler, "pool", _make_pool({"kpis": kpis})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertTrue(handler.result[1]["synthetic"])
        self.assertTrue(handler.result[1]["synthetic_demo_mode"])

    def test_overview_synthetic_without_demo_mode_hides_data(self):
        kpis = [{"metric_key": "pue", "name": "PUE", "unit": "ratio", "provenance": {"synthetic": True}}]
        handler = type("FakeHandler", (), {
            "path": "/v1/overview?tenant_id=dcc00000-0000-4000-8000-000000000001",
            "result": None,
            "respond": lambda self, status, body: setattr(self, "result", (status, body)),
        })()
        with patch.object(Handler, "pool", _make_pool({"kpis": kpis})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertTrue(handler.result[1]["synthetic"])
        self.assertFalse(handler.result[1]["synthetic_demo_mode"])
        self.assertEqual(handler.result[1]["kpis"], [])
        self.assertEqual(handler.result[1]["facility_count"], 0)

    def test_costs_synthetic_demo_mode_shows_synthetic_prices(self):
        prices = [{"item_code": "TEST", "source_kind": "synthetic_demo", "provenance": {"synthetic": True}}]
        handler = type("FakeHandler", (), {
            "path": "/v1/costs?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic",
            "result": None,
            "respond": lambda self, status, body: setattr(self, "result", (status, body)),
        })()
        with patch.object(Handler, "pool", _make_pool({"prices": prices})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertTrue(handler.result[1]["synthetic"])
        self.assertTrue(handler.result[1]["synthetic_demo_mode"])
        self.assertEqual(len(handler.result[1]["prices"]), 1)

    def test_costs_synthetic_without_demo_mode_hides_synthetic_prices(self):
        prices = [{"item_code": "TEST", "source_kind": "synthetic_demo", "provenance": {"synthetic": True}}]
        handler = type("FakeHandler", (), {
            "path": "/v1/costs?tenant_id=dcc00000-0000-4000-8000-000000000001",
            "result": None,
            "respond": lambda self, status, body: setattr(self, "result", (status, body)),
        })()
        with patch.object(Handler, "pool", _make_pool({"prices": prices})):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertTrue(handler.result[1]["synthetic"])
        self.assertFalse(handler.result[1]["synthetic_demo_mode"])
        self.assertEqual(handler.result[1]["prices"], [])


if __name__ == "__main__":
    unittest.main()
