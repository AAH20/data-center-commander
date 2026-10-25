-- ---------------------------------------------------------------------------
-- 012 -- one backup policy, two axes.
--
-- The defect
-- ----------
-- Three layers described a backup policy and no two of them agreed:
--
--   dcc.backup_policies (008)   src/dcc/dr/policies.py       /v2/dr/policies
--   -------------------------   --------------------------   ---------------
--   policy_type:                PolicyType:                  raw row, whatever
--     scheduled|continuous|       full|incremental|            the column held
--     on_demand|snapshot          differential|continuous|
--                                 snapshot
--   compression: none|gzip|     compression: bool            raw row
--     zstd|lz4
--   status: run state           status: lifecycle            raw row
--     pending|running|            active|paused|disabled|
--     succeeded|failed|disabled   archived
--
-- The intersection of the two `policy_type` vocabularies is
-- {continuous, snapshot}: every other value in either layer was rejected by the
-- other. So a policy created as PolicyType.FULL -- the default of
-- BackupPolicy and of create_policy, i.e. the ordinary case -- could not be
-- written to this table at all, and the API returned a `policy_type` that meant
-- "when it runs" while the record it was supposed to describe used the same
-- name for "what it writes".
--
-- The resolution
-- --------------
-- Those are two independent axes, and both are legitimate, so the table gets
-- two columns rather than one column with a union of values:
--
--   backup_type  NEW   full|incremental|differential, or NULL
--                      "what a run writes". Same three values as
--                      dcc.backup_runs.backup_type and as the engine's
--                      BackupType, so a policy and the run it produces
--                      describe the artifact identically. NULL is not
--                      "unknown": it is reserved for continuous and snapshot
--                      policies, which produce no discrete full/incr/diff
--                      backup. The CHECK makes that biconditional, so a NULL
--                      cannot be forgotten and cannot be added to a policy
--                      that has no artifact either.
--
--   policy_type        scheduled|continuous|on_demand|snapshot
--                      "when a run happens". The 008 CHECK already said this
--                      and is left exactly as it was -- it was never wrong,
--                      it was just made to carry a second meaning.
--
-- and the two columns that meant different things under the same name are
-- brought into line with the record:
--
--   compression  bool "compress?" -> none|gzip|zstd|lz4 codec.
--                The column already holds the codec; the dataclass now does
--                too. No bool anywhere: a bool cannot express zstd, and
--                `True` versus the column's default of 'none' disagreed about
--                what the default even is.
--
--   status       pending|running|succeeded|failed|disabled (run state)
--                -> active|paused|disabled|archived (lifecycle).
--                A run's outcome is a fact about a run, and
--                dcc.backup_runs already stores it per run. Keeping run state
--                here meant a policy that had once failed looked "failed"
--                forever and a policy that had never run looked "pending" --
--                neither of which answers "is this policy switched on?".
--
-- Everything below is idempotent: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT
-- IF EXISTS before ADD CONSTRAINT, and UPDATEs whose WHERE clause is empty on a
-- second run. Running it twice is a no-op apart from re-creating the
-- constraints, which is how it is tested.
-- ---------------------------------------------------------------------------

BEGIN;

-- 1. The new axis ------------------------------------------------------------
ALTER TABLE dcc.backup_policies
    ADD COLUMN IF NOT EXISTS backup_type text;

-- Existing rows: the pre-012 table could only describe policies that produced
-- a whole-database dump (every writer was a scheduled or on-demand run of
-- BackupEngine, whose only backup types are full/incremental/differential, and
-- the rows carried no further detail). 'full' is what those rows meant.
-- continuous/snapshot rows keep NULL, which is what the CHECK requires of them.
UPDATE dcc.backup_policies
   SET backup_type = 'full'
 WHERE backup_type IS NULL
   AND policy_type NOT IN ('continuous', 'snapshot');

ALTER TABLE dcc.backup_policies
    ALTER COLUMN backup_type SET DEFAULT 'full';

-- 2. status: run state -> lifecycle -----------------------------------------
ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_status_check;

-- The mapping, stated once:
--   pending / running / succeeded -> active   (the policy is in force; what
--                                              happened on its last run is a
--                                              property of that run)
--   failed                        -> paused   (the safe direction: a policy
--                                              whose only signal was failure
--                                              must not be silently promoted
--                                              to active)
--   disabled                      -> disabled
UPDATE dcc.backup_policies
   SET status = CASE status
                    WHEN 'pending'   THEN 'active'
                    WHEN 'running'   THEN 'active'
                    WHEN 'succeeded' THEN 'active'
                    WHEN 'failed'    THEN 'paused'
                    WHEN 'disabled'  THEN 'disabled'
                    ELSE status
                END
 WHERE status NOT IN ('active', 'paused', 'disabled', 'archived');

ALTER TABLE dcc.backup_policies
    ALTER COLUMN status SET DEFAULT 'active';

-- A policy that is not active is not enabled either. Without this, a row that
-- migrated to 'paused' or 'disabled' would say enabled=true and never run,
-- because the scheduler requires both.
UPDATE dcc.backup_policies
   SET enabled = false
 WHERE enabled
   AND status <> 'active';

