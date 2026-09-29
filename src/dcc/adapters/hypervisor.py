"""Read-only hypervisor workload telemetry adapter.

Provides bounded, read-only access to VM/host inventory, power, and capacity
telemetry from VMware vCenter, KVM/libvirt, and Hyper-V through a vendor-neutral
HTTPS API gateway. The gateway fronts the hypervisor-specific APIs and exposes
a unified, read-only contract.

Supported hypervisors:
  - VMware vCenter (via gateway)
  - KVM/libvirt (via gateway)
  - Hyper-V (via gateway)

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

# Fixed, operator-configured hypervisor gateway endpoint (no tenant-supplied URLs)
DEFAULT_HYPERVISOR_ENDPOINT = "https://hypervisor-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_VMS_PER_PAGE = 500
MAX_HOSTS_PER_PAGE = 200
MAX_ROWS = 200
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "hypervisor"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Multi-Hypervisor Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = [
    "read_vm_inventory",
    "read_host_inventory",
    "read_power_metrics",
    "read_capacity_metrics",
    "read_vm_state",
]
SCOPES = ["vm_inventory", "host_inventory", "power_metrics", "capacity_metrics", "vm_state"]
DATA_CLASSIFICATION = "operational_telemetry"

SUPPORTED_HYPERVISORS = {"vmware_vcenter", "kvm_libvirt", "hyperv"}


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
                f"Hypervisor gateway response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Hypervisor gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Hypervisor gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Hypervisor gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Hypervisor gateway response did not match the expected contract")
    return payload


def _validate_hypervisor_type(hv_type: str) -> str:
    """Validate the hypervisor type identifier."""
    hv_type = hv_type.strip().lower()
    if hv_type not in SUPPORTED_HYPERVISORS:
        raise ValueError(
            f"hypervisor_type must be one of: {', '.join(sorted(SUPPORTED_HYPERVISORS))}"
        )
    return hv_type


def _validate_vm_id(vm_id: str) -> str:
    """Validate a VM identifier."""
    vm_id = vm_id.strip()
    if not vm_id or len(vm_id) > 120:
        raise ValueError("vm_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", vm_id):
        raise ValueError("vm_id contains unsupported characters")
    return vm_id


def _validate_host_id(host_id: str) -> str:
    """Validate a host identifier."""
    host_id = host_id.strip()
    if not host_id or len(host_id) > 120:
        raise ValueError("host_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", host_id):
        raise ValueError("host_id contains unsupported characters")
    return host_id


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
    """Resolve the hypervisor gateway endpoint from parameter or environment."""
    raw = (
        endpoint
        or os.environ.get("HYPERVISOR_GATEWAY_ENDPOINT", DEFAULT_HYPERVISOR_ENDPOINT)
    ).strip()
    if not raw:
        raise ConnectionError("HYPERVISOR_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("Hypervisor gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Hypervisor gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("Hypervisor gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("HYPERVISOR_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("Hypervisor credential reference is invalid")
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
        raise ConnectionError("Hypervisor gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("Hypervisor gateway scopes did not match the expected contract")

    supported_hv = info.get("supported_hypervisors", [])
    if not isinstance(supported_hv, list):
        raise ConnectionError("Hypervisor gateway supported_hypervisors did not match the expected contract")

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
        "supported_hypervisors": supported_hv[:50],
        "probe_success": True,
        "probe_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_vm_inventory(
    *,
    hypervisor_type: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    power_state: str | None = None,
    host_id: str | None = None,
) -> dict[str, Any]:
    """Fetch VM inventory from the hypervisor gateway.

    Args:
        hypervisor_type: One of 'vmware_vcenter', 'kvm_libvirt', 'hyperv'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        power_state: Optional filter by power state ('powered_on', 'powered_off', 'suspended')
        host_id: Optional filter by host identifier

    Returns:
        Dict with VMs list, sync metadata, and provenance
    """
    hv_type = _validate_hypervisor_type(hypervisor_type)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "hypervisor_type": hv_type,
        "limit": str(MAX_VMS_PER_PAGE),
    }
    if power_state:
        ps = power_state.strip().lower()
        if ps not in {"powered_on", "powered_off", "suspended"}:
            raise ValueError("power_state must be one of: powered_on, powered_off, suspended")
        params["power_state"] = ps
    if host_id:
        params["host_id"] = _validate_host_id(host_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/vms?{query}"
    payload = _get_json(url, headers)

    raw_vms = payload.get("vms", [])
    if not isinstance(raw_vms, list):
        raise ConnectionError("Hypervisor VM inventory response did not match the expected contract")

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
            "hypervisor_type": hv_type,
            "power_state": str(raw.get("power_state", "unknown"))[:50],
            "host_id": str(raw.get("host_id", ""))[:120] or None,
            "cpu_count": cpu_count,
            "memory_mb": memory_mb,
            "guest_os": str(raw.get("guest_os", ""))[:200] or None,
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
            "resource_pool": str(raw.get("resource_pool", ""))[:200] or None,
            "cluster": str(raw.get("cluster", ""))[:200] or None,
            "datastores": [
                str(ds)[:200]
                for ds in (raw.get("datastores") or [])[:10]
                if isinstance(ds, str)
            ],
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        vms.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "hypervisor_type": hv_type,
        "vms": vms,
        "returned": len(vms),
        "truncated": len(raw_vms) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_host_inventory(
    *,
    hypervisor_type: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch physical host inventory from the hypervisor gateway.

    Args:
        hypervisor_type: One of 'vmware_vcenter', 'kvm_libvirt', 'hyperv'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with hosts list, sync metadata, and provenance
    """
    hv_type = _validate_hypervisor_type(hypervisor_type)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "hypervisor_type": hv_type,
        "limit": str(MAX_HOSTS_PER_PAGE),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/hosts?{query}"
    payload = _get_json(url, headers)

    raw_hosts = payload.get("hosts", [])
    if not isinstance(raw_hosts, list):
        raise ConnectionError("Hypervisor host inventory response did not match the expected contract")

    hosts = []
    for raw in raw_hosts[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        host_id = str(raw.get("host_id", "")).strip()
        if not host_id:
            continue
        total_cpu_cores = _safe_int(raw.get("total_cpu_cores"))
        total_memory_mb = _safe_int(raw.get("total_memory_mb"))
        row = {
            "host_id": host_id,
            "name": str(raw.get("name", ""))[:200],
            "hypervisor_type": hv_type,
            "status": str(raw.get("status", "unknown"))[:50],
            "cluster": str(raw.get("cluster", ""))[:200] or None,
            "total_cpu_cores": total_cpu_cores,
            "total_memory_mb": total_memory_mb,
            "cpu_model": str(raw.get("cpu_model", ""))[:200] or None,
            "esxi_version": str(raw.get("esxi_version", ""))[:100] or None,
            "libvirt_version": str(raw.get("libvirt_version", ""))[:100] or None,
            "hyperv_version": str(raw.get("hyperv_version", ""))[:100] or None,
            "network_adapters": [
                str(nic)[:200]
                for nic in (raw.get("network_adapters") or [])[:10]
                if isinstance(nic, str)
            ],
            "datastores": [
                str(ds)[:200]
                for ds in (raw.get("datastores") or [])[:10]
                if isinstance(ds, str)
            ],
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        hosts.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "hypervisor_type": hv_type,
        "hosts": hosts,
        "returned": len(hosts),
        "truncated": len(raw_hosts) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_power_metrics(
    *,
    hypervisor_type: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    vm_ids: list[str] | None = None,
    host_id: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch power consumption metrics from the hypervisor gateway.

    Args:
        hypervisor_type: One of 'vmware_vcenter', 'kvm_libvirt', 'hyperv'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        vm_ids: Optional list of specific VM IDs to fetch metrics for
        host_id: Optional host ID to fetch host-level power metrics
        since: Optional ISO-8601 timestamp for incremental sync

    Returns:
        Dict with power metrics list and metadata
    """
    hv_type = _validate_hypervisor_type(hypervisor_type)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "hypervisor_type": hv_type,
        "limit": str(MAX_ROWS),
    }
    if vm_ids:
        if len(vm_ids) > 100:
            raise ValueError("at most 100 vm_ids may be requested at once")
        validated = [_validate_vm_id(vid) for vid in vm_ids]
        params["vm_ids"] = ",".join(validated)
    if host_id:
        params["host_id"] = _validate_host_id(host_id)
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
        raise ConnectionError("Hypervisor power metrics response did not match the expected contract")

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
            "hypervisor_type": hv_type,
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
        "hypervisor_type": hv_type,
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
    hypervisor_type: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    host_id: str | None = None,
) -> dict[str, Any]:
    """Fetch capacity and utilization metrics from the hypervisor gateway.

    Args:
        hypervisor_type: One of 'vmware_vcenter', 'kvm_libvirt', 'hyperv'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        host_id: Optional host ID to fetch host-level capacity metrics

    Returns:
        Dict with capacity metrics list and metadata
    """
    hv_type = _validate_hypervisor_type(hypervisor_type)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "hypervisor_type": hv_type,
        "limit": str(MAX_ROWS),
    }
    if host_id:
        params["host_id"] = _validate_host_id(host_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/metrics/capacity?{query}"
    payload = _get_json(url, headers)

    raw_metrics = payload.get("metrics", [])
    if not isinstance(raw_metrics, list):
        raise ConnectionError("Hypervisor capacity metrics response did not match the expected contract")

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
            "hypervisor_type": hv_type,
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
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "source_timestamp": _parse_timestamp(raw.get("source_timestamp")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        metrics.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "hypervisor_type": hv_type,
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
    hypervisor_type: str,
    vm_ids: list[str],
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch current state for specific VMs.

    Args:
        hypervisor_type: One of 'vmware_vcenter', 'kvm_libvirt', 'hyperv'
        vm_ids: List of VM IDs to fetch state for (1-100)
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with VM state list and metadata
    """
    hv_type = _validate_hypervisor_type(hypervisor_type)
    if not vm_ids:
        raise ValueError("at least one vm_id is required")
    if len(vm_ids) > 100:
        raise ValueError("at most 100 vm_ids may be requested at once")
    validated_ids = [_validate_vm_id(vid) for vid in vm_ids]

    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "hypervisor_type": hv_type,
        "vm_ids": ",".join(validated_ids),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/vms/state?{query}"
    payload = _get_json(url, headers)

    raw_states = payload.get("states", [])
    if not isinstance(raw_states, list):
        raise ConnectionError("Hypervisor VM state response did not match the expected contract")

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
            "hypervisor_type": hv_type,
            "power_state": str(raw.get("power_state", "unknown"))[:50],
            "uptime_seconds": uptime_s,
            "guest_os": str(raw.get("guest_os", ""))[:200] or None,
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
            "tools_status": str(raw.get("tools_status", ""))[:50] or None,
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        states.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "hypervisor_type": hv_type,
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
    """Check hypervisor gateway health: connectivity, auth, schema, and freshness.

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
        freshness_url = f"{base}/vms?{urllib.parse.urlencode({'hypervisor_type': 'kvm_libvirt', 'limit': '1'})}"
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
    "DEFAULT_HYPERVISOR_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_HYPERVISORS",
    "VENDOR",
    "fetch_capacity_metrics",
    "fetch_host_inventory",
    "fetch_power_metrics",
    "fetch_vm_inventory",
    "fetch_vm_state",
    "health_check",
    "probe",
]
