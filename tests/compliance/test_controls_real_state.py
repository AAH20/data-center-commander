"""Prove each repointed control moves when the fact it measures moves.

WHY THIS FILE EXISTS
--------------------
``tests/compliance/test_controls.py`` shows the controls produce the right shape
and the right answer for the state of this checkout. That is not enough: a
control that can only ever return FAIL is as useless as one that can only return
PASS, and a control wired to a constant would pass both files. Every test here
therefore asserts a TRANSITION via the real control evaluator:

    PASS -> FAIL when the fact is broken
    FAIL -> PASS when the fact is repaired

HOW THE FACTS ARE CHANGED SAFELY
--------------------------------
This repository is worked on concurrently, so mutating the demo database --
disabling RLS on a shared table, tampering with a shared audit row -- would
corrupt other people's runs even if it were rolled back afterwards (the controls
open their own connection and would never see an uncommitted change anyway).

Instead each test module creates its own throwaway database, applies the same
DDL shape ``database/schema.sql`` produces, and points ``DCC_DATABASE_URL`` at it.
The controls then observe a database whose state this file owns and may change
freely. The database is dropped at teardown.

Tests that need no database (the environment-variable guards) run everywhere. The
database-backed ones skip with an explicit reason when no server is reachable,
rather than pretending the coverage exists.
"""
from __future__ import annotations

import ast
import os
import re
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dcc.compliance import observables
from dcc.compliance.controls import get_builtin_controls
from dcc.compliance.models import ComplianceStatus
from dcc.compliance.scanner import ComplianceScanner
from dcc.provenance.evidence import compute_event_hash

TENANT_A = "aaaaaaaa-0000-4000-8000-000000000001"
TENANT_B = "aaaaaaaa-0000-4000-8000-000000000002"

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLIANCE_ROOT = REPO_ROOT / "src" / "dcc" / "compliance"


def _base_dsn() -> str:
    return (
        os.environ.get("DCC_OWNER_DATABASE_URL")
        or os.environ.get("DCC_DATABASE_URL")
        or "postgresql://localhost:5432/dcc_demo_local"
    )


def _with_database(dsn: str, database: str, *, options: str | None = None) -> str:
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(dsn)
    params["dbname"] = database
    params.setdefault("connect_timeout", "5")
    if options is not None:
        params["options"] = options
    return make_conninfo(**params)


def _server_available() -> tuple[bool, str]:
    try:
        import psycopg

        with psycopg.connect(_base_dsn(), connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True, ""
    except Exception as exc:  # noqa: BLE001 - any failure means "no server here"
        return False, f"no PostgreSQL server reachable for real-state tests: {exc}"


DB_AVAILABLE, DB_UNAVAILABLE_REASON = _server_available()
requires_db = pytest.mark.skipif(not DB_AVAILABLE, reason=DB_UNAVAILABLE_REASON)


# ---------------------------------------------------------------------------
# Scratch database
# ---------------------------------------------------------------------------

_DDL = """
CREATE SCHEMA IF NOT EXISTS dcc;

CREATE TABLE dcc.tenants (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug             text NOT NULL UNIQUE,
    name             text NOT NULL,
    status           text NOT NULL DEFAULT 'active',
    retention_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dcc.assets (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE
);
ALTER TABLE dcc.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE dcc.assets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON dcc.assets
    USING (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);

CREATE TABLE dcc.evidence_events (
    tenant_id     uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    sequence      bigint NOT NULL,
    id            uuid NOT NULL DEFAULT gen_random_uuid(),
    event_type    text NOT NULL,
    occurred_at   timestamptz NOT NULL DEFAULT now(),
    actor_ref     text,
    subject_type  text,
    subject_id    text,
    payload       jsonb NOT NULL,
    previous_hash text,
    event_hash    text NOT NULL,
    PRIMARY KEY (tenant_id, sequence)
);
ALTER TABLE dcc.evidence_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dcc.evidence_events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON dcc.evidence_events
    USING (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);

CREATE TABLE dcc.incidents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    workflow_id         uuid,
    external_itsm_id    text,
    severity            text NOT NULL,
    state               text NOT NULL,
    incident_commander  text,
    opened_at           timestamptz NOT NULL DEFAULT now(),
    detected_at         timestamptz,
    mitigated_at        timestamptz,
    resolved_at         timestamptz,
    impact              jsonb NOT NULL DEFAULT '{}'::jsonb,
    root_cause_confidence numeric(5, 4),
    timeline            jsonb NOT NULL DEFAULT '[]'::jsonb
);
ALTER TABLE dcc.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE dcc.incidents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON dcc.incidents
    USING (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);

INSERT INTO dcc.tenants (id, slug, name, status) VALUES
    ('aaaaaaaa-0000-4000-8000-000000000001', 'probe-a', 'Probe A', 'active'),
    ('aaaaaaaa-0000-4000-8000-000000000002', 'probe-b', 'Probe B', 'active');

INSERT INTO dcc.assets (tenant_id) VALUES
    ('aaaaaaaa-0000-4000-8000-000000000001'),
    ('aaaaaaaa-0000-4000-8000-000000000002');

INSERT INTO dcc.incidents (tenant_id, severity, state, incident_commander, detected_at)
VALUES ('aaaaaaaa-0000-4000-8000-000000000001', 'SEV-3', 'investigating', 'ic-probe', now());
"""


class ScratchDatabase:
    """A disposable database the tests fully own."""

    def __init__(self, name: str, dsn: str) -> None:
        self.name = name
        self.dsn = dsn

    def execute(self, sql: str, params: tuple = ()) -> None:
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            conn.autocommit = True
            conn.execute(sql, params)

    def rows(self, sql: str, params: tuple = ()) -> list[tuple]:
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def reset_events(self) -> None:
        """Empty the audit trail so a test starts from a known state."""
        self.execute("DELETE FROM dcc.evidence_events")

    def append_event(
        self,
        *,
        tenant_id: str = TENANT_A,
        event_type: str = "auth.key.issued",
        actor_ref: str | None = "probe-actor",
        payload: dict | None = None,
    ) -> str:
        """Append a correctly-hashed event, the way a writer must.

        The hash comes from ``dcc.provenance.evidence`` -- the same function the
        verifier and the HTTP route use -- so a chain built here is valid by
        construction and any FAIL the control reports is a real broken link.
        """
        head = self.rows(
            "SELECT event_hash FROM dcc.evidence_events "
            "WHERE tenant_id = %s::uuid ORDER BY sequence DESC LIMIT 1",
            (tenant_id,),
        )
        previous_hash = head[0][0] if head else ""
        next_sequence = int(
            self.rows(
                "SELECT coalesce(max(sequence), 0) + 1 FROM dcc.evidence_events "
                "WHERE tenant_id = %s::uuid",
                (tenant_id,),
            )[0][0]
        )
        event = {
            "tenant_id": tenant_id,
            "sequence": next_sequence,
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc),
            "actor_ref": actor_ref,
            "subject_type": "probe",
            "subject_id": None,
            "payload": payload or {"probe": True},
            "previous_hash": previous_hash,
        }
        event_hash = compute_event_hash(event)
        self.execute(
            "INSERT INTO dcc.evidence_events "
            "(tenant_id, sequence, id, event_type, occurred_at, actor_ref, subject_type, "
            " subject_id, payload, previous_hash, event_hash) "
            "VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)",
            (
                event["tenant_id"],
                event["sequence"],
                event["id"],
                event["event_type"],
                event["occurred_at"],
                event["actor_ref"],
                event["subject_type"],
                event["subject_id"],
                __import__("json").dumps(event["payload"]),
                previous_hash,
                event_hash,
            ),
        )
        return event_hash

    def tamper(self, *, tenant_id: str = TENANT_A, sequence: int = 1) -> None:
        """Edit a stored event's payload without repairing its hash."""
        self.execute(
            "UPDATE dcc.evidence_events SET payload = %s::jsonb "
            "WHERE tenant_id = %s::uuid AND sequence = %s",
            ('{"probe": "edited-in-place"}', tenant_id, sequence),
        )


