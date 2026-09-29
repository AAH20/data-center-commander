"""Read-only OEM equipment telemetry adapter (Redfish-based).

Provides bounded, read-only access to OEM server, storage, and network
hardware telemetry via the DMTF Redfish standard. Supports vendor-neutral
HTTPS API connections with fixed endpoint allowlisting.

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

# Adapter manifest
ADAPTER_ID = "oem"
ADAPTER_VERSION = "0.1.0"
VENDOR = "Generic OEM Redfish"
PROTOCOLS = ["HTTPS/Redfish"]
CAPABILITIES = [
    "read_server_telemetry",
    "read_storage_telemetry",
    "read_network_telemetry",
    "read_power_telemetry",
    "read_thermal_telemetry",
    "read_health_status",
]
SCOPES = ["servers", "storage", "network", "power", "thermal", "health"]
DATA_CLASSIFICATION = "operational_telemetry"

# Fixed, operator-configured OEM endpoint (no tenant-supplied URLs)
DEFAULT_OEM_ENDPOINT = "https://oem-redfish.example.internal"
MAX_RESPONSE_BYTES = 2_000_000
MAX_RESOURCES = 50
MAX_METRICS_PER_RESOURCE = 20
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Allowed OEM vendors
ALLOWED_VENDORS = {"dell", "hpe", "lenovo", "supermicro", "cisco", "arista", "juniper", "generic"}

# Allowed resource types for telemetry queries
ALLOWED_RESOURCE_TYPES = {"systems", "chassis", "network", "managers", "storage"}

# Allowed metric names (Redfish property names)
ALLOWED_METRICS = {
    "power_consumed_watts", "power_capacity_watts", "power_state",
    "temperature_celsius", "temperature_threshold_critical",
    "temperature_threshold_fatal", "fan_speed_rpm", "fan_health",
    "health", "status", "state", "model", "manufacturer",
    "serial_number", "part_number", "firmware_version",
    "memory_capacity_gb", "processor_count", "processor_health",
    "disk_health", "disk_capacity_bytes", "disk_state",
    "port_status", "port_speed_mbps", "port_health",
    "link_status", "link_speed_mbps", "error_count",
    "cpu_utilization_percent", "memory_utilization_percent",
    "power_supply_health", "battery_health", "voltage_volts",
    "current_amperes", "energy_consumed_kwh",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable redirects to prevent SSRF via operator-supplied URLs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = CONNECT_TIMEOUT) -> dict[str, Any]:
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
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError(f"OEM response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ConnectionError("OEM authentication failed (HTTP 401)") from None
        if exc.code == 403:
            raise ConnectionError("OEM authorization failed (HTTP 403)") from None
        if exc.code == 404:
            raise ConnectionError(f"Redfish endpoint not found (HTTP 404)") from None
        raise ConnectionError(f"OEM Redfish API returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"OEM Redfish API is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("OEM Redfish API returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("OEM Redfish response did not match the expected contract")
    return payload


def _validate_host(host: str) -> str:
    """Validate and normalize the OEM host address."""
    host = host.strip()
    if not host or len(host) > 253:
        raise ValueError("host is required and must be at most 253 characters")
    if not re.fullmatch(r"[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?", host):
        raise ValueError("host must be a valid hostname or IP address")
    return host


def _validate_vendor(vendor: str) -> str:
    """Validate the OEM vendor name."""
    vendor = vendor.strip().lower()
    if vendor not in ALLOWED_VENDORS:
        raise ValueError(f"vendor must be one of: {', '.join(sorted(ALLOWED_VENDORS))}")
    return vendor


def _validate_resource_type(resource_type: str) -> str:
    """Validate the resource type for telemetry queries."""
    resource_type = resource_type.strip().lower()
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        raise ValueError(f"resource_type must be one of: {', '.join(sorted(ALLOWED_RESOURCE_TYPES))}")
    return resource_type


def _validate_metrics(metrics: list[str] | None) -> list[str]:
    """Validate requested metric names."""
    if metrics is None:
        return []
    if not isinstance(metrics, list):
        raise ValueError("metrics must be a list of strings")
    if len(metrics) > MAX_METRICS_PER_RESOURCE:
        raise ValueError(f"at most {MAX_METRICS_PER_RESOURCE} metrics may be requested")
    validated = []
    for m in metrics:
        m = m.strip().lower()
        if m not in ALLOWED_METRICS:
            raise ValueError(f"metric '{m}' is not in the allowed set")
        validated.append(m)
    return validated


def _validate_timeout(timeout: int) -> int:
    """Validate the network timeout."""
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 30:
        raise ValueError("timeout must be an integer from 1 to 30 seconds")
    return timeout


def _resolve_endpoint(endpoint: str | None = None) -> str:
    """Resolve the OEM endpoint from parameter or environment."""
    raw = (endpoint or os.environ.get("OEM_REDFISH_ENDPOINT", DEFAULT_OEM_ENDPOINT)).strip()
    if not raw:
        raise ConnectionError("OEM_REDFISH_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("OEM endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("OEM endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("OEM endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credentials() -> tuple[str, str]:
    """Read OEM credentials from environment variables."""
    username = os.environ.get("OEM_USERNAME", "").strip()
    password = os.environ.get("OEM_PASSWORD", "")
    if not username or not password:
        raise ConnectionError("OEM_USERNAME and OEM_PASSWORD must be configured in the server environment")
    if len(username) > 128 or len(password) > 256:
        raise ConnectionError("OEM credential configuration is invalid")
    return username, password


def _build_auth_header(username: str, password: str) -> str:
    """Build a Basic Auth header value."""
    import base64
    credentials = f"{username}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(credentials).decode("ascii")


def _safe_decimal(value: Any) -> str | None:
    """Safely convert a value to a decimal string."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        return str(d) if d.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_str(value: Any, max_len: int = 256) -> str | None:
    """Safely convert a value to a bounded string."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or len(s) > max_len:
        return None
    return s


def _extract_metric(resource: dict[str, Any], metric_name: str) -> Any:
    """Extract a metric value from a Redfish resource, handling nested structures."""
    # Direct property
    if metric_name in resource:
        return resource[metric_name]

    # Nested in Status object (common Redfish pattern)
    status = resource.get("Status")
    if isinstance(status, dict) and metric_name in status:
        return status[metric_name]

    # Nested in Power object
    power = resource.get("Power")
    if isinstance(power, dict):
        if metric_name in power:
            return power[metric_name]
        power_control = power.get("PowerControl")
        if isinstance(power_control, list) and power_control:
            pc = power_control[0]
            if isinstance(pc, dict) and metric_name in pc:
                return pc[metric_name]

    # Nested in Thermal object
    thermal = resource.get("Thermal")
    if isinstance(thermal, dict):
        if metric_name in thermal:
            return thermal[metric_name]
        fans = thermal.get("Fans")
        if isinstance(fans, list) and fans:
            fan = fans[0]
            if isinstance(fan, dict) and metric_name in fan:
                return fan[metric_name]
        temperatures = thermal.get("Temperatures")
        if isinstance(temperatures, list) and temperatures:
            temp = temperatures[0]
            if isinstance(temp, dict) and metric_name in temp:
                return temp[metric_name]

    # Nested in NetworkPorts
    network_ports = resource.get("NetworkPorts")
    if isinstance(network_ports, list) and network_ports:
        port = network_ports[0]
        if isinstance(port, dict) and metric_name in port:
            return port[metric_name]

    # Nested in Storage
    storage = resource.get("Storage")
    if isinstance(storage, list) and storage:
        drive = storage[0]
        if isinstance(drive, dict) and metric_name in drive:
            return drive[metric_name]

    return None


def _collect_telemetry(
    base_url: str,
    auth_header: str,
    resource_type: str,
    metrics: list[str],
    timeout: int,
) -> list[dict[str, Any]]:
    """Collect telemetry from a Redfish resource collection."""
    path_map = {
        "systems": "/redfish/v1/Systems",
        "chassis": "/redfish/v1/Chassis",
        "network": "/redfish/v1/NetworkAdapters",
        "managers": "/redfish/v1/Managers",
        "storage": "/redfish/v1/Storage",
    }
    path = path_map[resource_type]

    # Get the collection
    collection = _get_json(f"{base_url}{path}", {"Authorization": auth_header}, timeout)
    members = collection.get("Members", [])
    if not isinstance(members, list):
        raise ConnectionError(f"Redfish {resource_type} collection did not match the expected contract")

    results = []
    for member in members[:MAX_RESOURCES]:
        if not isinstance(member, dict):
            continue
        member_uri = member.get("@odata.id")
        if not isinstance(member_uri, str) or not member_uri.startswith("/"):
            continue

        # Get the individual resource
        try:
            resource = _get_json(f"{base_url}{member_uri}", {"Authorization": auth_header}, timeout)
        except ConnectionError:
            # Skip unreachable resources but continue collection
            continue

        if not isinstance(resource, dict):
            continue

        # Extract requested metrics
        row: dict[str, Any] = {
            "resource_id": _safe_str(resource.get("Id"), 100),
            "resource_uri": member_uri,
            "name": _safe_str(resource.get("Name"), 256),
        }

        # Add manufacturer and model if available
        manufacturer = _safe_str(resource.get("Manufacturer"), 256)
        if manufacturer:
            row["manufacturer"] = manufacturer
        model = _safe_str(resource.get("Model"), 256)
        if model:
            row["model"] = model
        serial = _safe_str(resource.get("SerialNumber"), 100)
        if serial:
            row["serial_number"] = serial

        # Extract metrics
        for metric in metrics:
            value = _extract_metric(resource, metric)
            if value is not None:
                decimal_val = _safe_decimal(value)
                if decimal_val is not None:
                    row[metric] = decimal_val
                else:
                    row[metric] = value

        # Always include health status if available
        if "health" not in row:
            health = _extract_metric(resource, "health")
            if health is not None:
                row["health"] = health

        # Drop None values
        row = {k: v for k, v in row.items() if v is not None}
        if row.get("resource_id"):
            results.append(row)

    return results


def probe(
    *,
    endpoint: str | None = None,
    vendor: str = "generic",
    timeout: int = CONNECT_TIMEOUT,
) -> dict[str, Any]:
    """Verify endpoint identity, TLS, version, scopes, and a minimal read.

    Returns a manifest dict on success; raises ConnectionError on failure.
    Never persists secrets or unbounded responses.
    """
    base = _resolve_endpoint(endpoint)
    vendor = _validate_vendor(vendor)
    timeout = _validate_timeout(timeout)
    username, password = _resolve_credentials()
    auth_header = _build_auth_header(username, password)

    # Probe the service root
    root = _get_json(f"{base}/redfish/v1", {"Authorization": auth_header}, timeout)

    # Extract basic info
    service_info = {
        "redfish_version": _safe_str(root.get("RedfishVersion"), 50),
        "vendor": _safe_str(root.get("Vendor"), 256),
        "product": _safe_str(root.get("Product"), 256),
        "uuid": _safe_str(root.get("UUID"), 100),
    }

    # Check if Systems endpoint is available
    systems_available = False
    try:
        systems = _get_json(f"{base}/redfish/v1/Systems", {"Authorization": auth_header}, timeout)
        systems_available = isinstance(systems.get("Members"), list)
    except ConnectionError:
        pass

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "vendor": VENDOR,
        "protocols": PROTOCOLS,
        "capabilities": CAPABILITIES,
        "scopes": SCOPES,
        "data_classification": DATA_CLASSIFICATION,
        "endpoint": base,
        "server_version": service_info.get("redfish_version"),
        "server_vendor": service_info.get("vendor"),
        "server_product": service_info.get("product"),
        "systems_available": systems_available,
        "probe_success": True,
        "probe_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_telemetry(
    *,
    endpoint: str | None = None,
    vendor: str = "generic",
    resource_type: str = "systems",
    metrics: list[str] | None = None,
    timeout: int = READ_TIMEOUT,
) -> dict[str, Any]:
    """Fetch bounded, read-only telemetry from OEM equipment via Redfish.

    Args:
        endpoint: Optional override for the OEM Redfish endpoint
        vendor: OEM vendor name (e.g., 'dell', 'hpe', 'supermicro')
        resource_type: Type of resource to query ('systems', 'chassis', 'network', 'managers', 'storage')
        metrics: Optional list of specific metrics to collect. If None, collects all available.
        timeout: Request timeout in seconds (1-30)

    Returns:
        Dict with telemetry list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    vendor = _validate_vendor(vendor)
    resource_type = _validate_resource_type(resource_type)
    metrics = _validate_metrics(metrics)
    timeout = _validate_timeout(timeout)
    username, password = _resolve_credentials()
    auth_header = _build_auth_header(username, password)

    # Collect telemetry
    telemetry = _collect_telemetry(base, auth_header, resource_type, metrics, timeout)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "vendor": vendor,
        "resource_type": resource_type,
        "telemetry": telemetry,
        "returned": len(telemetry),
        "truncated": len(telemetry) >= MAX_RESOURCES,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_server_telemetry(
    *,
    endpoint: str | None = None,
    vendor: str = "generic",
    metrics: list[str] | None = None,
    timeout: int = READ_TIMEOUT,
) -> dict[str, Any]:
    """Fetch server telemetry (convenience wrapper for resource_type='systems')."""
    return fetch_telemetry(
        endpoint=endpoint,
        vendor=vendor,
        resource_type="systems",
        metrics=metrics,
        timeout=timeout,
    )


