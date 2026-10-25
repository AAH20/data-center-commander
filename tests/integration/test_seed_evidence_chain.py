"""The demo seed must produce an evidence chain that verifies.

The seeded row is the product's own demonstration of tamper-evident evidence. If the
seed cannot pass its own verifier, the demo shows a broken chain and every downstream
claim about provenance is unsupported by the fixture.

This was real: the row was inserted with `gen_random_uuid()` for `id` and `now()` for
`occurred_at`, both of which the hash covers, so a hash could never be pinned to it. The
seed was later updated to pin both, but the insert was ON CONFLICT DO NOTHING -- so a
database seeded before the fix kept the corrupt row forever and re-running the seed could
not repair it. Changing to DO UPDATE with a WHERE that ignores already-correct rows makes
the seed idempotent and self-healing.

These tests need a real database: the defect is in SQL that a fake cannot reproduce.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

REPO = Path(__file__).resolve().parents[2]
TENANT = "dcc00000-0000-4000-8000-000000000001"
SCRATCH_DB = "dcc_seed_chain_test"


def _admin_dsn() -> str:
    return os.environ.get("DCC_VERIFY_DSN") or "postgresql:///postgres"


def _scratch_dsn() -> str:
    return f"postgresql:///{SCRATCH_DB}"


def _psql(dsn: str, *args: str) -> None:
    subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-q", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def seeded():
    """A scratch database built from schema, every migration, then the demo seed."""
    pytest.importorskip("psycopg")
    try:
        subprocess.run(["dropdb", "--if-exists", SCRATCH_DB], check=True, capture_output=True)
        subprocess.run(["createdb", SCRATCH_DB], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("cannot create a scratch database on this host")

    try:
        _psql(_scratch_dsn(), "-f", str(REPO / "database/schema.sql"))
        for migration in sorted((REPO / "database/migrations").glob("*.sql")):
            _psql(_scratch_dsn(), "-f", str(migration))
        _psql(_scratch_dsn(), "-f", str(REPO / "database/demo_seed.sql"))
        yield _scratch_dsn()
    finally:
        subprocess.run(["dropdb", "--if-exists", SCRATCH_DB], capture_output=True)


def _verify(dsn: str) -> dict:
    from dcc.provenance.evidence import verify_evidence_chain

    conn = psycopg.connect(dsn, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tenant_id, sequence, id, event_type, occurred_at, actor_ref, "
                "subject_type, subject_id, payload, previous_hash, event_hash "
                "FROM dcc.evidence_events WHERE tenant_id = %s ORDER BY sequence",
                (TENANT,),
            )
            columns = [d.name for d in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()
    return verify_evidence_chain(rows)


def test_seeded_chain_verifies(seeded: str) -> None:
    result = _verify(seeded)

    assert result["total_events"] >= 1, "the seed inserted no evidence events"
    assert result["chain_valid"] is True, (
        f"the demo seed produces an invalid evidence chain: {result['reason']} at "
        f"sequence {result['broken_at']}. The seeded fixture fails the product's own "
        f"verifier, so nothing downstream can claim provenance from it."
    )


def test_seed_pins_the_hashed_fields(seeded: str) -> None:
    """id and occurred_at are covered by the hash, so they cannot be left to defaults."""
    conn = psycopg.connect(seeded, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, occurred_at FROM dcc.evidence_events "
                "WHERE tenant_id = %s AND sequence = 1",
                (TENANT,),
            )
            event_id, occurred_at = cur.fetchone()
    finally:
        conn.close()

    assert event_id == "dcc00000-0000-4000-8000-0000000000e1", (
        "the seeded event id is random; a hash over it cannot be pinned in the seed"
    )
    assert occurred_at.astimezone(__import__("datetime").timezone.utc).isoformat(
        timespec="microseconds"
    ) == "2026-01-01T00:00:00.000000+00:00", (
        "the seeded occurred_at moved; the pinned hash no longer matches"
    )


def test_reseeding_repairs_a_corrupted_chain(seeded: str) -> None:
    """ON CONFLICT DO NOTHING made a broken fixture permanent. DO UPDATE repairs it."""
    conn = psycopg.connect(seeded, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE dcc.evidence_events SET event_hash = 'synthetic-demo-event-hash-v1' "
                "WHERE tenant_id = %s AND sequence = 1",
                (TENANT,),
            )
    finally:
        conn.close()

    assert _verify(seeded)["chain_valid"] is False, "the verifier did not notice tampering"

    _psql(seeded, "-f", str(REPO / "database/demo_seed.sql"))

    assert _verify(seeded)["chain_valid"] is True, (
        "re-running the seed did not repair the chain; a database seeded before the fix "
        "stays corrupt forever"
    )


def test_reseeding_a_valid_chain_changes_nothing(seeded: str) -> None:
    """The repair must be conditional, so a routine re-seed is not a write to every row."""
    before = _verify(seeded)
    _psql(seeded, "-f", str(REPO / "database/demo_seed.sql"))
    after = _verify(seeded)

    assert after["chain_valid"] is True
    assert after["total_events"] == before["total_events"]
