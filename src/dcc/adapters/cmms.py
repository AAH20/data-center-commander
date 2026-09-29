"""Read-only CMMS (Computerized Maintenance Management System) adapter.

Bounded, read-only connector for maintenance management data: work orders,
assets, and schedules. Never persists data, never follows redirects, never
executes commands. All queries are tenant-scoped and bounded.
"""
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

MAX_RESPONSE_BYTES = 2_000_000
MAX_ROWS = 200
DEFAULT_TIMEOUT = 8

# CMMS API endpoint patterns (allowlist)
ALLOWED_SCHEMES = {"https"}
ALLOWED_HOSTS = {
    "cmms.example.com",
    "api.cmms.example.com",
    "maintenance.example.com",
    "itms.example.com",
    "eam.example.com",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_endpoint(endpoint: str) -> str:
    """Validate CMMS endpoint URL against allowlist."""
    endpoint = endpoint.strip()
    if not endpoint:
        raise ValueError("CMMS endpoint is required")
    if len(endpoint) > 512:
        raise ValueError("CMMS endpoint URL is too long")
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError("CMMS endpoint must use HTTPS")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"CMMS host '{parsed.hostname}' is not in the allowlist")
    if parsed.username or parsed.password:
        raise ValueError("CMMS endpoint must not contain embedded credentials")
    return endpoint


def _get_api_key() -> str:
    """Retrieve CMMS API key from environment."""
    key = os.environ.get("CMMS_API_KEY", "").strip()
    if not key:
        raise ConnectionError("CMMS_API_KEY is not configured in the server environment")
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("CMMS API key configuration is invalid")
    return key


