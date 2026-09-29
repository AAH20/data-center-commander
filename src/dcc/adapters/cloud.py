"""Unified read-only cloud provider cost and usage adapter.

Supports AWS, Azure, and GCP public pricing catalogs.
All operations are bounded, read-only, and never persist data.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from ..azure_prices import fetch_azure_retail_prices
from ..google_prices import fetch_google_cloud_prices
from .registry import AdapterCapability, AdapterInfo, AdapterRegistry, get_registry

# Provider identifiers
Provider = Literal["aws", "azure", "gcp"]

# Endpoints
AWS_PRICING_ENDPOINT = "https://api.pricing.us-east-1.amazonaws.com/v1.0/offers"
AZURE_PRICING_ENDPOINT = "https://prices.azure.com/api/retail/prices"
GCP_BILLING_ENDPOINT = "https://cloudbilling.googleapis.com/v1"

# Limits
MAX_RESPONSE_BYTES = 2_000_000
MAX_ROWS = 100
TIMEOUT_SECONDS = 8

# AWS offer codes for common services
AWS_OFFER_CODES = {
    "ec2": "AmazonEC2",
    "s3": "AmazonS3",
    "rds": "AmazonRDS",
    "lambda": "AmazonLambda",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str, max_bytes: int = MAX_RESPONSE_BYTES) -> dict[str, Any]:
    """Fetch JSON from a URL with bounds."""
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ConnectionError(f"Response exceeded the {max_bytes // 1_000_000} MB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Response did not match expected contract")
    return payload


def _filter_value(value: str, field: str, pattern: str, *, required: bool = False) -> str:
    """Validate and filter a string value."""
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > 80 or (value and not re.fullmatch(pattern, value)):
        raise ValueError(f"{field} contains unsupported characters or is too long")
    return value


def _amount(value: Any) -> Decimal | None:
    """Parse a decimal amount."""
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def fetch_aws_prices(
    *,
    service: str,
    region: str = "",
    sku: str = "",
    currency: str = "USD",
) -> dict[str, Any]:
    """Fetch AWS public pricing data (bounded, read-only)."""
    service = _filter_value(service, "service", r"[A-Za-z0-9._-]+", required=True)
    region = _filter_value(region, "region", r"[A-Za-z0-9 ()._/-]*")
    sku = _filter_value(sku, "sku", r"[A-Za-z0-9._-]*")
    currency = currency.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter ISO currency code")

    # Map service to AWS offer code
    offer_code = AWS_OFFER_CODES.get(service.lower())
    if offer_code is None:
        raise ValueError(f"unsupported AWS service: {service}")

    # Query AWS Price List API
    url = f"{AWS_PRICING_ENDPOINT}/{offer_code}/index.json"
    payload = _get_json(url)

    # Extract products and pricing
    products = payload.get("products", {})
    terms = payload.get("terms", {}).get("OnDemand", {})
    if not isinstance(products, dict) or not isinstance(terms, dict):
        raise ConnectionError("AWS pricing response did not match expected contract")

    rows = []
    for product_id, product in products.items():
        if not isinstance(product, dict):
            continue
        attributes = product.get("attributes", {})
        if not isinstance(attributes, dict):
            continue

        # Filter by region if specified
        if region and attributes.get("location") != region:
            continue

        # Filter by SKU if specified
        if sku and sku.lower() not in product_id.lower():
            continue

        # Extract pricing
        for term_id, term in terms.items():
            if not isinstance(term, dict):
                continue
            if term.get("productId") != product_id:
                continue
            price_dimensions = term.get("priceDimensions", {})
            if not isinstance(price_dimensions, dict):
                continue
            for dim_id, dim in price_dimensions.items():
                if not isinstance(dim, dict):
                    continue
                price_per_unit = dim.get("pricePerUnit", {})
                if not isinstance(price_per_unit, dict):
                    continue
                price = _amount(price_per_unit.get(currency))
                if price is None:
                    continue
                rows.append({
                    "provider": "AWS",
                    "service": service,
                    "sku": product_id,
                    "region": attributes.get("location", ""),
                    "instance_type": attributes.get("instanceType", ""),
                    "price": str(price),
                    "currency": currency,
                    "unit": dim.get("unit", ""),
                })
                if len(rows) >= MAX_ROWS:
                    break
            if len(rows) >= MAX_ROWS:
                break
        if len(rows) >= MAX_ROWS:
            break

    return {
        "provider": "AWS Price List API",
        "api_version": "v1.0",
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_url": url,
        "query": {"service": service, "region": region or None, "sku": sku or None, "currency": currency},
        "prices": rows,
        "returned": len(rows),
        "truncated": len(rows) >= MAX_ROWS,
        "commercial_basis": "Public AWS list rates; excludes negotiated discounts, tax, support, and customer-specific terms.",
        "persisted": False,
        "execution_permitted": False,
    }


class CloudCostAdapter:
    """Unified read-only cloud provider cost and usage adapter."""

    def __init__(self) -> None:
        self._registry = get_registry()
        self._register_adapters()

    def _register_adapters(self) -> None:
        """Register all supported cloud providers."""
        for provider, info in [
            ("aws", AdapterInfo(
                name="aws",
                version="1.0.0",
                description="AWS Price List API (public catalog)",
                capabilities=frozenset([AdapterCapability.PRICE_LOOKUP, AdapterCapability.SKU_SEARCH]),
                endpoint=AWS_PRICING_ENDPOINT,
            )),
            ("azure", AdapterInfo(
                name="azure",
                version="1.0.0",
                description="Azure Retail Prices API (public catalog)",
                capabilities=frozenset([AdapterCapability.PRICE_LOOKUP, AdapterCapability.SKU_SEARCH]),
                endpoint=AZURE_PRICING_ENDPOINT,
            )),
            ("gcp", AdapterInfo(
                name="gcp",
                version="1.0.0",
                description="Google Cloud Billing Catalog API (public catalog)",
                capabilities=frozenset([AdapterCapability.PRICE_LOOKUP, AdapterCapability.SKU_SEARCH]),
                endpoint=GCP_BILLING_ENDPOINT,
            )),
        ]:
            self._registry.register(info)

    def fetch_prices(
        self,
        provider: Provider,
        *,
        service: str,
        region: str = "",
        sku: str = "",
        currency: str = "USD",
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Fetch prices from a cloud provider."""
        if provider == "aws":
            return fetch_aws_prices(service=service, region=region, sku=sku, currency=currency)
        elif provider == "azure":
            return fetch_azure_retail_prices(service_name=service, region=region, sku=sku, currency=currency)
        elif provider == "gcp":
            return fetch_google_cloud_prices(service_name=service, region=region, sku_query=sku, currency=currency, api_key=api_key)
        else:
            raise ValueError(f"unsupported provider: {provider}")

    def health_check(self, provider: Provider) -> bool:
        """Check if a provider is healthy."""
        try:
            service = "ec2" if provider == "aws" else "Virtual Machines" if provider == "azure" else "Compute Engine"
            self.fetch_prices(provider, service=service)
            return True
        except Exception:
            return False


# Module-level singleton
_default_adapter: CloudCostAdapter | None = None


def get_adapter() -> CloudCostAdapter:
    """Return the process-wide default adapter."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = CloudCostAdapter()
    return _default_adapter
