"""Rancher namespace inventory.

Provides bounded, read-only access to Rancher namespace inventory through
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
    MAX_NAMESPACES_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _safe_int,
    _validate_namespace_id,
    _validate_platform,
)


@dataclass(slots=True)
class NamespaceInfo:
    """Namespace inventory information."""
    namespace_id: str
    name: str
    project_id: str
    cluster_id: str
    platform: str
    status: str | None = None
    workload_count: int | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


def fetch_namespace_inventory(
    *,
    platform: str = "rancher",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    cluster_id: str | None = None,
    project_id: str | None = None,
    namespace_id: str | None = None,
) -> dict[str, Any]:
    """Fetch namespace inventory from the Rancher gateway.

    Args:
        platform: One of 'rancher'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        cluster_id: Optional filter by cluster identifier
        project_id: Optional filter by project identifier
        namespace_id: Optional filter by namespace identifier

    Returns:
        Dict with namespaces list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_NAMESPACES_PER_PAGE),
    }
    if cluster_id:
        params["cluster_id"] = _validate_namespace_id(cluster_id)
    if project_id:
        params["project_id"] = _validate_namespace_id(project_id)
    if namespace_id:
        params["namespace_id"] = _validate_namespace_id(namespace_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/namespaces?{query}"
    payload = _get_json(url, headers)

    raw_namespaces = payload.get("namespaces", [])
    if not isinstance(raw_namespaces, list):
        raise ConnectionError("Rancher namespace inventory response did not match the expected contract")

    namespaces = []
    for raw in raw_namespaces[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        namespace_id_val = str(raw.get("namespace_id", "")).strip()
        if not namespace_id_val:
            continue
        row = {
            "namespace_id": namespace_id_val,
            "name": str(raw.get("name", ""))[:200],
            "project_id": str(raw.get("project_id", ""))[:120],
            "cluster_id": str(raw.get("cluster_id", ""))[:120],
            "platform": plat,
            "status": str(raw.get("status", "unknown"))[:50],
            "workload_count": _safe_int(raw.get("workload_count")),
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        namespaces.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "namespaces": namespaces,
        "returned": len(namespaces),
        "truncated": len(raw_namespaces) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


__all__ = [
    "NamespaceInfo",
    "fetch_namespace_inventory",
]
