import json
import unittest
from unittest.mock import patch

from dcc.adapters.cmms import (
    fetch_assets,
    fetch_schedules,
    fetch_work_orders,
    probe_cmms,
)


class CMMSAdapterTests(unittest.TestCase):
    def test_probe_validates_endpoint_before_network(self):
        with patch("dcc.adapters.cmms.urllib.request.build_opener") as build:
            with self.assertRaises(ValueError):
                probe_cmms(endpoint="http://cmms.example.com/api/v1")
            with self.assertRaises(ValueError):
                probe_cmms(endpoint="https://evil.com/api/v1")
            with self.assertRaises(ValueError):
                probe_cmms(endpoint="")
        build.assert_not_called()

    def test_probe_requires_api_key_before_network(self):
        with patch("dcc.adapters.cmms.urllib.request.build_opener") as build:
            with self.assertRaisesRegex(ConnectionError, "CMMS_API_KEY"):
                probe_cmms(endpoint="https://cmms.example.com/api/v1", api_key="")
        build.assert_not_called()

    def test_probe_returns_health_status(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({"data": []}).encode()

        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = probe_cmms(endpoint="https://cmms.example.com/api/v1", api_key="test-key")
        self.assertEqual(result["status"], "healthy")
        self.assertTrue(result["work_orders_accessible"])
        self.assertFalse(result["persisted"])
        self.assertFalse(result["execution_permitted"])
        self.assertEqual(opener.timeout, 8)

    def test_fetch_work_orders_bounded_and_safe(self):
        class Response:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(self.payload).encode()

        class Opener:
            def __init__(self): self.calls = []
            def open(self, request, timeout):
                self.calls.append((request.full_url, timeout))
                return Response({
                    "data": [
                        {
                            "id": "wo-1",
                            "title": "Replace UPS battery",
                            "status": "open",
                            "priority": "high",
                            "asset_id": "asset-1",
                            "asset_name": "UPS-A",
                            "work_type": "corrective",
                            "scheduled_start": "2026-10-01T08:00:00Z",
                            "estimated_hours": "4.5",
                            "cost_estimate": "1200.00",
                            "failure_code": "BAT-001",
                        },
                        {
                            "id": "wo-2",
                            "title": "HVAC filter change",
                            "status": "scheduled",
                            "priority": "normal",
                            "asset_id": "asset-2",
                            "work_type": "preventive",
                            "next_due": "2026-10-15T00:00:00Z",
                        },
                    ],
                    "next_page": None,
                })

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_work_orders(
                endpoint="https://cmms.example.com/api/v1",
                api_key="test-key",
                status="open",
                limit=50,
            )
        self.assertEqual(len(opener.calls), 1)
        url, timeout = opener.calls[0]
        self.assertTrue(url.startswith("https://cmms.example.com/api/v1/work-orders?"))
        self.assertIn("limit=50", url)
        self.assertIn("status=open", url)
        self.assertEqual(timeout, 8)
        self.assertEqual(result["returned"], 2)
        self.assertFalse(result["truncated"])
        self.assertFalse(result["persisted"])
        self.assertFalse(result["execution_permitted"])
        self.assertEqual(result["work_orders"][0]["id"], "wo-1")
        self.assertEqual(result["work_orders"][0]["title"], "Replace UPS battery")
        self.assertEqual(result["work_orders"][0]["estimated_hours"], "4.5")
        self.assertEqual(result["work_orders"][1]["id"], "wo-2")

    def test_fetch_work_orders_rejects_invalid_limit(self):
        with patch("dcc.adapters.cmms.urllib.request.build_opener") as build:
            with self.assertRaises(ValueError):
                fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k", limit=0)
            with self.assertRaises(ValueError):
                fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k", limit=999)
            with self.assertRaises(ValueError):
                fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k", limit=True)
        build.assert_not_called()

    def test_fetch_work_orders_rejects_invalid_status(self):
        with patch("dcc.adapters.cmms.urllib.request.build_opener") as build:
            with self.assertRaises(ValueError):
                fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k", status="open;DROP")
        build.assert_not_called()

    def test_fetch_assets_bounded_and_safe(self):
        class Response:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(self.payload).encode()

        class Opener:
            def open(self, request, timeout):
                return Response({
                    "data": [
                        {
                            "id": "asset-1",
                            "name": "UPS-A",
                            "asset_type": "ups",
                            "status": "active",
                            "location": "DC1-Room-A",
                            "serial_number": "SN12345",
                            "manufacturer": "APC",
                            "model": "Symmetra 100kVA",
                            "criticality": "critical",
                        },
                    ],
                })

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_assets(
                endpoint="https://cmms.example.com/api/v1",
                api_key="test-key",
                asset_type="ups",
            )
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["assets"][0]["id"], "asset-1")
        self.assertEqual(result["assets"][0]["name"], "UPS-A")
        self.assertEqual(result["assets"][0]["criticality"], "critical")
        self.assertFalse(result["persisted"])
        self.assertFalse(result["execution_permitted"])

    def test_fetch_schedules_bounded_and_safe(self):
        class Response:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(self.payload).encode()

        class Opener:
            def open(self, request, timeout):
                return Response({
                    "data": [
                        {
                            "id": "sched-1",
                            "title": "Quarterly UPS maintenance",
                            "schedule_type": "preventive",
                            "asset_id": "asset-1",
                            "asset_name": "UPS-A",
                            "frequency": "quarterly",
                            "next_due": "2026-12-01T00:00:00Z",
                            "estimated_hours": "8.0",
                            "status": "active",
                        },
                    ],
                })

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_schedules(
                endpoint="https://cmms.example.com/api/v1",
                api_key="test-key",
                schedule_type="preventive",
            )
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["schedules"][0]["id"], "sched-1")
        self.assertEqual(result["schedules"][0]["frequency"], "quarterly")
        self.assertFalse(result["persisted"])
        self.assertFalse(result["execution_permitted"])

    def test_malformed_response_raises_connection_error(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"not json"

        class Opener:
            def open(self, request, timeout):
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ConnectionError, "invalid JSON"):
                fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k")

    def test_non_dict_response_raises_connection_error(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps([1, 2, 3]).encode()

        class Opener:
            def open(self, request, timeout):
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ConnectionError, "did not match"):
                fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k")

    def test_missing_data_key_returns_empty_list(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps({"unexpected": []}).encode()

        class Opener:
            def open(self, request, timeout):
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k")
        self.assertEqual(result["work_orders"], [])
        self.assertEqual(result["returned"], 0)

    def test_api_key_never_in_output(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps({"data": []}).encode()

        class Opener:
            def open(self, request, timeout):
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="secret-key-123")
        self.assertNotIn("secret-key-123", repr(result))

    def test_truncation_detected(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({"data": [{"id": f"wo-{i}"} for i in range(5)], "next_page": "url"}).encode()

        class Opener:
            def open(self, request, timeout):
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k", limit=5)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["returned"], 5)

    def test_none_values_stripped_from_rows(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({"data": [{"id": "wo-1", "title": "Test", "status": None, "priority": "high"}]}).encode()

        class Opener:
            def open(self, request, timeout):
                return Response()

        opener = Opener()
        with patch("dcc.adapters.cmms.urllib.request.build_opener", return_value=opener):
            result = fetch_work_orders(endpoint="https://cmms.example.com/api/v1", api_key="k")
        self.assertNotIn("status", result["work_orders"][0])
        self.assertEqual(result["work_orders"][0]["priority"], "high")


if __name__ == "__main__":
    unittest.main()
