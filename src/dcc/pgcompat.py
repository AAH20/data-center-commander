"""psycopg3 compatibility layer for asyncpg-style queries.

WHY THIS EXISTS
---------------
Every query in dcc.api_async was written in asyncpg style:

    await conn.execute("SELECT set_config('dcc.tenant_id', $1, true)", tenant_id)
    rows = await conn.fetch("SELECT ... WHERE tenant_id=$1::uuid", tenant_id)
    row  = await conn.fetchrow("SELECT count(*) ...")

but the pool is built from psycopg_pool.AsyncConnectionPool (psycopg3). asyncpg is
not installed at all. The two APIs differ in every relevant respect:

    asyncpg                          psycopg3
    $1 placeholders                  %s placeholders
    conn.fetch() / conn.fetchrow()   cursor.execute() + cursor.fetchall()
    params positionally             params positionally, by occurrence

The result was that no query in the module could execute: $1 is not a placeholder to
psycopg3 ("the query has 0 placeholders but 1 parameters were passed"), and
AsyncConnection has no .fetch attribute. Routes returned 503 when no DSN was set and
would have returned 500 with a DSN set, so the failure was invisible in a test suite
that never pointed at a database.

This adapter keeps the queries as written. Rewriting ~40 queries by hand would have
introduced far more risk than translating placeholders in one place, and the
translation is mechanical enough to test directly.

PLACEHOLDER ORDER MATTERS
-------------------------
asyncpg lets a query reuse $1 out of order. psycopg3 binds strictly by occurrence, so
the nth %s consumes the nth parameter. The adapter therefore rewrites placeholders to
their order of appearance and reorders the arguments to match, which keeps reuse
correct instead of silently binding the wrong value.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

_PLACEHOLDER = re.compile(r"\$(\d+)")


def translate(sql: str, params: Sequence[Any]) -> tuple[str, list[Any]]:
    """Convert asyncpg $n placeholders to psycopg3 %s, reordering params to match.

    A literal '%' in the SQL must be escaped for psycopg3, otherwise it is read as a
    format specifier. Queries here are not expected to contain one, but escaping is
    one line and a corrupt query is not worth the risk.
    """
    if isinstance(params, (str, bytes)):
        # A bare string would be indexed character by character and bind one letter.
        # That is a silent wrong answer, so refuse it loudly.
        raise TypeError("params must be a sequence; pass a 1-tuple for a single value")

    sql = sql.replace("%", "%%")

    ordered: list[Any] = []

    def _sub(match: re.Match) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(params):
            raise ValueError(
                f"query references ${match.group(1)} but only {len(params)} parameter(s) given"
            )
        ordered.append(params[index])
        return "%s"

    return _PLACEHOLDER.sub(_sub, sql), ordered


class PgConnection:
    """asyncpg-shaped wrapper over a psycopg3 connection."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def transaction(self):
        """psycopg3 transaction context; async with conn.transaction() works as before."""
        return self._conn.transaction()

    async def _run(self, sql: str, params: Sequence[Any]) -> Any:
        query, args = translate(sql, params)
        cur = self._conn.cursor()
        await cur.execute(query, args or None)
        return cur

    async def execute(self, sql: str, *params: Any) -> Any:
        cur = await self._run(sql, params)
        return cur.rowcount

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        cur = await self._run(sql, params)
        return list(await cur.fetchall())

    async def fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        cur = await self._run(sql, params)
        return await cur.fetchone()

    async def fetchval(self, sql: str, *params: Any) -> Any:
        row = await self.fetchrow(sql, *params)
        return next(iter(row.values())) if row else None


class PgPool:
    """Wrapper so pool.connection() yields a PgConnection."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def connection(self) -> "_ConnectionCtx":
        return _ConnectionCtx(self._pool.connection())

    async def open(self) -> None:
        await self._pool.open()

    async def wait(self, timeout: float | None = None) -> None:
        await self._pool.wait(timeout=timeout)

    async def close(self) -> None:
        await self._pool.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pool, name)


class _ConnectionCtx:
    """Async context manager that wraps the raw connection on entry."""

    def __init__(self, ctx: Any) -> None:
        self._ctx = ctx

    async def __aenter__(self) -> PgConnection:
        return PgConnection(await self._ctx.__aenter__())

    async def __aexit__(self, *exc: Any) -> Any:
        return await self._ctx.__aexit__(*exc)
