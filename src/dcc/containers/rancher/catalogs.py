"""Rancher catalog inventory.

Provides bounded, read-only access to Rancher catalog (Helm chart repository)
inventory through the vendor-neutral HTTPS API gateway.
"""
from __future__ import annotations

import datetime as dt
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_CATALOGS_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _validate_catalog_id,
    _validate_platform,
)


@dataclass(slots=True)
class CatalogInfo:
    """Catalog inventory information."""
    catalog_id: str
    name: str
    url: str
    platform: str
    scope: str | None = None
    branch: str | None = None
    commit: str | None = None
    version: str | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


def fetch_catalog_inventory(
    *,
    platform: str = "rancher",
    endpoint: str | None = None,
    credential_ref: str | None = None,
    cluster_id: str | None = None,
    project_id: str | None = None,
    catalog_id: str | None = None,
) -> dict[str, Any]:
    """Fetch catalog inventory from the Rancher gateway.

    Args:
        platform: One of 'rancher'
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        cluster_id: Optional filter by cluster identifier
        project_id: Optional filter by project identifier
        catalog_id: Optional filter by catalog identifier

    Returns:
        Dict with catalogs list, sync metadata, and provenance
    """
    plat = _validate_platform(platform)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "platform": plat,
        "limit": str(MAX_CATALOGS_PER_PAGE),
    }
    if cluster_id:
        params["cluster_id"] = _validate_catalog_id(cluster_id)
    if project_id:
        params["project_id"] = _validate_catalog_id(project_id)
    if catalog_id:
        params["catalog_id"] = _validate_catalog_id(catalog_id)

    query = urllib.parse.urlencode(params)
    url = f"{base}/catalogs?{query}"
    payload = _get_json(url, headers)

    raw_catalogs = payload.get("catalogs", [])
    if not isinstance(raw_catalogs, list):
        raise ConnectionError("Rancher catalog inventory response did not match the expected contract")

    catalogs = []
    for raw in raw_catalogs[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        catalog_id_val = str(raw.get("catalog_id", "")).strip()
        if not catalog_id_val:
            continue
        row = {
            "catalog_id": catalog_id_val,
            "name": str(raw.get("name", ""))[:200],
            "url": str(raw.get("url", ""))[:500],
            "platform": plat,
            "scope": str(raw.get("scope", ""))[:50] or None,
            "branch": str(raw.get("branch", ""))[:100] or None,
            "commit": str(raw.get("commit", ""))[:100] or None,
            "version": str(raw.get("version", ""))[:100] or None,
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        catalogs.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "platform": plat,
        "catalogs": catalogs,
        "returned": len(catalogs),
        "truncated": len(raw_catalogs) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


__all__ = [
    "CatalogInfo",
    "fetch_catalog_inventory",
]
