"""OpenShift templates: fetch template inventory and individual template details."""
from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_TEMPLATES_PER_PAGE,
    MAX_ROWS,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _validate_resource_name,
)


def fetch_templates(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
    namespace: str | None = None,
    label_selector: str | None = None,
) -> dict[str, Any]:
    """Fetch OpenShift template inventory from the gateway.

    Args:
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference
        namespace: Optional filter by namespace
        label_selector: Optional label selector filter

    Returns:
        Dict with templates list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "limit": str(MAX_TEMPLATES_PER_PAGE),
    }
    if namespace:
        params["namespace"] = _validate_resource_name(namespace)
    if label_selector:
        ls = label_selector.strip()
        if len(ls) > 500:
            raise ValueError("label_selector must be at most 500 characters")
        params["label_selector"] = ls

    query = urllib.parse.urlencode(params)
    url = f"{base}/templates?{query}"
    payload = _get_json(url, headers)

    raw_templates = payload.get("templates", [])
    if not isinstance(raw_templates, list):
        raise ConnectionError("OpenShift template inventory response did not match the expected contract")

    templates = []
    for raw in raw_templates[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        row = {
            "name": name,
            "namespace": str(raw.get("namespace", ""))[:200] or None,
            "description": str(raw.get("description", ""))[:500] or None,
            "parameters": [
                str(param)[:200]
                for param in (raw.get("parameters") or [])[:50]
                if isinstance(param, str)
            ],
            "object_count": None,
            "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
            "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
            "created_at": _parse_timestamp(raw.get("created_at")),
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        # Count objects if available
        objects = raw.get("objects")
        if isinstance(objects, list):
            row["object_count"] = len(objects)
        templates.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "templates": templates,
        "returned": len(templates),
        "truncated": len(raw_templates) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_template(
    *,
    name: str,
    namespace: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a single OpenShift template by name and namespace.

    Args:
        name: Template name
        namespace: Namespace name
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with template details and metadata
    """
    validated_name = _validate_resource_name(name)
    validated_ns = _validate_resource_name(namespace)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/namespaces/{urllib.parse.quote(validated_ns, safe='')}/templates/{urllib.parse.quote(validated_name, safe='')}"
    payload = _get_json(url, headers)

    raw = payload.get("template", payload)
    if not isinstance(raw, dict):
        raise ConnectionError("OpenShift template response did not match the expected contract")

    template_name = str(raw.get("name", "")).strip()
    if not template_name:
        raise ConnectionError("OpenShift template response missing name")

    row = {
        "name": template_name,
        "namespace": str(raw.get("namespace", ""))[:200] or None,
        "description": str(raw.get("description", ""))[:500] or None,
        "parameters": [
            str(param)[:200]
            for param in (raw.get("parameters") or [])[:50]
            if isinstance(param, str)
        ],
        "object_count": None,
        "labels": raw.get("labels") if isinstance(raw.get("labels"), dict) else {},
        "annotations": raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {},
        "created_at": _parse_timestamp(raw.get("created_at")),
        "observed_at": _parse_timestamp(raw.get("observed_at")),
        "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
    }
    objects = raw.get("objects")
    if isinstance(objects, list):
        row["object_count"] = len(objects)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "template": row,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }
