"""Rancher project inventory.

Provides bounded, read-only access to Rancher project inventory through
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
    MAX_PROJECTS_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _safe_int,
    _validate_platform,
    _validate_project_id,
)


@dataclass(slots=True)
class ProjectInfo:
    """Project inventory information."""
    project_id: str
    name: str
    cluster_id: str
    platform: str
    namespace_count: int | None = None
    workload_count: int | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


def fetch_project_inventory(
    *,
    platform: str = "rancher",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    cluster_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Fetch project inventory from the Rancher gateway.

    Args:
        platform: One of 'rancher'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        cluster_id: Optional filter by cluster identifier
        project_id: Optional filter by project identifier

    Returns:
        Dict with projects list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_PROJECTS_PER_PAGE),
    }
    if cluster_id:
        params["cluster_id"] = _validate_project_id(cluster_id)
    if project_id:
        params["project_id"] = _validate_project_id(project_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/projects?{query}"
    payload = _get_json(url, headers)

    raw_projects = payload.get("projects", [])
    if not isinstance(raw_projects, list):
        raise ConnectionError("Rancher project inventory response did not match the expected contract")

    projects = []
    for raw in raw_projects[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        project_id_val = str(raw.get("project_id", "")).strip()
        if not project_id_val:
            continue
        row = {
            "project_id": project_id_val,
            "name": str(raw.get("name", ""))[:200],
            "cluster_id": str(raw.get("cluster_id", ""))[:120],
            "platform": plat,
            "namespace_count": _safe_int(raw.get("namespace_count")),
            "workload_count": _safe_int(raw.get("workload_count")),
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        projects.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "projects": projects,
        "returned": len(projects),
        "truncated": len(raw_projects) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


__all__ = [
    "ProjectInfo",
    "fetch_project_inventory",
]
