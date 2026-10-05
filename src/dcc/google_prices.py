"""Bounded, public Google Cloud Billing Catalog pricing lookup."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

BASE = "https://cloudbilling.googleapis.com/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_SKU_PAGE = 1000
MAX_ROWS = 100


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "DataCenterCommander/0.1"}, method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError("Google Cloud Billing response exceeded the 2 MB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Google Cloud Billing catalog returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Google Cloud Billing catalog is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Google Cloud Billing catalog returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Google Cloud Billing response did not match the catalog contract")
    return payload


def _amount(money: Any) -> Decimal | None:
    if not isinstance(money, dict):
        return None
    try:
        amount = Decimal(str(money.get("units", "0"))) + Decimal(str(money.get("nanos", 0))) / Decimal(1_000_000_000)
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def fetch_google_cloud_prices(*, service_name: str, region: str, sku_query: str, currency: str = "USD", api_key: str | None = None) -> dict[str, Any]:
    """Search the first bounded SKU page; never persists a price or follows user URLs."""
    service_name, region, sku_query = service_name.strip(), region.strip(), sku_query.strip()
    currency = currency.strip().upper()
    if not service_name or len(service_name) > 80 or not re.fullmatch(r"[A-Za-z0-9 &()._/-]+", service_name):
        raise ValueError("service_name is required and may contain only catalog-safe characters")
    if not region or len(region) > 80 or not re.fullmatch(r"[A-Za-z0-9._-]+", region):
        raise ValueError("a valid Google Cloud region is required")
    if not sku_query or len(sku_query) > 100 or not re.fullmatch(r"[A-Za-z0-9 &()._/-]+", sku_query):
        raise ValueError("sku_query is required and may contain only catalog-safe characters")
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter ISO currency code")
    key = (api_key if api_key is not None else os.environ.get("GOOGLE_CLOUD_BILLING_API_KEY", "")).strip()
    if not key:
        raise ConnectionError("GOOGLE_CLOUD_BILLING_API_KEY is not configured in the server environment")
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("Google Cloud Billing API key configuration is invalid")

    services_url = f"{BASE}/services?{urllib.parse.urlencode({'pageSize': 5000, 'key': key})}"
    services = _get_json(services_url)
    matches = [s for s in services.get("services", []) if isinstance(s, dict) and str(s.get("displayName", "")).casefold() == service_name.casefold()]
    service = next((s for s in matches if re.fullmatch(r"[A-Za-z0-9-]{4,40}", str(s.get("serviceId", "")))), None)
    if service is None:
        raise ValueError("service name did not match a public Google Cloud catalog service")

    sku_query_url = f"{BASE}/services/{urllib.parse.quote(service['serviceId'], safe='')}/skus?{urllib.parse.urlencode({'pageSize': MAX_SKU_PAGE, 'currencyCode': currency, 'key': key})}"
    catalog = _get_json(sku_query_url)
    candidates = catalog.get("skus", [])
    if not isinstance(candidates, list):
        raise ConnectionError("Google Cloud Billing SKU response did not match the catalog contract")
    needle = sku_query.casefold()
    rows = []
    for sku in candidates:
        if not isinstance(sku, dict) or needle not in str(sku.get("description", "")).casefold():
            continue
        regions = sku.get("serviceRegions") if isinstance(sku.get("serviceRegions"), list) else []
        if regions and region not in regions:
            continue
        info = sku.get("pricingInfo") if isinstance(sku.get("pricingInfo"), list) else []
        latest = info[-1] if info and isinstance(info[-1], dict) else {}
        expression = latest.get("pricingExpression") if isinstance(latest.get("pricingExpression"), dict) else {}
        tiers = expression.get("tieredRates") if isinstance(expression.get("tieredRates"), list) else []
        safe_tiers = []
        for tier in tiers:
            if not isinstance(tier, dict):
                continue
            amount = _amount(tier.get("unitPrice"))
            if amount is not None:
                safe_tiers.append({"start_usage_amount": str(tier.get("startUsageAmount", "0")), "unit_price": str(amount)})
        simple = len(safe_tiers) == 1 and Decimal(safe_tiers[0]["start_usage_amount"]) == 0
        unit = str(expression.get("usageUnitDescription") or expression.get("usageUnit") or "").strip()
        row = {
            "serviceName": service_name,
            "serviceId": service["serviceId"],
            "skuId": str(sku.get("skuId", "")),
            "description": str(sku.get("description", ""))[:256],
            "region": region,
            "available_regions": regions[:100],
            "usage_type": str((sku.get("category") or {}).get("usageType", "")) if isinstance(sku.get("category"), dict) else "",
            "currencyCode": currency,
            "unitOfMeasure": unit,
            "effectiveStartDate": latest.get("effectiveTime"),
            "tiered_rates": safe_tiers,
            "tier_count": len(safe_tiers),
            "estimate_eligible": simple,
            "retailPrice": safe_tiers[0]["unit_price"] if simple else None,
        }
        rows.append(row)
        if len(rows) >= MAX_ROWS:
            break
    truncated = bool(catalog.get("nextPageToken")) or len(rows) >= MAX_ROWS
    return {
        "provider": "Google Cloud Billing Catalog API",
        "api_version": "v1",
        "retrieved_at": dt.datetime.now(dt.UTC).isoformat(),
        "source_url": f"{BASE}/services",
        "query": {"service_name": service_name, "region": region, "sku_query": sku_query, "currency": currency},
        "prices": rows,
        "returned": len(rows),
        "truncated": truncated,
        "commercial_basis": "Public Google Cloud catalog list rates; may use Google currency conversion; excludes account-specific contract pricing, taxes, support, and other bill adjustments.",
        "persisted": False,
        "execution_permitted": False,
    }
