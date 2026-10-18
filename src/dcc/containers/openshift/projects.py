"""OpenShift projects: fetch project inventory and individual project details."""
from __future__ import annotations

import datetime as dt
import urllib.parse
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
    _validate_project_name,
)


def fetch_projects(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    label_selector: str | None = None,
) -> dict[str, Any]:
    """Fetch OpenShift project inventory from the gateway.

    Args:
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace/project name
        label_selector: Optional label selector filter

    Returns:
        Dict with projects list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "limit": str(MAX_PROJECTS_PER_PAGE),
    }
    if namespace:
        params["namespace"] = _validate_project_name(namespace)
    if label_selector:
        ls = label_selector.strip()
        if len(ls) > 500:
            raise ValueError("label_selector must be at most 500 characters")
        params["label_selector"] = ls

    query = urllib.parse.urlencode(params)
    url = f"{base}/projects?{query}"
    payload = _get_json(url, headers)

    raw_projects = payload.get("projects", [])
    if not isinstance(raw_projects, list):
        raise ConnectionError("OpenShift project inventory response did not match the expected contract")

    projects = []
    for raw in raw_projects[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        row = {
            "name": name,
            "display_name": str(raw.get("display_name", ""))[:200] or None,
            "description": str(raw.get("description", ""))[:500] or None,
            "status": str(raw.get("status", "unknown"))[:50],
            "phase": str(raw.get("phase", "unknown"))[:50],
            "created_at": _parse_timestamp(raw.get("created_at")),
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
            "resource_quota": raw.get("resource_quota") if isinstance(raw.get("resource_quota"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        projects.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "projects": projects,
        "returned": len(projects),
        "truncated": len(raw_projects) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_project(
    *,
    name: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a single OpenShift project by name.

    Args:
        name: Project name (DNS-1123 subdomain)
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with project details and metadata
    """
    validated_name = _validate_project_name(name)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/projects/{urllib.parse.quote(validated_name, safe='')}"
    payload = _get_json(url, headers)

    raw = payload.get("project", payload)
    if not isinstance(raw, dict):
        raise ConnectionError("OpenShift project response did not match the expected contract")

    project_name = str(raw.get("name", "")).strip()
    if not project_name:
        raise ConnectionError("OpenShift project response missing name")

    row = {
        "name": project_name,
        "display_name": str(raw.get("display_name", ""))[:200] or None,
        "description": str(raw.get("description", ""))[:500] or None,
        "status": str(raw.get("status", "unknown"))[:50],
        "phase": str(raw.get("phase", "unknown"))[:50],
        "created_at": _parse_timestamp(raw.get("created_at")),
        "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
        "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
        "resource_quota": raw.get("resource_quota") if isinstance(raw.get("resource_quota"), dict) else {},
        "observed_at": _parse_timestamp(raw.get("observed_at")),
        "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
    }

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "project": row,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }
