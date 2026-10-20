"""Tests for the canonical evidence-chain hash and verifier.

The point of this file is the negative controls. A verifier that returns
``chain_valid: true`` for everything passes a happy-path test and is worthless, so
every rejection path below is asserted explicitly, and one test reproduces the
original defect (a hash computed over a different payload) to prove the verifier
would have caught it.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from dcc.provenance.evidence import (
    GENESIS_HASH,
    canonical_payload,
    compute_event_hash,
    normalise_timestamp,
    verify_evidence_chain,
)

TENANT = "dcc00000-0000-4000-8000-000000000001"
BASE_TIME = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _chain(count: int = 3, tenant: str = TENANT) -> list[dict[str, Any]]:
    """Build a correctly linked chain of ``count`` events."""
    rows: list[dict[str, Any]] = []
    previous = GENESIS_HASH
    for i in range(1, count + 1):
        row = {
            "tenant_id": tenant,
            "sequence": i,
            "id": f"dcc00000-0000-4000-8000-{i:012d}",
            "event_type": "estimate.created",
            "occurred_at": BASE_TIME + timedelta(minutes=i),
            "actor_ref": "user:ahmed",
            "subject_type": "estimate",
            "subject_id": f"est-{i}",
            "payload": {"amount": 1000 * i, "currency": "USD"},
            "previous_hash": previous,
        }
        row["event_hash"] = compute_event_hash(row)
        rows.append(row)
        previous = row["event_hash"]
    return rows


# --- the hash itself ---------------------------------------------------------


def test_hash_is_deterministic() -> None:
    row = _chain(1)[0]
    assert compute_event_hash(row) == compute_event_hash(dict(row))


def test_hash_is_insensitive_to_field_order() -> None:
    row = _chain(1)[0]
    shuffled = {k: row[k] for k in reversed(list(row.keys()))}
    assert compute_event_hash(row) == compute_event_hash(shuffled)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("event_type", "estimate.deleted"),
        ("actor_ref", "user:someone-else"),
        ("payload", {"amount": 999999, "currency": "USD"}),
        ("sequence", 99),
        ("subject_id", "est-other"),
    ],
)
def test_hash_changes_when_any_covered_field_changes(field: str, replacement: Any) -> None:
    row = _chain(1)[0]
    original = compute_event_hash(row)
    row[field] = replacement
    assert compute_event_hash(row) != original, f"editing {field} did not change the hash"


def test_timestamp_normalisation_is_stable_across_representations() -> None:
    """The same instant written three ways must hash identically.

    This is the defect behind the original bug: one implementation hashed a Python
    isoformat string, another hashed postgres's timestamptz::text rendering, so no
    two verifiers could agree.
    """
    base = _chain(1)[0]
    instant = base["occurred_at"]                      # the row's OWN instant
    as_offset = instant.isoformat()                    # 2026-10-20T12:01:00+00:00
    as_zulu = instant.isoformat().replace("+00:00", "Z")

    for spelling in (instant, as_offset, as_zulu):
        row = dict(base, occurred_at=spelling)
        assert compute_event_hash(row) == compute_event_hash(base), spelling

    # and normalisation collapses all three to one string
    assert normalise_timestamp(instant) == normalise_timestamp(as_offset)
    assert normalise_timestamp(instant) == normalise_timestamp(as_zulu)


def test_naive_datetime_is_treated_as_utc() -> None:
    naive = datetime(2026, 10, 20, 12, 0, 0)
    aware = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
    assert normalise_timestamp(naive) == normalise_timestamp(aware)


# --- the verifier accepts a good chain ---------------------------------------


def test_intact_chain_validates() -> None:
    result = verify_evidence_chain(_chain(3))
    assert result["chain_valid"] is True
    assert result["invalid_events"] == 0
    assert result["valid_events"] == 3
    assert result["broken_at"] is None


def test_empty_chain_is_vacuously_valid() -> None:
    result = verify_evidence_chain([])
    assert result["chain_valid"] is True
    assert result["total_events"] == 0


def test_order_of_input_does_not_matter() -> None:
    rows = _chain(3)
    assert verify_evidence_chain(reversed(rows))["chain_valid"] is True


# --- NEGATIVE CONTROLS: the verifier must reject -----------------------------


def test_tampered_payload_is_rejected() -> None:
    rows = _chain(3)
    rows[1]["payload"] = {"amount": 1, "currency": "USD"}
    result = verify_evidence_chain(rows)
    assert result["chain_valid"] is False
    assert result["reason"] == "event_hash_mismatch"
    assert result["broken_at"] == 2


def test_tampered_actor_is_rejected() -> None:
    rows = _chain(3)
    rows[0]["actor_ref"] = "user:attacker"
    assert verify_evidence_chain(rows)["chain_valid"] is False


def test_deleted_middle_row_is_rejected() -> None:
    rows = _chain(3)
    del rows[1]
    result = verify_evidence_chain(rows)
    assert result["chain_valid"] is False
    assert result["reason"] == "chain_link_mismatch"


def test_tampered_previous_hash_is_rejected() -> None:
    """Rewriting a link is rejected by the row's own hash.

    ``previous_hash`` is part of the hashed payload, so editing it changes the
    recomputed hash too. The row therefore fails on ``event_hash_mismatch`` before
    the link check is reached -- which is the stronger outcome: a tampered link
    cannot be made self-consistent without also forging the hash.
    """
    rows = _chain(3)
    rows[2]["previous_hash"] = "0" * 64
    result = verify_evidence_chain(rows)
    assert result["chain_valid"] is False
    assert result["reason"] == "event_hash_mismatch"


def test_reordered_input_list_still_validates() -> None:
    """A shuffled caller-supplied list is not an attack.

    ``sequence`` is the authoritative order, so verification sorts by it. Swapping
    whole rows in the input does not alter the data and must not be reported as
    tampering -- otherwise the endpoint would cry wolf on a harmless query order.
    """
    rows = _chain(3)
    rows[1], rows[2] = rows[2], rows[1]
    assert verify_evidence_chain(rows)["chain_valid"] is True


def test_single_tamper_is_reported_once_not_cascaded() -> None:
    """Editing one row must not report every later row as broken."""
    rows = _chain(4)
    rows[1]["payload"] = {"amount": 0, "currency": "USD"}
    result = verify_evidence_chain(rows)
    assert result["invalid_events"] == 1
    assert result["broken_at"] == 2


def test_verifier_catches_the_original_defect() -> None:
    """Reproduce the bug this module was written to fix.

    The API route computed ``sha256(previous_hash + event_type + occurred_at)``.
    Rows written that way must be rejected by the canonical verifier, proving the
    verifier would have caught the mismatch rather than reporting a clean chain.
    """
    rows = _chain(2)
    previous = GENESIS_HASH
    for row in rows:
        legacy = hashlib.sha256(
            f"{previous}{row['event_type']}{row['occurred_at']}".encode()
        ).hexdigest()
        row["event_hash"] = legacy
        previous = legacy

    result = verify_evidence_chain(rows)
    assert result["chain_valid"] is False
    assert result["reason"] == "event_hash_mismatch"


def test_canonical_payload_covers_every_chain_column() -> None:
    """If a column is added to the table and not to the payload, the chain stops
    being tamper-evident for that column. This pins the covered set."""
    assert set(canonical_payload(_chain(1)[0])) == {
        "tenant_id",
        "sequence",
        "id",
        "event_type",
        "occurred_at",
        "actor_ref",
        "subject_type",
        "subject_id",
        "payload",
        "previous_hash",
    }
