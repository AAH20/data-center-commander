"""Unit tests for dcc.azure_prices module."""
import unittest
from unittest.mock import patch, MagicMock

from dcc.azure_prices import (
    ENDPOINT,
    API_VERSION,
    MAX_RESPONSE_BYTES,
    MAX_ROWS,
    fetch_azure_retail_prices,
)


class TestConstants(unittest.TestCase):
    def test_endpoint(self):
        self.assertEqual(ENDPOINT, "https://prices.azure.com/api/retail/prices")

    def test_api_version(self):
        self.assertEqual(API_VERSION, "2023-01-01-preview")

    def test_max_response_bytes(self):
        self.assertEqual(MAX_RESPONSE_BYTES, 1_000_000)

    def test_max_rows(self):
        self.assertEqual(MAX_ROWS, 100)


class TestFetchAzureRetailPrices(unittest.TestCase):
    def test_invalid_service_name(self):
        with self.assertRaises(ValueError):
            fetch_azure_retail_prices(service_name="")

    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            fetch_azure_retail_prices(service_name="Compute", currency="INVALID")

    def test_invalid_service_name_chars(self):
        with self.assertRaises(ValueError):
            fetch_azure_retail_prices(service_name="test@name")

    def test_invalid_region_chars(self):
        with self.assertRaises(ValueError):
            fetch_azure_retail_prices(service_name="Compute", region="test@region")

    def test_invalid_sku_chars(self):
        with self.assertRaises(ValueError):
            fetch_azure_retail_prices(service_name="Compute", sku="test@sku")


if __name__ == "__main__":
    unittest.main()
