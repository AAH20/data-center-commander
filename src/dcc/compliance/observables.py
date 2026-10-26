"""Measurements of running-system state, for compliance controls to judge.

WHY THIS MODULE EXISTS
----------------------
Every built-in control used to derive its verdict by reading an environment
variable. Most of those variables appeared nowhere in the served application:
``DCC_TLS_ENFORCED``, ``DCC_MFA_ENABLED``, ``DCC_AUDIT_TRAIL_ENABLED`` and a dozen
more. An operator could set one, change nothing about the system, and watch the
compliance report go green. That is worse than having no control, because it
manufactures assurance an auditor will rely on.

A control may only assert something the running system can be asked about. This
module performs those interrogations and returns a :class:`Measurement`:

    ``verdict is True``   the fact holds, measured just now
    ``verdict is False``  the fact is violated, measured just now
    ``verdict is None``   the fact cannot be measured from here, with a reason

The third case is the important one. "Cannot be measured" is not "passed", and
the reason travels with the measurement into the report so a reader can see the
gap instead of an unexplained blank.

SOURCES OF TRUTH, IN ORDER OF PREFERENCE
----------------------------------------
1. The database the application is configured to use (``DCC_DATABASE_URL``, the
   same variable ``api_async`` reads at startup). Schema facts -- row-level
   security, audit tables, chain integrity -- are read from it directly.
2. The application's own configuration that it actually consumes
   (``DCC_API_KEYS``, ``DCC_ALLOW_ANONYMOUS``, the DSN's ``sslmode``).
3. Files that are part of the deployed artifact (alert rules, policy documents).

Nothing here reads a variable the application ignores, and
``tests/compliance/test_controls_real_state.py`` enforces that mechanically.

WHY raw psycopg AND NOT THE APP POOL
------------------------------------
Controls run inside request handlers and from the CLI. Taking a connection from
the application's async pool from inside an evaluator would deadlock a worker
under load, so these use a short-lived synchronous connection with a 3 s connect
timeout. A compliance scan that hangs is a compliance scan nobody runs.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..provenance.evidence import verify_evidence_chain
from .models import EvidenceType

#: Reconciliation only. Not a fallback: if this is unset, controls report that
#: they cannot see a database instead of guessing at one.
DSN_ENV = "DCC_DATABASE_URL"

_SCHEMA = "dcc"
_CONNECT_TIMEOUT = 3

#: Event types that constitute evidence of *access* being exercised: the raw
#: material an access review (SOC 2 CC6.3) is performed from. Matched as
#: substrings, case-insensitively, against ``event_type``.
ACCESS_EVENT_HINTS = (
    "auth",
    "access",
    "login",
    "logon",
    "signin",
    "session",
    "key",
    "token",
    "permission",
    "grant",
    "revoke",
    "role",
    "mfa",
    "privilege",
)

_TLS_REQUIRED_MODES = {"require", "verify-ca", "verify-full"}


class ObserverUnavailable(RuntimeError):
    """A measurement could not be performed at all.

    Distinct from "the fact is false": it means there was nothing to look at --
    no DSN, no reachable server, no file. Controls turn this into NOT_ASSESSED.
    """


@dataclass(frozen=True)
class Measurement:
    """One observation, ready to become a finding.

    Attributes
    ----------
    verdict:
        ``True`` the fact holds; ``False`` it is violated; ``None`` unmeasurable.
    statement:
        What was measured, in plain language, including the numbers behind the
        verdict so the finding is auditable without re-running the query.
    source:
        Where the observation came from, for the evidence record.
    evidence_type:
        Category, matching :class:`EvidenceType`.
    detail:
        Structured detail for the evidence payload.
    remediation:
        What an operator would change to move the verdict, when there is one.
    """

    verdict: bool | None
    statement: str
    source: str
    evidence_type: EvidenceType = EvidenceType.DATABASE
    detail: Mapping[str, Any] = field(default_factory=dict)
    remediation: str = ""

    @property
    def assessed(self) -> bool:
        return self.verdict is not None


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------


def database_url() -> str:
    """The DSN the served application is configured to use.

    ``DCC_DATABASE_URL`` is read by ``api_async`` at startup, so it is the one
    address whose state the application actually depends on.
    """
    return (os.environ.get(DSN_ENV) or "").strip()


def require_dsn() -> str:
    dsn = database_url()
    if not dsn:
        raise ObserverUnavailable(
            f"{DSN_ENV} is not set, so there is no database to inspect (the served "
            "application has the same problem: it answers 503 until a DSN is configured)"
        )
    return dsn


def db_rows(
    sql: str,
    params: Sequence[Any] = (),
    *,
    dsn: str | None = None,
) -> list[dict[str, Any]]:
    """Run a read-only query and return rows as dicts.

    Raises
    ------
    ObserverUnavailable
        When there is no DSN, psycopg is missing, the server is unreachable, or
        the query fails. Never swallowed: a control that cannot look must say so.
    """
    dsn = dsn or require_dsn()
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - psycopg is a declared dep
        raise ObserverUnavailable(f"psycopg is not installed: {exc}") from exc

    try:
        with psycopg.connect(dsn, connect_timeout=_CONNECT_TIMEOUT) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                if cur.description is None:
                    return []
                columns = [d.name for d in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except ObserverUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - any driver error means "cannot look"
        raise ObserverUnavailable(f"database unreachable or query failed: {exc}") from exc


def db_columns(table: str) -> set[str]:
    """Column names of ``dcc.<table>``, or empty when the table does not exist."""
    rows = db_rows(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (_SCHEMA, table),
    )
    return {str(r["column_name"]) for r in rows}


def tenant_ids() -> list[str]:
    rows = db_rows(f"SELECT id::text AS id FROM {_SCHEMA}.tenants ORDER BY created_at")
    return [str(r["id"]) for r in rows]


def _unavailable(what: str, exc: ObserverUnavailable) -> Measurement:
    return Measurement(
        verdict=None,
        statement=f"{what} could not be measured: {exc}",
        source="postgres",
        detail={"error": str(exc)},
    )


# ---------------------------------------------------------------------------
# Row-level security: who can see which tenant's rows
# ---------------------------------------------------------------------------


def measure_tenant_rls() -> Measurement:
    """Every tenant-scoped table in ``dcc`` must have RLS enabled AND forced.

    ``ENABLE`` alone exempts the table owner, and the owner is the role the
    application usually connects as, so a table with ``ENABLE`` and no ``FORCE``
    filters nobody in practice. Both, plus at least one policy, is the bar.

    This is measurable from ``pg_class``/``pg_policy`` and it changes the moment
    somebody runs ``ALTER TABLE ... DISABLE ROW LEVEL SECURITY`` -- which is why
    it is a real control and not a configuration claim.
    """
    sql = """
        SELECT c.relname                                   AS table_name,
               c.relkind::text                             AS kind,
               c.relrowsecurity                            AS rls_enabled,
               c.relforcerowsecurity                       AS rls_forced,
               (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s
           AND c.relkind IN ('r', 'p')
           AND EXISTS (
                 SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema = %s
                    AND col.table_name = c.relname
                    AND col.column_name = 'tenant_id')
         ORDER BY c.relname
    """
    try:
        rows = db_rows(sql, (_SCHEMA, _SCHEMA))
    except ObserverUnavailable as exc:
        return _unavailable("row-level security coverage", exc)

    if not rows:
        return Measurement(
            verdict=False,
            statement=(
                "No tenant-scoped tables were found in the dcc schema: tenant isolation "
                "cannot be enforced by the database at all"
            ),
            source=f"pg_class (schema {_SCHEMA})",
            detail={"tables": []},
            remediation="Apply database/schema.sql so tenant tables exist with tenant_scope policies",
        )

    gaps = [
        {
            "table": r["table_name"],
            "rls_enabled": bool(r["rls_enabled"]),
            "rls_forced": bool(r["rls_forced"]),
            "policies": int(r["policies"]),
        }
        for r in rows
        if not (r["rls_enabled"] and r["rls_forced"] and int(r["policies"]) > 0)
    ]

    if gaps:
        names = ", ".join(g["table"] for g in gaps[:8])
        more = "" if len(gaps) <= 8 else f" (+{len(gaps) - 8} more)"
        return Measurement(
            verdict=False,
            statement=(
                f"{len(gaps)} of {len(rows)} tenant-scoped table(s) do not enforce row-level "
                f"security with FORCE and a policy: {names}{more}. A tenant-scoped query "
                "against these tables is not filtered by the database."
            ),
            source=f"pg_class / pg_policy (schema {_SCHEMA})",
            detail={"tables_checked": len(rows), "gaps": gaps},
            remediation=(
                "ALTER TABLE dcc.<table> ENABLE ROW LEVEL SECURITY; "
                "ALTER TABLE dcc.<table> FORCE ROW LEVEL SECURITY; "
                "CREATE POLICY tenant_scope ON dcc.<table> USING/WITH CHECK (tenant_id = ...)"
            ),
        )

    return Measurement(
        verdict=True,
        statement=(
            f"All {len(rows)} tenant-scoped tables in the database enforce row-level "
            "security (ENABLE + FORCE + a tenant_scope policy)"
        ),
        source=f"pg_class / pg_policy (schema {_SCHEMA})",
        detail={"tables_checked": len(rows), "gaps": []},
    )


# ---------------------------------------------------------------------------
# The audit / evidence trail
# ---------------------------------------------------------------------------


def _evidence_rows(tenant_id: str, limit: int) -> list[dict[str, Any]]:
    """One tenant's evidence chain, read with that tenant's RLS scope applied.

    Reading without the scope would return zero rows on a correctly configured
    database and look like "no logging", so the scope is set explicitly.
    """
    return db_rows(
        "SELECT tenant_id::text AS tenant_id, sequence, id::text AS id, event_type, "
        "       occurred_at, actor_ref, subject_type, subject_id, payload, "
        "       previous_hash, event_hash "
        f"  FROM {_SCHEMA}.evidence_events "
        " WHERE tenant_id = %s::uuid "
        " ORDER BY sequence LIMIT %s",
        (tenant_id, limit),
        dsn=_tenant_scoped_dsn(tenant_id),
    )


def _tenant_scoped_dsn(tenant_id: str) -> str:
    """DSN carrying ``options=-c dcc.tenant_id=<id>`` so RLS scopes the session.

    The GUC is set at connection time rather than with a statement so the read is
    correct even if the connection is reused, and so no statement can run before
    the scope is in place.
    """
    dsn = require_dsn()
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(dsn)
    existing = params.get("options") or ""
    params["options"] = f"{existing} -c dcc.tenant_id={tenant_id}".strip()
    params.setdefault("connect_timeout", str(_CONNECT_TIMEOUT))
    return make_conninfo(**params)


def measure_evidence_chain(max_events: int = 2000) -> Measurement:
    """The audit trail must exist, hold events, and verify end to end.

    Two independent failures are detected per row: the stored ``event_hash`` must
    match a recomputation over the row's own fields (nothing was edited), and
    ``previous_hash`` must match the preceding row's hash (nothing was inserted,
    removed or reordered).
    """
    try:
        tenants = tenant_ids()
    except ObserverUnavailable as exc:
        return _unavailable("evidence chain integrity", exc)

    if not tenants:
        return Measurement(
            verdict=False,
            statement="No tenants exist, so no audit trail can be attributed or verified",
            source=f"{_SCHEMA}.tenants",
            detail={"tenants": 0},
            remediation="Provision a tenant before relying on the audit trail",
        )

    total_events = 0
    invalid: list[dict[str, Any]] = []
    per_tenant: list[dict[str, Any]] = []
    try:
        for tenant_id in tenants:
            rows = _evidence_rows(tenant_id, max_events)
            total_events += len(rows)
            result = verify_evidence_chain(rows) if rows else {
                "chain_valid": True,
                "total_events": 0,
                "invalid_events": 0,
            }
            per_tenant.append(
                {
                    "tenant_id": tenant_id,
                    "events": len(rows),
                    "chain_valid": bool(result["chain_valid"]),
                    "invalid_events": int(result["invalid_events"]),
                    "broken_at": result.get("broken_at"),
                    "reason": result.get("reason"),
                }
            )
            if not result["chain_valid"]:
                invalid.append(per_tenant[-1])
    except ObserverUnavailable as exc:
        return _unavailable("evidence chain integrity", exc)

    if invalid:
        first = invalid[0]
        return Measurement(
            verdict=False,
            statement=(
                f"The audit trail does not verify: {len(invalid)} of {len(tenants)} tenant "
                f"chain(s) are broken. First break at sequence {first['broken_at']} "
                f"({first['reason']}) for tenant {first['tenant_id']} -- rows have been "
                "edited, inserted or removed."
            ),
            source=f"{_SCHEMA}.evidence_events (verified with dcc.provenance.evidence)",
            detail={"per_tenant": per_tenant, "total_events": total_events},
            remediation=(
                "Treat the tampering as an incident; the chain cannot be repaired in place, "
                "so preserve the rows and record an explanation event"
            ),
        )

    if total_events == 0:
        return Measurement(
            verdict=False,
            statement=(
                "The audit trail is empty: no evidence events are recorded for any tenant, "
                "so nothing about system activity can be verified after the fact"
            ),
            source=f"{_SCHEMA}.evidence_events",
            detail={"per_tenant": per_tenant, "total_events": 0},
            remediation="Record operational events through the writers that append to dcc.evidence_events",
        )

    return Measurement(
        verdict=True,
        statement=(
            f"The audit trail holds {total_events} event(s) across {len(tenants)} tenant(s) "
            "and every hash chain verifies (no edited, inserted or reordered rows)"
        ),
        source=f"{_SCHEMA}.evidence_events (verified with dcc.provenance.evidence)",
        detail={"per_tenant": per_tenant, "total_events": total_events},
    )


def measure_event_attribution() -> Measurement:
    """Recorded events must say who acted: an event with no actor is not an audit record.

    ISO 27001 A.12.4.1 asks for event logging that supports later investigation.
    A row with a null ``actor_ref`` records that something happened and not who
    did it, which is the part an investigation needs.
    """
    try:
        tenants = tenant_ids()
    except ObserverUnavailable as exc:
        return _unavailable("event attribution", exc)
    if not tenants:
        return Measurement(
            verdict=False,
            statement="No tenants exist, so no event can be attributed to anyone",
            source=f"{_SCHEMA}.tenants",
            detail={"tenants": 0},
        )

    total = 0
    unattributed = 0
    types: set[str] = set()
    per_tenant: list[dict[str, Any]] = []
    try:
        for tenant_id in tenants:
            rows = db_rows(
                "SELECT count(*) AS total, "
                "       count(*) FILTER (WHERE actor_ref IS NULL OR btrim(actor_ref) = '') AS missing, "
                "       array_remove(array_agg(DISTINCT event_type), NULL) AS event_types "
                f"  FROM {_SCHEMA}.evidence_events WHERE tenant_id = %s::uuid",
                (tenant_id,),
                dsn=_tenant_scoped_dsn(tenant_id),
            )
            row = rows[0] if rows else {"total": 0, "missing": 0, "event_types": []}
            total += int(row["total"] or 0)
            unattributed += int(row["missing"] or 0)
            types.update(str(t) for t in (row["event_types"] or []) if t)
            per_tenant.append(
                {
                    "tenant_id": tenant_id,
                    "events": int(row["total"] or 0),
                    "without_actor": int(row["missing"] or 0),
                }
            )
    except ObserverUnavailable as exc:
        return _unavailable("event attribution", exc)

    detail = {
        "total_events": total,
        "events_without_actor": unattributed,
        "event_types": sorted(types),
        "per_tenant": per_tenant,
    }

    if total == 0:
        return Measurement(
            verdict=False,
            statement="No events are recorded, so there is no event log to attribute",
            source=f"{_SCHEMA}.evidence_events",
            detail=detail,
            remediation="Enable event writes; a log with no rows cannot support an investigation",
        )
    if unattributed:
        return Measurement(
            verdict=False,
            statement=(
                f"{unattributed} of {total} recorded event(s) have no actor_ref: the log "
                "records that something happened but not who did it"
            ),
            source=f"{_SCHEMA}.evidence_events",
            detail=detail,
            remediation="Populate actor_ref on every event write path",
        )
    return Measurement(
        verdict=True,
        statement=(
            f"All {total} recorded event(s) carry an actor_ref across "
            f"{len(types)} event type(s)"
        ),
        source=f"{_SCHEMA}.evidence_events",
        detail=detail,
    )


def measure_access_events(window_days: int = 3650) -> Measurement:
    """Are access decisions themselves being recorded?

    An access review needs records of who authenticated and what they were
    allowed to do. A chain that only contains data fixtures cannot support a
    review no matter how well it verifies.
    """
    try:
        tenants = tenant_ids()
    except ObserverUnavailable as exc:
        return _unavailable("access event coverage", exc)
    if not tenants:
        return Measurement(
            verdict=None,
            statement=(
                "Access review evidence cannot be measured: no tenants exist, so there is no "
                "access to review"
            ),
            source=f"{_SCHEMA}.tenants",
            detail={"tenants": 0},
        )

    clauses = " OR ".join(["event_type ILIKE %s"] * len(ACCESS_EVENT_HINTS))
    params_base = [f"%{hint}%" for hint in ACCESS_EVENT_HINTS]
    total = 0
    access_like = 0
    samples: list[str] = []
    per_tenant: list[dict[str, Any]] = []
    sql = (
        "SELECT count(*) AS total, "
        f"       count(*) FILTER (WHERE {clauses}) AS access_events, "
        "       array_remove(array_agg(DISTINCT event_type), NULL) AS event_types "
        f"  FROM {_SCHEMA}.evidence_events "
        f" WHERE tenant_id = %s::uuid "
        "   AND occurred_at > now() - (%s || ' days')::interval"
    )
    try:
        for tenant_id in tenants:
            rows = db_rows(
                sql,
                [*params_base, tenant_id, str(window_days)],
                dsn=_tenant_scoped_dsn(tenant_id),
            )
            row = rows[0] if rows else {"total": 0, "access_events": 0, "event_types": []}
            total += int(row["total"] or 0)
            access_like += int(row["access_events"] or 0)
            samples.extend(str(t) for t in (row["event_types"] or []) if t)
            per_tenant.append(
                {
                    "tenant_id": tenant_id,
                    "events": int(row["total"] or 0),
                    "access_events": int(row["access_events"] or 0),
                }
            )
    except ObserverUnavailable as exc:
        return _unavailable("access event coverage", exc)

    detail = {
        "window_days": window_days,
        "total_events": total,
        "access_events": access_like,
        "event_types": sorted(set(samples)),
        "matched_on": list(ACCESS_EVENT_HINTS),
        "per_tenant": per_tenant,
    }

    if total == 0:
        return Measurement(
            verdict=None,
            statement=(
                "No events are recorded at all, so access review evidence cannot be "
                "distinguished from a logging outage"
            ),
            source=f"{_SCHEMA}.evidence_events",
            detail=detail,
        )
    if access_like == 0:
        return Measurement(
            verdict=False,
            statement=(
                f"None of the {total} recorded event(s) are access, authentication or "
                f"permission events (recorded types: {', '.join(sorted(set(samples))) or 'none'}). "
                "An access review has nothing to review."
            ),
            source=f"{_SCHEMA}.evidence_events",
            detail=detail,
            remediation=(
                "Record authentication and authorisation decisions as events "
                "(e.g. auth.key.used, authz.denied) so periodic access review has evidence"
            ),
        )
    return Measurement(
        verdict=True,
        statement=(
            f"{access_like} of {total} recorded event(s) are access, authentication or "
            "permission events, which is the evidence a periodic access review reads"
        ),
        source=f"{_SCHEMA}.evidence_events",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Incident response
# ---------------------------------------------------------------------------

_INCIDENT_LIFECYCLE = ("opened_at", "detected_at", "mitigated_at", "resolved_at")


def measure_incident_lifecycle() -> Measurement:
    """Does the system record an incident from detection to resolution?

    An incident response process that leaves no record cannot be shown to have
    operated. The measurable part is whether incident records exist and can hold
    the full timeline; whether people followed the process is not observable.
    """
    try:
        columns = db_columns("incidents")
    except ObserverUnavailable as exc:
        return _unavailable("incident records", exc)

    if not columns:
        return Measurement(
            verdict=False,
            statement="There is no dcc.incidents table: an incident leaves no record at all",
            source=f"{_SCHEMA}.incidents",
            detail={"columns": []},
            remediation="Apply database/schema.sql so incidents are recorded",
        )

    missing = [c for c in (*_INCIDENT_LIFECYCLE, "incident_commander") if c not in columns]
    rows = db_rows(
        "SELECT count(*) AS total, "
        "       count(*) FILTER (WHERE incident_commander IS NULL OR btrim(incident_commander) = '') AS no_commander"
        f"  FROM {_SCHEMA}.incidents"
    )
    row = rows[0] if rows else {"total": 0, "no_commander": 0}
    detail = {
        "columns": sorted(columns),
        "missing_timeline_columns": missing,
        "incidents": int(row["total"] or 0),
        "incidents_without_commander": int(row["no_commander"] or 0),
    }

    if missing:
        return Measurement(
            verdict=False,
            statement=(
                "Incident records cannot capture an incident timeline: "
                f"{', '.join(missing)} missing from dcc.incidents"
            ),
            source=f"{_SCHEMA}.incidents",
            detail=detail,
            remediation="Add the timeline columns so detection, mitigation and resolution are recorded",
        )

    return Measurement(
        verdict=True,
        statement=(
            f"Incident records exist with a full detection-to-resolution timeline "
            f"({int(row['total'] or 0)} incident(s) on record, "
            f"{int(row['no_commander'] or 0)} without a named commander)"
        ),
        source=f"{_SCHEMA}.incidents",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Credentials: what the application actually loads and enforces
# ---------------------------------------------------------------------------


def api_key_entries() -> list[dict[str, Any]]:
    """Parse ``DCC_API_KEYS`` the way ``api_async._bootstrap_api_keys`` parses it.

    The application reads this variable at startup and refuses to start on a
    malformed entry, so this is configuration the system really consumes -- not
    a knob it ignores. Malformed entries are reported, not raised, so a control
    can describe the defect rather than error out.
    """
    raw = (os.environ.get("DCC_API_KEYS") or "").strip()
    entries: list[dict[str, Any]] = []
    if not raw:
        return entries
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        tenant_id, _, key_hash = chunk.partition(":")
        tenant_id, key_hash = tenant_id.strip(), key_hash.strip()
        entries.append(
            {
                "tenant_id": tenant_id,
                "key_hash": key_hash,
                "hash_length": len(key_hash),
                "is_sha256_hex": bool(re.fullmatch(r"[0-9a-fA-F]{64}", key_hash)),
                "tenant_is_uuid": bool(
                    re.fullmatch(
                        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                        tenant_id,
                    )
                ),
            }
        )
    return entries


def live_key_store() -> Any | None:
    """The running application's key store, if this process is that application.

    ``dcc.api_async`` is imported lazily by design, so it is present in
    ``sys.modules`` only when a server or test has actually loaded it. When it is
    absent the control falls back to what the loader is configured with, and says
    so -- it never invents a store.
    """
    module = sys.modules.get("dcc.api_async")
    if module is None:
        return None
    return getattr(module, "_API_KEYS", None)


def measure_credential_expiry(store: Any | None = None) -> Measurement:
    """Are credentials able to expire, so access stops when it is no longer needed?

    Judged from the key store when this process holds one, otherwise from the
    only credential source the served application has: ``DCC_API_KEYS``, whose
    format carries no expiry and whose loader registers every entry with
    ``expires_at=None``. Either way the answer is measured, not declared.
    """
    store = store if store is not None else live_key_store()

    if store is not None:
        try:
            keys = list(store.list_keys())
        except Exception as exc:  # noqa: BLE001 - a store that cannot be listed is a finding
            return Measurement(
                verdict=None,
                statement=f"The live key store could not be listed: {exc}",
                source="dcc.api_async._API_KEYS",
                detail={"error": str(exc)},
            )
        if not keys:
            return Measurement(
                verdict=None,
                statement=(
                    "Credential expiry cannot be judged: the live key store is empty, so "
                    "there is no credential lifecycle to assess"
                ),
                source="dcc.api_async._API_KEYS",
                detail={"keys": 0},
            )
        permanent = [k for k in keys if getattr(k, "expires_at", None) is None and not getattr(k, "revoked", False)]
        detail = {
            "source": "live_key_store",
            "keys": len(keys),
            "without_expiry": len(permanent),
            "expiring": len(keys) - len(permanent),
        }
        if permanent:
            return Measurement(
                verdict=False,
                statement=(
                    f"{len(permanent)} of {len(keys)} active credential(s) in the running key "
                    "store have no expiry: access continues until someone removes it by hand"
                ),
                source="dcc.api_async._API_KEYS",
                detail=detail,
                remediation="Register credentials with an expires_at and rotate on a schedule",
            )
        return Measurement(
            verdict=True,
            statement=f"All {len(keys)} active credential(s) carry an expiry",
            source="dcc.api_async._API_KEYS",
            detail=detail,
        )

    entries = api_key_entries()
    detail = {
        "source": "DCC_API_KEYS",
        "keys": len(entries),
        "without_expiry": len(entries),
        "expiring": 0,
    }
    if not entries:
        return Measurement(
            verdict=None,
            statement=(
                "No credentials are configured and no live key store is loaded in this "
                "process, so credential expiry cannot be judged"
            ),
            source="DCC_API_KEYS",
            detail=detail,
        )
    return Measurement(
        verdict=False,
        statement=(
            f"All {len(entries)} configured credential(s) never expire: DCC_API_KEYS entries "
            "carry no expiry and the loader registers them with expires_at=None, so removing "
            "access requires editing the environment and restarting"
        ),
        source="DCC_API_KEYS",
        detail=detail,
        remediation="Extend the key loader to accept an expiry, and rotate credentials periodically",
    )


def measure_credential_strength() -> Measurement:
    """Credentials in use must be strong, hashed secrets -- not passwords in the clear.

    PCI DSS 8.2 asks for adequate authentication for every user. The deployment
    authenticates with bearer keys, so the measurable requirement is that each
    configured credential is a high-entropy secret stored as a SHA-256 digest.
    """
    entries = api_key_entries()
    if not entries:
        return Measurement(
            verdict=False,
            statement=(
                "No credentials are configured: no user can authenticate, so the "
                "authentication requirement is not met by this deployment"
            ),
            source="DCC_API_KEYS",
            detail={"keys": 0},
            remediation="Mint a key with 'python -m dcc.keys_cli create' and set DCC_API_KEYS",
        )

    weak = [e for e in entries if not e["is_sha256_hex"]]
    detail = {
        "keys": len(entries),
        "sha256_hashes": len(entries) - len(weak),
        "weak_entries": [
            {"tenant_id": e["tenant_id"], "hash_length": e["hash_length"]} for e in weak
        ],
        "entropy_bits": 256,
    }
    if weak:
        return Measurement(
            verdict=False,
            statement=(
                f"{len(weak)} of {len(entries)} credential entries are not a SHA-256 digest "
                "(a plaintext or truncated secret stored where a hash belongs)"
            ),
            source="DCC_API_KEYS",
            detail=detail,
            remediation="Store only 'tenant_id:sha256hex' pairs; never a plaintext or truncated key",
        )
    return Measurement(
        verdict=True,
        statement=(
            f"All {len(entries)} credential(s) are 256-bit random keys stored as SHA-256 "
            "digests; no password authentication exists in this deployment"
        ),
        source="DCC_API_KEYS",
        detail=detail,
    )


def measure_identity_uniqueness() -> Measurement:
    """Every credential must identify exactly one principal, and that principal must exist.

    Unique user identification (HIPAA 164.312(a)(1)) is only satisfied if a
    credential cannot be shared between principals and a deleted tenant's
    credential stops working. Both are checkable.
    """
    entries = api_key_entries()
    if not entries:
        return Measurement(
            verdict=None,
            statement=(
                "Unique user identification cannot be measured: no credentials are configured, "
                "so there is no principal to identify"
            ),
            source="DCC_API_KEYS",
            detail={"keys": 0},
        )

    seen: dict[str, int] = {}
    for e in entries:
        seen[e["key_hash"]] = seen.get(e["key_hash"], 0) + 1
    duplicates = sorted(h for h, n in seen.items() if n > 1)
    malformed = [e for e in entries if not e["tenant_is_uuid"]]

    try:
        known = set(tenant_ids())
    except ObserverUnavailable as exc:
        return _unavailable("credential-to-tenant mapping", exc)

    unknown = sorted({e["tenant_id"] for e in entries} - known)
    detail = {
        "keys": len(entries),
        "distinct_hashes": len(seen),
        "duplicate_hashes": [h[:12] + "..." for h in duplicates],
        "malformed_tenant_ids": [e["tenant_id"] for e in malformed],
        "tenants_in_database": len(known),
        "unknown_tenant_ids": unknown,
    }

    if duplicates:
        return Measurement(
            verdict=False,
            statement=(
                f"{len(duplicates)} credential hash(es) are configured more than once: two "
                "principals share an identifier, and removing one removes both"
            ),
            source="DCC_API_KEYS",
            detail=detail,
            remediation="Issue a distinct key per principal",
        )
    if malformed:
        return Measurement(
            verdict=False,
            statement=(
                f"{len(malformed)} credential entr(ies) carry a tenant id that is not a UUID: "
                "the credential cannot be attributed to a principal"
            ),
            source="DCC_API_KEYS",
            detail=detail,
            remediation="Use the tenant UUID printed by keys_cli as the key's tenant",
        )
    if unknown:
        return Measurement(
            verdict=False,
            statement=(
                f"{len(unknown)} credential(s) point at tenant ids that do not exist in "
                "dcc.tenants: the identifier resolves to nobody"
            ),
            source="DCC_API_KEYS + dcc.tenants",
            detail=detail,
            remediation="Re-issue keys against existing tenants, or provision the tenant",
        )
    return Measurement(
        verdict=True,
        statement=(
            f"{len(entries)} credential(s) resolve to {len({e['tenant_id'] for e in entries})} "
            "distinct existing tenant(s) with no shared hashes"
        ),
        source="DCC_API_KEYS + dcc.tenants",
        detail=detail,
    )


def measure_account_register() -> Measurement:
    """Do credentialed principals exist as accounts with a lifecycle status?

    ``dcc.tenants`` is the account register: it carries a status
    (active/suspended/archived) and a creation time. A credential whose tenant is
    suspended must not be counted as an active account, because suspension is the
    mechanism by which access is withdrawn.
    """
    entries = api_key_entries()
    if not entries:
        return Measurement(
            verdict=None,
            statement=(
                "Account management cannot be measured: no credentials are configured, so no "
                "account is registered to manage"
            ),
            source="DCC_API_KEYS",
            detail={"keys": 0},
        )

    wanted = sorted({e["tenant_id"] for e in entries})
    try:
        rows = db_rows(
            "SELECT id::text AS id, slug, status, created_at "
            f"  FROM {_SCHEMA}.tenants WHERE id::text = ANY(%s)",
            (wanted,),
        )
    except ObserverUnavailable as exc:
        return _unavailable("account register", exc)

    by_id = {str(r["id"]): r for r in rows}
    missing = [t for t in wanted if t not in by_id]
    inactive = [
        {"tenant_id": tid, "status": by_id[tid]["status"]}
        for tid in wanted
        if tid in by_id and str(by_id[tid]["status"]) != "active"
    ]
    detail = {
        "accounts": len(wanted),
        "found": len(by_id),
        "missing": missing,
        "not_active": inactive,
        "statuses": {tid: by_id[tid]["status"] for tid in by_id},
    }

    if missing:
        return Measurement(
            verdict=False,
            statement=(
                f"{len(missing)} credential(s) have no account record in dcc.tenants: there is "
                "nothing to review, suspend or delete"
            ),
            source="DCC_API_KEYS + dcc.tenants",
            detail=detail,
            remediation="Register the tenant before issuing its credential",
        )
    if inactive:
        return Measurement(
            verdict=False,
            statement=(
                f"{len(inactive)} credential(s) belong to a tenant that is not active "
                f"({', '.join(sorted({i['status'] for i in inactive}))}): a suspended account still "
                "holds a usable key"
            ),
            source="DCC_API_KEYS + dcc.tenants",
            detail=detail,
            remediation="Refuse credentials for suspended or archived tenants in the auth middleware",
        )
    return Measurement(
        verdict=True,
        statement=(
            f"All {len(wanted)} credentialed principal(s) exist in dcc.tenants with status "
            "'active', so access can be withdrawn by changing account state"
        ),
        source="DCC_API_KEYS + dcc.tenants",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Encryption in transit
# ---------------------------------------------------------------------------


def dsn_tls_mode(dsn: str | None = None) -> str:
    """The ``sslmode`` the application's DSN asks for (psycopg's default is prefer)."""
    dsn = dsn if dsn is not None else database_url()
    if not dsn:
        return ""
    try:
        from psycopg.conninfo import conninfo_to_dict

        return str(conninfo_to_dict(dsn).get("sslmode") or "prefer").lower()
    except Exception:  # noqa: BLE001 - an unparseable DSN is itself the finding
        return ""


def tls_verdict(*, mode: str, sessions: int, encrypted: int) -> tuple[bool | None, str]:
    """Pure decision over observed TLS facts. Split out so the rule can be tested.

    A pass needs both halves: the DSN must refuse plaintext (otherwise the client
    silently falls back), and every session actually observed must be encrypted.
    """
    if mode not in _TLS_REQUIRED_MODES:
        return (
            False,
            f"sslmode={mode or 'unset (prefer)'} permits a plaintext connection: the client "
            "will fall back to cleartext rather than refuse",
        )
    if sessions and encrypted < sessions:
        return (
            False,
            f"{sessions - encrypted} of {sessions} live database session(s) are unencrypted "
            f"even though sslmode={mode} was requested",
        )
    if not sessions:
        return (
            None,
            f"sslmode={mode} requires TLS but no live database session could be observed to confirm it",
        )
    return (True, f"sslmode={mode} and all {sessions} live database session(s) are encrypted")


def measure_db_tls() -> Measurement:
    """Is the database link -- where tenant data actually lives -- encrypted?

    ``pg_stat_ssl`` reports the transport of live sessions, so this is measured
    from the server, not declared. The client leg (browser to the API) terminates
    outside this process and is deliberately not claimed here.
    """
    mode = dsn_tls_mode()
    try:
        rows = db_rows(
            "SELECT count(*) AS sessions, count(*) FILTER (WHERE s.ssl) AS encrypted "
            "  FROM pg_stat_ssl s JOIN pg_stat_activity a USING (pid) "
            " WHERE a.datname = current_database() AND a.pid <> pg_backend_pid()"
        )
    except ObserverUnavailable as exc:
        if not mode:
            return _unavailable("database transport encryption", exc)
        verdict, statement = tls_verdict(mode=mode, sessions=0, encrypted=0)
        return Measurement(
            verdict=verdict,
            statement=statement,
            source="psycopg conninfo (sslmode) + pg_stat_ssl",
            detail={"sslmode": mode, "error": str(exc)},
        )

    row = rows[0] if rows else {"sessions": 0, "encrypted": 0}
    sessions = int(row["sessions"] or 0)
    encrypted = int(row["encrypted"] or 0)
    verdict, statement = tls_verdict(mode=mode, sessions=sessions, encrypted=encrypted)
    return Measurement(
        verdict=verdict,
        statement=statement,
        source="pg_stat_ssl + psycopg conninfo (sslmode)",
        detail={"sslmode": mode, "sessions": sessions, "encrypted": encrypted},
        remediation=(
            "Configure the server with a certificate and set sslmode=require or "
            "verify-full on DCC_DATABASE_URL"
        )
        if verdict is False
        else "",
    )


# ---------------------------------------------------------------------------
# Encryption at rest
# ---------------------------------------------------------------------------


def measure_at_rest_encryption() -> Measurement:
    """Can at-rest encryption be observed from here?

    It cannot. Whether the Postgres data directory sits on an encrypted volume is
    a property of the storage layer; nothing in SQL or in this process reports it.
    Field-level encryption exists in ``dcc.security.encryption`` but no write path
    calls it, so no stored value can be shown to be ciphertext either. Reporting
    a pass here would mean reporting on a disk nobody can see.
    """
    wired = _field_encryption_call_sites()
    try:
        db_rows("SELECT 1")
        reachable = True
    except ObserverUnavailable:
        reachable = False

    return Measurement(
        verdict=None,
        statement=(
            "Encryption at rest cannot be observed from the application: it is a property of "
            "the storage volume under the Postgres data directory, which no query or process "
            f"inspection reports. Field-level encryption is implemented but has {wired} call "
            "site(s) outside its own module, so no column is shown to be ciphertext. This "
            "requires storage-layer evidence (volume encryption, tablespace, or a ciphertext "
            "column inventory) that does not exist yet."
        ),
        source="postgres (no observable) + dcc.security.encryption (call-site scan)",
        evidence_type=EvidenceType.CONFIG,
        detail={"database_reachable": reachable, "field_encryption_call_sites": wired},
    )


def _field_encryption_call_sites() -> int:
    """Count uses of the field encryptor outside its defining module and package exports."""
    src = Path(__file__).resolve().parents[1]
    pattern = re.compile(r"\b(create_default_field_encryptor|FieldEncryptor)\s*\(")
    count = 0
    for path in src.rglob("*.py"):
        if path.name in {"encryption.py", "__init__.py"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        count += len(pattern.findall(text))
    return count


# ---------------------------------------------------------------------------
# Monitoring: do the alert rules reference metrics that exist?
# ---------------------------------------------------------------------------

_MONITORING_ROOTS = (
    Path(__file__).resolve().parents[3] / "monitoring" / "prometheus",
    Path(__file__).resolve().parents[3] / "monitoring" / "iac" / "prometheus",
)

#: Metric namespaces this repository is responsible for producing. A rule over
#: ``node_*`` or ``kube_*`` depends on node-exporter or kube-state-metrics, which
#: are not part of this deployment's scrape configuration; holding this control
#: responsible for them would be measuring someone else's system.
_OWNED_METRIC_PREFIXES = ("dcc_", "api_", "iac_")

#: PromQL keywords/functions/labels that are not metric names.
_PROMQL_NOISE = {
    "sum", "rate", "by", "without", "avg", "max", "min", "count", "increase",
    "histogram_quantile", "le", "on", "ignoring", "group_left", "group_right",
    "up", "and", "or", "unless", "bool", "clamp_max", "clamp_min",
    "avg_over_time", "max_over_time", "min_over_time", "topk", "bottomk",
    "job", "instance", "route", "status", "severity", "namespace", "pod",
    "absent", "scalar", "vector", "time", "delta", "irate", "deriv",
    "label_replace", "offset", "container", "reason", "mode", "fstype",
}

_LABEL_BLOCK = re.compile(r"\{[^}]*\}")
_CALL_OR_IDENT = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")


def _parse_alert_rules(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read Prometheus rule files. Returns (rules, parse_errors)."""
    import yaml

    rules: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - a rule file that will not load is a finding
            errors.append(f"{path}: {exc}")
            continue
        if not isinstance(data, dict):
            continue
        for group in data.get("groups") or []:
            for rule in (group or {}).get("rules") or []:
                if isinstance(rule, dict) and rule.get("alert"):
                    rules.append(
                        {
                            "alert": str(rule["alert"]),
                            "expr": str(rule.get("expr", "")),
                            "file": str(path),
                        }
                    )
    return rules, errors


def _rule_metrics(expr: str) -> set[str]:
    """Metric names referenced by an expression.

    Label selectors are removed first, then every identifier that is not followed
    by ``(`` is a candidate -- function names and keywords are filtered out, so
    what remains is a series name.
    """
    stripped = _LABEL_BLOCK.sub(" ", expr)
    names: set[str] = set()
    for match in _CALL_OR_IDENT.finditer(stripped):
        name = match.group(1)
        if name in _PROMQL_NOISE or name.isdigit():
            continue
        if stripped[match.end():].lstrip().startswith("("):
            continue
        names.add(name)
    return names


def _exported_metrics() -> set[str]:
    """Metric names this repository's processes actually publish.

    Built from the code that produces exposition: the Prometheus exporters, the
    application metrics module, and the metric names ``api_async`` records. ``up``
    is added because Prometheus synthesises it for every scrape target.
    """
    repo = Path(__file__).resolve().parents[3]
    sources = [
        repo / "monitoring" / "exporter",
        repo / "monitoring" / "iac" / "exporter",
        repo / "src" / "dcc" / "observability",
        repo / "src" / "dcc" / "api_async.py",
    ]
    literal = re.compile(r"[\"']([a-z][a-z0-9_]{2,})[\"']")
    names: set[str] = {"up"}
    for source in sources:
        paths = [source] if source.is_file() else sorted(source.rglob("*.py"))
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            names.update(literal.findall(text))
    return names


