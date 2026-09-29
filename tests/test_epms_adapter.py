"""Tests for the EPMS adapter."""
import json
import unittest
from unittest.mock import patch, MagicMock

from dcc.adapters.epms import (
    EPMSCapability,
    EPMSConfig,
    GenericEPMSAdapter,
    MeterReading,
    BreakerStatus,
    UPSStatus,
    AlarmEvent,
    create_epms_adapter,
    _validate_point_id,
    _validate_iso_timestamp,
    _safe_float,
    _safe_decimal,
    MAX_POINTS_PER_QUERY,
    MAX_ALARMS_PER_QUERY,
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


class EPMSFactoryTests(unittest.TestCase):
    def test_create_adapter_with_valid_config(self):
        adapter = create_epms_adapter(
            endpoint="https://epms.example.com/api",
            api_version="v2",
            vendor="Schneider",
            product="EcoStruxure",
            site_timezone="Africa/Cairo",
        )
        self.assertEqual(adapter.config.endpoint, "https://epms.example.com/api")
        self.assertEqual(adapter.config.api_version, "v2")
        self.assertEqual(adapter.config.vendor, "Schneider")
        self.assertEqual(adapter.config.product, "EcoStruxure")
        self.assertEqual(adapter.config.site_timezone, "Africa/Cairo")

    def test_rejects_non_https_endpoint(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            create_epms_adapter(endpoint="http://epms.example.com")

    def test_rejects_invalid_api_version(self):
        with self.assertRaisesRegex(ValueError, "api_version"):
            create_epms_adapter(
                endpoint="https://epms.example.com",
                api_version="v1; DROP TABLE",
            )

    def test_rejects_invalid_rate_limit(self):
        with self.assertRaisesRegex(ValueError, "rate_limit"):
            create_epms_adapter(
                endpoint="https://epms.example.com",
                rate_limit_per_minute=0,
            )

    def test_rejects_invalid_timeout(self):
        with self.assertRaisesRegex(ValueError, "timeout"):
            create_epms_adapter(
                endpoint="https://epms.example.com",
                timeout_s=0.1,
            )

    def test_rejects_long_endpoint(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            create_epms_adapter(endpoint="https://example.com/" + "a" * 3000)


class EPMSValidationTests(unittest.TestCase):
    def test_validate_point_id_accepts_valid(self):
        self.assertEqual(_validate_point_id("MTR-01"), "MTR-01")
        self.assertEqual(_validate_point_id("bus/section1/point-2"), "bus/section1/point-2")

    def test_validate_point_id_rejects_invalid(self):
        for bad in ("", "a" * 121, "point id", "point;id", "point'id"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_point_id(bad)

    def test_validate_iso_timestamp_accepts_valid(self):
        self.assertEqual(
            _validate_iso_timestamp("2026-09-29T10:00:00Z", "since"),
            "2026-09-29T10:00:00Z",
        )
        self.assertEqual(
            _validate_iso_timestamp("2026-09-29T10:00:00+03:00", "since"),
            "2026-09-29T10:00:00+03:00",
        )

    def test_validate_iso_timestamp_rejects_invalid(self):
        for bad in ("", "yesterday", "2026-13-01", "not-a-date"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_iso_timestamp(bad, "since")

    def test_safe_float(self):
        self.assertEqual(_safe_float(42), 42.0)
        self.assertEqual(_safe_float("3.14"), 3.14)
        self.assertIsNone(_safe_float(None))
        self.assertIsNone(_safe_float("abc"))
        self.assertIsNone(_safe_float(float("nan")))
        self.assertIsNone(_safe_float(float("inf")))
        self.assertEqual(_safe_float(-5, min_val=0), None)
        self.assertEqual(_safe_float(50, min_val=0, max_val=100), 50.0)
        self.assertEqual(_safe_float(150, min_val=0, max_val=100), None)

    def test_safe_decimal(self):
        self.assertEqual(_safe_decimal("123.45").__str__(), "123.45")
        self.assertIsNone(_safe_decimal(None))
        self.assertIsNone(_safe_decimal("abc"))
        self.assertIsNone(_safe_decimal(float("nan")))


class EPMSAdapterHealthTests(unittest.TestCase):
    def test_health_check_success(self):
        opener = FakeOpener([{"status": "ok"}])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            self.assertTrue(adapter.health_check())
        self.assertEqual(len(opener.calls), 1)
        self.assertIn("/health", opener.calls[0][0])

    def test_health_check_failure(self):
        opener = FakeOpener([{"status": "error"}])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            self.assertFalse(adapter.health_check())

    def test_health_check_connection_error(self):
        with patch("dcc.adapters.epms.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            self.assertFalse(adapter.health_check())


class EPMSAdapterMeterTests(unittest.TestCase):
    def test_read_meters_success(self):
        payload = {
            "readings": [
                {"pointId": "MTR-01", "meterId": "meter-fac-01", "timestamp": "2026-09-29T10:00:00Z",
                 "value": 1234.5, "unit": "kW", "quality": "good"},
                {"pointId": "MTR-02", "meterId": "meter-it-01", "timestamp": "2026-09-29T10:00:00Z",
                 "value": 567.8, "unit": "kW", "quality": "good"},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            readings = adapter.read_meters()
        self.assertEqual(len(readings), 2)
        self.assertEqual(readings[0].point_id, "MTR-01")
        self.assertEqual(readings[0].value, 1234.5)
        self.assertEqual(readings[0].unit, "kW")
        self.assertEqual(readings[1].point_id, "MTR-02")

    def test_read_meters_with_point_ids(self):
        payload = {"readings": [
            {"pointId": "MTR-01", "meterId": "meter-fac-01", "timestamp": "2026-09-29T10:00:00Z",
             "value": 100.0, "unit": "kW"},
        ]}
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            readings = adapter.read_meters(point_ids=["MTR-01"])
        self.assertEqual(len(readings), 1)
        self.assertIn("pointIds=MTR-01", opener.calls[0][0])

    def test_read_meters_with_since(self):
        payload = {"readings": []}
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            adapter.read_meters(since="2026-09-01T00:00:00Z")
        self.assertIn("since=2026-09-01", opener.calls[0][0])

    def test_read_meters_rejects_too_many_points(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        with self.assertRaisesRegex(ValueError, "exceeds maximum"):
            adapter.read_meters(point_ids=[f"P-{i}" for i in range(MAX_POINTS_PER_QUERY + 1)])

    def test_read_meters_skips_invalid_entries(self):
        payload = {
            "readings": [
                {"pointId": "MTR-01", "timestamp": "2026-09-29T10:00:00Z", "value": 100, "unit": "kW"},
                {"pointId": "", "timestamp": "2026-09-29T10:00:00Z", "value": 200, "unit": "kW"},
                {"pointId": "MTR-03", "timestamp": "2026-09-29T10:00:00Z", "value": "bad", "unit": "kW"},
                {"pointId": "MTR-04", "timestamp": "2026-09-29T10:00:00Z", "value": 300, "unit": ""},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            readings = adapter.read_meters()
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].point_id, "MTR-01")

    def test_read_meters_empty_response(self):
        opener = FakeOpener([{"readings": []}])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            readings = adapter.read_meters()
        self.assertEqual(len(readings), 0)


class EPMSAdapterBreakerTests(unittest.TestCase):
    def test_read_breakers_success(self):
        payload = {
            "breakers": [
                {"pointId": "BRK-01", "breakerId": "breaker-01", "timestamp": "2026-09-29T10:00:00Z",
                 "state": "closed", "currentA": 45.2, "voltageV": 400.0, "quality": "good"},
                {"pointId": "BRK-02", "breakerId": "breaker-02", "timestamp": "2026-09-29T10:00:00Z",
                 "state": "open", "currentA": 0.0, "voltageV": 400.0},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            breakers = adapter.read_breakers()
        self.assertEqual(len(breakers), 2)
        self.assertEqual(breakers[0].state, "closed")
        self.assertEqual(breakers[0].current_a, 45.2)
        self.assertEqual(breakers[1].state, "open")

    def test_read_breakers_normalizes_unknown_state(self):
        payload = {
            "breakers": [
                {"pointId": "BRK-01", "timestamp": "2026-09-29T10:00:00Z", "state": "weird"},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            breakers = adapter.read_breakers()
        self.assertEqual(breakers[0].state, "unknown")


class EPMSAdapterUPSTests(unittest.TestCase):
    def test_read_ups_success(self):
        payload = {
            "ups": [
                {"pointId": "UPS-01", "upsId": "ups-01", "timestamp": "2026-09-29T10:00:00Z",
                 "onBattery": False, "loadPct": 65.0, "batteryPct": 100.0,
                 "runtimeMin": 45.0, "inputVoltageV": 400.0, "outputVoltageV": 400.0,
                 "quality": "good"},
                {"pointId": "UPS-02", "upsId": "ups-02", "timestamp": "2026-09-29T10:00:00Z",
                 "onBattery": True, "loadPct": 80.0, "batteryPct": 45.0,
                 "runtimeMin": 12.0, "inputVoltageV": 0.0, "outputVoltageV": 398.0},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            ups_list = adapter.read_ups()
        self.assertEqual(len(ups_list), 2)
        self.assertFalse(ups_list[0].on_battery)
        self.assertEqual(ups_list[0].load_pct, 65.0)
        self.assertTrue(ups_list[1].on_battery)
        self.assertEqual(ups_list[1].battery_pct, 45.0)

    def test_read_ups_clamps_out_of_range(self):
        payload = {
            "ups": [
                {"pointId": "UPS-01", "timestamp": "2026-09-29T10:00:00Z",
                 "onBattery": False, "loadPct": 200.0, "batteryPct": -5.0},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            ups_list = adapter.read_ups()
        self.assertIsNone(ups_list[0].load_pct)
        self.assertIsNone(ups_list[0].battery_pct)


class EPMSAdapterAlarmTests(unittest.TestCase):
    def test_read_alarms_success(self):
        payload = {
            "alarms": [
                {"alarmId": "ALM-001", "pointId": "UPS-01", "severity": "critical",
                 "message": "UPS on battery", "raisedAt": "2026-09-29T08:00:00Z",
                 "clearedAt": None, "acknowledged": False},
                {"alarmId": "ALM-002", "pointId": "BRK-01", "severity": "major",
                 "message": "Breaker tripped", "raisedAt": "2026-09-29T07:00:00Z",
                 "clearedAt": "2026-09-29T07:05:00Z", "acknowledged": True},
            ]
        }
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            alarms = adapter.read_alarms()
        self.assertEqual(len(alarms), 2)
        self.assertEqual(alarms[0].severity, "critical")
        self.assertFalse(alarms[0].acknowledged)
        self.assertIsNone(alarms[0].cleared_at)
        self.assertEqual(alarms[1].severity, "major")
        self.assertTrue(alarms[1].acknowledged)

    def test_read_alarms_with_filters(self):
        payload = {"alarms": []}
        opener = FakeOpener([payload])
        with patch("dcc.adapters.epms.urllib.request.build_opener", return_value=opener):
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            adapter.read_alarms(since="2026-09-01T00:00:00Z", severity="critical")
        url = opener.calls[0][0]
        self.assertIn("since=2026-09-01", url)
        self.assertIn("severity=critical", url)

    def test_read_alarms_rejects_invalid_severity(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        with self.assertRaisesRegex(ValueError, "severity"):
            adapter.read_alarms(severity="catastrophic")


class EPMSAdapterCapabilityTests(unittest.TestCase):
    def test_default_capabilities(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        self.assertTrue(adapter.supports(EPMSCapability.METER_READINGS))
        self.assertTrue(adapter.supports(EPMSCapability.BREAKER_STATUS))
        self.assertTrue(adapter.supports(EPMSCapability.UPS_STATUS))
        self.assertTrue(adapter.supports(EPMSCapability.ALARM_HISTORY))
        self.assertFalse(adapter.supports(EPMSCapability.POWER_QUALITY))
        self.assertFalse(adapter.supports(EPMSCapability.ENERGY_INTERVALS))

    def test_capabilities_property(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        caps = adapter.capabilities
        self.assertIn(EPMSCapability.METER_READINGS, caps)
        self.assertIn(EPMSCapability.BREAKER_STATUS, caps)
        self.assertIn(EPMSCapability.UPS_STATUS, caps)
        self.assertIn(EPMSCapability.ALARM_HISTORY, caps)


class EPMSAdapterMappingTests(unittest.TestCase):
    def test_map_to_canonical_full(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        mapping = adapter.map_to_canonical(
            point_id="MTR-01",
            asset_external_id="asset-001",
            meter_external_id="meter-001",
            metric_key="facility_energy_kwh",
        )
        self.assertEqual(mapping["point_id"], "MTR-01")
        self.assertEqual(mapping["confidence"], 0.9)
        self.assertIn("provenance", mapping)
        self.assertEqual(mapping["provenance"]["source"], "generic")

    def test_map_to_canonical_partial(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        mapping = adapter.map_to_canonical(
            point_id="MTR-01",
            asset_external_id="asset-001",
        )
        self.assertEqual(mapping["confidence"], 0.6)

    def test_map_to_canonical_minimal(self):
        adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
        mapping = adapter.map_to_canonical(point_id="MTR-01")
        self.assertEqual(mapping["confidence"], 0.3)


class EPMSAdapterSnapshotTests(unittest.TestCase):
    def test_snapshot(self):
        adapter = create_epms_adapter(
            endpoint="https://epms.example.com/api",
            vendor="Schneider",
            product="EcoStruxure",
        )
        snap = adapter.snapshot()
        self.assertEqual(snap["name"], "generic-epms")
        self.assertEqual(snap["vendor"], "Schneider")
        self.assertEqual(snap["product"], "EcoStruxure")
        self.assertIn("meter_readings", snap["capabilities"])
        self.assertFalse(snap["persisted"])
        self.assertFalse(snap["execution_permitted"])


class EPMSAdapterHTTPErrorTests(unittest.TestCase):
    def test_read_meters_connection_error(self):
        with patch("dcc.adapters.epms.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            with self.assertRaises(ConnectionError):
                adapter.read_meters()

    def test_read_breakers_connection_error(self):
        with patch("dcc.adapters.epms.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            with self.assertRaises(ConnectionError):
                adapter.read_breakers()

    def test_read_ups_connection_error(self):
        with patch("dcc.adapters.epms.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            with self.assertRaises(ConnectionError):
                adapter.read_ups()

    def test_read_alarms_connection_error(self):
        with patch("dcc.adapters.epms.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = ConnectionError("timeout")
            adapter = create_epms_adapter(endpoint="https://epms.example.com/api")
            with self.assertRaises(ConnectionError):
                adapter.read_alarms()


if __name__ == "__main__":
    unittest.main()