@pytest.fixture(scope="module")
def scratch() -> ScratchDatabase:
    import psycopg

    name = f"dcc_compliance_probe_{os.getpid()}"
    admin = _base_dsn()
    with psycopg.connect(admin) as conn:
        conn.autocommit = True
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        conn.execute(f'CREATE DATABASE "{name}"')

    dsn = _with_database(admin, name)
    db = ScratchDatabase(name, dsn)
    try:
        for statement in filter(None, (s.strip() for s in _DDL.split(";"))):
            db.execute(statement)
        yield db
    finally:
        with psycopg.connect(admin) as conn:
            conn.autocommit = True
            try:
                conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            except Exception:  # noqa: BLE001 - older servers lack WITH (FORCE)
                conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


@pytest.fixture()
def probe(scratch: ScratchDatabase, monkeypatch: pytest.MonkeyPatch) -> ScratchDatabase:
    """Point the controls at the scratch database with a known credential set."""
    entry = f"{TENANT_A}:{'b' * 64}"
    monkeypatch.setenv("DCC_DATABASE_URL", scratch.dsn)
    monkeypatch.setenv("DCC_API_KEYS", entry)
    monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "0")
    return scratch


def status_of(control_id: str) -> ComplianceStatus:
    """Evaluate one real control against whatever the environment currently says."""
    controls = {c.control_id: c for c in get_builtin_controls()}
    evaluator = controls[control_id].evaluator
    assert evaluator is not None, control_id
    return ComplianceScanner()._evaluate_control(controls[control_id]).status


def messages(control_id: str) -> str:
    controls = {c.control_id: c for c in get_builtin_controls()}
    evaluator = controls[control_id].evaluator
    assert evaluator is not None, control_id
    return " | ".join(f.message for f in evaluator())


# ---------------------------------------------------------------------------
# ISO 27001 A.9.4.1 -- row-level security
# ---------------------------------------------------------------------------