def measure_alert_coverage(root: Path | None = None) -> Measurement:
    """Alerting must reference metrics something exports, or it can never fire.

    An alert rule is not monitoring. ``expr: dcc_thing_errors_total > 0`` is inert
    if nothing publishes ``dcc_thing_errors_total``; the dashboard stays green and
    the pager stays silent, which is the worst combination.

    Scoped to the rule sets that monitor this application (``monitoring/prometheus``
    and the IaC pipeline's rules). Rules over third-party series such as ``node_*``
    or ``kube_*`` are counted but not judged: those depend on exporters this
    deployment does not run, and are not this control's subject.
    """
    roots = (root,) if root is not None else _MONITORING_ROOTS

    rules: list[dict[str, Any]] = []
    errors: list[str] = []
    for base in roots:
        if not base.exists():
            errors.append(f"{base}: no such directory")
            continue
        found, parse_errors = _parse_alert_rules(base)
        rules.extend(found)
        errors.extend(parse_errors)

    if errors and not rules:
        return Measurement(
            verdict=False,
            statement=(
                "No usable alert rule files were found ("
                + "; ".join(errors[:3])
                + "): this deployment ships no alerting for its own metrics"
            ),
            source=", ".join(str(r) for r in roots),
            evidence_type=EvidenceType.FILE,
            detail={"roots": [str(r) for r in roots], "errors": errors},
            remediation="Deploy alert rules for availability, error rate and latency",
        )
    if not rules:
        return Measurement(
            verdict=False,
            statement="No alert rules are defined for this application's metrics",
            source=", ".join(str(r) for r in roots),
            evidence_type=EvidenceType.FILE,
            detail={"rules": 0},
            remediation="Define alert rules for availability, error rate and latency",
        )

    exported = _exported_metrics()
    in_scope = 0
    out_of_scope: list[str] = []
    unbacked: list[dict[str, Any]] = []
    for rule in rules:
        owned = {
            name
            for name in _rule_metrics(rule["expr"])
            if name.startswith(_OWNED_METRIC_PREFIXES)
        }
        if not owned:
            out_of_scope.append(rule["alert"])
            continue
        in_scope += 1
        missing = sorted(owned - exported)
        if missing:
            unbacked.append({"alert": rule["alert"], "missing_metrics": missing})

    detail = {
        "rules": len(rules),
        "rules_in_scope": in_scope,
        "rules_out_of_scope": sorted(out_of_scope),
        "unbacked": unbacked,
        "exported_metrics": sorted(m for m in exported if m.startswith(_OWNED_METRIC_PREFIXES)),
        "roots": [str(r) for r in roots],
    }

    if in_scope == 0:
        return Measurement(
            verdict=None,
            statement=(
                f"{len(rules)} alert rule(s) exist but none reference a metric this "
                "repository produces, so coverage of this service cannot be judged"
            ),
            source=", ".join(str(r) for r in roots),
            evidence_type=EvidenceType.FILE,
            detail=detail,
        )
    if unbacked:
        names = ", ".join(u["alert"] for u in unbacked[:6])
        metrics = sorted({m for u in unbacked for m in u["missing_metrics"]})
        return Measurement(
            verdict=False,
            statement=(
                f"{len(unbacked)} of {in_scope} alert rule(s) for this service reference "
                f"metrics nothing exports ({', '.join(metrics[:6])}), so they can never "
                f"fire: {names}"
            ),
            source=", ".join(str(r) for r in roots),
            evidence_type=EvidenceType.FILE,
            detail=detail,
            remediation=(
                "Point the rules at the series the exporter actually publishes, or add the "
                "missing metric; a rule over a series that does not exist is permanently silent"
            ),
        )
    return Measurement(
        verdict=True,
        statement=(
            f"All {in_scope} alert rule(s) covering this service reference metrics that are "
            f"exported ({len(out_of_scope)} rule(s) over third-party series were not judged)"
        ),
        source=", ".join(str(r) for r in roots),
        evidence_type=EvidenceType.FILE,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Documents: measurable only as artefacts, never as adequacy
# ---------------------------------------------------------------------------

_POLICY_DOCUMENTS = (
    "docs/SECURITY_AND_GOVERNANCE.md",
    "docs/PURPLE_TEAM_READINESS.md",
    "SECURITY.md",
)


def policy_document_state() -> dict[str, Any]:
    """Which governance documents exist in the deployed artefact."""
    repo = Path(__file__).resolve().parents[3]
    found = []
    for rel in _POLICY_DOCUMENTS:
        path = repo / rel
        found.append(
            {
                "path": rel,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return {"repository_root": str(repo), "documents": found}


def measure_policy_document(what: str) -> Measurement:
    """Presence of a document, and nothing more.

    A file existing proves a document exists. It does not prove a security
    requirements analysis was performed or an audit policy is followed -- those
    are review judgements. The measurement says so and hands the auditor the path.
    """
    state = policy_document_state()
    present = [d for d in state["documents"] if d["exists"] and d["bytes"] > 0]
    listing = ", ".join(d["path"] for d in present) or "none"
    return Measurement(
        verdict=None,
        statement=(
            f"{what} is a document-review judgement, not something the system can be asked "
            f"about. Governance documents present in this artefact: {listing}. Presence is "
            "reported; adequacy is not asserted."
        ),
        source="repository documents",
        evidence_type=EvidenceType.FILE,
        detail=state,
    )


# ---------------------------------------------------------------------------
# Network segmentation
# ---------------------------------------------------------------------------


def measure_network_segmentation() -> Measurement:
    """Can segmentation be observed from inside the application? No.

    Segmentation is a property of the deployed network (subnets, security groups,
    NetworkPolicy). Nothing in the process or the database reports which networks
    the cardholder-data environment can reach. Manifests in the repository are
    declared configuration; whether they are applied is a different system.
    """
    repo = Path(__file__).resolve().parents[3]
    manifests = sorted(p for p in (repo / "security" / "soc" / "network-policies").rglob("*") if p.is_file())
    return Measurement(
        verdict=None,
        statement=(
            "Network segmentation cannot be observed from the application or its database: it "
            "is enforced by network devices the process cannot query. "
            f"{len(manifests)} network-policy manifest(s) are present in the repository as "
            "declared configuration, which is not evidence they are applied."
        ),
        source="no in-process observable",
        evidence_type=EvidenceType.CONFIG,
        detail={
            "declared_manifests": [str(p.relative_to(repo)) for p in manifests],
            "note": "requires network evidence from the deployment platform, not from this service",
        },
    )


# ---------------------------------------------------------------------------
# MFA
# ---------------------------------------------------------------------------


def measure_mfa() -> Measurement:
    """Is a second factor verified anywhere in the authentication path?

    ``dcc.security.authz`` can deny a request when its context carries
    ``mfa_verified``, but no component in the served application ever sets that
    claim and no factor is verified, so there is no MFA state to observe. The
    variable the old control read (``DCC_MFA_ENABLED``) was consulted by nothing.
    """
    return Measurement(
        verdict=None,
        statement=(
            "No MFA state is observable: no factor is verified in the authentication path and "
            "nothing populates the mfa_verified claim that dcc.security.authz can require. "
            "Whether MFA is enforced cannot be measured, and cannot be asserted from "
            "configuration."
        ),
        source="dcc.security.authz (claim) / no factor implementation",
        evidence_type=EvidenceType.CONFIG,
        detail={"mfa_state_source": "absent", "claim": "mfa_verified"},
    )
