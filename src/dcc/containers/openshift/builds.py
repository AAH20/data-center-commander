"""OpenShift builds: fetch build inventory and individual build details."""
from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_BUILDS_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _validate_resource_name,
)


def fetch_builds(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    build_config_name: str | None = None,
    label_selector: str | None = None,
) -> dict[str, Any]:
    """Fetch OpenShift build inventory from the gateway.

    Args:
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace
        build_config_name: Optional filter by BuildConfig name
        label_selector: Optional label selector filter

    Returns:
        Dict with builds list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "limit": str(MAX_BUILDS_PER_PAGE),
    }
    if namespace:
        params["namespace"] = _validate_resource_name(namespace)
    if build_config_name:
        params["build_config_name"] = _validate_resource_name(build_config_name)
    if label_selector:
        ls = label_selector.strip()
        if len(ls) > 500:
            raise ValueError("label_selector must be at most 500 characters")
        params["label_selector"] = ls

    query = urllib.parse.urlencode(params)
    url = f"{base}/builds?{query}"
    payload = _get_json(url, headers)

    raw_builds = payload.get("builds", [])
    if not isinstance(raw_builds, list):
        raise ConnectionError("OpenShift build inventory response did not match the expected contract")

    builds = []
    for raw in raw_builds[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        row = {
            "name": name,
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "build_config_name": str(raw.get("build_config_name", ""))[:200] or None,
            "status": str(raw.get("status", "unknown"))[:50],
            "phase": str(raw.get("phase", "unknown"))[:50],
            "reason": str(raw.get("reason", ""))[:200] or None,
            "message": str(raw.get("message", ""))[:500] or None,
            "image": str(raw.get("image", ""))[:200] or None,
            "source_type": str(raw.get("source_type", ""))[:50] or None,
            "source_revision": str(raw.get("source_revision", ""))[:200] or None,
            "started_at": _parse_timestamp(raw.get("started_at")),
            "completed_at": _parse_timestamp(raw.get("completed_at")),
            "duration_seconds": None,
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        # Calculate duration if both timestamps present
        if row["started_at"] and row["completed_at"]:
            try:
                start = dt.datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
                end = dt.datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
                row["duration_seconds"] = int((end - start).total_seconds())
            except (ValueError, TypeError):
                pass
        builds.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "builds": builds,
        "returned": len(builds),
        "truncated": len(raw_builds) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_build(
    *,
    name: str,
    namespace: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a single OpenShift build by name and namespace.

    Args:
        name: Build name
        namespace: Namespace name
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with build details and metadata
    """
    validated_name = _validate_resource_name(name)
    validated_ns = _validate_resource_name(namespace)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/namespaces/{urllib.parse.quote(validated_ns, safe='')}/builds/{urllib.parse.quote(validated_name, safe='')}"
    payload = _get_json(url, headers)

    raw = payload.get("build", payload)
    if not isinstance(raw, dict):
        raise ConnectionError("OpenShift build response did not match the expected contract")

    build_name = str(raw.get("name", "")).strip()
    if not build_name:
        raise ConnectionError("OpenShift build response missing name")

    row = {
        "name": build_name,
        "namespace": str(raw.get("namespace", ""))[:200] or None,
        "build_config_name": str(raw.get("build_config_name", ""))[:200] or None,
        "status": str(raw.get("status", "unknown"))[:50],
        "phase": str(raw.get("phase", "unknown"))[:50],
        "reason": str(raw.get("reason", ""))[:200] or None,
        "message": str(raw.get("message", ""))[:500] or None,
        "image": str(raw.get("image", ""))[:200] or None,
        "source_type": str(raw.get("source_type", ""))[:50] or None,
        "source_revision": str(raw.get("source_revision", ""))[:200] or None,
        "started_at": _parse_timestamp(raw.get("started_at")),
        "completed_at": _parse_timestamp(raw.get("completed_at")),
        "duration_seconds": None,
        "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
        "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
        "observed_at": _parse_timestamp(raw.get("observed_at")),
        "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
    }
    if row["started_at"] and row["completed_at"]:
        try:
            start = dt.datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
            end = dt.datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
            row["duration_seconds"] = int((end - start).total_seconds())
        except (ValueError, TypeError):
            pass

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "build": row,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }
