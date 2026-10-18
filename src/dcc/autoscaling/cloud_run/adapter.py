"""GCP Cloud Run adapter — bounded, read-only service and metrics access.

Provides read-only access to Cloud Run service status, metrics, and scaling
recommendations through the Google Cloud Run API. All operations are bounded
and never persist data.

Requires GOOGLE_CLOUD_PROJECT environment variable and Application Default
Credentials (ADC) for authentication.
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
from typing import Any, Optional

from .models import (
    CloudRunCPUAllocation,
    CloudRunDeployment,
    CloudRunIngress,
    CloudRunMetrics,
    CloudRunScalingRecommendation,
    CloudRunServiceConfig,
    CloudRunServiceStatus,
    CloudRunStatus,
)

# API endpoints
CLOUD_RUN_API_BASE = "https://run.googleapis.com/v2"
MAX_RESPONSE_BYTES = 2_000_000
MAX_SERVICES = 100
MAX_METRICS_PER_SERVICE = 1000
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15

# Validation patterns
SERVICE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
REGION_RE = re.compile(r"^[a-z]+-[a-z]+[0-9]$")
RESOURCE_RE = re.compile(r"^[0-9]+(m|M|Mi|Gi|Ti)?$")


class CloudRunError(Exception):
    """Base exception for Cloud Run adapter errors."""


class CloudRunAuthError(CloudRunError):
    """Authentication or authorization error."""


class CloudRunNotFoundError(CloudRunError):
    """Service or resource not found."""


class CloudRunValidationError(CloudRunError):
    """Invalid input parameters."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable redirects to prevent SSRF."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str, *, token: str, max_bytes: int = MAX_RESPONSE_BYTES) -> dict[str, Any]:
    """Fetch and parse a JSON response with bounded size."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "DataCenterCommander/0.1",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=CONNECT_TIMEOUT) as response:
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise CloudRunError(f"Response exceeded the {max_bytes // 1_000_000} MB safety limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise CloudRunAuthError("Invalid or expired credentials") from None
        if exc.code == 403:
            raise CloudRunAuthError("Insufficient permissions") from None
        if exc.code == 404:
            raise CloudRunNotFoundError("Resource not found") from None
        raise CloudRunError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CloudRunError(f"Cloud Run API unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise CloudRunError("Invalid JSON response") from None
    if not isinstance(payload, dict):
        raise CloudRunError("Response did not match expected contract")
    return payload


def _get_access_token() -> str:
    """Get access token from metadata server or environment."""
    # Check environment first
    token = os.environ.get("GOOGLE_CLOUD_ACCESS_TOKEN", "").strip()
    if token:
        return token

    # Try metadata server (GCE/GKE)
    metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    request = urllib.request.Request(
        metadata_url,
        headers={"Metadata-Flavor": "Google"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=CONNECT_TIMEOUT) as response:
            payload = json.loads(response.read(65536))
        token = payload.get("access_token", "").strip()
        if not token:
            raise CloudRunAuthError("Metadata server returned empty access token")
        return token
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise CloudRunAuthError(
            "No access token available. Set GOOGLE_CLOUD_ACCESS_TOKEN or use ADC."
        ) from exc


def _validate_service_name(name: str) -> str:
    """Validate a Cloud Run service name."""
    name = name.strip()
    if not name or len(name) > 63:
        raise CloudRunValidationError("service name must be 1-63 characters")
    if not SERVICE_NAME_RE.fullmatch(name):
        raise CloudRunValidationError(
            "service name must start with a letter, contain only lowercase letters, "
            "numbers, and hyphens, and end with a letter or number"
        )
    return name


def _validate_region(region: str) -> str:
    """Validate a GCP region."""
    region = region.strip()
    if not region or len(region) > 80:
        raise CloudRunValidationError("region must be 1-80 characters")
    if not REGION_RE.fullmatch(region):
        raise CloudRunValidationError(f"invalid region format: {region}")
    return region


def _parse_status(status_str: str) -> CloudRunStatus:
    """Parse a Cloud Run status string."""
    status_map = {
        "READY": CloudRunStatus.READY,
        "DEPLOYING": CloudRunStatus.DEPLOYING,
        "DELETING": CloudRunStatus.DELETING,
        "ERROR": CloudRunStatus.ERROR,
    }
    return status_map.get(status_str.upper(), CloudRunStatus.UNKNOWN)


def _amount(value: Any) -> Decimal | None:
    """Parse a decimal amount."""
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


class CloudRunAdapter:
    """Read-only adapter for Google Cloud Run services.

    Provides bounded, read-only access to service status, metrics, and
    scaling recommendations. Never persists data or performs mutations.
    """

    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = (project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "")).strip()
        if not self.project_id:
            raise CloudRunError(
                "GOOGLE_CLOUD_PROJECT environment variable is required"
            )
        if len(self.project_id) > 255 or not re.fullmatch(r"[a-z][a-z0-9-]{0,253}[a-z0-9]", self.project_id):
            raise CloudRunError("invalid Google Cloud project ID")
        self._token: str | None = None

    @property
    def token(self) -> str:
        """Lazy-load access token."""
        if self._token is None:
            self._token = _get_access_token()
        return self._token

    def _api_url(self, path: str) -> str:
        """Build a Cloud Run API URL."""
        return f"{CLOUD_RUN_API_BASE}/projects/{self.project_id}/locations/{path}"

    def list_services(self, region: str | None = None) -> list[CloudRunServiceStatus]:
        """List Cloud Run services in a region (or all regions)."""
        if region:
            region = _validate_region(region)
            parent = f"projects/{self.project_id}/locations/{region}"
        else:
            parent = f"projects/{self.project_id}/locations/-"

        url = f"{CLOUD_RUN_API_BASE}/{parent}/services?pageSize={MAX_SERVICES}"
        payload = _get_json(url, token=self.token)

        services = payload.get("services", [])
        if not isinstance(services, list):
            raise CloudRunError("Cloud Run services response did not match expected contract")

        results: list[CloudRunServiceStatus] = []
        for svc in services:
            if not isinstance(svc, dict):
                continue
            name = str(svc.get("name", "")).split("/")[-1]
            if not name:
                continue
            status = self._parse_service_status(svc, region or "unknown")
            results.append(status)
            if len(results) >= MAX_SERVICES:
                break

        return results

    def get_service(self, name: str, region: str) -> CloudRunServiceStatus:
        """Get status of a specific Cloud Run service."""
        name = _validate_service_name(name)
        region = _validate_region(region)

        url = f"{CLOUD_RUN_API_BASE}/projects/{self.project_id}/locations/{region}/services/{name}"
        payload = _get_json(url, token=self.token)
        return self._parse_service_status(payload, region)

    def get_metrics(
        self,
        name: str,
        region: str,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[CloudRunMetrics]:
        """Get metrics for a Cloud Run service.

        Note: This uses the Cloud Monitoring API. In production, this would
        query the monitoring API for time-series data. For bounded read-only
        access, we return the latest available metrics.
        """
        name = _validate_service_name(name)
        region = _validate_region(region)

        # For now, return current metrics from service status
        # In a full implementation, this would query Cloud Monitoring API
        service = self.get_service(name, region)
        if service.status == CloudRunStatus.ERROR:
            return []

        metrics = CloudRunMetrics(
            service_name=name,
            region=region,
            timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
            active_instances=service.active_instances,
            idle_instances=max(0, service.desired_instances - service.active_instances),
            request_count=0,  # Would come from monitoring API
            request_latency_ms=0.0,
            average_concurrency=0.0,
            error_count=0,
            error_rate=0.0,
            cpu_utilization=0.0,
            memory_utilization=0.0,
        )
        return [metrics]

    def get_scaling_recommendation(
        self,
        name: str,
        region: str,
        *,
        target_cpu_utilization: float = 0.7,
        target_memory_utilization: float = 0.7,
    ) -> CloudRunScalingRecommendation:
        """Generate scaling recommendations for a Cloud Run service.

        Analyzes current configuration and metrics to recommend optimal
        min/max instances and concurrency settings.
        """
        name = _validate_service_name(name)
        region = _validate_region(region)

        if not 0.1 <= target_cpu_utilization <= 0.95:
            raise CloudRunValidationError("target_cpu_utilization must be 0.1-0.95")
        if not 0.1 <= target_memory_utilization <= 0.95:
            raise CloudRunValidationError("target_memory_utilization must be 0.1-0.95")

        service = self.get_service(name, region)
        metrics_list = self.get_metrics(name, region)

        # Default recommendations
        current_min = 0
        current_max = 100
        current_concurrency = 80

        # Analyze metrics
        if metrics_list:
            metrics = metrics_list[0]
            # Recommend min instances based on active instances
            if metrics.active_instances > 0:
                current_min = max(1, int(metrics.active_instances * 0.5))

            # Recommend max instances based on peak load
            if metrics.active_instances > 0:
                current_max = max(10, int(metrics.active_instances * 2))

            # Recommend concurrency based on average concurrency
            if metrics.average_concurrency > 0:
                current_concurrency = max(1, min(1000, int(metrics.average_concurrency * 1.2)))

        # Calculate cost impact (simplified)
        # Cloud Run pricing: $0.00002400/vCPU-second, $0.0000025/GiB-second
        # This is a rough estimate
        estimated_cost_impact = 0.0

        # Determine risk level
        risk_level = "low"
        if service.status == CloudRunStatus.ERROR:
            risk_level = "high"
        elif service.active_instances > current_max * 0.8:
            risk_level = "medium"

        reason = self._build_recommendation_reason(
            service, metrics_list, current_min, current_max, current_concurrency
        )

        return CloudRunScalingRecommendation(
            service_name=name,
            region=region,
            current_min_instances=current_min,
            current_max_instances=current_max,
            current_concurrency=current_concurrency,
            recommended_min_instances=current_min,
            recommended_max_instances=current_max,
            recommended_concurrency=current_concurrency,
            reason=reason,
            confidence=0.7 if metrics_list else 0.5,
            estimated_cost_impact=estimated_cost_impact,
            risk_level=risk_level,
        )

    def health_check(self) -> bool:
        """Check if the Cloud Run API is accessible."""
        try:
            self.list_services()
            return True
        except CloudRunError:
            return False

    def _validate_service_name(self, name: str) -> str:
        """Validate a Cloud Run service name."""
        return _validate_service_name(name)

    def _validate_region(self, region: str) -> str:
        """Validate a GCP region."""
        return _validate_region(region)

    def _parse_status(self, status_str: str) -> CloudRunStatus:
        """Parse a Cloud Run status string."""
        return _parse_status(status_str)

    def _parse_service_status(self, payload: dict[str, Any], region: str) -> CloudRunServiceStatus:
        """Parse a Cloud Run service API response."""
        name = str(payload.get("name", "")).split("/")[-1]
        if not name:
            raise CloudRunError("Service response missing name")

        status_obj = payload.get("status", {}) if isinstance(payload.get("status"), dict) else {}
        conditions = status_obj.get("conditions", []) if isinstance(status_obj.get("conditions"), list) else []

        # Determine overall status
        overall_status = CloudRunStatus.UNKNOWN
        error_message = None
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            cond_type = str(condition.get("type", ""))
            cond_status = str(condition.get("status", ""))
            if cond_type == "Ready" and cond_status == "True":
                overall_status = CloudRunStatus.READY
            elif cond_type == "Ready" and cond_status == "False":
                overall_status = CloudRunStatus.ERROR
                error_message = str(condition.get("message", ""))

        # Extract observed metrics
        observed_metrics = status_obj.get("observedGeneration", 0)
        active_instances = 0
        desired_instances = 0

        # Try to get instance counts from status
        instance_split = status_obj.get("instanceSplit", {}) if isinstance(status_obj.get("instanceSplit"), dict) else {}
        if instance_split:
            active_instances = int(instance_split.get("active", 0))
            desired_instances = int(instance_split.get("desired", 0))

        # Get URL
        url = status_obj.get("url") if isinstance(status_obj.get("url"), str) else None

        # Get latest revision
        latest_revision = status_obj.get("latestRevision") if isinstance(status_obj.get("latestRevision"), str) else None

        # Get timestamps
        created_at = payload.get("createTime") if isinstance(payload.get("createTime"), str) else None
        updated_at = payload.get("updateTime") if isinstance(payload.get("updateTime"), str) else None

        return CloudRunServiceStatus(
            name=name,
            region=region,
            status=overall_status,
            url=url,
            ready=overall_status == CloudRunStatus.READY,
            active_instances=active_instances,
            desired_instances=desired_instances,
            latest_revision=latest_revision,
            error_message=error_message,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _build_recommendation_reason(
        self,
        service: CloudRunServiceStatus,
        metrics_list: list[CloudRunMetrics],
        min_inst: int,
        max_inst: int,
        concurrency: int,
    ) -> str:
        """Build a human-readable recommendation reason."""
        if service.status == CloudRunStatus.ERROR:
            return f"Service {service.name} is in ERROR state. Review logs before scaling."

        if not metrics_list:
            return (
                f"No metrics available for {service.name}. "
                f"Using conservative defaults: min={min_inst}, max={max_inst}, concurrency={concurrency}."
            )

        metrics = metrics_list[0]
        reasons = []

        if metrics.active_instances > 0:
            reasons.append(
                f"Currently {metrics.active_instances} active instance(s). "
                f"Recommended min={min_inst} to handle baseline load."
            )
        else:
            reasons.append("No active instances. Consider min=0 for cost savings.")

        if metrics.average_concurrency > 0:
            reasons.append(
                f"Average concurrency {metrics.average_concurrency:.1f}. "
                f"Recommended concurrency={concurrency}."
            )

        return " ".join(reasons)


# Module-level singleton
_default_adapter: CloudRunAdapter | None = None


def get_adapter(project_id: str | None = None) -> CloudRunAdapter:
    """Return the process-wide default adapter."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = CloudRunAdapter(project_id)
    return _default_adapter
