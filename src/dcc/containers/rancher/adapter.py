"""Rancher adapter: core HTTP client, probe, and health check.

Provides bounded, read-only access to Rancher-managed Kubernetes clusters,
projects, namespaces, catalogs, and monitoring through a vendor-neutral
HTTPS API gateway.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Fixed, operator-configured Rancher gateway endpoint (no tenant-supplied URLs)
DEFAULT_RANCHER_ENDPOINT = "https://rancher-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_CLUSTERS_PER_PAGE = 500
MAX_PROJECTS_PER_PAGE = 500
MAX_NAMESPACES_PER_PAGE = 500
MAX_CATALOGS_PER_PAGE = 200
MAX_ROWS = 200
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "rancher"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Rancher Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = [
    "read_cluster_inventory",
    "read_project_inventory",
    "read_namespace_inventory",
    "read_catalog_inventory",
    "read_monitoring_metrics",
    "read_cluster_state",
]
SCOPES = [
    "cluster_inventory",
    "project_inventory",
    "namespace_inventory",
    "catalog_inventory",
    "monitoring_metrics",
    "cluster_state",
]
DATA_CLASSIFICATION = "operational_telemetry"

SUPPORTED_PLATFORMS = {"rancher"}


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
                f"Rancher gateway response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"Rancher gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Rancher gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Rancher gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Rancher gateway response did not match the expected contract")
    return payload


def _validate_platform(platform: str) -> str:
    """Validate the platform identifier."""
    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"platform must be one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )
    return platform


def _validate_cluster_id(cluster_id: str) -> str:
    """Validate a cluster identifier."""
    cluster_id = cluster_id.strip()
    if not cluster_id or len(cluster_id) > 120:
        raise ValueError("cluster_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", cluster_id):
        raise ValueError("cluster_id contains unsupported characters")
    return cluster_id


def _validate_project_id(project_id: str) -> str:
    """Validate a project identifier."""
    project_id = project_id.strip()
    if not project_id or len(project_id) > 120:
        raise ValueError("project_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", project_id):
        raise ValueError("project_id contains unsupported characters")
    return project_id


def _validate_namespace_id(namespace_id: str) -> str:
    """Validate a namespace identifier."""
    namespace_id = namespace_id.strip()
    if not namespace_id or len(namespace_id) > 120:
        raise ValueError("namespace_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", namespace_id):
        raise ValueError("namespace_id contains unsupported characters")
    return namespace_id


def _validate_catalog_id(catalog_id: str) -> str:
    """Validate a catalog identifier."""
    catalog_id = catalog_id.strip()
    if not catalog_id or len(catalog_id) > 120:
        raise ValueError("catalog_id is required and must be at most 120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", catalog_id):
        raise ValueError("catalog_id contains unsupported characters")
    return catalog_id


def _parse_timestamp(value: Any) -> str | None:
    """Parse and validate an ISO-8601 timestamp from the gateway."""
    if not isinstance(value, str):
        return None
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely parse an integer value."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> float | None:
    """Safely parse a float value."""
    if value is None:
        return None
    try:
        f = float(value)
        return f if f == f and f != float("inf") and f != float("-inf") else None
    except (ValueError, TypeError):
        return None


def _resolve_endpoint(endpoint: str | None = None) -> str:
    """Resolve the Rancher gateway endpoint from parameter or environment."""
    raw = (
        endpoint
        or os.environ.get("RANCHER_GATEWAY_ENDPOINT", DEFAULT_RANCHER_ENDPOINT)
    ).strip()
    if not raw:
        raise ConnectionError("RANCHER_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("Rancher gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Rancher gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("Rancher gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("RANCHER_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("Rancher credential reference is invalid")
    return ref


@dataclass(slots=True)
class RancherConfig:
    """Configuration for the Rancher adapter."""
    endpoint: str
    api_version: str = "v1"
    vendor: str = "Rancher"
    product: str = "Rancher"
    rate_limit_per_minute: int = 60
    timeout_s: float = 15.0


class RancherAdapter:
    """Read-only Rancher adapter for cluster, project, namespace, catalog, and monitoring data."""

    def __init__(self, config: RancherConfig) -> None:
        self.config = config

    def health_check(self) -> bool:
        """Check Rancher gateway health."""
        try:
            result = health_check(endpoint=self.config.endpoint)
            return result.get("healthy", False)
        except Exception:
            return False

    def supports(self, capability: str) -> bool:
        """Check if the adapter supports a capability."""
        return capability in CAPABILITIES


def create_rancher_adapter(
    *,
    endpoint: str,
    api_version: str = "v1",
    vendor: str = "Rancher",
    product: str = "Rancher",
    rate_limit_per_minute: int = 60,
    timeout_s: float = 15.0,
) -> RancherAdapter:
    """Create a Rancher adapter with validation."""
    if not endpoint or not endpoint.startswith("https://"):
        raise ValueError("endpoint must use HTTPS")
    if len(endpoint) > 512:
        raise ValueError("endpoint URL is too long")
    if not re.fullmatch(r"v\d+", api_version):
        raise ValueError("api_version must be like 'v1', 'v2', etc.")
    if rate_limit_per_minute < 1:
        raise ValueError("rate_limit_per_minute must be at least 1")
    if timeout_s < 1.0:
        raise ValueError("timeout_s must be at least 1.0")

    config = RancherConfig(
        endpoint=endpoint,
        api_version=api_version,
        vendor=vendor,
        product=product,
        rate_limit_per_minute=rate_limit_per_minute,
        timeout_s=timeout_s,
    )
    return RancherAdapter(config)


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
        raise ConnectionError("Rancher gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("Rancher gateway scopes did not match the expected contract")

    supported_platforms = info.get("supported_platforms", [])
    if not isinstance(supported_platforms, list):
        raise ConnectionError("Rancher gateway supported_platforms did not match the expected contract")

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


def health_check(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Check Rancher gateway health: connectivity, auth, schema, and freshness.

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

        # Check freshness via a minimal cluster read
        freshness_url = f"{base}/clusters?{urllib.parse.urlencode({'platform': 'rancher', 'limit': '1'})}"
        freshness = _get_json(freshness_url, headers)
        clusters = freshness.get("clusters", [])
        if clusters and isinstance(clusters[0], dict):
            observed = _parse_timestamp(clusters[0].get("observed_at"))
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
    "DEFAULT_RANCHER_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_PLATFORMS",
    "VENDOR",
    "RancherAdapter",
    "RancherConfig",
    "create_rancher_adapter",
    "health_check",
    "probe",
]
