"""Canonical hash chain for the ``dcc.evidence_events`` table.

WHY THIS MODULE EXISTS
----------------------
The evidence chain had five independent implementations of the same hash, and they
disagreed:

    src/dcc/security/audit.py               sha256(json(19 audit fields))
    src/dcc/api_async.py                    sha256(prev + event_type + occurred_at)
    src/dcc/domain_services.py              sha256(prev + event_type + occurred_at)
    database/.../005_performance_indexes.sql      digest(prev || payload || occurred_at || actor_ref)
    database/.../005_performance_optimization.sql digest(prev || payload || occurred_at || actor_ref)

Two of those SQL files also shared the migration number 005 while both defining a
function named ``dcc.verify_evidence_chain``, so which definition exists in a given
database depended on filesystem order.

The consequence: the HTTP route recomputed a hash over ``event_type`` and
``occurred_at`` only, while the writer records more. No stored row could ever
validate, and the endpoint returned ``chain_valid: false`` for untouched data while
still looking like a working verifier.

This module is the single definition. Writers, the API route, and tests must all use
``compute_event_hash``. If a database-side verifier is ever required, it belongs in
its own migration and must be derived from this payload definition -- not retyped.

CANONICAL FORM
--------------
The hash covers every distinguishing column except ``event_hash`` itself:

    tenant_id, sequence, id, event_type, occurred_at, actor_ref,
    subject_type, subject_id, payload, previous_hash

``occurred_at`` is normalised to UTC ISO-8601 with microseconds. That matters:
``datetime.isoformat()``, PostgreSQL's ``timestamptz::text``, and default json
serialisation all render the same instant differently, and a hash computed over any
of those spellings cannot be reproduced from another. Normalising here is what makes
the value reproducible at all.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

__all__ = [
    "GENESIS_HASH",
    "canonical_payload",
    "compute_event_hash",
    "normalise_timestamp",
    "verify_evidence_chain",
]

#: ``previous_hash`` of the first event in a chain.
GENESIS_HASH = ""


def normalise_timestamp(value: Any) -> str:
    """Render a timestamp in the one spelling the hash is defined over.

    Naive datetimes are assumed to be UTC -- calling an ambiguous instant "local"
    would make the resulting hash depend on the machine that computed it.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def canonical_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact dict the hash is computed over.

    Every field is normalised to a JSON-stable form so that a row read back from
    PostgreSQL and a row produced in memory hash identically.
    """
    return {
        "tenant_id": str(event["tenant_id"]),
        "sequence": int(event["sequence"]),
        "id": str(event["id"]),
        "event_type": str(event["event_type"]),
        "occurred_at": normalise_timestamp(event.get("occurred_at")),
        "actor_ref": str(event.get("actor_ref") or ""),
        "subject_type": str(event.get("subject_type") or ""),
        "subject_id": str(event.get("subject_id") or ""),
        "payload": event.get("payload") or {},
        "previous_hash": str(event.get("previous_hash") or ""),
    }


def compute_event_hash(event: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical payload, hex encoded."""
    encoded = json.dumps(
        canonical_payload(event),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_evidence_chain(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Verify a tenant's evidence chain in sequence order.

    Two independent checks per row:

    1. ``event_hash`` matches a recomputation over the row's own fields -- the row
       has not been edited.
    2. ``previous_hash`` matches the preceding row's ``event_hash`` -- no row has
       been inserted, removed, or reordered.

    A verifier that cannot fail is indistinguishable from one that does not run, so
    any test for this function must include a tampered row and assert rejection.

    ``rows`` must be sorted ascending by ``sequence``. They are re-sorted here so a
    caller cannot accidentally verify a chain out of order and get ``valid: True``.
    """
    ordered = sorted(rows, key=lambda r: int(r["sequence"]))
    events: list[dict[str, Any]] = []
    previous_hash = GENESIS_HASH
    broken_at: Any = None
    reason: str | None = None

    for row in ordered:
        expected = compute_event_hash(row)
        stored = str(row.get("event_hash") or "")

        if stored != expected:
            valid = False
            reason = reason or "event_hash_mismatch"
            broken_at = row.get("sequence") if broken_at is None else broken_at
        elif str(row.get("previous_hash") or "") != previous_hash:
            valid = False
            reason = reason or "chain_link_mismatch"
            broken_at = row.get("sequence") if broken_at is None else broken_at
        else:
            valid = True

        events.append(
            {
                "sequence": row.get("sequence"),
                "event_type": row.get("event_type"),
                "occurred_at": normalise_timestamp(row.get("occurred_at")),
                "is_valid": valid,
                "expected_hash": expected,
                "stored_hash": stored,
            }
        )
        # Chain linkage always advances on the STORED hash: if a row was tampered
        # with, the next row's link is checked against what is actually recorded,
        # so a single edit is reported as one fault rather than cascading into
        # every subsequent row.
        previous_hash = stored

    invalid = [e for e in events if not e["is_valid"]]
    return {
        "chain_valid": not invalid,
        "total_events": len(events),
        "valid_events": len(events) - len(invalid),
        "invalid_events": len(invalid),
        "broken_at": broken_at,
        "reason": reason,
        "events": events,
    }
