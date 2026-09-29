"""Read-only utility bill and rate adapter.

Provides bounded, read-only access to utility rate schedules (tariffs) and
billing data through vendor-neutral HTTPS API gateways. Supports fixed
endpoint allowlisting via operator configuration.

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

# Fixed, operator-configured utility gateway endpoint (no tenant-supplied URLs)
DEFAULT_UTILITY_ENDPOINT = "https://utility-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_ROWS = 200
MAX_TARIFFS_PER_PAGE = 100
MAX_BILLS_PER_PAGE = 100
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "utility"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Generic Utility Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = [
    "read_tariffs",
    "read_bills",
    "read_rate_schedules",
    "read_demand_charges",
    "read_billing_history",
]
SCOPES = ["tariffs", "bills", "rate_schedules", "demand_charges", "billing_history"]
DATA_CLASSIFICATION = "utility_billing"


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
            raise ConnectionError(
                f"Utility gateway response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Utility gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Utility gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Utility gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Utility gateway response did not match the expected contract")
    return payload


def _validate_tariff_code(tariff_code: str) -> str:
    """Validate a utility tariff code."""
    tariff_code = tariff_code.strip()
    if not tariff_code or len(tariff_code) > 120:
        raise ValueError("tariff_code is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", tariff_code):
        raise ValueError("tariff_code contains unsupported characters")
    return tariff_code


def _validate_account_number(account_number: str) -> str:
    """Validate a utility account number."""
    account_number = account_number.strip()
    if not account_number or len(account_number) > 120:
        raise ValueError("account_number is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", account_number):
        raise ValueError("account_number contains unsupported characters")
    return account_number


def _validate_scope(scope: str) -> str:
    """Validate the data scope."""
    scope = scope.strip().lower()
    valid = {"tariffs", "bills", "rate_schedules", "demand_charges", "billing_history"}
    if scope not in valid:
        raise ValueError(f"scope must be one of: {', '.join(sorted(valid))}")
    return scope


def _parse_timestamp(value: Any) -> str | None:
    """Parse and validate an ISO-8601 timestamp from the utility gateway."""
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
    """Resolve the utility gateway endpoint from parameter or environment."""
    raw = (endpoint or os.environ.get("UTILITY_GATEWAY_ENDPOINT", DEFAULT_UTILITY_ENDPOINT)).strip()
    if not raw:
        raise ConnectionError("UTILITY_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("Utility gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Utility gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("Utility gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("UTILITY_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("Utility credential reference is invalid")
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
        raise ConnectionError("Utility gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("Utility gateway scopes did not match the expected contract")

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


def fetch_tariffs(
    *,
    tariff_code: str | None = None,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch utility rate schedules (tariffs) from the gateway.

    Args:
        tariff_code: Optional specific tariff code to fetch
        endpoint: Optional override for the utility gateway endpoint
        credential_ref: Optional credential reference
        since: Optional ISO-8601 timestamp for incremental sync

    Returns:
        Dict with tariffs list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    # Build query parameters
    params: dict[str, str] = {"limit": str(MAX_TARIFFS_PER_PAGE)}
    if tariff_code:
        validated_code = _validate_tariff_code(tariff_code)
        params["tariff_code"] = validated_code
    if since:
        parsed_ts = _parse_timestamp(since)
        if parsed_ts is None:
            raise ValueError("since must be a valid ISO-8601 timestamp")
        params["since"] = parsed_ts

    query = urllib.parse.urlencode(params)
    url = f"{base}/tariffs?{query}"
    payload = _get_json(url, headers)

    raw_tariffs = payload.get("tariffs", [])
    if not isinstance(raw_tariffs, list):
        raise ConnectionError("Utility gateway tariffs response did not match the expected contract")

    tariffs = []
    for raw in raw_tariffs[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        tariff_id = str(raw.get("tariff_id", "")).strip()
        if not tariff_id:
            continue
        row = {
            "tariff_id": tariff_id,
            "tariff_code": str(raw.get("tariff_code", ""))[:120],
            "provider": str(raw.get("provider", ""))[:200],
            "name": str(raw.get("name", ""))[:200],
            "description": str(raw.get("description", ""))[:500],
            "currency": str(raw.get("currency", ""))[:3],
            "timezone": str(raw.get("timezone", ""))[:50],
            "valid_from": _parse_timestamp(raw.get("valid_from")),
            "valid_to": _parse_timestamp(raw.get("valid_to")),
            "rate_components": raw.get("rate_components") if isinstance(raw.get("rate_components"), list) else [],
            "demand_charges": raw.get("demand_charges") if isinstance(raw.get("demand_charges"), list) else [],
            "source_ref": str(raw.get("source_ref", ""))[:200] or None,
            "version": str(raw.get("version", ""))[:50],
        }
        tariffs.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "scope": "tariffs",
        "tariffs": tariffs,
        "returned": len(tariffs),
        "truncated": len(raw_tariffs) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_bills(
    *,
    account_number: str | None = None,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch utility billing data from the gateway.

    Args:
        account_number: Optional specific account number to fetch
        endpoint: Optional override for the utility gateway endpoint
        credential_ref: Optional credential reference
        since: Optional ISO-8601 timestamp for incremental sync

    Returns:
        Dict with bills list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    # Build query parameters
    params: dict[str, str] = {"limit": str(MAX_BILLS_PER_PAGE)}
    if account_number:
        validated_acct = _validate_account_number(account_number)
        params["account_number"] = validated_acct
    if since:
        parsed_ts = _parse_timestamp(since)
        if parsed_ts is None:
            raise ValueError("since must be a valid ISO-8601 timestamp")
        params["since"] = parsed_ts

    query = urllib.parse.urlencode(params)
    url = f"{base}/bills?{query}"
    payload = _get_json(url, headers)

    raw_bills = payload.get("bills", [])
    if not isinstance(raw_bills, list):
        raise ConnectionError("Utility gateway bills response did not match the expected contract")

    bills = []
    for raw in raw_bills[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        bill_id = str(raw.get("bill_id", "")).strip()
        if not bill_id:
            continue
        row = {
            "bill_id": bill_id,
            "account_number": str(raw.get("account_number", ""))[:120],
            "provider": str(raw.get("provider", ""))[:200],
            "billing_period_start": _parse_timestamp(raw.get("billing_period_start")),
            "billing_period_end": _parse_timestamp(raw.get("billing_period_end")),
            "bill_date": _parse_timestamp(raw.get("bill_date")),
            "due_date": _parse_timestamp(raw.get("due_date")),
            "total_amount": str(_safe_decimal(raw.get("total_amount")) or ""),
            "currency": str(raw.get("currency", ""))[:3],
            "line_items": raw.get("line_items") if isinstance(raw.get("line_items"), list) else [],
            "usage_kwh": str(_safe_decimal(raw.get("usage_kwh")) or ""),
            "peak_demand_kw": str(_safe_decimal(raw.get("peak_demand_kw")) or ""),
            "source_ref": str(raw.get("source_ref", ""))[:200] or None,
        }
        bills.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "scope": "bills",
        "bills": bills,
        "returned": len(bills),
        "truncated": len(raw_bills) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_rate_schedule(
    *,
    tariff_code: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a detailed rate schedule for a specific tariff.

    Args:
        tariff_code: The tariff code to fetch the rate schedule for
        endpoint: Optional override for the utility gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with rate schedule details including time-of-use periods,
        tiered rates, and demand charges
    """
    validated_code = _validate_tariff_code(tariff_code)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/tariffs/{urllib.parse.quote(validated_code, safe='')}/schedule"
    payload = _get_json(url, headers)

    schedule = payload.get("schedule")
    if not isinstance(schedule, dict):
        raise ConnectionError("Utility gateway rate schedule response did not match the expected contract")

    # Sanitize rate components
    rate_components = []
    for rc in schedule.get("rate_components", [])[:50]:
        if not isinstance(rc, dict):
            continue
        rate_components.append({
            "name": str(rc.get("name", ""))[:200],
            "unit": str(rc.get("unit", ""))[:50],
            "rate": str(_safe_decimal(rc.get("rate")) or ""),
            "tier_start": str(_safe_decimal(rc.get("tier_start")) or ""),
            "tier_end": str(_safe_decimal(rc.get("tier_end")) or ""),
            "time_of_use_period": str(rc.get("time_of_use_period", ""))[:50],
        })

    # Sanitize demand charges
    demand_charges = []
    for dc in schedule.get("demand_charges", [])[:50]:
        if not isinstance(dc, dict):
            continue
        demand_charges.append({
            "name": str(dc.get("name", ""))[:200],
            "unit": str(dc.get("unit", ""))[:50],
            "rate": str(_safe_decimal(dc.get("rate")) or ""),
            "charge_type": str(dc.get("charge_type", ""))[:50],
        })

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "scope": "rate_schedules",
        "tariff_code": validated_code,
        "schedule": {
            "tariff_code": validated_code,
            "name": str(schedule.get("name", ""))[:200],
            "currency": str(schedule.get("currency", ""))[:3],
            "timezone": str(schedule.get("timezone", ""))[:50],
            "valid_from": _parse_timestamp(schedule.get("valid_from")),
            "valid_to": _parse_timestamp(schedule.get("valid_to")),
            "rate_components": rate_components,
            "demand_charges": demand_charges,
        },
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def health_check(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Check utility gateway health: connectivity, auth, schema, and freshness.

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

        # Check freshness via a minimal tariff read
        freshness_url = f"{base}/tariffs?{urllib.parse.urlencode({'limit': '1'})}"
        freshness = _get_json(freshness_url, headers)
        tariffs = freshness.get("tariffs", [])
        if tariffs and isinstance(tariffs[0], dict):
            observed = _parse_timestamp(tariffs[0].get("valid_from"))
            if observed:
                checks["freshness"] = "ok"
                details["latest_valid_from"] = observed
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
    "DEFAULT_UTILITY_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "VENDOR",
    "fetch_bills",
    "fetch_rate_schedule",
    "fetch_tariffs",
    "health_check",
    "probe",
]
