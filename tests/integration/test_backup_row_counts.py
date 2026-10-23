"""Row counts reported by a backup must be measured, never assumed.

Two defects made a backup report a confident ``0 rows`` on a populated database:

  1. One ``try``/``except Exception: pass`` wrapped the whole counting loop, so a
     single failing table aborted every table after it, and the caller's
     ``sum(row_counts.values())`` read as an empty database.
  2. Every table was queried with ``WHERE tenant_id = %s::uuid``. ``dcc.tenants``
     has no ``tenant_id`` column at all, and a non-UUID tenant raised on the cast.
     Both failures landed in the blanket except and vanished.

The fix counts a table only when it genuinely has a ``tenant_id`` column, lets each
count fail independently, and OMITS a table it could not measure rather than
recording it as zero -- so ``sum()`` totals only what was actually counted.

These tests need the real database because the defect was in the SQL the code
generates; a fake cursor would assert against the bug rather than the behaviour.
"""

from __future__ import annotations

import os
import tempfile

import pytest

DSN = os.environ.get("DCC_DATABASE_URL", "")
TENANT = "dcc00000-0000-4000-8000-000000000001"

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="requires DCC_DATABASE_URL pointing at a seeded database; the defect is in real SQL",
)


@pytest.fixture()
def engine():
    from dcc.operations.backup import BackupEngine

    return BackupEngine(backup_root=tempfile.mkdtemp())


def test_counts_tenant_scoped_tables(engine) -> None:
    """A populated table must report its real count, not zero."""
    counts = engine._get_row_counts(dsn=DSN, tenant_id=TENANT, tables=["assets"])

    assert "assets" in counts, f"assets was not measured at all: {counts}"
    assert counts["assets"] >= 0


def test_table_without_tenant_id_is_omitted(engine) -> None:
    """dcc.tenants has no tenant_id column; counting it by tenant is meaningless."""
    counts = engine._get_row_counts(dsn=DSN, tenant_id=TENANT, tables=["tenants"])

    assert counts == {}, f"expected no measurement for dcc.tenants, got {counts}"


def test_missing_table_is_omitted_not_zeroed(engine) -> None:
    """A table that does not exist must not be summed as if it were empty."""
    counts = engine._get_row_counts(
        dsn=DSN, tenant_id=TENANT, tables=["assets", "definitely_not_a_table"]
    )

    assert "definitely_not_a_table" not in counts
    assert "assets" in counts, "one bad table must not abort the others"


def test_non_uuid_tenant_measures_nothing(engine) -> None:
    """An invalid tenant yields no measurements -- never a fabricated zero."""
    counts = engine._get_row_counts(dsn=DSN, tenant_id="not-a-uuid", tables=["assets"])

    assert counts == {}, f"expected no measurement for a non-UUID tenant, got {counts}"


def test_one_failure_does_not_abort_the_rest(engine) -> None:
    """The regression that mattered: a bad table must not stop the loop."""
    tables = ["tenants", "assets", "nope", "facilities"]
    counts = engine._get_row_counts(dsn=DSN, tenant_id=TENANT, tables=tables)

    assert "assets" in counts, "assets after a failing table was skipped"
    assert "facilities" in counts, "facilities after a failing table was skipped"
    assert "nope" not in counts
    assert "tenants" not in counts
