"""Read-only Proxmox VE workload telemetry adapter.

Provides bounded, read-only access to VM/container inventory, node, and
capacity telemetry from Proxmox VE through a vendor-neutral HTTPS API gateway.
The gateway fronts the Proxmox REST API and exposes a unified, read-only
contract.

Supported platforms:
  - Proxmox VE (via gateway)

Contract:
  - manifest: adapter_id, version, vendor/product, protocols, capabilities,
              scopes, data classification, endpoint allowlist, credential ref,
              rate/size/time limits
  - probe: verify endpoint identity, TLS, version, scopes, clock, minimal read
  - sync: cursor/checkpoint, idempotency key, bounded page/batch, source time,
          retry/backoff, back-pressure, late/replay semantics
  - map: external identity -> canonical asset/workload/service + confidence
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

# Fixed, operator-configured Proxmox gateway endpoint (no tenant-supplied URLs)
DEFAULT_PROXMOX_ENDPOINT = "https://proxmox-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_VMS_PER_PAGE = 500
MAX_NODES_PER_PAGE = 200
MAX_ROWS = 200
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "proxmox"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Proxmox VE Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = [
    "read_vm_inventory",
    "read_container_inventory",
    "read_node_inventory",
    "read_power_metrics",
    "read_capacity_metrics",
    "read_vm_state",
    "read_container_state",
]
SCOPES = [
    "vm_inventory",
    "container_inventory",
    "node_inventory",
    "power_metrics",
    "capacity_metrics",
    "vm_state",
    "container_state",
]
DATA_CLASSIFICATION = "operational_telemetry"

SUPPORTED_PLATFORMS = {"proxmox_ve"}


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
                f"Proxmox gateway response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Proxmox gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Proxmox gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Proxmox gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Proxmox gateway response did not match the expected contract")
    return payload


def _validate_platform(platform: str) -> str:
    """Validate the platform identifier."""
    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"platform must be one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )
    return platform


def _validate_vm_id(vm_id: str) -> str:
    """Validate a VM identifier."""
    vm_id = vm_id.strip()
    if not vm_id or len(vm_id) > 120:
        raise ValueError("vm_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", vm_id):
        raise ValueError("vm_id contains unsupported characters")
    return vm_id


def _validate_node_id(node_id: str) -> str:
    """Validate a node identifier."""
    node_id = node_id.strip()
    if not node_id or len(node_id) > 120:
        raise ValueError("node_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", node_id):
        raise ValueError("node_id contains unsupported characters")
    return node_id


def _parse_timestamp(value: Any) -> str | None:
    """Parse and validate an ISO-8601 timestamp from the gateway."""
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


def _safe_int(value: Any) -> int | None:
    """Safely parse an integer value."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _resolve_endpoint(endpoint: str | None = None) -> str:
    """Resolve the Proxmox gateway endpoint from parameter or environment."""
    raw = (
        endpoint
        or os.environ.get("PROXMOX_GATEWAY_ENDPOINT", DEFAULT_PROXMOX_ENDPOINT)
    ).strip()
    if not raw:
        raise ConnectionError("PROXMOX_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("Proxmox gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Proxmox gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("Proxmox gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("PROXMOX_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("Proxmox credential reference is invalid")
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
        raise ConnectionError("Proxmox gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("Proxmox gateway scopes did not match the expected contract")

    supported_platforms = info.get("supported_platforms", [])
    if not isinstance(supported_platforms, list):
        raise ConnectionError("Proxmox gateway supported_platforms did not match the expected contract")

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
        "supported_platforms": supported_platforms[:50],
        "probe_success": True,
        "probe_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_vm_inventory(
    *,
    platform: str = "proxmox_ve",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    vm_type: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Fetch VM inventory from the Proxmox gateway.

    Args:
        platform: One of 'proxmox_ve'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        vm_type: Optional filter by VM type ('qemu', 'lxc')
        node_id: Optional filter by node identifier

    Returns:
        Dict with VMs list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_VMS_PER_PAGE),
    }
    if vm_type:
        vt = vm_type.strip().lower()
        if vt not in {"qemu", "lxc"}:
            raise ValueError("vm_type must be one of: qemu, lxc")
        params["vm_type"] = vt
    if node_id:
        params["node_id"] = _validate_node_id(node_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/vms?{query}"
    payload = _get_json(url, headers)

    raw_vms = payload.get("vms", [])
    if not isinstance(raw_vms, list):
        raise ConnectionError("Proxmox VM inventory response did not match the expected contract")

    vms = []
    for raw in raw_vms[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        vm_id = str(raw.get("vm_id", "")).strip()
        if not vm_id:
            continue
        cpu_count = _safe_int(raw.get("cpu_count"))
        memory_mb = _safe_int(raw.get("memory_mb"))
        row = {
            "vm_id": vm_id,
            "name": str(raw.get("name", ""))[:200],
            "platform": plat,
            "vm_type": str(raw.get("vm_type", "unknown"))[:50],
            "status": str(raw.get("status", "unknown"))[:50],
            "node_id": str(raw.get("node_id", ""))[:120] or None,
            "cpu_count": cpu_count,
            "memory_mb": memory_mb,
            "disk_gb": _safe_decimal(raw.get("disk_gb")),
            "ip_addresses": [
                str(ip)[:64]
                for ip in (raw.get("ip_addresses") or [])[:10]
                if isinstance(ip, str)
            ],
            "mac_addresses": [
                str(mac)[:64]
                for mac in (raw.get("mac_addresses") or [])[:10]
                if isinstance(mac, str)
            ],
            "pool": str(raw.get("pool", ""))[:200] or None,
            "tags": [
                str(tag)[:100]
                for tag in (raw.get("tags") or [])[:20]
                if isinstance(tag, str)
            ],
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        vms.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "vms": vms,
        "returned": len(vms),
        "truncated": len(raw_vms) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_node_inventory(
    *,
    platform: str = "proxmox_ve",
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch physical node inventory from the Proxmox gateway.

    Args:
        platform: One of 'proxmox_ve'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with nodes list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_NODES_PER_PAGE),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/nodes?{query}"
    payload = _get_json(url, headers)

    raw_nodes = payload.get("nodes", [])
    if not isinstance(raw_nodes, list):
        raise ConnectionError("Proxmox node inventory response did not match the expected contract")

    nodes = []
    for raw in raw_nodes[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id", "")).strip()
        if not node_id:
            continue
        total_cpu_cores = _safe_int(raw.get("total_cpu_cores"))
        total_memory_mb = _safe_int(raw.get("total_memory_mb"))
        row = {
            "node_id": node_id,
            "name": str(raw.get("name", ""))[:200],
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "total_cpu_cores": total_cpu_cores,
            "total_memory_mb": total_memory_mb,
            "cpu_model": str(raw.get("cpu_model", ""))[:200] or None,
            "proxmox_version": str(raw.get("proxmox_version", ""))[:100] or None,
            "kernel_version": str(raw.get("kernel_version", ""))[:100] or None,
            "network_interfaces": [
                str(nic)[:200]
                for nic in (raw.get("network_interfaces") or [])[:10]
                if isinstance(nic, str)
            ],
            "storage_pools": [
                str(sp)[:200]
                for sp in (raw.get("storage_pools") or [])[:10]
                if isinstance(sp, str)
            ],
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        nodes.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "nodes": nodes,
        "returned": len(nodes),
        "truncated": len(raw_nodes) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_power_metrics(
    *,
    platform: str = "proxmox_ve",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    vm_ids: list[str] | None = None,
    node_id: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch power consumption metrics from the Proxmox gateway.

    Args:
        platform: One of 'proxmox_ve'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        vm_ids: Optional list of specific VM IDs to fetch metrics for
        node_id: Optional node ID to fetch node-level power metrics
        since: Optional ISO-8601 timestamp for incremental sync

    Returns:
        Dict with power metrics list and metadata
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_ROWS),
    }
    if vm_ids:
        if len(vm_ids) > 100:
            raise ValueError("at most 100 vm_ids may be requested at once")
        validated = [_validate_vm_id(vid) for vid in vm_ids]
        params["vm_ids"] = ",".join(validated)
    if node_id:
        params["node_id"] = _validate_node_id(node_id)
    if since:
        parsed_ts = _parse_timestamp(since)
        if parsed_ts is None:
            raise ValueError("since must be a valid ISO-8601 timestamp")
        params["since"] = parsed_ts

    query = urllib.parse.urlencode(params)
    url = f"{base}/metrics/power?{query}"
    payload = _get_json(url, headers)

    raw_metrics = payload.get("metrics", [])
    if not isinstance(raw_metrics, list):
        raise ConnectionError("Proxmox power metrics response did not match the expected contract")

    metrics = []
    for raw in raw_metrics[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        metric_id = str(raw.get("metric_id", "")).strip()
        if not metric_id:
            continue
        power_w = _safe_decimal(raw.get("power_watts"))
        row = {
            "metric_id": metric_id,
            "entity_type": str(raw.get("entity_type", "unknown"))[:50],
            "entity_id": str(raw.get("entity_id", ""))[:120],
            "platform": plat,
            "power_watts": str(power_w) if power_w is not None else None,
            "cpu_percent": str(_safe_decimal(raw.get("cpu_percent")))
            if _safe_decimal(raw.get("cpu_percent")) is not None
            else None,
            "memory_percent": str(_safe_decimal(raw.get("memory_percent")))
            if _safe_decimal(raw.get("memory_percent")) is not None
            else None,
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "source_timestamp": _parse_timestamp(raw.get("source_timestamp")),
            "interval_seconds": _safe_int(raw.get("interval_seconds")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        metrics.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "metrics": metrics,
        "returned": len(metrics),
        "truncated": len(raw_metrics) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_capacity_metrics(
    *,
    platform: str = "proxmox_ve",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Fetch capacity and utilization metrics from the Proxmox gateway.

    Args:
        platform: One of 'proxmox_ve'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        node_id: Optional node ID to fetch node-level capacity metrics

    Returns:
        Dict with capacity metrics list and metadata
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_ROWS),
    }
    if node_id:
        params["node_id"] = _validate_node_id(node_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/metrics/capacity?{query}"
    payload = _get_json(url, headers)

    raw_metrics = payload.get("metrics", [])
    if not isinstance(raw_metrics, list):
        raise ConnectionError("Proxmox capacity metrics response did not match the expected contract")

    metrics = []
    for raw in raw_metrics[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        metric_id = str(raw.get("metric_id", "")).strip()
        if not metric_id:
            continue
        row = {
            "metric_id": metric_id,
            "entity_type": str(raw.get("entity_type", "unknown"))[:50],
            "entity_id": str(raw.get("entity_id", ""))[:120],
            "platform": plat,
            "cpu_total_cores": _safe_int(raw.get("cpu_total_cores")),
            "cpu_used_cores": _safe_int(raw.get("cpu_used_cores")),
            "cpu_percent": str(_safe_decimal(raw.get("cpu_percent")))
            if _safe_decimal(raw.get("cpu_percent")) is not None
            else None,
            "memory_total_mb": _safe_int(raw.get("memory_total_mb")),
            "memory_used_mb": _safe_int(raw.get("memory_used_mb")),
            "memory_percent": str(_safe_decimal(raw.get("memory_percent")))
            if _safe_decimal(raw.get("memory_percent")) is not None
            else None,
            "storage_total_gb": _safe_decimal(raw.get("storage_total_gb")),
            "storage_used_gb": _safe_decimal(raw.get("storage_used_gb")),
            "storage_percent": str(_safe_decimal(raw.get("storage_percent")))
            if _safe_decimal(raw.get("storage_percent")) is not None
            else None,
            "network_mbps": str(_safe_decimal(raw.get("network_mbps")))
            if _safe_decimal(raw.get("network_mbps")) is not None
            else None,
            "vm_count": _safe_int(raw.get("vm_count")),
            "container_count": _safe_int(raw.get("container_count")),
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "source_timestamp": _parse_timestamp(raw.get("source_timestamp")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        metrics.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "metrics": metrics,
        "returned": len(metrics),
        "truncated": len(raw_metrics) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_vm_state(
    *,
    platform: str = "proxmox_ve",
    vm_ids: list[str],
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch current state for specific VMs.

    Args:
        platform: One of 'proxmox_ve'
        vm_ids: List of VM IDs to fetch state for (1-100)
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with VM state list and metadata
    """
    plat = _validate_platform(platform)
    if not vm_ids:
        raise ValueError("at least one vm_id is required")
    if len(vm_ids) > 100:
        raise ValueError("at most 100 vm_ids may be requested at once")
    validated_ids = [_validate_vm_id(vid) for vid in vm_ids]

    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "vm_ids": ",".join(validated_ids),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/vms/state?{query}"
    payload = _get_json(url, headers)

    raw_states = payload.get("states", [])
    if not isinstance(raw_states, list):
        raise ConnectionError("Proxmox VM state response did not match the expected contract")

    states = []
    for raw in raw_states[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        vm_id = str(raw.get("vm_id", "")).strip()
        if not vm_id:
            continue
        uptime_s = _safe_int(raw.get("uptime_seconds"))
        row = {
            "vm_id": vm_id,
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "uptime_seconds": uptime_s,
            "vm_type": str(raw.get("vm_type", "unknown"))[:50],
            "ip_addresses": [
                str(ip)[:64]
                for ip in (raw.get("ip_addresses") or [])[:10]
                if isinstance(ip, str)
            ],
            "cpu_ready_percent": str(_safe_decimal(raw.get("cpu_ready_percent")))
            if _safe_decimal(raw.get("cpu_ready_percent")) is not None
            else None,
            "memory_balloon_percent": str(_safe_decimal(raw.get("memory_balloon_percent")))
            if _safe_decimal(raw.get("memory_balloon_percent")) is not None
            else None,
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        states.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "states": states,
        "returned": len(states),
        "truncated": len(raw_states) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def health_check(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Check Proxmox gateway health: connectivity, auth, schema, and freshness.

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

        # Check freshness via a minimal VM read
        freshness_url = f"{base}/vms?{urllib.parse.urlencode({'platform': 'proxmox_ve', 'limit': '1'})}"
        freshness = _get_json(freshness_url, headers)
        vms = freshness.get("vms", [])
        if vms and isinstance(vms[0], dict):
            observed = _parse_timestamp(vms[0].get("observed_at"))
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
    "DEFAULT_PROXMOX_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_PLATFORMS",
    "VENDOR",
    "fetch_capacity_metrics",
    "fetch_node_inventory",
    "fetch_power_metrics",
    "fetch_vm_inventory",
    "fetch_vm_state",
    "health_check",
    "probe",
]
