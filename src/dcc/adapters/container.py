"""Read-only container platform telemetry adapter.

Provides bounded, read-only access to container, pod, and node inventory,
power, and capacity telemetry from Docker, Kubernetes, Podman, containerd,
and OpenShift through a vendor-neutral HTTPS API gateway. The gateway fronts
the container-runtime-specific APIs and exposes a unified, read-only contract.

Supported platforms:
  - Docker (via gateway)
  - Kubernetes (via gateway)
  - Podman (via gateway)
  - containerd (via gateway)
  - OpenShift (via gateway)

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

# Fixed, operator-configured container gateway endpoint (no tenant-supplied URLs)
DEFAULT_CONTAINER_ENDPOINT = "https://container-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_CONTAINERS_PER_PAGE = 500
MAX_PODS_PER_PAGE = 500
MAX_NODES_PER_PAGE = 200
MAX_ROWS = 200
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "container"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Multi-Container Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = [
    "read_container_inventory",
    "read_pod_inventory",
    "read_node_inventory",
    "read_power_metrics",
    "read_capacity_metrics",
    "read_container_state",
    "read_pod_state",
]
SCOPES = [
    "container_inventory",
    "pod_inventory",
    "node_inventory",
    "power_metrics",
    "capacity_metrics",
    "container_state",
    "pod_state",
]
DATA_CLASSIFICATION = "operational_telemetry"

SUPPORTED_PLATFORMS = {"docker", "kubernetes", "podman", "containerd", "openshift"}


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
                f"Container gateway response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Container gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Container gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Container gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Container gateway response did not match the expected contract")
    return payload


def _validate_platform(platform: str) -> str:
    """Validate the platform identifier."""
    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"platform must be one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )
    return platform


def _validate_container_id(container_id: str) -> str:
    """Validate a container identifier."""
    container_id = container_id.strip()
    if not container_id or len(container_id) > 120:
        raise ValueError("container_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", container_id):
        raise ValueError("container_id contains unsupported characters")
    return container_id


def _validate_pod_id(pod_id: str) -> str:
    """Validate a pod identifier."""
    pod_id = pod_id.strip()
    if not pod_id or len(pod_id) > 120:
        raise ValueError("pod_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", pod_id):
        raise ValueError("pod_id contains unsupported characters")
    return pod_id


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
    """Resolve the container gateway endpoint from parameter or environment."""
    raw = (
        endpoint
        or os.environ.get("CONTAINER_GATEWAY_ENDPOINT", DEFAULT_CONTAINER_ENDPOINT)
    ).strip()
    if not raw:
        raise ConnectionError("CONTAINER_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("Container gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Container gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("Container gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("CONTAINER_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("Container credential reference is invalid")
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
        raise ConnectionError("Container gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("Container gateway scopes did not match the expected contract")

    supported_platforms = info.get("supported_platforms", [])
    if not isinstance(supported_platforms, list):
        raise ConnectionError("Container gateway supported_platforms did not match the expected contract")

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


def fetch_container_inventory(
    *,
    platform: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Fetch container inventory from the container gateway.

    Args:
        platform: One of 'docker', 'kubernetes', 'podman', 'containerd', 'openshift'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace (Kubernetes/OpenShift)
        node_id: Optional filter by node identifier

    Returns:
        Dict with containers list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_CONTAINERS_PER_PAGE),
    }
    if namespace:
        ns = namespace.strip()
        if len(ns) > 200:
            raise ValueError("namespace must be at most 200 characters")
        params["namespace"] = ns
    if node_id:
        params["node_id"] = _validate_node_id(node_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/containers?{query}"
    payload = _get_json(url, headers)

    raw_containers = payload.get("containers", [])
    if not isinstance(raw_containers, list):
        raise ConnectionError("Container inventory response did not match the expected contract")

    containers = []
    for raw in raw_containers[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        container_id = str(raw.get("container_id", "")).strip()
        if not container_id:
            continue
        row = {
            "container_id": container_id,
            "name": str(raw.get("name", ""))[:200],
            "platform": plat,
            "image": str(raw.get("image", ""))[:200] or None,
            "status": str(raw.get("status", "unknown"))[:50],
            "node_id": str(raw.get("node_id", ""))[:120] or None,
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "pod_id": str(raw.get("pod_id", ""))[:120] or None,
            "cpu_limit_millicores": _safe_int(raw.get("cpu_limit_millicores")),
            "memory_limit_mb": _safe_int(raw.get("memory_limit_mb")),
            "restart_count": _safe_int(raw.get("restart_count")),
            "ports": [
                str(port)[:100]
                for port in (raw.get("ports") or [])[:20]
                if isinstance(port, str)
            ],
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        containers.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "containers": containers,
        "returned": len(containers),
        "truncated": len(raw_containers) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_pod_inventory(
    *,
    platform: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Fetch pod inventory from the container gateway (Kubernetes/OpenShift).

    Args:
        platform: One of 'kubernetes', 'openshift'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace
        node_id: Optional filter by node identifier

    Returns:
        Dict with pods list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    if plat not in {"kubernetes", "openshift"}:
        raise ValueError("pod inventory is only supported for kubernetes and openshift")
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_PODS_PER_PAGE),
    }
    if namespace:
        ns = namespace.strip()
        if len(ns) > 200:
            raise ValueError("namespace must be at most 200 characters")
        params["namespace"] = ns
    if node_id:
        params["node_id"] = _validate_node_id(node_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/pods?{query}"
    payload = _get_json(url, headers)

    raw_pods = payload.get("pods", [])
    if not isinstance(raw_pods, list):
        raise ConnectionError("Pod inventory response did not match the expected contract")

    pods = []
    for raw in raw_pods[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        pod_id = str(raw.get("pod_id", "")).strip()
        if not pod_id:
            continue
        row = {
            "pod_id": pod_id,
            "name": str(raw.get("name", ""))[:200],
            "platform": plat,
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "status": str(raw.get("status", "unknown"))[:50],
            "node_id": str(raw.get("node_id", ""))[:120] or None,
            "phase": str(raw.get("phase", "unknown"))[:50],
            "container_count": _safe_int(raw.get("container_count")),
            "restart_count": _safe_int(raw.get("restart_count")),
            "ip_addresses": [
                str(ip)[:64]
                for ip in (raw.get("ip_addresses") or [])[:10]
                if isinstance(ip, str)
            ],
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        pods.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "pods": pods,
        "returned": len(pods),
        "truncated": len(raw_pods) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_node_inventory(
    *,
    platform: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch node inventory from the container gateway.

    Args:
        platform: One of 'docker', 'kubernetes', 'podman', 'containerd', 'openshift'
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
        raise ConnectionError("Node inventory response did not match the expected contract")

    nodes = []
    for raw in raw_nodes[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id", "")).strip()
        if not node_id:
            continue
        row = {
            "node_id": node_id,
            "name": str(raw.get("name", ""))[:200],
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "role": str(raw.get("role", "unknown"))[:50],
            "total_cpu_cores": _safe_int(raw.get("total_cpu_cores")),
            "total_memory_mb": _safe_int(raw.get("total_memory_mb")),
            "container_runtime": str(raw.get("container_runtime", ""))[:100] or None,
            "runtime_version": str(raw.get("runtime_version", ""))[:100] or None,
            "os_image": str(raw.get("os_image", ""))[:200] or None,
            "kernel_version": str(raw.get("kernel_version", ""))[:100] or None,
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
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
    platform: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    container_ids: list[str] | None = None,
    node_id: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch power consumption metrics from the container gateway.

    Args:
        platform: One of 'docker', 'kubernetes', 'podman', 'containerd', 'openshift'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        container_ids: Optional list of specific container IDs to fetch metrics for
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
    if container_ids:
        if len(container_ids) > 100:
            raise ValueError("at most 100 container_ids may be requested at once")
        validated = [_validate_container_id(cid) for cid in container_ids]
        params["container_ids"] = ",".join(validated)
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
        raise ConnectionError("Container power metrics response did not match the expected contract")

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
    platform: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Fetch capacity and utilization metrics from the container gateway.

    Args:
        platform: One of 'docker', 'kubernetes', 'podman', 'containerd', 'openshift'
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
        raise ConnectionError("Container capacity metrics response did not match the expected contract")

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
            "container_count": _safe_int(raw.get("container_count")),
            "pod_count": _safe_int(raw.get("pod_count")),
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


def fetch_container_state(
    *,
    platform: str,
    container_ids: list[str],
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch current state for specific containers.

    Args:
        platform: One of 'docker', 'kubernetes', 'podman', 'containerd', 'openshift'
        container_ids: List of container IDs to fetch state for (1-100)
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with container state list and metadata
    """
    plat = _validate_platform(platform)
    if not container_ids:
        raise ValueError("at least one container_id is required")
    if len(container_ids) > 100:
        raise ValueError("at most 100 container_ids may be requested at once")
    validated_ids = [_validate_container_id(cid) for cid in container_ids]

    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "container_ids": ",".join(validated_ids),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/containers/state?{query}"
    payload = _get_json(url, headers)

    raw_states = payload.get("states", [])
    if not isinstance(raw_states, list):
        raise ConnectionError("Container state response did not match the expected contract")

    states = []
    for raw in raw_states[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        container_id = str(raw.get("container_id", "")).strip()
        if not container_id:
            continue
        row = {
            "container_id": container_id,
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "uptime_seconds": _safe_int(raw.get("uptime_seconds")),
            "restart_count": _safe_int(raw.get("restart_count")),
            "image": str(raw.get("image", ""))[:200] or None,
            "ip_addresses": [
                str(ip)[:64]
                for ip in (raw.get("ip_addresses") or [])[:10]
                if isinstance(ip, str)
            ],
            "ports": [
                str(port)[:100]
                for port in (raw.get("ports") or [])[:20]
                if isinstance(port, str)
            ],
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


def fetch_pod_state(
    *,
    platform: str,
    pod_ids: list[str],
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch current state for specific pods (Kubernetes/OpenShift).

    Args:
        platform: One of 'kubernetes', 'openshift'
        pod_ids: List of pod IDs to fetch state for (1-100)
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with pod state list and metadata
    """
    plat = _validate_platform(platform)
    if plat not in {"kubernetes", "openshift"}:
        raise ValueError("pod state is only supported for kubernetes and openshift")
    if not pod_ids:
        raise ValueError("at least one pod_id is required")
    if len(pod_ids) > 100:
        raise ValueError("at most 100 pod_ids may be requested at once")
    validated_ids = [_validate_pod_id(pid) for pid in pod_ids]

    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "pod_ids": ",".join(validated_ids),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/pods/state?{query}"
    payload = _get_json(url, headers)

    raw_states = payload.get("states", [])
    if not isinstance(raw_states, list):
        raise ConnectionError("Pod state response did not match the expected contract")

    states = []
    for raw in raw_states[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        pod_id = str(raw.get("pod_id", "")).strip()
        if not pod_id:
            continue
        row = {
            "pod_id": pod_id,
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "phase": str(raw.get("phase", "unknown"))[:50],
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "node_id": str(raw.get("node_id", ""))[:120] or None,
            "container_count": _safe_int(raw.get("container_count")),
            "restart_count": _safe_int(raw.get("restart_count")),
            "ip_addresses": [
                str(ip)[:64]
                for ip in (raw.get("ip_addresses") or [])[:10]
                if isinstance(ip, str)
            ],
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
    """Check container gateway health: connectivity, auth, schema, and freshness.

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

        # Check freshness via a minimal container read
        freshness_url = f"{base}/containers?{urllib.parse.urlencode({'platform': 'docker', 'limit': '1'})}"
        freshness = _get_json(freshness_url, headers)
        containers = freshness.get("containers", [])
        if containers and isinstance(containers[0], dict):
            observed = _parse_timestamp(containers[0].get("observed_at"))
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
    "DEFAULT_CONTAINER_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_PLATFORMS",
    "VENDOR",
    "fetch_capacity_metrics",
    "fetch_container_inventory",
    "fetch_container_state",
    "fetch_node_inventory",
    "fetch_pod_inventory",
    "fetch_pod_state",
    "fetch_power_metrics",
    "health_check",
    "probe",
]