-- 3. schedule: the value set, and its pairing with custom_cron ---------------
-- The column was free text with no constraint, and the demo rows carried NULL.
-- '' and NULL meant the same thing; normalise to NULL first.
UPDATE dcc.backup_policies
   SET schedule = NULL
 WHERE schedule IS NOT NULL
   AND btrim(schedule) = '';

-- A scheduled policy with no cadence has no next run
-- (PolicyEngine._calculate_next_run returns None) and is therefore never due:
-- it is a policy that cannot fire. 'daily' is the model's default cadence (the
-- dataclass default, and what setup_tenant creates), so that is what an
-- under-specified scheduled row becomes. It is deliberately NOT inferred from
-- the row's name.
UPDATE dcc.backup_policies
   SET schedule = 'daily'
 WHERE policy_type = 'scheduled'
   AND schedule IS NULL;

-- A custom schedule with no expression is the same dead end, and create_policy
-- has always refused to build one. Fall back to the default cadence rather
-- than leave a row the new CHECK would reject.
UPDATE dcc.backup_policies
   SET schedule = 'daily',
       custom_cron = NULL
 WHERE schedule = 'custom'
   AND (custom_cron IS NULL OR btrim(custom_cron) = '');

-- 4. tags: jsonb array -> jsonb object --------------------------------------
-- The column defaulted to '[]' (an array) while the record holds a
-- dict[str, str], so a written policy came back as a list and
-- BackupPolicy.from_dict would have raised on it.
UPDATE dcc.backup_policies
   SET tags = '{}'::jsonb
 WHERE jsonb_typeof(tags) <> 'object';

ALTER TABLE dcc.backup_policies
    ALTER COLUMN tags SET DEFAULT '{}'::jsonb;

-- 5. Constraints -------------------------------------------------------------
-- Every one of these still rejects a genuinely invalid value. None of them is
-- a widened "anything goes" check: policy_type above is untouched, and the new
-- ones narrow the columns they cover.

-- The two axes, tied together so neither can be left half-set:
--   scheduled / on_demand  -> must name a full/incremental/differential backup
--   continuous / snapshot  -> must NOT (they produce no such artifact)
ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_backup_type_check;
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_backup_type_check
    CHECK (
        (backup_type IS NULL
         OR backup_type IN ('full', 'incremental', 'differential'))
        AND ((backup_type IS NULL) = (policy_type IN ('continuous', 'snapshot')))
    );

-- Codes only. Anything else is a typo that would otherwise be stored and then
-- rejected, or worse silently ignored, at execution time.
ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_compression_check;
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_compression_check
    CHECK (compression IN ('none', 'gzip', 'zstd', 'lz4'));

-- Cadence values, plus the two ways a cadence can be self-contradictory:
-- a custom schedule with no expression, and an expression with no custom
-- schedule.
ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_schedule_check;
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_schedule_check
    CHECK (schedule IS NULL
           OR schedule IN ('hourly', 'daily', 'weekly', 'monthly', 'custom'));

ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_schedule_coherence_check;
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_schedule_coherence_check
    CHECK (
        (policy_type <> 'scheduled' OR schedule IS NOT NULL)
        AND (custom_cron IS NULL) = (schedule IS DISTINCT FROM 'custom')
    );

-- Lifecycle only. The run states that used to live here are gone, so a writer
-- that still passes 'pending' now fails instead of coining a new state.
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_status_check
    CHECK (status IN ('active', 'paused', 'disabled', 'archived'));

-- enabled and status cannot contradict each other. is_due() requires
-- enabled AND status='active', so enabled+paused was a policy switched on and
-- guaranteed never to run.
ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_lifecycle_check;
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_lifecycle_check
    CHECK (NOT enabled OR status = 'active');

ALTER TABLE dcc.backup_policies
    DROP CONSTRAINT IF EXISTS backup_policies_tags_check;
ALTER TABLE dcc.backup_policies
    ADD CONSTRAINT backup_policies_tags_check
    CHECK (jsonb_typeof(tags) = 'object');

-- 6. Make the table describe itself -----------------------------------------
COMMENT ON COLUMN dcc.backup_policies.policy_type IS
    'WHEN the policy runs: scheduled | continuous | on_demand | snapshot. '
    'Not the backup kind -- see backup_type.';
COMMENT ON COLUMN dcc.backup_policies.backup_type IS
    'WHAT a run writes: full | incremental | differential. NULL only for '
    'continuous and snapshot policies, which produce no discrete backup. '
    'Same vocabulary as dcc.backup_runs.backup_type.';
COMMENT ON COLUMN dcc.backup_policies.compression IS
    'Codec written by the backup: none | gzip | zstd | lz4. '
    'BackupEngine can write only none and gzip.';
COMMENT ON COLUMN dcc.backup_policies.status IS
    'Lifecycle: active | paused | disabled | archived. Run outcomes belong to '
    'dcc.backup_runs.status, not here.';
COMMENT ON COLUMN dcc.backup_policies.schedule IS
    'Cadence: hourly | daily | weekly | monthly | custom, or NULL when the '
    'policy has no cadence. custom requires custom_cron.';

COMMIT;
