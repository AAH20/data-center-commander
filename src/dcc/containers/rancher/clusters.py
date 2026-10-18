"""Rancher cluster inventory and state.

Provides bounded, read-only access to Rancher-managed Kubernetes cluster
inventory and state through the vendor-neutral HTTPS API gateway.
"""
from __future__ import annotations

import datetime as dt
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_CLUSTERS_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _safe_int,
    _validate_cluster_id,
    _validate_platform,
)


@dataclass(slots=True)
class ClusterStatus:
    """Cluster status information."""
    phase: str = "unknown"
    message: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClusterInfo:
    """Cluster inventory information."""
    cluster_id: str
    name: str
    platform: str
    status: str
    provider: str | None = None
    version: str | None = None
    node_count: int | None = None
    cpu_total_cores: int | None = None
    memory_total_mb: int | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


def fetch_cluster_inventory(
    *,
    platform: str = "rancher",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    cluster_id: str | None = None,
) -> dict[str, Any]:
    """Fetch cluster inventory from the Rancher gateway.

    Args:
        platform: One of 'rancher'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        cluster_id: Optional filter by cluster identifier

    Returns:
        Dict with clusters list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_CLUSTERS_PER_PAGE),
    }
    if cluster_id:
        params["cluster_id"] = _validate_cluster_id(cluster_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/clusters?{query}"
    payload = _get_json(url, headers)

    raw_clusters = payload.get("clusters", [])
    if not isinstance(raw_clusters, list):
        raise ConnectionError("Rancher cluster inventory response did not match the expected contract")

    clusters = []
    for raw in raw_clusters[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        cluster_id_val = str(raw.get("cluster_id", "")).strip()
        if not cluster_id_val:
            continue
        row = {
            "cluster_id": cluster_id_val,
            "name": str(raw.get("name", ""))[:200],
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "provider": str(raw.get("provider", ""))[:100] or None,
            "version": str(raw.get("version", ""))[:100] or None,
            "node_count": _safe_int(raw.get("node_count")),
            "cpu_total_cores": _safe_int(raw.get("cpu_total_cores")),
            "memory_total_mb": _safe_int(raw.get("memory_total_mb")),
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        clusters.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "clusters": clusters,
        "returned": len(clusters),
        "truncated": len(raw_clusters) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_cluster_state(
    *,
    platform: str = "rancher",
    cluster_ids: list[str],
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch current state for specific clusters.

    Args:
        platform: One of 'rancher'
        cluster_ids: List of cluster IDs to fetch state for (1-100)
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with cluster state list and metadata
    """
    plat = _validate_platform(platform)
    if not cluster_ids:
        raise ValueError("at least one cluster_id is required")
    if len(cluster_ids) > 100:
        raise ValueError("at most 100 cluster_ids may be requested at once")
    validated_ids = [_validate_cluster_id(cid) for cid in cluster_ids]

    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "cluster_ids": ",".join(validated_ids),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/clusters/state?{query}"
    payload = _get_json(url, headers)

    raw_states = payload.get("states", [])
    if not isinstance(raw_states, list):
        raise ConnectionError("Rancher cluster state response did not match the expected contract")

    states = []
    for raw in raw_states[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        cluster_id_val = str(raw.get("cluster_id", "")).strip()
        if not cluster_id_val:
            continue
        row = {
            "cluster_id": cluster_id_val,
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "phase": str(raw.get("phase", "unknown"))[:50],
            "message": str(raw.get("message", ""))[:500] or None,
            "node_count": _safe_int(raw.get("node_count")),
            "conditions": raw.get("conditions") if isinstance(raw.get("conditions"), dict) else {},
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


__all__ = [
    "ClusterInfo",
    "ClusterStatus",
    "fetch_cluster_inventory",
    "fetch_cluster_state",
]
