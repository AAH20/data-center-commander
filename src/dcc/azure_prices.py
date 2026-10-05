"""Bounded read-only access to Microsoft's public Azure retail price catalog."""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

ENDPOINT = "https://prices.azure.com/api/retail/prices"
API_VERSION = "2023-01-01-preview"
MAX_RESPONSE_BYTES = 1_000_000
MAX_ROWS = 100


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _filter_value(value: str, field: str, pattern: str, *, required: bool = False) -> str:
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > 80 or (value and not re.fullmatch(pattern, value)):
        raise ValueError(f"{field} contains unsupported characters or is too long")
    return value


def fetch_azure_retail_prices(
    *, service_name: str, region: str = "", sku: str = "", currency: str = "USD"
) -> dict[str, Any]:
    """Fetch one bounded catalog page; never follows a provider-supplied next link."""
    service_name = _filter_value(
        service_name, "service_name", r"[A-Za-z0-9 ()&._/-]+", required=True
    )
    region = _filter_value(region, "region", r"[A-Za-z0-9._-]*")
    sku = _filter_value(sku, "sku", r"[A-Za-z0-9._-]*")
    currency = currency.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter ISO currency code")

    filters = [f"serviceName eq '{service_name.replace(chr(39), chr(39) * 2)}'"]
    if region:
        filters.append(f"armRegionName eq '{region}'")
    if sku:
        filters.append(f"armSkuName eq '{sku}'")
    filters.append("priceType eq 'Consumption'")
    query = urllib.parse.urlencode(
        {
            "api-version": API_VERSION,
            "$filter": " and ".join(filters),
            "currencyCode": currency,
        }
    )
    request = urllib.request.Request(
        f"{ENDPOINT}?{query}",
        headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError("Azure price response exceeded the 1 MB limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Azure price catalog returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(
            f"Azure price catalog is unavailable ({type(exc).__name__})"
        ) from None
    except json.JSONDecodeError:
        raise ConnectionError("Azure price catalog returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("Items"), list):
        raise ConnectionError("Azure price response did not match the retail catalog contract")

    rows = []
    for item in payload["Items"][:MAX_ROWS]:
        if not isinstance(item, dict):
            continue
        try:
            price = Decimal(str(item["retailPrice"]))
        except (KeyError, InvalidOperation, ValueError):
            continue
        if not price.is_finite() or price < 0:
            continue
        rows.append(
            {
                key: item.get(key)
                for key in (
                    "serviceName",
                    "productName",
                    "skuName",
                    "armSkuName",
                    "armRegionName",
                    "meterName",
                    "unitOfMeasure",
                    "currencyCode",
                    "effectiveStartDate",
                    "priceType",
                    "isPrimaryMeterRegion",
                )
            }
            | {"retailPrice": str(price)}
        )

    return {
        "provider": "Microsoft Azure Retail Prices API",
        "api_version": API_VERSION,
        "retrieved_at": dt.datetime.now(dt.UTC).isoformat(),
        "source_url": ENDPOINT,
        "query": {
            "service_name": service_name,
            "region": region or None,
            "sku": sku or None,
            "currency": currency,
        },
        "prices": rows,
        "returned": len(rows),
        "truncated": len(payload["Items"]) > MAX_ROWS or bool(payload.get("NextPageLink")),
        "commercial_basis": "Public retail list rates only; excludes negotiated discounts, tax, support, and customer-specific terms.",
        "persisted": False,
        "execution_permitted": False,
    }