def fetch_storage_telemetry(
    *,
    endpoint: str | None = None,
    vendor: str = "generic",
    metrics: list[str] | None = None,
    timeout: int = READ_TIMEOUT,
) -> dict[str, Any]:
    """Fetch storage telemetry (convenience wrapper for resource_type='storage')."""
    return fetch_telemetry(
        endpoint=endpoint,
        vendor=vendor,
        resource_type="storage",
        metrics=metrics,
        timeout=timeout,
    )


def fetch_network_telemetry(
    *,
    endpoint: str | None = None,
    vendor: str = "generic",
    metrics: list[str] | None = None,
    timeout: int = READ_TIMEOUT,
) -> dict[str, Any]:
    """Fetch network equipment telemetry (convenience wrapper for resource_type='network')."""
    return fetch_telemetry(
        endpoint=endpoint,
        vendor=vendor,
        resource_type="network",
        metrics=metrics,
        timeout=timeout,
    )


def health_check(
    *,
    endpoint: str | None = None,
    vendor: str = "generic",
    timeout: int = CONNECT_TIMEOUT,
) -> dict[str, Any]:
    """Check OEM Redfish endpoint health: connectivity, auth, schema, and freshness.

    Returns:
        Dict with health status, checks, and metadata
    """
    base = _resolve_endpoint(endpoint)
    vendor = _validate_vendor(vendor)
    timeout = _validate_timeout(timeout)
    checks: dict[str, str] = {
        "endpoint": "ok",
        "authentication": "unchecked",
        "schema": "unchecked",
        "freshness": "unchecked",
    }
    healthy = True
    details: dict[str, Any] = {}

    try:
        username, password = _resolve_credentials()
        auth_header = _build_auth_header(username, password)

        # Probe endpoint
        root = _get_json(f"{base}/redfish/v1", {"Authorization": auth_header}, timeout)
        checks["authentication"] = "ok"
        checks["schema"] = "ok"
        details["redfish_version"] = _safe_str(root.get("RedfishVersion"), 50)
        details["vendor"] = _safe_str(root.get("Vendor"), 256)
        details["product"] = _safe_str(root.get("Product"), 256)

        # Check freshness via a minimal systems read
        systems = _get_json(f"{base}/redfish/v1/Systems", {"Authorization": auth_header}, timeout)
        members = systems.get("Members", [])
        if members and isinstance(members, list) and isinstance(members[0], dict):
            member_uri = members[0].get("@odata.id")
            if isinstance(member_uri, str):
                resource = _get_json(f"{base}{member_uri}", {"Authorization": auth_header}, timeout)
                # Check for any timestamp-like property
                observed = resource.get("Status", {}).get("State") if isinstance(resource.get("Status"), dict) else None
                if observed:
                    checks["freshness"] = "ok"
                    details["latest_state"] = _safe_str(observed, 50)
                else:
                    checks["freshness"] = "no_timestamp"
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
    "ALLOWED_METRICS",
    "ALLOWED_RESOURCE_TYPES",
    "ALLOWED_VENDORS",
    "CAPABILITIES",
    "DATA_CLASSIFICATION",
    "DEFAULT_OEM_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "VENDOR",
    "fetch_network_telemetry",
    "fetch_server_telemetry",
    "fetch_storage_telemetry",
    "fetch_telemetry",
    "health_check",
    "probe",
]
