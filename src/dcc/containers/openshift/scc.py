"""OpenShift Security Context Constraints (SCC): fetch SCC inventory and details."""
from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    MAX_ROWS,
    MAX_SCCS_PER_PAGE,
    _get_json,
    _parse_timestamp,
    _resolve_credential,
    _resolve_endpoint,
    _validate_scc_name,
)


def fetch_sccs(
    *,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch OpenShift Security Context Constraints inventory from the gateway.

    Args:
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with SCCs list, sync metadata, and provenance
    """
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    params: dict[str, str] = {
        "limit": str(MAX_SCCS_PER_PAGE),
    }

    query = urllib.parse.urlencode(params)
    url = f"{base}/sccs?{query}"
    payload = _get_json(url, headers)

    raw_sccs = payload.get("sccs", [])
    if not isinstance(raw_sccs, list):
        raise ConnectionError("OpenShift SCC inventory response did not match the expected contract")

    sccs = []
    for raw in raw_sccs[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        row = {
            "name": name,
            "priority": None,
            "privileged": bool(raw.get("privileged")),
            "allow_privileged_container": bool(raw.get("allow_privileged_container")),
            "default_add_capabilities": [
                str(cap)[:100]
                for cap in (raw.get("default_add_capabilities") or [])[:20]
                if isinstance(cap, str)
            ],
            "required_drop_capabilities": [
                str(cap)[:100]
                for cap in (raw.get("required_drop_capabilities") or [])[:20]
                if isinstance(cap, str)
            ],
            "allowed_capabilities": [
                str(cap)[:100]
                for cap in (raw.get("allowed_capabilities") or [])[:20]
                if isinstance(cap, str)
            ],
            "volumes": [
                str(vol)[:100]
                for vol in (raw.get("volumes") or [])[:20]
                if isinstance(vol, str)
            ],
            "se_linux_context": str(raw.get("se_linux_context", ""))[:200] or None,
            "fs_group": str(raw.get("fs_group", ""))[:200] or None,
            "run_as_user": str(raw.get("run_as_user", ""))[:200] or None,
            "supplemental_groups": str(raw.get("supplemental_groups", ""))[:200] or None,
            "users": [
                str(user)[:200]
                for user in (raw.get("users") or [])[:50]
                if isinstance(user, str)
            ],
            "groups": [
                str(group)[:200]
                for group in (raw.get("groups") or [])[:50]
                if isinstance(group, str)
            ],
            "created_at": _parse_timestamp(raw.get("created_at")),
            "observed_at": _parse_timestamp(raw.get("observed_at")),
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        # Parse priority
        priority = raw.get("priority")
        if priority is not None:
            try:
                row["priority"] = int(priority)
            except (ValueError, TypeError):
                pass
        sccs.append(row)

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "sccs": sccs,
        "returned": len(sccs),
        "truncated": len(raw_sccs) > MAX_ROWS or bool(payload.get("next_cursor")),
        "sync_cursor": payload.get("next_cursor"),
        "source_lag_seconds": payload.get("source_lag_seconds"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }


def fetch_scc(
    *,
    name: str,
    endpoint: str | None = None,
    credential_ref: str | None = None,
) -> dict[str, Any]:
    """Fetch a single OpenShift SCC by name.

    Args:
        name: SCC name
        endpoint: Optional override for the gateway endpoint
        credential_ref: Optional credential reference

    Returns:
        Dict with SCC details and metadata
    """
    validated_name = _validate_scc_name(name)
    base = _resolve_endpoint(endpoint)
    cred = _resolve_credential(credential_ref)
    headers = {"X-Credential-Ref": cred} if cred else {}

    url = f"{base}/sccs/{urllib.parse.quote(validated_name, safe='')}"
    payload = _get_json(url, headers)

    raw = payload.get("scc", payload)
    if not isinstance(raw, dict):
        raise ConnectionError("OpenShift SCC response did not match the expected contract")

    scc_name = str(raw.get("name", "")).strip()
    if not scc_name:
        raise ConnectionError("OpenShift SCC response missing name")

    row = {
        "name": scc_name,
        "priority": None,
        "privileged": bool(raw.get("privileged")),
        "allow_privileged_container": bool(raw.get("allow_privileged_container")),
        "default_add_capabilities": [
            str(cap)[:100]
            for cap in (raw.get("default_add_capabilities") or [])[:20]
            if isinstance(cap, str)
        ],
        "required_drop_capabilities": [
            str(cap)[:100]
            for cap in (raw.get("required_drop_capabilities") or [])[:20]
            if isinstance(cap, str)
        ],
        "allowed_capabilities": [
            str(cap)[:100]
            for cap in (raw.get("allowed_capabilities") or [])[:20]
            if isinstance(cap, str)
        ],
        "volumes": [
            str(vol)[:100]
            for vol in (raw.get("volumes") or [])[:20]
            if isinstance(vol, str)
        ],
        "se_linux_context": str(raw.get("se_linux_context", ""))[:200] or None,
        "fs_group": str(raw.get("fs_group", ""))[:200] or None,
        "run_as_user": str(raw.get("run_as_user", ""))[:200] or None,
        "supplemental_groups": str(raw.get("supplemental_groups", ""))[:200] or None,
        "users": [
            str(user)[:200]
            for user in (raw.get("users") or [])[:50]
            if isinstance(user, str)
        ],
        "groups": [
            str(group)[:200]
            for group in (raw.get("groups") or [])[:50]
            if isinstance(group, str)
        ],
        "created_at": _parse_timestamp(raw.get("created_at")),
        "observed_at": _parse_timestamp(raw.get("observed_at")),
        "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
    }
    priority = raw.get("priority")
    if priority is not None:
        try:
            row["priority"] = int(priority)
        except (ValueError, TypeError):
            pass

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "scc": row,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "persisted": False,
        "execution_permitted": False,
    }
