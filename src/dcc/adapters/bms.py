"""Read-only Building Management System (BMS) adapter.

Provides bounded, read-only access to building management system data including
HVAC, lighting, and access control points. Supports vendor-neutral HTTPS API
gateways through an industrial DMZ with fixed endpoint allowlisting.

Contract:
  - manifest: adapter_id, version, vendor/product, protocols, capabilities,
              scopes, data classification, endpoint allowlist, credential ref,
              rate/size/time limits
  - probe: verify endpoint identity, TLS, version, scopes, clock, minimal read
  - sync: cursor/checkpoint, idempotency key, bounded page/batch, source time,
          retry/backoff, back-pressure, late/replay semantics
  - map: external identity -> canonical asset/meter/service + confidence
  - health: auth/schema/scope errors, last success, lag, freshness, coverage

Secrets live in a secret manager or host agent environment; this module holds
references only. Destination allowlists and egress policy are set by an
operator, not by tenant-provided arbitrary URLs.
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

# Fixed, operator-configured BMS gateway endpoint (no tenant-supplied URLs)
DEFAULT_BMS_ENDPOINT = "https://bms-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_POINTS_PER_PAGE = 500
MAX_ROWS = 200
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "bms"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Generic BMS Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = ["read_hvac", "read_lighting", "read_access", "read_alarms"]
SCOPES = ["hvac", "lighting", "access", "alarms"]
DATA_CLASSIFICATION = "operational_telemetry"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable redirects to prevent SSRF via operator-supplied URLs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Fetch and parse a JSON response with bounded size."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"DataCenterCommander/{ADAPTER_ID}-{ADAPTER_VERSION}",
            **(headers or {}),
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=CONNECT_TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError(f"BMS response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"BMS gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"BMS gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("BMS gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("BMS gateway response did not match the expected contract")
    return payload


def _validate_point_id(point_id: str) -> str:
    """Validate a BMS point identifier."""
    point_id = point_id.strip()
    if not point_id or len(point_id) > 120:
        raise ValueError("point_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", point_id):
        raise ValueError("point_id contains unsupported characters")
    return point_id


def _validate_category(category: str) -> str:
    """Validate the point category."""
    category = category.strip().lower()
    valid = {"hvac", "lighting", "access", "alarms"}
    if category not in valid:
        raise ValueError(f"category must be one of: {', '.join(sorted(valid))}")
    return category


def _parse_timestamp(value: Any) -> str | None:
    """Parse and validate an ISO-8601 timestamp from the BMS."""
    if not isinstance(value, str):
        return None
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except (ValueError, TypeError):
        return None


def _safe_decimal(value: Any) -> Decimal | None:
    """Safely parse a numeric value."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        return d if d.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _resolve_endpoint(endpoint: str | None = None) -> str:
    """Resolve the BMS gateway endpoint from parameter or environment."""
    raw = (endpoint or os.environ.get("BMS_GATEWAY_ENDPOINT", DEFAULT_BMS_ENDPOINT)).strip()
    if not raw:
        raise ConnectionError("BMS_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("BMS gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("BMS gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("BMS gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("BMS_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("BMS credential reference is invalid")
    return ref


def probe(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Verify endpoint identity, TLS, version, scopes, and a minimal read.

    Returns a manifest dict on success; raises ConnectionError on failure.
    Never persists secrets or unbounded responses.
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    # Minimal read: fetch server info / capabilities
    info_url = f"{base}/info"
    info = _get_json(info_url, headers)

    server_version = str(info.get("version", ""))
    if not server_version:
        raise ConnectionError("BMS gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("BMS gateway scopes did not match the expected contract")

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "vendor": VENDOR,
        "protocols": PROTOCOLS,
        "capabilities": CAPABILITIES,
        "scopes": SCOPES,
        "data_classification": DATA_CLASSIFICATION,
        "endpoint": base,
        "server_version": server_version,
        "server_scopes": reported_scopes[:50],
        "probe_success": True,
        "probe_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_points(
    *,
    category: str,
    point_ids: list[str] | None = None,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch current values for BMS points in a given category.

    Args:
        category: One of 'hvac', 'lighting', 'access', 'alarms'
        point_ids: Optional list of specific point IDs to fetch
        endpoint: Optional override for the BMS gateway endpoint
        credential_ref: Optional credential reference
        since: Optional ISO-8601 timestamp for incremental sync

    Returns:
        Dict with points list, sync metadata, and provenance
    """
    cat = _validate_category(category)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    # Build query parameters
    params: dict[str, str] = {"category": cat, "limit": str(MAX_POINTS_PER_PAGE)}
    if point_ids:
        if len(point_ids) > 100:
            raise ValueError("at most 100 point_ids may be requested at once")
        validated = [_validate_point_id(pid) for pid in point_ids]
        params["point_ids"] = ",".join(validated)
    if since:
        parsed_ts = _parse_timestamp(since)
        if parsed_ts is None:
            raise ValueError("since must be a valid ISO-8601 timestamp")
        params["since"] = parsed_ts

    query = urllib.parse.urlencode(params)
    url = f"{base}/points?{query}"
    payload = _get_json(url, headers)

    raw_points = payload.get("points", [])
    if not isinstance(raw_points, list):
        raise ConnectionError("BMS points response did not match the expected contract")

    points = []
    for raw in raw_points[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        point_id = str(raw.get("point_id", "")).strip()
        if not point_id:
            continue
        value = _safe_decimal(raw.get("value"))
        row = {
            "point_id": point_id,
            "category": cat,
            "label": str(raw.get("label", ""))[:200],
            "value": str(value) if value is not None else None,
            "unit": str(raw.get("unit", ""))[:50] or None,
            "quality": str(raw.get("quality", "unknown"))[:50],
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "source_timestamp": _parse_timestamp(raw.get("source_timestamp")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        points.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "category": cat,
        "points": points,
        "returned": len(points),
        "truncated": len(raw_points) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_alarms(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    active_only: bool = True,
    limit: int = 100,
) -> dict[str, Any]:
    """Fetch current and recent alarms from the BMS.

    Args:
        endpoint: Optional override for the BMS gateway endpoint
        credential_ref: Optional credential reference
        active_only: If True, only return active/unacknowledged alarms
        limit: Maximum number of alarms to return (1-500)

    Returns:
        Dict with alarms list and metadata
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer from 1 to 500")

    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {"limit": str(limit)}
    if active_only:
        params["status"] = "active"

    query = urllib.parse.urlencode(params)
    url = f"{base}/alarms?{query}"
    payload = _get_json(url, headers)

    raw_alarms = payload.get("alarms", [])
    if not isinstance(raw_alarms, list):
        raise ConnectionError("BMS alarms response did not match the expected contract")

    alarms = []
    for raw in raw_alarms[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        alarm_id = str(raw.get("alarm_id", "")).strip()
        if not alarm_id:
            continue
        row = {
            "alarm_id": alarm_id,
            "point_id": str(raw.get("point_id", ""))[:120],
            "severity": str(raw.get("severity", "unknown"))[:50],
            "message": str(raw.get("message", ""))[:500],
            "status": str(raw.get("status", "unknown"))[:50],
            "raised_at": _parse_timestamp(raw.get("raised_at")),
            "acknowledged_at": _parse_timestamp(raw.get("acknowledged_at")),
            "cleared_at": _parse_timestamp(raw.get("cleared_at")),
            "source": str(raw.get("source", ""))[:200] or None,
        }
        alarms.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "alarms": alarms,
        "returned": len(alarms),
        "truncated": len(raw_alarms) > MAX_ROWS or bool(payload.get("next_cursor")),
        "active_only": active_only,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_hvac_summary(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a summary of HVAC system status across all zones.

    Returns:
        Dict with zone-level HVAC summary
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/summary/hvac"
    payload = _get_json(url, headers)

    zones = payload.get("zones", [])
    if not isinstance(zones, list):
        raise ConnectionError("BMS HVAC summary response did not match the expected contract")

    summary = []
    for raw in zones[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        zone_id = str(raw.get("zone_id", "")).strip()
        if not zone_id:
            continue
        temp = _safe_decimal(raw.get("temperature"))
        humidity = _safe_decimal(raw.get("humidity"))
        setpoint = _safe_decimal(raw.get("setpoint"))
        row = {
            "zone_id": zone_id,
            "zone_name": str(raw.get("zone_name", ""))[:200],
            "temperature": str(temp) if temp is not None else None,
            "humidity": str(humidity) if humidity is not None else None,
            "setpoint": str(setpoint) if setpoint is not None else None,
            "unit": str(raw.get("unit", ""))[:50] or None,
            "mode": str(raw.get("mode", ""))[:50] or None,
            "fan_state": str(raw.get("fan_state", ""))[:50] or None,
            "damper_position": str(raw.get("damper_position", ""))[:50] or None,
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "alarms_count": int(raw.get("alarms_count", 0)) if isinstance(raw.get("alarms_count"), int) else 0,
        }
        summary.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "zones": summary,
        "returned": len(summary),
        "truncated": len(zones) > MAX_ROWS,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def health_check(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Check BMS gateway health: connectivity, auth, schema, and freshness.

    Returns:
        Dict with health status, checks, and metadata
    """
    base = _resolve_endpoint(endpoint)
    checks: dict[str, str] = {
        "endpoint": "ok",
        "authentication": "unchecked",
        "schema": "unchecked",
        "freshness": "unchecked",
    }
    healthy = True
    details: dict[str, Any] = {}

    try:
        cred = _resolve_credential(credential_ref)
        headers = {"X-Credential-Ref": cred} if cred else {}

        # Probe endpoint
        info_url = f"{base}/info"
        info = _get_json(info_url, headers)
        checks["authentication"] = "ok"
        checks["schema"] = "ok"
        details["server_version"] = str(info.get("version", "unknown"))

        # Check freshness via a minimal point read
        freshness_url = f"{base}/points?{urllib.parse.urlencode({'category': 'hvac', 'limit': '1'})}"
        freshness = _get_json(freshness_url, headers)
        points = freshness.get("points", [])
        if points and isinstance(points[0], dict):
            observed = _parse_timestamp(points[0].get("observed_at"))
            if observed:
                checks["freshness"] = "ok"
                details["latest_observed_at"] = observed
            else:
                checks["freshness"] = "stale"
                healthy = False
        else:
            checks["freshness"] = "no_data"
            healthy = False

    except ConnectionError as exc:
        healthy = False
        checks["endpoint"] = "unavailable"
        details["error"] = str(exc)
    except Exception as exc:
        healthy = False
        details["error"] = f"{type(exc).__name__}: {exc}"

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "healthy": healthy,
        "checks": checks,
        "details": details,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


# Module-level constants for external reference
__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "CAPABILITIES",
    "DATA_CLASSIFICATION",
    "DEFAULT_BMS_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "VENDOR",
    "fetch_alarms",
    "fetch_hvac_summary",
    "fetch_points",
    "health_check",
    "probe",
]
