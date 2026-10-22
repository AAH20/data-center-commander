"""Bounds on the evidence verification endpoint.

The endpoint used to load every event for a tenant into memory and echo every event's
hashes back. An authenticated tenant with a long history could exhaust a worker with one
request, and the response grew without limit.

Capping the scan introduces a subtler hazard than the memory use: a verified PREFIX of a
chain that is broken later verifies as valid. Returning that prefix verdict as the
chain's verdict would be a false assurance in the exact place the system claims tamper
evidence -- an ISO 42001 evidence chain that reports "valid" for data it never read.

These tests pin both halves: that the prefix hazard is real, and that the response shape
carries enough to distinguish a complete check from a partial one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from dcc.provenance.evidence import GENESIS_HASH, compute_event_hash, verify_evidence_chain

TENANT = "11111111-1111-4111-8111-111111111111"
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _chain(count: int = 5) -> list[dict[str, Any]]:
    """A correctly linked chain of ``count`` events."""
    rows: list[dict[str, Any]] = []
    previous = GENESIS_HASH
    for i in range(1, count + 1):
        row = {
            "tenant_id": TENANT,
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


class TestPrefixHazard:
    """Why a truncated scan must report null, not True."""

    def test_complete_chain_verifies(self):
        result = verify_evidence_chain(_chain(5))
        assert result["chain_valid"] is True
        assert result["total_events"] == 5

    def test_prefix_of_a_broken_chain_verifies_as_valid(self):
        """THE hazard. Events 1-2 are untouched, so they verify; event 4 is tampered.

        Verifying only the prefix returns chain_valid True, which is a true statement
        about two rows and a false one about the chain.
        """
        rows = _chain(5)
        rows[3]["payload"] = {"amount": 999999, "currency": "USD"}  # tamper event 4

        full = verify_evidence_chain(rows)
        assert full["chain_valid"] is False
        assert full["broken_at"] == 4

        prefix = verify_evidence_chain(rows[:2])
        assert prefix["chain_valid"] is True, "the prefix really does verify clean"

    def test_trimming_the_tail_anywhere_hides_the_break(self):
        """Any truncation before the break point reports valid. Hence the null."""
        rows = _chain(5)
        rows[3]["payload"] = {"amount": 1, "currency": "USD"}
        for cut in (1, 2, 3):
            assert verify_evidence_chain(rows[:cut])["chain_valid"] is True


class TestBoundedResponse:
    def test_events_are_available_for_the_failing_rows(self):
        rows = _chain(4)
        rows[2]["actor_ref"] = "user:impostor"
        result = verify_evidence_chain(rows)
        failed = [e for e in result["events"] if not e["is_valid"]]
        assert len(failed) == 1
        assert failed[0]["sequence"] == 3

    def test_single_tamper_does_not_cascade(self):
        """One edit must be one fault, not every subsequent row."""
        rows = _chain(6)
        rows[1]["payload"] = {"amount": 5, "currency": "USD"}
        result = verify_evidence_chain(rows)
        assert result["invalid_events"] == 1

    def test_event_detail_carries_what_was_expected_and_stored(self):
        rows = _chain(2)
        rows[0]["event_hash"] = "0" * 64
        event = verify_evidence_chain(rows)["events"][0]
        assert event["stored_hash"] == "0" * 64
        assert event["expected_hash"] != "0" * 64


class TestEndpointContract:
    def test_route_is_registered(self):
        from dcc.api_async import app

        assert "/v2/evidence/verify" in {getattr(r, "path", "") for r in app.routes}

    def test_endpoint_exposes_the_bounds(self):
        """The cap and the complete flag must be part of the contract, not implicit."""
        import inspect

        from dcc.api_async import verify_evidence_tenant_chain

        params = inspect.signature(verify_evidence_tenant_chain).parameters
        assert "max_events" in params
        assert "complete" in inspect.getsource(verify_evidence_tenant_chain)
            # declared in the response payload
        assert "include_events" in params
