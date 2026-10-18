"""Rancher monitoring metrics.

Provides bounded, read-only access to Rancher monitoring metrics through
the vendor-neutral HTTPS API gateway.
"""
from __future__ import annotations

import datetime as dt
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _safe_float,
    _safe_int,
    _validate_platform,
)


@dataclass(slots=True)
class MonitoringMetrics:
    """Monitoring metrics for a cluster or namespace."""
    metric_id: str
    entity_type: str
    entity_id: str
    platform: str
    cpu_usage_percent: float | None = None
    memory_usage_percent: float | None = None
    cpu_usage_cores: float | None = None
    memory_usage_mb: float | None = None
    network_rx_mbps: float | None = None
    network_tx_mbps: float | None = None
    disk_usage_percent: float | None = None
    pod_count: int | None = None
    observed_at: str | None = None
    source_timestamp: str | None = None
    interval_seconds: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


def fetch_monitoring_metrics(
    *,
    platform: str = "rancher",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    cluster_id: str | None = None,
    project_id: str | None = None,
    namespace_id: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Fetch monitoring metrics from the Rancher gateway.

    Args:
        platform: One of 'rancher'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        cluster_id: Optional filter by cluster identifier
        project_id: Optional filter by project identifier
        namespace_id: Optional filter by namespace identifier
        since: Optional ISO-8601 timestamp for incremental sync

    Returns:
        Dict with monitoring metrics list and metadata
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_ROWS),
    }
    if cluster_id:
        params["cluster_id"] = cluster_id
    if project_id:
        params["project_id"] = project_id
    if namespace_id:
        params["namespace_id"] = namespace_id
    if since:
        parsed_ts = _parse_timestamp(since)
        if parsed_ts is None:
            raise ValueError("since must be a valid ISO-8601 timestamp")
        params["since"] = parsed_ts

    query = urllib.parse.urlencode(params)
    url = f"{base}/metrics/monitoring?{query}"
    payload = _get_json(url, headers)

    raw_metrics = payload.get("metrics", [])
    if not isinstance(raw_metrics, list):
        raise ConnectionError("Rancher monitoring metrics response did not match the expected contract")

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
            "cpu_usage_percent": _safe_float(raw.get("cpu_usage_percent")),
            "memory_usage_percent": _safe_float(raw.get("memory_usage_percent")),
            "cpu_usage_cores": _safe_float(raw.get("cpu_usage_cores")),
            "memory_usage_mb": _safe_float(raw.get("memory_usage_mb")),
            "network_rx_mbps": _safe_float(raw.get("network_rx_mbps")),
            "network_tx_mbps": _safe_float(raw.get("network_tx_mbps")),
            "disk_usage_percent": _safe_float(raw.get("disk_usage_percent")),
            "pod_count": _safe_int(raw.get("pod_count")),
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


__all__ = [
    "MonitoringMetrics",
    "fetch_monitoring_metrics",
]
