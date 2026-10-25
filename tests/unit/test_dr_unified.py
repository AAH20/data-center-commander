"""Pins the three unification decisions for the DR/HA boundary.

1. ``FailoverResult`` exists in ``dcc.dr.failover`` only. The HA manager's
   node-pair outcome is ``FailoverOutcome``. The two were both named
   ``FailoverResult`` -- different shapes, same name -- so an import typo
   produced the wrong one and no checker noticed.
2. DR run state lives on disk under the orchestrator's subsystem roots, and
   ``get_status`` reads through to it. The only process-local failover state is
   the step-handler registry, which is code, not data.
3. ``dr.BackupPolicy`` is a declarative record with no executor. Its link to
   the real engine is ``to_engine_params``, which is checked against
   ``BackupEngine.create_backup``'s actual signature.

These are contract tests: they are meant to fail if someone re-introduces the
name collision, makes the status counts memory-only again, or lets the policy
record grow an implicit execution path.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

import pytest

import dcc.dr.failover as dr_failover
import dcc.operations.ha as ops_ha
from dcc.dr.failover import FailoverAutomation, FailoverResult
from dcc.dr.orchestrator import DROrchestrator, DROrchestratorConfig
from dcc.dr.policies import BackupPolicy, PolicyType, PolicyValidationError
from dcc.operations.backup import BackupEngine, BackupType, CompressionType
from dcc.operations.ha import FailoverOutcome

SRC = Path(__file__).resolve().parents[2] / "src" / "dcc"
TENANT = "dcc00000-0000-4000-8000-00000000t001"


# ---------------------------------------------------------------------------
# 1. The two failover result types are distinguishable
# ---------------------------------------------------------------------------


def test_failover_result_name_is_defined_exactly_once_in_the_product():
    """A product-wide name collision cannot come back unnoticed."""
    definitions = {"FailoverResult": [], "FailoverOutcome": []}
    pattern = re.compile(r"^class (FailoverResult|FailoverOutcome)\b", re.MULTILINE)
    for path in SRC.rglob("*.py"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            definitions[match.group(1)].append(path.relative_to(SRC).as_posix())

    assert definitions["FailoverResult"] == ["dr/failover.py"]
    assert definitions["FailoverOutcome"] == ["operations/ha.py"]


def test_each_name_resolves_only_in_its_own_module():
    """Importing the wrong module cannot hand back the other shape."""
    assert FailoverResult.__module__ == "dcc.dr.failover"
    assert FailoverOutcome.__module__ == "dcc.operations.ha"

    assert not hasattr(dr_failover, "FailoverOutcome")
    assert not hasattr(ops_ha, "FailoverResult")


def test_failover_types_have_documented_and_disjoint_shapes():
    """They are different concepts, so their fields and docs must say so."""
    result_fields = set(FailoverResult.__dataclass_fields__)
    outcome_fields = set(FailoverOutcome.__dataclass_fields__)

    # Execution-level record vs single node-pair move.
    assert {"execution_id", "steps_completed", "steps_total", "rolled_back"} <= result_fields
    assert {"source_node", "target_node", "duration_ms", "timestamp"} <= outcome_fields

    # The discriminating fields are not shared, so a misuse at a call site
    # fails on attribute access rather than silently reading a plausible value.
    assert "execution_id" not in outcome_fields
    assert "source_node" not in result_fields

    # Each docstring names the other type, so a reader hitting the wrong one is
    # told which one they wanted.
    result_doc = FailoverResult.__doc__ or ""
    outcome_doc = FailoverOutcome.__doc__ or ""
    assert "FailoverOutcome" in result_doc
    assert "FailoverResult" in outcome_doc


def test_operations_package_exports_the_outcome_not_the_collision():
    from dcc import operations

    assert operations.FailoverOutcome is FailoverOutcome
    assert not hasattr(operations, "FailoverResult")


# ---------------------------------------------------------------------------
# 2. DR orchestration state: durable on disk, with a known process-local edge
# ---------------------------------------------------------------------------


def _automation(root: Path) -> FailoverAutomation:
    return FailoverAutomation(root / "procedures")


def test_execution_history_survives_a_restart(tmp_path):
    """A new process must be able to report what happened during the incident."""
    first = _automation(tmp_path)
    result = first.execute_failover(TENANT, "node-a", "node-b")
    assert result.success is True

    restarted = _automation(tmp_path)

    # The run is readable by id, not only listed.
    recovered = restarted.get_execution(result.execution_id)
    assert recovered is not None
    assert recovered.tenant_id == TENANT
    assert recovered.source_node == "node-a"

    # And it is counted. This is where the old implementation reported zero:
    # get_status() counted the in-memory dict instead of the records on disk.
    status = restarted.get_status()
    assert status["total_executions"] == 1
    assert status["completed"] == 1
    assert [e.execution_id for e in restarted.list_executions()] == [result.execution_id]


def test_rollback_after_restart_uses_the_persisted_execution(tmp_path):
    """Rollback must not depend on the failing process still being alive."""
    first = _automation(tmp_path)
    result = first.execute_failover(TENANT, "node-a", "node-b")

    restarted = _automation(tmp_path)
    rollback = restarted.rollback(result.execution_id)

    assert rollback.success is True, rollback.message
    assert rollback.rolled_back is True
    assert rollback.execution_id == result.execution_id

    recovered = restarted.get_execution(result.execution_id)
    assert recovered is not None
    assert recovered.status.value == "rolled_back"


def test_step_handlers_are_process_local_by_design(tmp_path):
    """The one piece of state that is not durable -- pinned so it stays honest.

    Handlers are code, so they cannot be recovered from disk. A restarted
    process that has not registered its handlers falls back to the simulated
    default handler. If this ever changes, the FailoverAutomation docstring
    ("What is process-local and NOT durable") has to change with it.
    """
    first = _automation(tmp_path)
    calls: list[str] = []
    first.register_step_handler("pre_check", lambda execution, step: calls.append(step.name))

    restarted = _automation(tmp_path)

    assert first._step_handlers.keys() == {"pre_check"}
    assert restarted._step_handlers == {}

    restarted.execute_failover(TENANT, "node-a", "node-b")
    assert calls == []  # the handler registered in the dead process never ran


def test_orchestrator_holds_no_run_state_of_its_own(tmp_path):
    """Constructing a second orchestrator over the same roots recovers history."""
    config = DROrchestratorConfig(
        backup_root=str(tmp_path / "backups"),
        policy_root=str(tmp_path / "policies"),
        procedure_root=str(tmp_path / "procedures"),
        tracker_root=str(tmp_path / "tracking"),
        test_root=str(tmp_path / "tests"),
    )
    first = DROrchestrator(config)
    result = first.execute_failover(TENANT, "node-a", "node-b")
    assert result.success is True

    restarted = DROrchestrator(config)

    assert restarted.failover_automation.get_status()["total_executions"] == 1
    summary = restarted.get_tenant_summary(TENANT)
    assert summary.failover_execution_count == 1


def test_durability_is_documented_where_readers_look(tmp_path):
    """The docstrings must describe what the code actually does."""
    automation_doc = FailoverAutomation.__doc__ or ""
    assert "Durability" in automation_doc
    assert "_exec_<execution_id>.json" in automation_doc
    assert "process-local" in automation_doc
    # The claim the old code made implicitly by omission must be stated.
    assert "does not continue it" in automation_doc

    assert "keeps no run state of its own" in (DROrchestrator.__doc__ or "")


# ---------------------------------------------------------------------------
# 3. BackupPolicy is declarative, and its bridge to the engine is real
# ---------------------------------------------------------------------------


def _policy(**kwargs: Any) -> BackupPolicy:
    base: dict[str, Any] = {"policy_id": "p1", "tenant_id": TENANT, "name": "nightly"}
    base.update(kwargs)
    return BackupPolicy(**base)


def test_policy_engine_params_match_the_real_engine_signature():
    """The bridge is checked against BackupEngine, not against a copy of it."""
    params = inspect.signature(BackupEngine.create_backup).parameters
    engine_params = _policy().to_engine_params()

    assert set(engine_params) <= set(params)
    # Values are the engine's own enum members, by value.
    assert BackupType(engine_params["backup_type"]) is BackupType.FULL
    assert CompressionType(engine_params["compression"]) is CompressionType.GZIP


def test_policy_types_the_engine_cannot_run_are_refused_not_downgraded():
    """A continuous policy must not silently become a nightly dump."""
    with pytest.raises(PolicyValidationError) as exc:
        _policy(policy_type=PolicyType.CONTINUOUS).to_engine_params()
    assert "continuous" in str(exc.value)

    with pytest.raises(PolicyValidationError):
        _policy(policy_type=PolicyType.SNAPSHOT).to_engine_params()

    assert _policy(policy_type=PolicyType.INCREMENTAL).to_engine_params()["backup_type"] == (
        "incremental"
    )


def test_policy_table_selection_distinguishes_all_from_none():
    """Empty ``tables`` means every table, which the engine spells None."""
    assert _policy().to_engine_params()["tables"] is None
    assert _policy(tables=["events"]).to_engine_params()["tables"] == ["events"]


def test_retention_days_maps_to_the_engine_age_cap():
    assert _policy(retention_days=14).to_retention_params() == {"max_age_days": 14}


def test_backup_policy_has_no_consumer_outside_the_dr_package():
    """Pins the "declarative only" claim: nothing executes the real engine from it."""
    consumers: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.relative_to(SRC).parts[0] == "dr":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bBackupPolicy\b", text):
            consumers.append(path.relative_to(SRC).as_posix())

    assert consumers == [], (
        "dr.BackupPolicy gained a consumer outside dcc.dr; update its docstring "
        f"(it claims to be declarative only): {consumers}"
    )


def test_dr_package_does_not_import_the_execution_layer():
    """Keeps the documented stdlib-only boundary that forced the adapter dict."""
    offenders = [
        path.relative_to(SRC).as_posix()
        for path in (SRC / "dr").glob("*.py")
        if re.search(r"^\s*(from|import)\s+dcc\.operations|^\s*from\s+\.\.operations", path.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    assert offenders == []
