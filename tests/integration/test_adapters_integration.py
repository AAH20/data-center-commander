"""Integration tests for adapter modules.

Tests all adapter integrations: BMS, Cloud, CMMS, EPMS, Hypervisor,
Meter, OEM, Utility, Weather, and the adapter registry.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestAdapterRegistryIntegration(unittest.TestCase):
    """Integration tests for the adapter registry."""

    def test_register_and_discover_multiple_adapters(self):
        from dcc.adapters.registry import AdapterRegistry, AdapterInfo, AdapterCapability, HealthStatus
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="test-adapter-1", version="1.0", description="Test 1",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
        ))
        reg.register(AdapterInfo(
            name="test-adapter-2", version="1.0", description="Test 2",
            capabilities=frozenset([AdapterCapability.SKU_SEARCH]),
            endpoint="https://example2.com",
        ))
        all_adapters = reg.discover()
        self.assertEqual(len(all_adapters), 2)

    def test_capability_negotiation_across_adapters(self):
        from dcc.adapters.registry import AdapterRegistry, AdapterInfo, AdapterCapability
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="multi", version="1.0", description="Multi",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP, AdapterCapability.SKU_SEARCH]),
            endpoint="https://example.com",
        ))
        reg.register(AdapterInfo(
            name="single", version="1.0", description="Single",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example2.com",
        ))
        result = reg.negotiate({AdapterCapability.SKU_SEARCH})
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "multi")

    def test_health_check_integration(self):
        from dcc.adapters.registry import AdapterRegistry, AdapterInfo, AdapterCapability, HealthStatus
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="healthy", version="1.0", description="Healthy",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
            health_check=lambda: True,
        ))
        health = reg.check_health("healthy")
        self.assertEqual(health.status, HealthStatus.HEALTHY)

    def test_rate_limit_tracking_integration(self):
        from dcc.adapters.registry import AdapterRegistry, AdapterInfo, AdapterCapability
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="limited", version="1.0", description="Limited",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
        ))
        state = reg.update_rate_limit("limited", limit=100, remaining=50)
        self.assertEqual(state.limit, 100)
        self.assertEqual(state.remaining, 50)

    def test_snapshot_integration(self):
        from dcc.adapters.registry import AdapterRegistry, AdapterInfo, AdapterCapability, HealthStatus
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="snap", version="1.0", description="Snap",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
            health_check=lambda: True,
        ))
        reg.check_health("snap")
        reg.update_rate_limit("snap", limit=100, remaining=50)
        snap = reg.snapshot()
        self.assertIn("snap", snap["adapters"])
        self.assertIn("snap", snap["health"])
        self.assertIn("snap", snap["rate_limits"])


class TestCloudAdapterIntegration(unittest.TestCase):
    """Integration tests for the cloud cost adapter."""

    def test_aws_price_fetch_integration(self):
        from dcc.adapters.cloud import fetch_aws_prices
        mock_response = {
            "products": {
                "SKU1": {
                    "attributes": {"location": "US East", "instanceType": "m5.large"},
                },
            },
            "terms": {
                "OnDemand": {
                    "TERM1": {
                        "productId": "SKU1",
                        "priceDimensions": {
                            "DIM1": {
                                "pricePerUnit": {"USD": "0.096"},
                                "unit": "Hrs",
                            },
                        },
                    },
                },
            },
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_response).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.cloud.urllib.request.build_opener", return_value=Opener()):
            result = fetch_aws_prices(service="ec2", region="US East", sku="m5.large")
        self.assertEqual(result["provider"], "AWS Price List API")
        self.assertTrue(result["persisted"] is False)
        self.assertTrue(result["execution_permitted"] is False)

    def test_aws_unsupported_service_rejected(self):
        from dcc.adapters.cloud import fetch_aws_prices
        with self.assertRaises(ValueError):
            fetch_aws_prices(service="unsupported")

    def test_aws_invalid_currency_rejected(self):
        from dcc.adapters.cloud import fetch_aws_prices
        with self.assertRaises(ValueError):
            fetch_aws_prices(service="ec2", currency="INVALID")

    def test_cloud_cost_adapter_registers_providers(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        self.assertIsNotNone(adapter)

    def test_cloud_cost_adapter_fetch_prices_aws(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        with patch("dcc.adapters.cloud.fetch_aws_prices", return_value={"prices": []}):
            result = adapter.fetch_prices("aws", service="ec2")
        self.assertIn("prices", result)

    def test_cloud_cost_adapter_fetch_prices_azure(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        with patch("dcc.adapters.cloud.fetch_azure_retail_prices", return_value={"prices": []}):
            result = adapter.fetch_prices("azure", service="Virtual Machines")
        self.assertIn("prices", result)

    def test_cloud_cost_adapter_fetch_prices_gcp(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        with patch("dcc.adapters.cloud.fetch_google_cloud_prices", return_value={"prices": []}):
            result = adapter.fetch_prices("gcp", service="Compute Engine")
        self.assertIn("prices", result)

    def test_cloud_cost_adapter_unsupported_provider(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        with self.assertRaises(ValueError):
            adapter.fetch_prices("unsupported", service="test")

    def test_cloud_cost_adapter_health_check(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        with patch("dcc.adapters.cloud.fetch_aws_prices", return_value={"prices": []}):
            self.assertTrue(adapter.health_check("aws"))

    def test_cloud_cost_adapter_health_check_failure(self):
        from dcc.adapters.cloud import CloudCostAdapter
        adapter = CloudCostAdapter()
        with patch("dcc.adapters.cloud.fetch_aws_prices", side_effect=Exception("fail")):
            self.assertFalse(adapter.health_check("aws"))

    def test_get_adapter_singleton(self):
        from dcc.adapters.cloud import get_adapter
        a1 = get_adapter()
        a2 = get_adapter()
        self.assertIs(a1, a2)


class TestEPMSAdapterIntegration(unittest.TestCase):
    """Integration tests for the EPMS adapter."""

    def test_create_adapter_with_valid_config(self):
        from dcc.adapters.epms import create_epms_adapter, EPMSConfig, GenericEPMSAdapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        self.assertIsInstance(adapter, GenericEPMSAdapter)
        self.assertEqual(adapter.name, "generic-epms")

    def test_create_adapter_rejects_http(self):
        from dcc.adapters.epms import create_epms_adapter
        with self.assertRaises(ValueError):
            create_epms_adapter("http://epms.example.com/api")

    def test_create_adapter_rejects_empty_endpoint(self):
        from dcc.adapters.epms import create_epms_adapter
        with self.assertRaises(ValueError):
            create_epms_adapter("")

    def test_create_adapter_rejects_long_endpoint(self):
        from dcc.adapters.epms import create_epms_adapter
        with self.assertRaises(ValueError):
            create_epms_adapter("https://example.com/" + "x" * 2048)

    def test_create_adapter_rejects_invalid_api_version(self):
        from dcc.adapters.epms import create_epms_adapter
        with self.assertRaises(ValueError):
            create_epms_adapter("https://epms.example.com/api", api_version="v1;drop")

    def test_create_adapter_rejects_invalid_rate_limit(self):
        from dcc.adapters.epms import create_epms_adapter
        with self.assertRaises(ValueError):
            create_epms_adapter("https://epms.example.com/api", rate_limit_per_minute=0)

    def test_create_adapter_rejects_invalid_timeout(self):
        from dcc.adapters.epms import create_epms_adapter
        with self.assertRaises(ValueError):
            create_epms_adapter("https://epms.example.com/api", timeout_s=0.1)

    def test_adapter_capabilities(self):
        from dcc.adapters.epms import create_epms_adapter, EPMSCapability
        adapter = create_epms_adapter("https://epms.example.com/api")
        self.assertTrue(adapter.supports(EPMSCapability.METER_READINGS))
        self.assertTrue(adapter.supports(EPMSCapability.BREAKER_STATUS))
        self.assertTrue(adapter.supports(EPMSCapability.UPS_STATUS))
        self.assertTrue(adapter.supports(EPMSCapability.ALARM_HISTORY))

    def test_adapter_health_check_success(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps({"status": "ok"}).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
            self.assertTrue(adapter.health_check())

    def test_adapter_health_check_failure(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("timeout")

        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
            self.assertFalse(adapter.health_check())

    def test_adapter_read_meters(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        mock_data = {
            "readings": [
                {"pointId": "p1", "timestamp": "2026-01-01T00:00:00Z", "value": 100.0, "unit": "kW"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
            readings = adapter.read_meters()
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].point_id, "p1")
        self.assertEqual(readings[0].value, 100.0)

    def test_adapter_read_breakers(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        mock_data = {
            "breakers": [
                {"pointId": "b1", "timestamp": "2026-01-01T00:00:00Z", "state": "closed"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
            breakers = adapter.read_breakers()
        self.assertEqual(len(breakers), 1)
        self.assertEqual(breakers[0].state, "closed")

    def test_adapter_read_ups(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        mock_data = {
            "ups": [
                {"pointId": "u1", "timestamp": "2026-01-01T00:00:00Z", "onBattery": False, "loadPct": 50.0},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
            ups = adapter.read_ups()
        self.assertEqual(len(ups), 1)
        self.assertFalse(ups[0].on_battery)

    def test_adapter_read_alarms(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        mock_data = {
            "alarms": [
                {"alarmId": "a1", "pointId": "p1", "severity": "critical", "message": "Test", "raisedAt": "2026-01-01T00:00:00Z"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
            alarms = adapter.read_alarms()
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].severity, "critical")

    def test_adapter_map_to_canonical(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        mapping = adapter.map_to_canonical(
            point_id="p1",
            asset_external_id="a1",
            meter_external_id="m1",
            metric_key="power",
        )
        self.assertEqual(mapping["point_id"], "p1")
        self.assertEqual(mapping["confidence"], 0.9)

    def test_adapter_snapshot(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        snap = adapter.snapshot()
        self.assertEqual(snap["name"], "generic-epms")
        self.assertIn("capabilities", snap)
        self.assertIn("consecutive_failures", snap)

    def test_adapter_read_meters_validates_point_ids(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        with self.assertRaises(ValueError):
            adapter.read_meters(point_ids=["invalid point id!"])

    def test_adapter_read_meters_too_many_points(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        with self.assertRaises(ValueError):
            adapter.read_meters(point_ids=[f"p{i}" for i in range(501)])

    def test_adapter_read_alarms_validates_severity(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        with self.assertRaises(ValueError):
            adapter.read_alarms(severity="invalid")

    def test_adapter_read_alarms_valid_severities(self):
        from dcc.adapters.epms import create_epms_adapter
        adapter = create_epms_adapter("https://epms.example.com/api")
        for sev in ("critical", "major", "minor", "info", "cleared"):
            mock_data = {"alarms": []}

            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self, limit): return json.dumps(mock_data).encode()

            class Opener:
                def open(self, request, timeout): return Response()

            with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=Opener()):
                result = adapter.read_alarms(severity=sev)
            self.assertEqual(result, [])


class TestCMMSAdapterIntegration(unittest.TestCase):
    """Integration tests for the CMMS adapter."""

    def test_probe_cmms_success(self):
        from dcc.adapters.cmms import probe_cmms
        mock_data = {"data": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=Opener()):
            result = probe_cmms(endpoint="https://cmms.example.com/api", api_key="test-key")
        self.assertEqual(result["status"], "healthy")
        self.assertTrue(result["work_orders_accessible"])

    def test_probe_cmms_rejects_http(self):
        from dcc.adapters.cmms import probe_cmms
        with self.assertRaises(ValueError):
            probe_cmms(endpoint="http://cmms.example.com/api", api_key="test-key")

    def test_probe_cmms_rejects_unknown_host(self):
        from dcc.adapters.cmms import probe_cmms
        with self.assertRaises(ValueError):
            probe_cmms(endpoint="https://unknown.example.com/api", api_key="test-key")

    def test_probe_cmms_rejects_embedded_credentials(self):
        from dcc.adapters.cmms import probe_cmms
        with self.assertRaises(ValueError):
            probe_cmms(endpoint="https://user:pass@cmms.example.com/api", api_key="test-key")

    def test_fetch_work_orders_success(self):
        from dcc.adapters.cmms import fetch_work_orders
        mock_data = {
            "data": [
                {"id": "wo1", "title": "Fix server", "status": "open", "priority": "high"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=Opener()):
            result = fetch_work_orders(endpoint="https://cmms.example.com/api", api_key="test-key")
        self.assertEqual(len(result["work_orders"]), 1)
        self.assertEqual(result["work_orders"][0]["id"], "wo1")

    def test_fetch_work_orders_rejects_invalid_limit(self):
        from dcc.adapters.cmms import fetch_work_orders
        with self.assertRaises(ValueError):
            fetch_work_orders(endpoint="https://cmms.example.com/api", api_key="test-key", limit=0)

    def test_fetch_work_orders_rejects_invalid_status(self):
        from dcc.adapters.cmms import fetch_work_orders
        with self.assertRaises(ValueError):
            fetch_work_orders(endpoint="https://cmms.example.com/api", api_key="test-key", status="invalid!")

    def test_fetch_assets_success(self):
        from dcc.adapters.cmms import fetch_assets
        mock_data = {
            "data": [
                {"id": "a1", "name": "Server 1", "asset_type": "server"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=Opener()):
            result = fetch_assets(endpoint="https://cmms.example.com/api", api_key="test-key")
        self.assertEqual(len(result["assets"]), 1)

    def test_fetch_schedules_success(self):
        from dcc.adapters.cmms import fetch_schedules
        mock_data = {
            "data": [
                {"id": "s1", "title": "Monthly maintenance", "schedule_type": "preventive"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=Opener()):
            result = fetch_schedules(endpoint="https://cmms.example.com/api", api_key="test-key")
        self.assertEqual(len(result["schedules"]), 1)

    def test_fetch_work_orders_response_not_list(self):
        from dcc.adapters.cmms import fetch_work_orders
        mock_data = {"data": "not a list"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                fetch_work_orders(endpoint="https://cmms.example.com/api", api_key="test-key")


class TestBMSAdapterIntegration(unittest.TestCase):
    """Integration tests for the BMS adapter."""

    def test_probe_success(self):
        from dcc.adapters.bms import probe
        mock_data = {"version": "1.0", "scopes": ["hvac", "lighting"]}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://bms.example.com/api")
        self.assertTrue(result["probe_success"])
        self.assertEqual(result["server_version"], "1.0")

    def test_probe_rejects_http(self):
        from dcc.adapters.bms import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://bms.example.com/api")

    def test_probe_rejects_missing_version(self):
        from dcc.adapters.bms import probe
        mock_data = {"scopes": []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ConnectionError):
                probe(endpoint="https://bms.example.com/api")

    def test_fetch_points_success(self):
        from dcc.adapters.bms import fetch_points
        mock_data = {
            "points": [
                {"point_id": "hvac-1", "value": 22.5, "unit": "C", "observed_at": "2026-01-01T00:00:00Z"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            result = fetch_points(category="hvac", endpoint="https://bms.example.com/api")
        self.assertEqual(len(result["points"]), 1)
        self.assertEqual(result["points"][0]["point_id"], "hvac-1")

    def test_fetch_points_rejects_invalid_category(self):
        from dcc.adapters.bms import fetch_points
        with self.assertRaises(ValueError):
            fetch_points(category="invalid", endpoint="https://bms.example.com/api")

    def test_fetch_points_rejects_too_many_point_ids(self):
        from dcc.adapters.bms import fetch_points
        with self.assertRaises(ValueError):
            fetch_points(category="hvac", endpoint="https://bms.example.com/api", point_ids=[f"p{i}" for i in range(101)])

    def test_fetch_points_rejects_invalid_since(self):
        from dcc.adapters.bms import fetch_points
        with self.assertRaises(ValueError):
            fetch_points(category="hvac", endpoint="https://bms.example.com/api", since="not-a-date")

    def test_fetch_alarms_success(self):
        from dcc.adapters.bms import fetch_alarms
        mock_data = {
            "alarms": [
                {"alarm_id": "a1", "severity": "critical", "message": "High temp", "status": "active"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            result = fetch_alarms(endpoint="https://bms.example.com/api")
        self.assertEqual(len(result["alarms"]), 1)

    def test_fetch_alarms_rejects_invalid_limit(self):
        from dcc.adapters.bms import fetch_alarms
        with self.assertRaises(ValueError):
            fetch_alarms(endpoint="https://bms.example.com/api", limit=0)

    def test_fetch_hvac_summary_success(self):
        from dcc.adapters.bms import fetch_hvac_summary
        mock_data = {
            "zones": [
                {"zone_id": "z1", "temperature": 22.5, "humidity": 45.0},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            result = fetch_hvac_summary(endpoint="https://bms.example.com/api")
        self.assertEqual(len(result["zones"]), 1)

    def test_health_check_success(self):
        from dcc.adapters.bms import health_check
        mock_info = {"version": "1.0", "scopes": []}
        mock_points = {"points": [{"observed_at": "2026-01-01T00:00:00Z"}]}

        class InfoResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_info).encode()

        class PointsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_points).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return InfoResponse()
                return PointsResponse()

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://bms.example.com/api")
        self.assertTrue(result["healthy"])

    def test_health_check_failure(self):
        from dcc.adapters.bms import health_check

        class Opener:
            def open(self, request, timeout):
                raise ConnectionError("timeout")

        with patch("dcc.adapters.bms.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://bms.example.com/api")
        self.assertFalse(result["healthy"])


class TestHypervisorAdapterIntegration(unittest.TestCase):
    """Integration tests for the hypervisor adapter."""

    def test_probe_success(self):
        from dcc.adapters.hypervisor import probe
        mock_data = {"version": "1.0", "scopes": ["vm_inventory"], "supported_hypervisors": ["vmware_vcenter"]}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://hypervisor.example.com/api")
        self.assertTrue(result["probe_success"])

    def test_probe_rejects_http(self):
        from dcc.adapters.hypervisor import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://hypervisor.example.com/api")

    def test_fetch_vm_inventory_success(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        mock_data = {
            "vms": [
                {"vm_id": "vm-1", "name": "Web Server", "power_state": "powered_on", "cpu_count": 4},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_inventory(hypervisor_type="vmware_vcenter", endpoint="https://hypervisor.example.com/api")
        self.assertEqual(len(result["vms"]), 1)

    def test_fetch_vm_inventory_rejects_invalid_type(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(hypervisor_type="invalid", endpoint="https://hypervisor.example.com/api")

    def test_fetch_vm_inventory_rejects_invalid_power_state(self):
        from dcc.adapters.hypervisor import fetch_vm_inventory
        with self.assertRaises(ValueError):
            fetch_vm_inventory(hypervisor_type="vmware_vcenter", endpoint="https://hypervisor.example.com/api", power_state="invalid")

    def test_fetch_host_inventory_success(self):
        from dcc.adapters.hypervisor import fetch_host_inventory
        mock_data = {
            "hosts": [
                {"host_id": "h1", "name": "Host 1", "total_cpu_cores": 32},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_host_inventory(hypervisor_type="vmware_vcenter", endpoint="https://hypervisor.example.com/api")
        self.assertEqual(len(result["hosts"]), 1)

    def test_fetch_power_metrics_success(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        mock_data = {
            "metrics": [
                {"metric_id": "m1", "power_watts": 500.0, "entity_type": "vm"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_power_metrics(hypervisor_type="vmware_vcenter", endpoint="https://hypervisor.example.com/api")
        self.assertEqual(len(result["metrics"]), 1)

    def test_fetch_power_metrics_rejects_too_many_vm_ids(self):
        from dcc.adapters.hypervisor import fetch_power_metrics
        with self.assertRaises(ValueError):
            fetch_power_metrics(
                hypervisor_type="vmware_vcenter",
                endpoint="https://hypervisor.example.com/api",
                vm_ids=[f"vm-{i}" for i in range(101)],
            )

    def test_fetch_capacity_metrics_success(self):
        from dcc.adapters.hypervisor import fetch_capacity_metrics
        mock_data = {
            "metrics": [
                {"metric_id": "c1", "cpu_total_cores": 32, "cpu_used_cores": 16},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_capacity_metrics(hypervisor_type="vmware_vcenter", endpoint="https://hypervisor.example.com/api")
        self.assertEqual(len(result["metrics"]), 1)

    def test_fetch_vm_state_success(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        mock_data = {
            "states": [
                {"vm_id": "vm-1", "power_state": "powered_on", "uptime_seconds": 3600},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.hypervisor.urllib.request.build_opener", return_value=Opener()):
            result = fetch_vm_state(hypervisor_type="vmware_vcenter", vm_ids=["vm-1"], endpoint="https://hypervisor.example.com/api")
        self.assertEqual(len(result["states"]), 1)

    def test_fetch_vm_state_rejects_empty_vm_ids(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(hypervisor_type="vmware_vcenter", vm_ids=[], endpoint="https://hypervisor.example.com/api")

    def test_fetch_vm_state_rejects_too_many_vm_ids(self):
        from dcc.adapters.hypervisor import fetch_vm_state
        with self.assertRaises(ValueError):
            fetch_vm_state(
                hypervisor_type="vmware_vcenter",
                vm_ids=[f"vm-{i}" for i in range(101)],
                endpoint="https://hypervisor.example.com/api",
            )

    def test_health_check_success(self):
        from dcc.adapters.hypervisor import health_check
        mock_info = {"version": "1.0", "scopes": [], "supported_hypervisors": []}
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


class TestMeterAdapterIntegration(unittest.TestCase):
    """Integration tests for the meter adapter."""

    def test_quality_status_enum(self):
        from dcc.adapters.meter import QualityStatus
        self.assertEqual(QualityStatus.GOOD, "good")
        self.assertEqual(QualityStatus.ESTIMATED, "estimated")
        self.assertEqual(QualityStatus.SUSPECT, "suspect")
        self.assertEqual(QualityStatus.BAD, "bad")
        self.assertEqual(QualityStatus.STALE, "stale")

    def test_meter_adapter_error_hierarchy(self):
        from dcc.adapters.meter import MeterAdapterError, ConnectionError_, TimeoutError_, ProtocolError_, ValidationError_
        self.assertTrue(issubclass(ConnectionError_, MeterAdapterError))
        self.assertTrue(issubclass(TimeoutError_, MeterAdapterError))
        self.assertTrue(issubclass(ProtocolError_, MeterAdapterError))
        self.assertTrue(issubclass(ValidationError_, MeterAdapterError))

    def test_validate_host_rejects_invalid(self):
        from dcc.adapters.meter import _validate_host, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_host("")

    def test_validate_port_rejects_invalid(self):
        from dcc.adapters.meter import _validate_port, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_port(0)

    def test_validate_timeout_rejects_invalid(self):
        from dcc.adapters.meter import _validate_timeout, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_timeout(0)

    def test_validate_unit_id_rejects_invalid(self):
        from dcc.adapters.meter import _validate_unit_id, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_unit_id(-1)

    def test_validate_register_rejects_invalid(self):
        from dcc.adapters.meter import _validate_register, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_register(-1)

    def test_validate_oid_rejects_invalid(self):
        from dcc.adapters.meter import _validate_oid, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_oid("")

    def test_validate_meter_id_rejects_invalid(self):
        from dcc.adapters.meter import _validate_meter_id, ValidationError_
        with self.assertRaises(ValidationError_):
            _validate_meter_id("")

    def test_modbus_crc16(self):
        from dcc.adapters.meter import _modbus_crc16
        crc = _modbus_crc16(b"\x01\x03\x00\x00\x00\x01")
        self.assertIsInstance(crc, int)

    def test_build_modbus_request(self):
        from dcc.adapters.meter import _build_modbus_request
        request = _build_modbus_request(1, 1, 3, 0, 1)
        self.assertIsInstance(request, bytes)
        self.assertEqual(len(request), 12)
        # MBAP header: transaction id, protocol id, length, unit id
        self.assertEqual(request[:2], b"\x00\x01")
        self.assertEqual(request[6], 1)

    def test_decode_register_value(self):
        from dcc.adapters.meter import _decode_register_value
        value, raw = _decode_register_value([0x0064], "uint16", 1.0, "kWh")
        self.assertEqual(value, 100)
        self.assertEqual(raw, 100)

    def test_read_meter_data_modbus(self):
        from dcc.adapters.meter import read_meter_data
        # MBAP(tid=1,pid=0,len=5,uid=1) + fc=3 + byte_count=2 + one uint16 register
        mock_response = b"\x00\x01\x00\x00\x00\x05\x01\x03\x02\x00\x64"

        class MockSocket:
            """Streaming socket double: recv() honours bufsize like a real socket."""
            def __init__(self):
                self.sent = None
                self._buf = mock_response
            def connect(self, addr): pass
            def settimeout(self, timeout): pass
            def sendall(self, data): self.sent = data
            def recv(self, bufsize):
                chunk, self._buf = self._buf[:bufsize], self._buf[bufsize:]
                return chunk
            def close(self): pass

        with patch("dcc.adapters.meter.socket.socket", return_value=MockSocket()):
            result = read_meter_data(
                protocol="modbus_tcp",
                host="192.168.1.1",
                port=502,
                unit_id=1,
                registers=[{"address": 0, "unit": "kWh", "meter_id": "m1"}],
            )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].meter_id, "m1")
        self.assertEqual(result[0].value, 100.0)
        self.assertEqual(result[0].quality.value, "good")

    def test_read_meter_data_rejects_invalid_protocol(self):
        from dcc.adapters.meter import read_meter_data, ValidationError_
        with self.assertRaises(ValidationError_):
            read_meter_data(protocol="invalid_protocol", host="127.0.0.1")

    def test_reading_to_dict(self):
        from dcc.adapters.meter import MeterReading, reading_to_dict, QualityStatus
        reading = MeterReading(
            meter_id="m1",
            observed_at="2026-01-01T00:00:00Z",
            value=100.0,
            unit="kWh",
            quality=QualityStatus.GOOD,
            protocol="modbus_tcp",
            source_address="192.168.1.1:502",
        )
        result = reading_to_dict(reading)
        self.assertEqual(result["meter_id"], "m1")
        self.assertEqual(result["value"], 100.0)


class TestOEMAdapterIntegration(unittest.TestCase):
    """Integration tests for the OEM Redfish adapter."""

    def test_probe_success(self):
        from dcc.adapters.oem import probe
        mock_root = {"RedfishVersion": "1.0.0", "Vendor": "Dell"}
        mock_systems = {"Members": []}

        class RootResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_root).encode()

        class SystemsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_systems).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return RootResponse()
                return SystemsResponse()

        env = {"OEM_USERNAME": "admin", "OEM_PASSWORD": "password"}
        with patch("dcc.adapters.oem.urllib.request.build_opener", return_value=Opener()):
            with patch.dict("os.environ", env):
                result = probe(endpoint="https://oem.example.com", vendor="dell")
        self.assertTrue(result["probe_success"])

    def test_probe_rejects_http(self):
        from dcc.adapters.oem import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://oem.example.com")

    def test_probe_rejects_invalid_vendor(self):
        from dcc.adapters.oem import probe
        with self.assertRaises(ValueError):
            probe(endpoint="https://oem.example.com", vendor="invalid")

    def test_fetch_telemetry_success(self):
        from dcc.adapters.oem import fetch_telemetry
        mock_collection = {"Members": [{"@odata.id": "/redfish/v1/Systems/1"}]}
        mock_resource = {"Id": "1", "Name": "Server 1", "Power": {"PowerControl": [{"PowerConsumedWatts": 500}]}}

        class CollectionResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_collection).encode()

        class ResourceResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_resource).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return CollectionResponse()
                return ResourceResponse()

        env = {"OEM_USERNAME": "admin", "OEM_PASSWORD": "password"}
        with patch("dcc.adapters.oem.urllib.request.build_opener", return_value=Opener()):
            with patch.dict("os.environ", env):
                result = fetch_telemetry(endpoint="https://oem.example.com", vendor="dell", resource_type="systems")
        self.assertEqual(len(result["telemetry"]), 1)

    def test_fetch_telemetry_rejects_invalid_resource_type(self):
        from dcc.adapters.oem import fetch_telemetry
        with self.assertRaises(ValueError):
            fetch_telemetry(endpoint="https://oem.example.com", vendor="dell", resource_type="invalid")

    def test_fetch_telemetry_rejects_invalid_metrics(self):
        from dcc.adapters.oem import fetch_telemetry
        with self.assertRaises(ValueError):
            fetch_telemetry(endpoint="https://oem.example.com", vendor="dell", metrics=["invalid_metric"])

    def test_fetch_telemetry_rejects_too_many_metrics(self):
        from dcc.adapters.oem import fetch_telemetry
        with self.assertRaises(ValueError):
            fetch_telemetry(endpoint="https://oem.example.com", vendor="dell", metrics=[f"m{i}" for i in range(21)])

    def test_health_check_success(self):
        from dcc.adapters.oem import health_check
        mock_root = {"RedfishVersion": "1.0.0", "Vendor": "Dell"}
        mock_systems = {"Members": [{"@odata.id": "/redfish/v1/Systems/1"}]}
        mock_resource = {"Status": {"State": "Enabled"}}

        class RootResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_root).encode()

        class SystemsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_systems).encode()

        class ResourceResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_resource).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return RootResponse()
                elif self.call_count == 2:
                    return SystemsResponse()
                return ResourceResponse()

        env = {"OEM_USERNAME": "admin", "OEM_PASSWORD": "password"}
        with patch("dcc.adapters.oem.urllib.request.build_opener", return_value=Opener()):
            with patch.dict("os.environ", env):
                result = health_check(endpoint="https://oem.example.com", vendor="dell")
        self.assertTrue(result["healthy"])


class TestUtilityAdapterIntegration(unittest.TestCase):
    """Integration tests for the utility adapter."""

    def test_probe_success(self):
        from dcc.adapters.utility import probe
        mock_data = {"version": "1.0", "scopes": ["tariffs"]}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.utility.urllib.request.build_opener", return_value=Opener()):
            result = probe(endpoint="https://utility.example.com/api")
        self.assertTrue(result["probe_success"])

    def test_probe_rejects_http(self):
        from dcc.adapters.utility import probe
        with self.assertRaises(ValueError):
            probe(endpoint="http://utility.example.com/api")

    def test_fetch_tariffs_success(self):
        from dcc.adapters.utility import fetch_tariffs
        mock_data = {
            "tariffs": [
                {"tariff_id": "t1", "tariff_code": "RES-1", "provider": "Utility Co"},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.utility.urllib.request.build_opener", return_value=Opener()):
            result = fetch_tariffs(endpoint="https://utility.example.com/api")
        self.assertEqual(len(result["tariffs"]), 1)

    def test_fetch_tariffs_rejects_invalid_tariff_code(self):
        from dcc.adapters.utility import fetch_tariffs
        with self.assertRaises(ValueError):
            fetch_tariffs(endpoint="https://utility.example.com/api", tariff_code="invalid!")

    def test_fetch_tariffs_rejects_invalid_since(self):
        from dcc.adapters.utility import fetch_tariffs
        with self.assertRaises(ValueError):
            fetch_tariffs(endpoint="https://utility.example.com/api", since="not-a-date")

    def test_fetch_bills_success(self):
        from dcc.adapters.utility import fetch_bills
        mock_data = {
            "bills": [
                {"bill_id": "b1", "account_number": "ACC-1", "total_amount": 100.0},
            ]
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.utility.urllib.request.build_opener", return_value=Opener()):
            result = fetch_bills(endpoint="https://utility.example.com/api")
        self.assertEqual(len(result["bills"]), 1)

    def test_fetch_bills_rejects_invalid_account_number(self):
        from dcc.adapters.utility import fetch_bills
        with self.assertRaises(ValueError):
            fetch_bills(endpoint="https://utility.example.com/api", account_number="invalid!")

    def test_fetch_rate_schedule_success(self):
        from dcc.adapters.utility import fetch_rate_schedule
        mock_data = {
            "schedule": {
                "tariff_code": "RES-1",
                "name": "Residential",
                "rate_components": [{"name": "energy", "unit": "kWh", "rate": 0.12}],
            }
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.utility.urllib.request.build_opener", return_value=Opener()):
            result = fetch_rate_schedule(tariff_code="RES-1", endpoint="https://utility.example.com/api")
        self.assertIn("schedule", result)

    def test_fetch_rate_schedule_rejects_invalid_tariff_code(self):
        from dcc.adapters.utility import fetch_rate_schedule
        with self.assertRaises(ValueError):
            fetch_rate_schedule(tariff_code="invalid!", endpoint="https://utility.example.com/api")

    def test_health_check_success(self):
        from dcc.adapters.utility import health_check
        mock_info = {"version": "1.0", "scopes": []}
        mock_tariffs = {"tariffs": [{"valid_from": "2026-01-01T00:00:00Z"}]}

        class InfoResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_info).encode()

        class TariffsResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_tariffs).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return InfoResponse()
                return TariffsResponse()

        with patch("dcc.adapters.utility.urllib.request.build_opener", return_value=Opener()):
            result = health_check(endpoint="https://utility.example.com/api")
        self.assertTrue(result["healthy"])


class TestWeatherAdapterIntegration(unittest.TestCase):
    """Integration tests for the weather adapter."""

    def test_fetch_weather_success(self):
        from dcc.adapters.weather import fetch_weather
        mock_data = {
            "current": {"temperature_2m": 20.0, "relative_humidity_2m": 50.0},
            "daily": {"time": ["2026-01-01"], "temperature_2m_max": [25.0]},
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.weather.urllib.request.build_opener", return_value=Opener()):
            result = fetch_weather(latitude="40.7128", longitude="-74.0060")
        self.assertEqual(result["provider"], "Open-Meteo")

    def test_fetch_weather_rejects_invalid_latitude(self):
        from dcc.adapters.weather import fetch_weather
        with self.assertRaises(ValueError):
            fetch_weather(latitude="91.0", longitude="-74.0060")

    def test_fetch_weather_rejects_invalid_longitude(self):
        from dcc.adapters.weather import fetch_weather
        with self.assertRaises(ValueError):
            fetch_weather(latitude="40.7128", longitude="-181.0")

    def test_fetch_weather_rejects_invalid_forecast_days(self):
        from dcc.adapters.weather import fetch_weather
        with self.assertRaises(ValueError):
            fetch_weather(latitude="40.7128", longitude="-74.0060", forecast_days=0)

    def test_fetch_weather_rejects_forecast_days_over_7(self):
        from dcc.adapters.weather import fetch_weather
        with self.assertRaises(ValueError):
            fetch_weather(latitude="40.7128", longitude="-74.0060", forecast_days=8)

    def test_fetch_carbon_intensity_success(self):
        from dcc.adapters.weather import fetch_carbon_intensity
        mock_data = {"carbonIntensity": 400.0, "zone": "US-NY-NYIS"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_data).encode()

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dcc.adapters.weather.urllib.request.build_opener", return_value=Opener()):
            result = fetch_carbon_intensity(latitude="40.7128", longitude="-74.0060", api_key="test-key")
        self.assertEqual(result["provider"], "Electricity Maps")

    def test_fetch_carbon_intensity_rejects_missing_key(self):
        from dcc.adapters.weather import fetch_carbon_intensity
        with self.assertRaises(ConnectionError):
            fetch_carbon_intensity(latitude="40.7128", longitude="-74.0060")

    def test_fetch_weather_and_carbon_success(self):
        from dcc.adapters.weather import fetch_weather_and_carbon
        mock_weather = {
            "current": {"temperature_2m": 20.0},
            "daily": {"time": ["2026-01-01"]},
        }
        mock_carbon = {"carbonIntensity": 400.0}

        class WeatherResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_weather).encode()

        class CarbonResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_carbon).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return WeatherResponse()
                return CarbonResponse()

        with patch("dcc.adapters.weather.urllib.request.build_opener", return_value=Opener()):
            result = fetch_weather_and_carbon(latitude="40.7128", longitude="-74.0060", carbon_api_key="test-key")
        self.assertIn("weather", result)
        self.assertIn("carbon_intensity", result)

    def test_fetch_weather_and_carbon_handles_carbon_failure(self):
        from dcc.adapters.weather import fetch_weather_and_carbon
        mock_weather = {
            "current": {"temperature_2m": 20.0},
            "daily": {"time": ["2026-01-01"]},
        }

        class WeatherResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(mock_weather).encode()

        class Opener:
            def __init__(self): self.call_count = 0
            def open(self, request, timeout):
                self.call_count += 1
                if self.call_count == 1:
                    return WeatherResponse()
                raise ConnectionError("no key")

        with patch("dcc.adapters.weather.urllib.request.build_opener", return_value=Opener()):
            result = fetch_weather_and_carbon(latitude="40.7128", longitude="-74.0060")
        self.assertIn("weather", result)
        self.assertIsNone(result["carbon_intensity"])
        self.assertIsNotNone(result["carbon_error"])


if __name__ == "__main__":
    unittest.main()
