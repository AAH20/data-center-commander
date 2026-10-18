"""Unit tests for dcc.google_prices module."""
import unittest
from unittest.mock import patch, MagicMock

from dcc.google_prices import (
    BASE,
    MAX_RESPONSE_BYTES,
    MAX_SKU_PAGE,
    MAX_ROWS,
    fetch_google_cloud_prices,
)


class TestConstants(unittest.TestCase):
    def test_base(self):
        self.assertEqual(BASE, "https://cloudbilling.googleapis.com/v1")

    def test_max_response_bytes(self):
        self.assertEqual(MAX_RESPONSE_BYTES, 2_000_000)

    def test_max_sku_page(self):
        self.assertEqual(MAX_SKU_PAGE, 1000)

    def test_max_rows(self):
        self.assertEqual(MAX_ROWS, 100)


class TestFetchGoogleCloudPrices(unittest.TestCase):
    def test_invalid_service_name(self):
        with self.assertRaises(ValueError):
            fetch_google_cloud_prices(service_name="", region="us-east1", sku_query="test")

    def test_invalid_region(self):
        with self.assertRaises(ValueError):
            fetch_google_cloud_prices(service_name="Compute", region="", sku_query="test")

    def test_invalid_sku_query(self):
        with self.assertRaises(ValueError):
            fetch_google_cloud_prices(service_name="Compute", region="us-east1", sku_query="")

    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            fetch_google_cloud_prices(service_name="Compute", region="us-east1", sku_query="test", currency="INVALID")


if __name__ == "__main__":
    unittest.main()
