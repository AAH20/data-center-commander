import json
import unittest
from unittest.mock import patch

from dcc.api import Handler
from dcc.azure_prices import ENDPOINT, fetch_azure_retail_prices
from dcc.google_prices import fetch_google_cloud_prices


class AzureRetailPricesTests(unittest.TestCase):
    def test_fixed_endpoint_bounded_query_and_price_provenance(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({"Items": [{
                    "serviceName": "Virtual Machines", "armRegionName": "eastus",
                    "armSkuName": "Standard_D2s_v5", "retailPrice": 0.096,
                    "unitOfMeasure": "1 Hour", "currencyCode": "USD",
                    "effectiveStartDate": "2026-01-01T00:00:00Z", "priceType": "Consumption",
                }]}).encode()

        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return Response()

        opener = Opener()
        with patch("dcc.azure_prices.urllib.request.build_opener", return_value=opener):
            result = fetch_azure_retail_prices(service_name="Virtual Machines", region="eastus", sku="Standard_D2s_v5")
        self.assertTrue(opener.request.full_url.startswith(ENDPOINT + "?"))
        self.assertEqual(opener.timeout, 8)
        self.assertEqual(result["prices"][0]["retailPrice"], "0.096")
        self.assertFalse(result["persisted"])
        self.assertFalse(result["execution_permitted"])
        self.assertIn("Public retail list rates only", result["commercial_basis"])

    def test_rejects_invalid_inputs_before_network_access(self):
        with patch("dcc.azure_prices.urllib.request.build_opener") as build:
            with self.assertRaises(ValueError):
                fetch_azure_retail_prices(service_name="Virtual Machines' or name eq 'x")
            with self.assertRaises(ValueError):
                fetch_azure_retail_prices(service_name="Virtual Machines", currency="USDX")
        build.assert_not_called()

    def test_http_route_requires_one_tenant_and_returns_read_only_result(self):
        class FakeHandler:
            path = "/v1/pricing/azure-retail?tenant_id=dcc00000-0000-4000-8000-000000000001"
            def respond(self, status, body): self.result = (status, body)

        handler = FakeHandler()
        with patch("dcc.azure_prices.fetch_azure_retail_prices", return_value={"prices": [], "execution_permitted": False}) as fetch:
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 200)
        self.assertFalse(handler.result[1]["execution_permitted"])
        self.assertEqual(fetch.call_args.kwargs["service_name"], "Virtual Machines")

        handler.path = "/v1/pricing/azure-retail?tenant_id=bad"
        Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 400)

    def test_google_catalog_is_fixed_bounded_and_marks_tiered_rates_non_linear(self):
        class MockResponse:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps(self.payload).encode()

        class Opener:
            def __init__(self): self.calls = []
            def open(self, request, timeout):
                self.calls.append((request.full_url, timeout))
                if len(self.calls) == 1:
                    return MockResponse({"services": [{"displayName": "Compute Engine", "serviceId": "6F81-5844-456A"}]})
                return MockResponse({"skus": [
                    {"skuId": "SKU-1", "description": "N2 Instance Core running", "serviceRegions": ["us-central1"], "category": {"usageType": "OnDemand"}, "pricingInfo": [{"effectiveTime": "2026-09-01T00:00:00Z", "pricingExpression": {"usageUnitDescription": "hour", "tieredRates": [{"startUsageAmount": 0, "unitPrice": {"units": "0", "nanos": 96000000}}]}}]},
                    {"skuId": "SKU-2", "description": "N2 Instance Core tiered", "serviceRegions": ["us-central1"], "pricingInfo": [{"pricingExpression": {"tieredRates": [{"startUsageAmount": 0, "unitPrice": {"units": "0", "nanos": 0}}, {"startUsageAmount": 100, "unitPrice": {"units": "1", "nanos": 0}}]}}]},
                ], "nextPageToken": "bounded-next-page"})

        opener = Opener()
        with patch("dcc.google_prices.urllib.request.build_opener", return_value=opener):
            result = fetch_google_cloud_prices(service_name="Compute Engine", region="us-central1", sku_query="N2 Instance Core", api_key="not-returned")
        self.assertEqual(len(opener.calls), 2)
        self.assertTrue(all(url.startswith("https://cloudbilling.googleapis.com/v1/") for url, _ in opener.calls))
        self.assertTrue(all(timeout == 8 for _, timeout in opener.calls))
        self.assertEqual(result["prices"][0]["retailPrice"], "0.096")
        self.assertTrue(result["prices"][0]["estimate_eligible"])
        self.assertFalse(result["prices"][1]["estimate_eligible"])
        self.assertIsNone(result["prices"][1]["retailPrice"])
        self.assertTrue(result["truncated"])
        self.assertNotIn("not-returned", repr(result))

    def test_google_catalog_requires_server_key_before_network(self):
        with patch("dcc.google_prices.urllib.request.build_opener") as build, self.assertRaisesRegex(ConnectionError, "GOOGLE_CLOUD_BILLING_API_KEY"):
            fetch_google_cloud_prices(service_name="Compute Engine", region="us-central1", sku_query="N2 Instance Core", api_key="")
        build.assert_not_called()

    def test_google_http_route_is_tenant_scoped_and_reports_missing_server_key(self):
        class FakeHandler:
            path = "/v1/pricing/google-cloud-retail?tenant_id=dcc00000-0000-4000-8000-000000000001&region=us-central1&sku_query=N2"
            def respond(self, status, body): self.result = (status, body)

        handler = FakeHandler()
        with patch("dcc.google_prices.fetch_google_cloud_prices", side_effect=ConnectionError("GOOGLE_CLOUD_BILLING_API_KEY is not configured in the server environment")):
            Handler.do_GET(handler)
        self.assertEqual(handler.result[0], 503)
        self.assertFalse(handler.result[1]["execution_permitted"])


if __name__ == "__main__":
    unittest.main()