def _get_json(url: str, api_key: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch JSON from CMMS API with bounded response."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "DataCenterCommander/0.1",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError("CMMS response exceeded the 2 MB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"CMMS API returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"CMMS API is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("CMMS API returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("CMMS API response did not match the expected contract")
    return payload


def _safe_decimal(value: Any) -> str | None:
    """Safely convert a value to a decimal string."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d < 0:
            return None
        return str(d)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to an integer."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_str(value: Any, max_len: int = 256) -> str | None:
    """Safely convert a value to a bounded string."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or len(s) > max_len:
        return None
    return s


def _safe_timestamp(value: Any) -> str | None:
    """Safely convert a value to an ISO timestamp."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return s
    except ValueError:
        return None


def probe_cmms(
    *,
    endpoint: str,
    api_key: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Probe CMMS API health and connectivity.

    Performs a minimal read to verify endpoint identity, authentication,
    and basic connectivity. Never persists data.
    """
    endpoint = _validate_endpoint(endpoint)
    key = api_key if api_key else _get_api_key()
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("CMMS API key configuration is invalid")

    # Use a minimal work orders query as the probe
    query = urllib.parse.urlencode({"limit": 1, "status": "open"})
    url = f"{endpoint}/work-orders?{query}"
    payload = _get_json(url, key, timeout)

    return {
        "provider": "CMMS API",
        "endpoint": endpoint,
        "probed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "healthy",
        "work_orders_accessible": isinstance(payload.get("data"), list),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_work_orders(
    *,
    endpoint: str,
    api_key: str | None = None,
    status: str = "",
    asset_id: str = "",
    limit: int = 100,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch work orders from CMMS with bounded, read-only query.

    Returns a bounded list of work orders. Never persists data.
    """
    endpoint = _validate_endpoint(endpoint)
    key = api_key if api_key else _get_api_key()
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("CMMS API key configuration is invalid")

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be an integer from 1 to {MAX_ROWS}")

    status = status.strip()
    if status and (len(status) > 50 or not re.fullmatch(r"[A-Za-z0-9_-]+", status)):
        raise ValueError("status contains unsupported characters")

    asset_id = asset_id.strip()
    if asset_id and (len(asset_id) > 100 or not re.fullmatch(r"[A-Za-z0-9_-]+", asset_id)):
        raise ValueError("asset_id contains unsupported characters")

    params: dict[str, str] = {"limit": str(limit)}
    if status:
        params["status"] = status
    if asset_id:
        params["asset_id"] = asset_id

    query = urllib.parse.urlencode(params)
    url = f"{endpoint}/work-orders?{query}"
    payload = _get_json(url, key, timeout)

    raw_orders = payload.get("data", [])
    if not isinstance(raw_orders, list):
        raise ConnectionError("CMMS work orders response did not match the expected contract")

    rows = []
    for item in raw_orders[:MAX_ROWS]:
        if not isinstance(item, dict):
            continue
        row = {
            "id": _safe_str(item.get("id"), 100),
            "title": _safe_str(item.get("title"), 256),
            "status": _safe_str(item.get("status"), 50),
            "priority": _safe_str(item.get("priority"), 50),
            "asset_id": _safe_str(item.get("asset_id"), 100),
            "asset_name": _safe_str(item.get("asset_name"), 256),
            "work_type": _safe_str(item.get("work_type"), 100),
            "scheduled_start": _safe_timestamp(item.get("scheduled_start")),
            "scheduled_end": _safe_timestamp(item.get("scheduled_end")),
            "completed_at": _safe_timestamp(item.get("completed_at")),
            "assigned_to": _safe_str(item.get("assigned_to"), 256),
            "estimated_hours": _safe_decimal(item.get("estimated_hours")),
            "actual_hours": _safe_decimal(item.get("actual_hours")),
            "cost_estimate": _safe_decimal(item.get("cost_estimate")),
            "failure_code": _safe_str(item.get("failure_code"), 100),
            "description": _safe_str(item.get("description"), 2000),
        }
        # Drop None values for cleaner output
        row = {k: v for k, v in row.items() if v is not None}
        if row.get("id"):
            rows.append(row)

    return {
        "provider": "CMMS API",
        "endpoint": endpoint,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": {"status": status or None, "asset_id": asset_id or None, "limit": limit},
        "work_orders": rows,
        "returned": len(rows),
        "truncated": len(raw_orders) > MAX_ROWS or bool(payload.get("next_page")),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_assets(
    *,
    endpoint: str,
    api_key: str | None = None,
    asset_type: str = "",
    status: str = "",
    limit: int = 100,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch assets from CMMS with bounded, read-only query.

    Returns a bounded list of assets. Never persists data.
    """
    endpoint = _validate_endpoint(endpoint)
    key = api_key if api_key else _get_api_key()
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("CMMS API key configuration is invalid")

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be an integer from 1 to {MAX_ROWS}")

    asset_type = asset_type.strip()
    if asset_type and (len(asset_type) > 50 or not re.fullmatch(r"[A-Za-z0-9_-]+", asset_type)):
        raise ValueError("asset_type contains unsupported characters")

    status = status.strip()
    if status and (len(status) > 50 or not re.fullmatch(r"[A-Za-z0-9_-]+", status)):
        raise ValueError("status contains unsupported characters")

    params: dict[str, str] = {"limit": str(limit)}
    if asset_type:
        params["asset_type"] = asset_type
    if status:
        params["status"] = status

    query = urllib.parse.urlencode(params)
    url = f"{endpoint}/assets?{query}"
    payload = _get_json(url, key, timeout)

    raw_assets = payload.get("data", [])
    if not isinstance(raw_assets, list):
        raise ConnectionError("CMMS assets response did not match the expected contract")

    rows = []
    for item in raw_assets[:MAX_ROWS]:
        if not isinstance(item, dict):
            continue
        row = {
            "id": _safe_str(item.get("id"), 100),
            "name": _safe_str(item.get("name"), 256),
            "asset_type": _safe_str(item.get("asset_type"), 100),
            "status": _safe_str(item.get("status"), 50),
            "location": _safe_str(item.get("location"), 256),
            "serial_number": _safe_str(item.get("serial_number"), 100),
            "manufacturer": _safe_str(item.get("manufacturer"), 256),
            "model": _safe_str(item.get("model"), 256),
            "install_date": _safe_timestamp(item.get("install_date")),
            "warranty_expiry": _safe_timestamp(item.get("warranty_expiry")),
            "criticality": _safe_str(item.get("criticality"), 50),
            "parent_asset_id": _safe_str(item.get("parent_asset_id"), 100),
        }
        row = {k: v for k, v in row.items() if v is not None}
        if row.get("id"):
            rows.append(row)

    return {
        "provider": "CMMS API",
        "endpoint": endpoint,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": {"asset_type": asset_type or None, "status": status or None, "limit": limit},
        "assets": rows,
        "returned": len(rows),
        "truncated": len(raw_assets) > MAX_ROWS or bool(payload.get("next_page")),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_schedules(
    *,
    endpoint: str,
    api_key: str | None = None,
    schedule_type: str = "",
    asset_id: str = "",
    limit: int = 100,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch maintenance schedules from CMMS with bounded, read-only query.

    Returns a bounded list of schedules. Never persists data.
    """
    endpoint = _validate_endpoint(endpoint)
    key = api_key if api_key else _get_api_key()
    if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
        raise ValueError("CMMS API key configuration is invalid")

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be an integer from 1 to {MAX_ROWS}")

    schedule_type = schedule_type.strip()
    if schedule_type and (len(schedule_type) > 50 or not re.fullmatch(r"[A-Za-z0-9_-]+", schedule_type)):
        raise ValueError("schedule_type contains unsupported characters")

    asset_id = asset_id.strip()
    if asset_id and (len(asset_id) > 100 or not re.fullmatch(r"[A-Za-z0-9_-]+", asset_id)):
        raise ValueError("asset_id contains unsupported characters")

    params: dict[str, str] = {"limit": str(limit)}
    if schedule_type:
        params["schedule_type"] = schedule_type
    if asset_id:
        params["asset_id"] = asset_id

    query = urllib.parse.urlencode(params)
    url = f"{endpoint}/schedules?{query}"
    payload = _get_json(url, key, timeout)

    raw_schedules = payload.get("data", [])
    if not isinstance(raw_schedules, list):
        raise ConnectionError("CMMS schedules response did not match the expected contract")

    rows = []
    for item in raw_schedules[:MAX_ROWS]:
        if not isinstance(item, dict):
            continue
        row = {
            "id": _safe_str(item.get("id"), 100),
            "title": _safe_str(item.get("title"), 256),
            "schedule_type": _safe_str(item.get("schedule_type"), 100),
            "asset_id": _safe_str(item.get("asset_id"), 100),
            "asset_name": _safe_str(item.get("asset_name"), 256),
            "frequency": _safe_str(item.get("frequency"), 100),
            "next_due": _safe_timestamp(item.get("next_due")),
            "last_completed": _safe_timestamp(item.get("last_completed")),
            "assigned_to": _safe_str(item.get("assigned_to"), 256),
            "estimated_hours": _safe_decimal(item.get("estimated_hours")),
            "status": _safe_str(item.get("status"), 50),
            "procedure_ref": _safe_str(item.get("procedure_ref"), 256),
        }
        row = {k: v for k, v in row.items() if v is not None}
        if row.get("id"):
            rows.append(row)

    return {
        "provider": "CMMS API",
        "endpoint": endpoint,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": {"schedule_type": schedule_type or None, "asset_id": asset_id or None, "limit": limit},
        "schedules": rows,
        "returned": len(rows),
        "truncated": len(raw_schedules) > MAX_ROWS or bool(payload.get("next_page")),
        "persisted": False,
        "execution_permitted": False,
    }