@requires_db
class TestRowLevelSecurityMoves:
    def test_pass_then_fail_when_rls_is_disabled_then_pass_again(self, probe: ScratchDatabase) -> None:
        assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.PASS, messages("ISO27001-A.9.4.1")

        probe.execute("ALTER TABLE dcc.assets DISABLE ROW LEVEL SECURITY")
        try:
            assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.FAIL
            assert "assets" in messages("ISO27001-A.9.4.1")
        finally:
            probe.execute("ALTER TABLE dcc.assets ENABLE ROW LEVEL SECURITY")

        assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.PASS

    def test_fail_when_force_is_dropped_even_though_rls_is_enabled(self, probe: ScratchDatabase) -> None:
        """ENABLE without FORCE exempts the owner, which is the role the app uses."""
        probe.execute("ALTER TABLE dcc.evidence_events NO FORCE ROW LEVEL SECURITY")
        try:
            assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.FAIL
            assert "evidence_events" in messages("ISO27001-A.9.4.1")
        finally:
            probe.execute("ALTER TABLE dcc.evidence_events FORCE ROW LEVEL SECURITY")
        assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.PASS

    def test_fail_when_the_policy_is_removed(self, probe: ScratchDatabase) -> None:
        probe.execute("DROP POLICY tenant_scope ON dcc.assets")
        try:
            assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.FAIL
        finally:
            probe.execute(
                "CREATE POLICY tenant_scope ON dcc.assets "
                "USING (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid) "
                "WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)"
            )
        assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.PASS

    def test_reports_not_assessed_without_a_database(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DCC_DATABASE_URL", raising=False)
        assert status_of("ISO27001-A.9.4.1") is ComplianceStatus.NOT_ASSESSED
        assert "DCC_DATABASE_URL" in messages("ISO27001-A.9.4.1")


# ---------------------------------------------------------------------------
# PCI DSS 10.1 -- audit trail integrity
# ---------------------------------------------------------------------------


@requires_db
class TestAuditTrailMoves:
    def test_empty_trail_fails_then_a_valid_event_passes(self, probe: ScratchDatabase) -> None:
        probe.reset_events()
        assert status_of("PCI-10.1") is ComplianceStatus.FAIL
        assert "empty" in messages("PCI-10.1").lower()

        probe.append_event(tenant_id=TENANT_A, event_type="audit.probe")
        assert status_of("PCI-10.1") is ComplianceStatus.PASS, messages("PCI-10.1")

    def test_tampering_with_a_stored_row_breaks_the_control(self, probe: ScratchDatabase) -> None:
        probe.reset_events()
        probe.append_event(tenant_id=TENANT_A, event_type="audit.probe")
        assert status_of("PCI-10.1") is ComplianceStatus.PASS

        probe.tamper(tenant_id=TENANT_A, sequence=1)
        try:
            assert status_of("PCI-10.1") is ComplianceStatus.FAIL
            assert "event_hash_mismatch" in messages("PCI-10.1")
        finally:
            probe.execute(
                "DELETE FROM dcc.evidence_events WHERE tenant_id = %s::uuid AND sequence = 1",
                (TENANT_A,),
            )
        probe.append_event(tenant_id=TENANT_A, event_type="audit.probe.repaired")
        assert status_of("PCI-10.1") is ComplianceStatus.PASS, messages("PCI-10.1")
        probe.reset_events()

    def test_a_removed_row_breaks_the_chain_link(self, probe: ScratchDatabase) -> None:
        """Deleting a middle row must be detected by the next row's previous_hash."""
        probe.reset_events()
        probe.append_event(tenant_id=TENANT_B, event_type="audit.probe.first")
        probe.append_event(tenant_id=TENANT_B, event_type="audit.probe.second")
        probe.append_event(tenant_id=TENANT_B, event_type="audit.probe.third")
        assert status_of("PCI-10.1") is ComplianceStatus.PASS

        probe.execute(
            "DELETE FROM dcc.evidence_events WHERE tenant_id = %s::uuid AND sequence = 2",
            (TENANT_B,),
        )
        try:
            assert status_of("PCI-10.1") is ComplianceStatus.FAIL
            assert "chain_link_mismatch" in messages("PCI-10.1")
        finally:
            probe.execute("DELETE FROM dcc.evidence_events WHERE tenant_id = %s::uuid", (TENANT_B,))
        probe.append_event(tenant_id=TENANT_A, event_type="audit.probe.after-removal")
        assert status_of("PCI-10.1") is ComplianceStatus.PASS, messages("PCI-10.1")
        probe.reset_events()


# ---------------------------------------------------------------------------
# SOC 2 CC6.3 -- evidence for access review
# ---------------------------------------------------------------------------


@requires_db
class TestAccessReviewEvidenceMoves:
    def test_fixture_only_events_fail_then_an_access_event_passes(self, probe: ScratchDatabase) -> None:
        probe.append_event(tenant_id=TENANT_A, event_type="demo.fixture.seeded")
        try:
            assert status_of("SOC2-CC6.3") is ComplianceStatus.FAIL
            assert "access review has nothing to review" in messages("SOC2-CC6.3")
        finally:
            probe.execute("DELETE FROM dcc.evidence_events WHERE tenant_id = %s::uuid", (TENANT_A,))

        probe.append_event(tenant_id=TENANT_A, event_type="auth.key.issued")
        try:
            assert status_of("SOC2-CC6.3") is ComplianceStatus.PASS, messages("SOC2-CC6.3")
        finally:
            probe.execute("DELETE FROM dcc.evidence_events WHERE tenant_id = %s::uuid", (TENANT_A,))


# ---------------------------------------------------------------------------
# ISO 27001 A.12.4.1 -- event logging with attribution
# ---------------------------------------------------------------------------


@requires_db
class TestEventAttributionMoves:
    def test_attributed_events_pass_and_an_unattributed_one_fails(self, probe: ScratchDatabase) -> None:
        probe.append_event(tenant_id=TENANT_A, event_type="auth.key.used", actor_ref="alice")
        try:
            assert status_of("ISO27001-A.12.4.1") is ComplianceStatus.PASS

            probe.append_event(tenant_id=TENANT_A, event_type="auth.key.used", actor_ref=None)
            assert status_of("ISO27001-A.12.4.1") is ComplianceStatus.FAIL
            assert "no actor_ref" in messages("ISO27001-A.12.4.1")
        finally:
            probe.execute("DELETE FROM dcc.evidence_events WHERE tenant_id = %s::uuid", (TENANT_A,))

    def test_no_events_at_all_fails(self, probe: ScratchDatabase) -> None:
        assert status_of("ISO27001-A.12.4.1") is ComplianceStatus.FAIL
        assert "No events are recorded" in messages("ISO27001-A.12.4.1")


# ---------------------------------------------------------------------------
# SOC 2 CC7.2 -- incident lifecycle
# ---------------------------------------------------------------------------


@requires_db
class TestIncidentLifecycleMoves:
    def test_pass_when_the_timeline_can_be_recorded_fail_when_a_column_is_gone(
        self, probe: ScratchDatabase
    ) -> None:
        assert status_of("SOC2-CC7.2") is ComplianceStatus.PASS, messages("SOC2-CC7.2")

        probe.execute("ALTER TABLE dcc.incidents DROP COLUMN detected_at")
        try:
            assert status_of("SOC2-CC7.2") is ComplianceStatus.FAIL
            assert "detected_at" in messages("SOC2-CC7.2")
        finally:
            probe.execute("ALTER TABLE dcc.incidents ADD COLUMN detected_at timestamptz")

        assert status_of("SOC2-CC7.2") is ComplianceStatus.PASS


# ---------------------------------------------------------------------------
# HIPAA 164.312(a)(1) -- unique identification
# ---------------------------------------------------------------------------


@requires_db
class TestIdentityUniquenessMoves:
    def test_pass_then_fail_on_a_duplicate_hash(self, probe: ScratchDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
        assert status_of("HIPAA-164.312(a)(1)") is ComplianceStatus.PASS, messages("HIPAA-164.312(a)(1)")
        shared = "c" * 64
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{shared},{TENANT_B}:{shared}")
        assert status_of("HIPAA-164.312(a)(1)") is ComplianceStatus.FAIL
        assert "share an identifier" in messages("HIPAA-164.312(a)(1)")

    def test_fail_when_a_credential_points_at_no_tenant(self, probe: ScratchDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{'d' * 64},cccccccc-0000-4000-8000-000000000009:{'e' * 64}")
        assert status_of("HIPAA-164.312(a)(1)") is ComplianceStatus.FAIL
        assert "do not exist" in messages("HIPAA-164.312(a)(1)")


# ---------------------------------------------------------------------------
# NIST AC-2 -- account register
# ---------------------------------------------------------------------------


@requires_db
class TestAccountRegisterMoves:
    def test_pass_when_active_then_fail_when_suspended(self, probe: ScratchDatabase) -> None:
        assert status_of("NIST-AC-2") is ComplianceStatus.PASS, messages("NIST-AC-2")

        probe.execute("UPDATE dcc.tenants SET status = 'suspended' WHERE id = %s::uuid", (TENANT_A,))
        try:
            assert status_of("NIST-AC-2") is ComplianceStatus.FAIL
            assert "not active" in messages("NIST-AC-2")
        finally:
            probe.execute("UPDATE dcc.tenants SET status = 'active' WHERE id = %s::uuid", (TENANT_A,))

        assert status_of("NIST-AC-2") is ComplianceStatus.PASS


# ---------------------------------------------------------------------------
# PCI DSS 8.2 -- credential strength
# ---------------------------------------------------------------------------


class TestCredentialStrengthMoves:
    def test_status_follows_the_credential_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{'a' * 64}")
        assert status_of("PCI-8.2") is ComplianceStatus.PASS

        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:hunter2")
        assert status_of("PCI-8.2") is ComplianceStatus.FAIL

        monkeypatch.setenv("DCC_API_KEYS", "")
        assert status_of("PCI-8.2") is ComplianceStatus.FAIL


# ---------------------------------------------------------------------------
# SOC 2 CC6.2 -- credential expiry
# ---------------------------------------------------------------------------


class TestCredentialExpiryMoves:
    """Two branches, because the served process has a key store and the CLI does not.

    ``observables.live_key_store()`` returns the running application's store when
    ``dcc.api_async`` has been imported -- that IS the live truth in a server. The
    tests below force the store away (``_API_KEYS = None``) to exercise the
    configuration branch deterministically, and exercise the store branch by passing
    a real ``ApiKeyStore``. Anything else would make the assertion depend on which
    other test modules happened to import the app first.
    """

    @pytest.fixture()
    def no_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import dcc.api_async as api

        monkeypatch.setattr(api, "_API_KEYS", None, raising=False)

    def test_env_loaded_credentials_never_expire(
        self, monkeypatch: pytest.MonkeyPatch, no_store: None
    ) -> None:
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{'a' * 64}")
        assert status_of("SOC2-CC6.2") is ComplianceStatus.FAIL
        assert "never expire" in messages("SOC2-CC6.2")

    def test_expiring_credentials_in_the_live_store_pass(self) -> None:
        """The verdict is read off real ApiKey objects, not a config string."""
        import time

        from dcc.security.api_keys import ApiKeyStore

        # dsn="" forces the in-memory backend. A bare ApiKeyStore() picks up
        # DCC_DATABASE_URL and would read whatever keys a previous run left in the
        # development database, so the test would assert about residue rather than
        # about the objects it just registered.
        store = ApiKeyStore(dsn="")
        store.register_hash(tenant_id=TENANT_A, key_hash="a" * 64)  # permanent
        assert observables.measure_credential_expiry(store=store).verdict is False

        expiring = ApiKeyStore(dsn="")
        expiring.register_hash(
            tenant_id=TENANT_A, key_hash="b" * 64, expires_at=time.time() + 3600
        )
        assert observables.measure_credential_expiry(store=expiring).verdict is True

    def test_no_store_and_no_keys_is_not_assessed(
        self, monkeypatch: pytest.MonkeyPatch, no_store: None
    ) -> None:
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        assert status_of("SOC2-CC6.2") is ComplianceStatus.NOT_ASSESSED


# ---------------------------------------------------------------------------
# HIPAA 164.312(e)(1) -- transport encryption
# ---------------------------------------------------------------------------


@requires_db
class TestTransportEncryptionMoves:
    def test_plaintext_dsn_fails(self, probe: ScratchDatabase) -> None:
        assert status_of("HIPAA-164.312(e)(1)") is ComplianceStatus.FAIL
        assert "permits a plaintext connection" in messages("HIPAA-164.312(e)(1)")

    def test_transport_is_measured_not_declared(self) -> None:
        """The decision rule, exercised on the facts pg_stat_ssl reports."""
        verdict, why = observables.tls_verdict(mode="require", sessions=3, encrypted=3)
        assert verdict is True, why

        verdict, why = observables.tls_verdict(mode="require", sessions=3, encrypted=2)
        assert verdict is False and "unencrypted" in why

        verdict, why = observables.tls_verdict(mode="prefer", sessions=3, encrypted=3)
        assert verdict is False and "fall back" in why

        verdict, _ = observables.tls_verdict(mode="require", sessions=0, encrypted=0)
        assert verdict is None

    def test_requires_tls_but_cannot_connect_is_not_assessed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A server without TLS refuses a require-mode connection: nothing to observe."""
        monkeypatch.setenv("DCC_DATABASE_URL", f"{_base_dsn()}?sslmode=require")
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{'a' * 64}")
        measurement = observables.measure_db_tls()
        assert measurement.verdict is None
        assert "no live database session" in measurement.statement


# ---------------------------------------------------------------------------
# SOC 2 CC6.1 -- authentication posture, with MFA left honest
# ---------------------------------------------------------------------------


class TestAuthenticationPostureMoves:
    def test_anonymous_then_enforced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        key = f"{TENANT_A}:{'a' * 64}"
        monkeypatch.setenv("DCC_API_KEYS", key)

        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        assert status_of("SOC2-CC6.1") is ComplianceStatus.FAIL

        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "0")
        # Authentication is now enforced, so the auth finding passes, but the
        # control as a whole is not assessed because MFA cannot be measured.
        findings = get_builtin_controls()[0]
        controls = {c.control_id: c for c in get_builtin_controls()}
        result = ComplianceScanner()._evaluate_control(controls["SOC2-CC6.1"])
        assert result.status is ComplianceStatus.NOT_ASSESSED
        assert any(f.status is ComplianceStatus.PASS for f in result.findings)
        assert findings is not None


# ---------------------------------------------------------------------------
# SOC 2 CC7.1 -- alert rules must reference exported metrics
# ---------------------------------------------------------------------------


class TestAlertCoverageMoves:
    def _rules(self, tmp_path: Path, expr: str) -> Path:
        (tmp_path / "rules.yml").write_text(
            textwrap.dedent(
                f"""
                groups:
                  - name: probe
                    rules:
                      - alert: ProbeAlert
                        expr: {expr} > 0
                        labels:
                          severity: warning
                """
            ),
            encoding="utf-8",
        )
        return tmp_path

    def test_rule_over_an_exported_metric_passes(self, tmp_path: Path) -> None:
        root = self._rules(tmp_path, "dcc_api_healthy")
        assert observables.measure_alert_coverage(root=root).verdict is True

    def test_rule_over_a_metric_nothing_exports_fails(self, tmp_path: Path) -> None:
        root = self._rules(tmp_path, "dcc_imaginary_errors_total")
        measurement = observables.measure_alert_coverage(root=root)
        assert measurement.verdict is False
        assert "dcc_imaginary_errors_total" in measurement.statement

    def test_missing_rules_fail(self, tmp_path: Path) -> None:
        measurement = observables.measure_alert_coverage(root=tmp_path / "absent")
        assert measurement.verdict is False

    def test_unparseable_rules_fail(self, tmp_path: Path) -> None:
        (tmp_path / "broken.yml").write_text("groups: [ unclosed", encoding="utf-8")
        measurement = observables.measure_alert_coverage(root=tmp_path)
        assert measurement.verdict is False
        assert "no usable alert rule files" in measurement.statement.lower()

    def test_the_control_reads_the_repository_rules(self) -> None:
        """The control's own verdict is the repository measurement, not a constant."""
        expected = observables.measure_alert_coverage().verdict
        status = status_of("SOC2-CC7.1")
        if expected is True:
            assert status is ComplianceStatus.PASS
        elif expected is False:
            assert status is ComplianceStatus.FAIL
        else:
            assert status is ComplianceStatus.NOT_ASSESSED


# ---------------------------------------------------------------------------
# The durable guard: no control may read a variable the application ignores
# ---------------------------------------------------------------------------

APP_SOURCE_ROOT = REPO_ROOT / "src" / "dcc"

_ENV_CALL_PATTERNS = (
    re.compile(r"os\.environ\.get\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
    re.compile(r"os\.environ\[\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
    re.compile(r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
    # dcc.security.posture::_truthy reads os.getenv(variable) -- its call sites are
    # the only place the name appears as a literal.
    re.compile(r"_truthy\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
)


def _application_env_names() -> set[str]:
    """Every environment variable the served application reads, by name."""
    names: set[str] = set()
    for path in APP_SOURCE_ROOT.rglob("*.py"):
        if COMPLIANCE_ROOT in path.parents:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in _ENV_CALL_PATTERNS:
            names.update(pattern.findall(text))
    return names


def _env_names_read_by_compliance() -> dict[str, set[str]]:
    """Environment variables the compliance code reads, resolved through constants.

    Parsed rather than grepped so a name held in a module constant
    (``DSN_ENV = "DCC_DATABASE_URL"``) is resolved to its value, and so names that
    merely appear in prose are not mistaken for reads.
    """
    found: dict[str, set[str]] = {}

    def _resolve(node: ast.AST, constants: dict[str, str]) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    for path in COMPLIANCE_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        constants: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            constants[target.id] = node.value.value
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _env_call_name(node.func)
                if name is not None and node.args:
                    resolved = _resolve(node.args[0], constants)
                    if resolved:
                        names.add(resolved)
            elif isinstance(node, ast.Subscript):
                value = node.value
                if (
                    isinstance(value, ast.Attribute)
                    and value.attr == "environ"
                    and isinstance(value.value, ast.Name)
                    and value.value.id == "os"
                ):
                    resolved = _resolve(node.slice, constants)
                    if resolved:
                        names.add(resolved)
        if names:
            found[str(path.relative_to(COMPLIANCE_ROOT))] = names
    return found


def _env_call_name(func: ast.AST) -> str | None:
    """Is this ``os.environ.get`` / ``os.getenv`` / ``environ.get``?"""
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in {"get", "getenv"}:
        return None
    inner = func.value
    if isinstance(inner, ast.Name) and inner.id in {"os", "environ"}:
        return func.attr
    if isinstance(inner, ast.Attribute) and inner.attr == "environ":
        return func.attr
    return None


class TestNoPhantomVariables:
    def test_compliance_reads_only_variables_the_application_reads(self) -> None:
        app_names = _application_env_names()
        assert "DCC_DATABASE_URL" in app_names
        assert "DCC_API_KEYS" in app_names
        assert "DCC_ALLOW_ANONYMOUS" in app_names

        reads = _env_names_read_by_compliance()
        assert reads, "expected the compliance package to read the DSN and key variables"
        phantom = {
            path: sorted(names - app_names) for path, names in reads.items() if names - app_names
        }
        assert not phantom, (
            "compliance controls read environment variables the served application never "
            f"consults: {phantom}. A control must measure state, not a knob nobody turns."
        )

    @pytest.mark.parametrize(
        "variable",
        [
            "DCC_AUTH_ENABLED",
            "DCC_MFA_ENABLED",
            "DCC_SESSION_TIMEOUT_MINUTES",
            "DCC_AUDIT_ENABLED",
            "DCC_MONITORING_ENABLED",
            "DCC_IR_PLAN_PATH",
            "DCC_RBAC_ENABLED",
            "DCC_LOG_LEVEL",
            "DCC_SECURITY_POLICY_PATH",
            "DCC_NETWORK_SEGMENTED",
            "DCC_ENCRYPTION_AT_REST",
            "DCC_MIN_PASSWORD_LENGTH",
            "DCC_AUDIT_TRAIL_ENABLED",
            "DCC_UNIQUE_USER_IDS",
            "DCC_TLS_ENFORCED",
            "DCC_ACCOUNT_MANAGEMENT",
            "DCC_AUDIT_POLICY_PATH",
        ],
    )
    def test_historical_knob_cannot_move_any_control(
        self, variable: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting a variable the app ignores must change no verdict at all.

        This is the behavioural half of the guard: the text scan above catches a
        new ``os.environ.get`` in the compliance package, and this catches a verdict
        that ends up depending on a variable some other way.
        """
        baseline = {
            c.control_id: [
                (f.status, f.message) for f in (c.evaluator() if c.evaluator else [])
            ]
            for c in get_builtin_controls()
        }

        for value in ("true", "false", "1", "0", "/tmp/does-not-exist"):
            monkeypatch.setenv(variable, value)
            after = {
                c.control_id: [
                    (f.status, f.message) for f in (c.evaluator() if c.evaluator else [])
                ]
                for c in get_builtin_controls()
            }
            assert after == baseline, f"{variable}={value} changed a control verdict"

    def test_unmeasurable_controls_are_never_green(self) -> None:
        """The four controls with no observable must not be passable by any input."""
        for control_id in ("ISO27001-A.14.1.1", "PCI-1.1", "PCI-3.4", "NIST-AU-1"):
            assert status_of(control_id) is ComplianceStatus.NOT_ASSESSED, control_id
