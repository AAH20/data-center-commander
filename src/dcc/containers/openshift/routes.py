"""OpenShift routes: fetch route inventory and individual route details."""
from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_ROUTES_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _validate_resource_name,
)


def fetch_routes(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    label_selector: str | None = None,
) -> dict[str, Any]:
    """Fetch OpenShift route inventory from the gateway.

    Args:
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace
        label_selector: Optional label selector filter

    Returns:
        Dict with routes list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "limit": str(MAX_ROUTES_PER_PAGE),
    }
    if namespace:
        params["namespace"] = _validate_resource_name(namespace)
    if label_selector:
        ls = label_selector.strip()
        if len(ls) > 500:
            raise ValueError("label_selector must be at most 500 characters")
        params["label_selector"] = ls

    query = urllib.parse.urlencode(params)
    url = f"{base}/routes?{query}"
    payload = _get_json(url, headers)

    raw_routes = payload.get("routes", [])
    if not isinstance(raw_routes, list):
        raise ConnectionError("OpenShift route inventory response did not match the expected contract")

    routes = []
    for raw in raw_routes[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        row = {
            "name": name,
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "host": str(raw.get("host", ""))[:253] or None,
            "path": str(raw.get("path", ""))[:200] or None,
            "service": str(raw.get("service", ""))[:200] or None,
            "target_port": str(raw.get("target_port", ""))[:100] or None,
            "tls_enabled": bool(raw.get("tls_enabled")),
            "tls_termination": str(raw.get("tls_termination", ""))[:50] or None,
            "tls_insecure_edge_termination_policy": str(raw.get("tls_insecure_edge_termination_policy", ""))[:50] or None,
            "status": str(raw.get("status", "unknown"))[:50],
            "created_at": _parse_timestamp(raw.get("created_at")),
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        routes.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "routes": routes,
        "returned": len(routes),
        "truncated": len(raw_routes) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_route(
    *,
    name: str,
    namespace: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a single OpenShift route by name and namespace.

    Args:
        name: Route name
        namespace: Namespace name
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with route details and metadata
    """
    validated_name = _validate_resource_name(name)
    validated_ns = _validate_resource_name(namespace)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/namespaces/{urllib.parse.quote(validated_ns, safe='')}/routes/{urllib.parse.quote(validated_name, safe='')}"
    payload = _get_json(url, headers)

    raw = payload.get("route", payload)
    if not isinstance(raw, dict):
        raise ConnectionError("OpenShift route response did not match the expected contract")

    route_name = str(raw.get("name", "")).strip()
    if not route_name:
        raise ConnectionError("OpenShift route response missing name")

    row = {
        "name": route_name,
        "namespace": str(raw.get("namespace", ""))[:200] or None,
        "host": str(raw.get("host", ""))[:253] or None,
        "path": str(raw.get("path", ""))[:200] or None,
        "service": str(raw.get("service", ""))[:200] or None,
        "target_port": str(raw.get("target_port", ""))[:100] or None,
        "tls_enabled": bool(raw.get("tls_enabled")),
        "tls_termination": str(raw.get("tls_termination", ""))[:50] or None,
        "tls_insecure_edge_termination_policy": str(raw.get("tls_insecure_edge_termination_policy", ""))[:50] or None,
        "status": str(raw.get("status", "unknown"))[:50],
        "created_at": _parse_timestamp(raw.get("created_at")),
        "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
        "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
        "observed_at": _parse_timestamp(raw.get("observed_at")),
        "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
    }

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "route": row,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }
