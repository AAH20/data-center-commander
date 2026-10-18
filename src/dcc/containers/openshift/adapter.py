"""OpenShift adapter core: configuration, HTTP client, and health checks."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# Fixed, operator-configured OpenShift gateway endpoint (no tenant-supplied URLs)
DEFAULT_OPENSHIFT_ENDPOINT = "https://openshift-gateway.example.internal/api/v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_PROJECTS_PER_PAGE = 200
MAX_DEPLOYMENTS_PER_PAGE = 200
MAX_ROUTES_PER_PAGE = 200
MAX_BUILDS_PER_PAGE = 200
MAX_TEMPLATES_PER_PAGE = 200
MAX_SCCS_PER_PAGE = 100
MAX_ROWS = 200
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Adapter manifest
ADAPTER_ID = "openshift"
ADAPTER_VERSION = "0.1.0"
VENDOR = "OpenShift Gateway"
PROTOCOLS = ["HTTPS/JSON"]
CAPABILITIES = [
    "read_projects",
    "read_deployments",
    "read_routes",
    "read_builds",
    "read_templates",
    "read_scc",
]
SCOPES = [
    "projects",
    "deployments",
    "routes",
    "builds",
    "templates",
    "scc",
]
DATA_CLASSIFICATION = "operational_telemetry"

SUPPORTED_PLATFORMS = {"openshift"}


@dataclass
class OpenShiftConfig:
    """Configuration for the OpenShift adapter."""

    endpoint: str
    api_version: str = "v1"
    vendor: str = "OpenShift"
    product: str = "OpenShift Container Platform"
    rate_limit_per_minute: int = 60
    timeout_s: float = 15.0
    max_retries: int = 3
    extra_headers: dict[str, str] = field(default_factory=dict)


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
                f"OpenShift gateway response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"OpenShift gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"OpenShift gateway is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("OpenShift gateway returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("OpenShift gateway response did not match the expected contract")
    return payload


def _validate_platform(platform: str) -> str:
    """Validate the platform identifier."""
    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"platform must be one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )
    return platform


def _validate_project_name(name: str) -> str:
    """Validate an OpenShift project name."""
    name = name.strip()
    if not name or len(name) > 63:
        raise ValueError("project name is required and must be at most 63 characters")
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", name):
        raise ValueError("project name must be a valid DNS-1123 subdomain")
    return name


def _validate_resource_name(name: str) -> str:
    """Validate an OpenShift resource name."""
    name = name.strip()
    if not name or len(name) > 253:
        raise ValueError("resource name is required and must be at most 253 characters")
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", name):
        raise ValueError("resource name must be a valid DNS-1123 subdomain")
    return name


def _validate_scc_name(name: str) -> str:
    """Validate an SCC name."""
    name = name.strip()
    if not name or len(name) > 253:
        raise ValueError("SCC name is required and must be at most 253 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", name):
        raise ValueError("SCC name contains unsupported characters")
    return name


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
    """Resolve the OpenShift gateway endpoint from parameter or environment."""
    raw = (
        endpoint
        or os.environ.get("OPENSHIFT_GATEWAY_ENDPOINT", DEFAULT_OPENSHIFT_ENDPOINT)
    ).strip()
    if not raw:
        raise ConnectionError("OPENSHIFT_GATEWAY_ENDPOINT is not configured")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https":
        raise ValueError("OpenShift gateway endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("OpenShift gateway endpoint must include a hostname")
    if len(raw) > 512:
        raise ValueError("OpenShift gateway endpoint URL is too long")
    return raw.rstrip("/")


def _resolve_credential(credential_ref: str | None = None) -> str | None:
    """Resolve a credential reference from environment (never from source)."""
    ref = (credential_ref or os.environ.get("OPENSHIFT_CREDENTIAL_REF", "")).strip()
    if not ref:
        return None
    if len(ref) > 256 or any(ch in ref for ch in "\r\n\x00"):
        raise ValueError("OpenShift credential reference is invalid")
    return ref


class OpenShiftAdapter:
    """Read-only OpenShift adapter for DCC."""

    def __init__(self, config: OpenShiftConfig):
        self.config = config

    def probe(
        self,
        *,
        endpoint: str | None = None,
        credential_ref: str | None = None,
    ) -> dict[str, Any]:
        """Verify endpoint identity, TLS, version, scopes, and a minimal read."""
        base = _resolve_endpoint(endpoint or self.config.endpoint)
        cred = _resolve_credential(credential_ref)
        headers = {"X-Credential-Ref": cred} if cred else {}

        info_url = f"{base}/info"
        info = _get_json(info_url, headers)

        server_version = str(info.get("version", ""))
        if not server_version:
            raise ConnectionError("OpenShift gateway did not report a version")

        reported_scopes = info.get("scopes", [])
        if not isinstance(reported_scopes, list):
            raise ConnectionError("OpenShift gateway scopes did not match the expected contract")

        supported_platforms = info.get("supported_platforms", [])
        if not isinstance(supported_platforms, list):
            raise ConnectionError("OpenShift gateway supported_platforms did not match the expected contract")

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
        self,
        *,
        endpoint: str | None = None,
        credential_ref: str | None = None,
    ) -> dict[str, Any]:
        """Check OpenShift gateway health: connectivity, auth, schema, and freshness."""
        base = _resolve_endpoint(endpoint or self.config.endpoint)
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

            info_url = f"{base}/info"
            info = _get_json(info_url, headers)
            checks["authentication"] = "ok"
            checks["schema"] = "ok"
            details["server_version"] = str(info.get("version", "unknown"))

            # Check freshness via a minimal project read
            freshness_url = f"{base}/projects?{urllib.parse.urlencode({'limit': '1'})}"
            freshness = _get_json(freshness_url, headers)
            projects = freshness.get("projects", [])
            if projects and isinstance(projects[0], dict):
                observed = _parse_timestamp(projects[0].get("observed_at"))
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
            checks["endpoint"] = "unavailable"
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


def create_openshift_adapter(
    *,
    endpoint: str,
    api_version: str = "v1",
    vendor: str = "OpenShift",
    product: str = "OpenShift Container Platform",
    rate_limit_per_minute: int = 60,
    timeout_s: float = 15.0,
    max_retries: int = 3,
    extra_headers: dict[str, str] | None = None,
) -> OpenShiftAdapter:
    """Create an OpenShift adapter with validation."""
    if not endpoint or not isinstance(endpoint, str):
        raise ValueError("endpoint is required")
    if len(endpoint) > 512:
        raise ValueError("endpoint URL is too long")
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https":
        raise ValueError("endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("endpoint must include a hostname")
    if not re.fullmatch(r"v\d+", api_version):
        raise ValueError("api_version must be like 'v1'")
    if rate_limit_per_minute < 1:
        raise ValueError("rate_limit_per_minute must be at least 1")
    if timeout_s < 1.0:
        raise ValueError("timeout_s must be at least 1.0")
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative")

    config = OpenShiftConfig(
        endpoint=endpoint,
        api_version=api_version,
        vendor=vendor,
        product=product,
        rate_limit_per_minute=rate_limit_per_minute,
        timeout_s=timeout_s,
        max_retries=max_retries,
        extra_headers=extra_headers or {},
    )
    return OpenShiftAdapter(config)


def probe(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Module-level probe convenience function."""
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    info_url = f"{base}/info"
    info = _get_json(info_url, headers)

    server_version = str(info.get("version", ""))
    if not server_version:
        raise ConnectionError("OpenShift gateway did not report a version")

    reported_scopes = info.get("scopes", [])
    if not isinstance(reported_scopes, list):
        raise ConnectionError("OpenShift gateway scopes did not match the expected contract")

    supported_platforms = info.get("supported_platforms", [])
    if not isinstance(supported_platforms, list):
        raise ConnectionError("OpenShift gateway supported_platforms did not match the expected contract")

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
    """Module-level health check convenience function."""
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

        info_url = f"{base}/info"
        info = _get_json(info_url, headers)
        checks["authentication"] = "ok"
        checks["schema"] = "ok"
        details["server_version"] = str(info.get("version", "unknown"))

        freshness_url = f"{base}/projects?{urllib.parse.urlencode({'limit': '1'})}"
        freshness = _get_json(freshness_url, headers)
        projects = freshness.get("projects", [])
        if projects and isinstance(projects[0], dict):
            observed = _parse_timestamp(projects[0].get("observed_at"))
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
        checks["endpoint"] = "unavailable"
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
    "DEFAULT_OPENSHIFT_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_PLATFORMS",
    "VENDOR",
    "OpenShiftAdapter",
    "OpenShiftConfig",
    "create_openshift_adapter",
    "health_check",
    "probe",
]
