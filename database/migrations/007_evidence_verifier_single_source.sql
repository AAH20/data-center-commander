-- ---------------------------------------------------------------------------
-- Remove the database-side evidence verifier.
--
-- Two migrations previously defined dcc.verify_evidence_chain(p_tenant_id uuid)
-- with different hash formulas, using CREATE OR REPLACE, in two files that BOTH
-- carried the number 005. The function that existed in a given database therefore
-- depended on filesystem ordering, and both bodies disagreed with the Python
-- writer and with each other:
--
--   005_performance_indexes.sql       digest(prev || payload::text || occurred_at::text || actor_ref)
--   006_performance_optimization.sql digest(prev || payload::text || occurred_at::text || actor_ref)
--   src/dcc/provenance/evidence.py   sha256(canonical_json(10 fields))
--
-- The payload::text and occurred_at::text renderings are not stable across
-- PostgreSQL versions or server settings, so even the two SQL copies could diverge
-- from each other over time. A verifier that disagrees with the writer reports
-- "invalid" for untouched data, which is worse than having no verifier: it trains
-- operators to ignore the check.
--
-- Verification is CPU-light, runs once per request, and is already implemented in
-- Python by dcc.provenance.evidence.verify_evidence_chain, which the writer and the
-- HTTP route both use. That is now the single implementation.
--
-- If database-side verification is ever genuinely required (very large tenants,
-- rows that never leave the database), it must be written once, derived from the
-- canonical payload definition in that module, and proven byte-identical to it by a
-- test that hashes the same row in both places. Do not reintroduce a hand-written
-- SQL variant without that test.
-- ---------------------------------------------------------------------------

DROP FUNCTION IF EXISTS dcc.verify_evidence_chain(uuid);

COMMENT ON TABLE dcc.evidence_events IS
  'Tamper-evident event log. event_hash is computed over the canonical payload '
  'defined in src/dcc/provenance/evidence.py; verification is performed there.';
