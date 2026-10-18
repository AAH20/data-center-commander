"""OpenShift deployments: fetch deployment inventory and individual deployment details."""
from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_DEPLOYMENTS_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _safe_int,
    _validate_resource_name,
)


def fetch_deployments(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    label_selector: str | None = None,
) -> dict[str, Any]:
    """Fetch OpenShift deployment inventory from the gateway.

    Args:
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace
        label_selector: Optional label selector filter

    Returns:
        Dict with deployments list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "limit": str(MAX_DEPLOYMENTS_PER_PAGE),
    }
    if namespace:
        params["namespace"] = _validate_resource_name(namespace)
    if label_selector:
        ls = label_selector.strip()
        if len(ls) > 500:
            raise ValueError("label_selector must be at most 500 characters")
        params["label_selector"] = ls

    query = urllib.parse.urlencode(params)
    url = f"{base}/deployments?{query}"
    payload = _get_json(url, headers)

    raw_deployments = payload.get("deployments", [])
    if not isinstance(raw_deployments, list):
        raise ConnectionError("OpenShift deployment inventory response did not match the expected contract")

    deployments = []
    for raw in raw_deployments[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        row = {
            "name": name,
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "status": str(raw.get("status", "unknown"))[:50],
            "replicas": _safe_int(raw.get("replicas")),
            "ready_replicas": _safe_int(raw.get("ready_replicas")),
            "available_replicas": _safe_int(raw.get("available_replicas")),
            "unavailable_replicas": _safe_int(raw.get("unavailable_replicas")),
            "updated_replicas": _safe_int(raw.get("updated_replicas")),
            "image": str(raw.get("image", ""))[:200] or None,
            "container_count": _safe_int(raw.get("container_count")),
            "restart_count": _safe_int(raw.get("restart_count")),
            "created_at": _parse_timestamp(raw.get("created_at")),
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
            "selector": raw.get("selector") if isinstance(raw.get("selector"), dict) else {},
            "strategy": str(raw.get("strategy", ""))[:100] or None,
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        deployments.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "deployments": deployments,
        "returned": len(deployments),
        "truncated": len(raw_deployments) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_deployment(
    *,
    name: str,
    namespace: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a single OpenShift deployment by name and namespace.

    Args:
        name: Deployment name
        namespace: Namespace name
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with deployment details and metadata
    """
    validated_name = _validate_resource_name(name)
    validated_ns = _validate_resource_name(namespace)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/namespaces/{urllib.parse.quote(validated_ns, safe='')}/deployments/{urllib.parse.quote(validated_name, safe='')}"
    payload = _get_json(url, headers)

    raw = payload.get("deployment", payload)
    if not isinstance(raw, dict):
        raise ConnectionError("OpenShift deployment response did not match the expected contract")

    dep_name = str(raw.get("name", "")).strip()
    if not dep_name:
        raise ConnectionError("OpenShift deployment response missing name")

    row = {
        "name": dep_name,
        "namespace": str(raw.get("namespace", ""))[:200] or None,
        "status": str(raw.get("status", "unknown"))[:50],
        "replicas": _safe_int(raw.get("replicas")),
        "ready_replicas": _safe_int(raw.get("ready_replicas")),
        "available_replicas": _safe_int(raw.get("available_replicas")),
        "unavailable_replicas": _safe_int(raw.get("unavailable_replicas")),
        "updated_replicas": _safe_int(raw.get("updated_replicas")),
        "image": str(raw.get("image", ""))[:200] or None,
        "container_count": _safe_int(raw.get("container_count")),
        "restart_count": _safe_int(raw.get("restart_count")),
        "created_at": _parse_timestamp(raw.get("created_at")),
        "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
        "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
        "selector": raw.get("selector") if isinstance(raw.get("selector"), dict) else {},
        "strategy": str(raw.get("strategy", ""))[:100] or None,
        "observed_at": _parse_timestamp(raw.get("observed_at")),
        "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
    }

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "deployment": row,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }
