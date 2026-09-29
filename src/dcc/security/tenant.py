"""Multi-tenant data isolation: row-level security and tenant context propagation.

This module provides the application-layer tenant context management that
complements the PostgreSQL RLS policies defined in the database schema.

Architecture
------------
- PostgreSQL RLS policies use ``current_setting('dcc.tenant_id', true)`` to
  filter rows. The setting is transaction-local (``set_config(..., true)``).
- This module provides :class:`TenantContext`, a context manager that sets
  ``dcc.tenant_id`` for the duration of a ``with`` block, and
  :class:`TenantContextVar`, a ``contextvars.ContextVar`` that propagates the
  tenant ID through the Python call stack (thread-safe and asyncio-safe).
- **Fail-closed**: if no tenant context is active, database queries return
  zero rows because the RLS policy ``tenant_id = nullif(..., '')::uuid``
  evaluates to NULL when the setting is absent.

Usage
-----
.. code-block:: python

    from dcc.security.tenant import TenantContext, current_tenant

    # In a request handler:
    with TenantContext(tenant_id):
        # All database queries in this block are scoped to the tenant.
        rows = conn.execute("SELECT * FROM dcc.assets").fetchall()

    # Outside the context, current_tenant() raises TenantNotFoundError.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, Optional
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

__all__ = [
    "TENANT_SETTING",
    "TenantContext",
    "TenantContextVar",
    "TenantNotFoundError",
    "TenantValidationError",
    "clear_tenant",
    "current_tenant",
    "get_tenant_id",
    "is_tenant_active",
    "parse_tenant_id",
    "require_tenant",
    "set_tenant",
]

# The PostgreSQL GUC (Grand Unified Configuration) parameter used by RLS policies.
TENANT_SETTING = "dcc.tenant_id"

# Strict UUID validation regex (same pattern used in api.py).
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


class TenantNotFoundError(RuntimeError):
    """Raised when a tenant context is required but none is active.

    This is a fail-closed design: if no tenant is set, the caller cannot
    accidentally access cross-tenant data.
    """


class TenantValidationError(ValueError):
    """Raised when a tenant ID is not a valid UUID."""


def parse_tenant_id(value: str | UUID) -> str:
    """Validate and normalize a tenant ID to a canonical UUID string.

    Parameters
    ----------
    value:
        A UUID object or a string that looks like a UUID.

    Returns
    -------
    str
        The canonical lowercase UUID string.

    Raises
    ------
    TenantValidationError
        If the value is not a valid UUID.
    """
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str):
        raise TenantValidationError(
            f"tenant_id must be a string or UUID, got {type(value).__name__}"
        )
    if not _UUID_RE.fullmatch(value):
        raise TenantValidationError(
            f"tenant_id must be a UUID, got {value!r}"
        )
    return str(UUID(value))


# ---------------------------------------------------------------------------
# Context variable for tenant propagation through the Python call stack
# ---------------------------------------------------------------------------

class TenantContextVar:
    """Wrapper around contextvars.ContextVar for tenant ID propagation.

    This provides a clean interface for getting, setting, and clearing the
    current tenant ID in a thread-safe and asyncio-safe manner.
    """

    _var: ContextVar[Optional[str]] = ContextVar(
        "dcc_tenant_id", default=None
    )

    @classmethod
    def get(cls) -> Optional[str]:
        """Return the current tenant ID, or None if not set."""
        return cls._var.get()

    @classmethod
    def set(cls, tenant_id: str | UUID) -> None:
        """Set the current tenant ID."""
        cls._var.set(parse_tenant_id(tenant_id))

    @classmethod
    def clear(cls) -> None:
        """Clear the current tenant ID."""
        cls._var.set(None)

    @classmethod
    def is_active(cls) -> bool:
        """Return True if a tenant context is currently active."""
        return cls._var.get() is not None


def set_tenant(tenant_id: str | UUID) -> None:
    """Set the current tenant in the context variable.

    This propagates to all code running in the same context (thread or
    asyncio task). It does **not** set the PostgreSQL GUC — use
    :class:`TenantContext` for that.

    Parameters
    ----------
    tenant_id:
        The tenant UUID to set.
    """
    TenantContextVar.set(tenant_id)


def clear_tenant() -> None:
    """Clear the current tenant from the context variable."""
    TenantContextVar.clear()


def get_tenant_id() -> Optional[str]:
    """Return the current tenant ID from the context variable, or None."""
    return TenantContextVar.get()


def is_tenant_active() -> bool:
    """Return True if a tenant context is currently active."""
    return TenantContextVar.is_active()


def current_tenant() -> str:
    """Return the current tenant ID, raising if none is active.

    Returns
    -------
    str
        The canonical UUID string of the current tenant.

    Raises
    ------
    TenantNotFoundError
        If no tenant context is active.
    """
    tenant = TenantContextVar.get()
    if tenant is None:
        raise TenantNotFoundError(
            "No tenant context is active. Use `with TenantContext(tenant_id):` "
            "to scope database operations to a tenant."
        )
    return tenant


def require_tenant() -> str:
    """Alias for :func:`current_tenant` with a more imperative name."""
    return current_tenant()


# ---------------------------------------------------------------------------
# Context manager for database transactions
# ---------------------------------------------------------------------------


@dataclass
class TenantContext:
    """Context manager that scopes database operations to a single tenant.

    On entry, this sets the PostgreSQL ``dcc.tenant_id`` GUC parameter to the
    given tenant UUID for the duration of the ``with`` block. The GUC is set
    with ``is_local=True`` (transaction-local), so it automatically reverts
    when the transaction ends.

    The tenant ID is also stored in a :class:`contextvars.ContextVar` so that
    nested function calls can discover the current tenant without passing it
    through every function signature.

    Parameters
    ----------
    tenant_id:
        The tenant UUID to scope operations to.
    connection:
        An optional psycopg connection. If provided, the GUC is set
        immediately. If omitted, the GUC is set lazily on the first
        :meth:`__enter__` call that has a connection.

    Examples
    --------
    .. code-block:: python

        with TenantContext(tenant_id, conn) as ctx:
            rows = conn.execute("SELECT * FROM dcc.assets").fetchall()
            assert ctx.tenant_id == tenant_id
    """

    tenant_id: str
    connection: Optional[psycopg.Connection] = None

    def __post_init__(self) -> None:
        # Validate eagerly so misconfiguration is caught at construction time.
        object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))

    def __enter__(self) -> TenantContext:
        """Set the tenant context variable and the PostgreSQL GUC."""
        object.__setattr__(self, "_previous_tenant", TenantContextVar.get())
        TenantContextVar.set(self.tenant_id)
        if self.connection is not None:
            self._set_guc(self.connection)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Restore the previous tenant context variable.

        The PostgreSQL GUC is transaction-local, so it reverts automatically
        when the transaction ends. We do not need to unset it explicitly.
        """
        previous = getattr(self, "_previous_tenant", None)
        if previous is not None:
            TenantContextVar.set(previous)
        else:
            TenantContextVar.clear()

    def _set_guc(self, conn: psycopg.Connection) -> None:
        """Set the ``dcc.tenant_id`` GUC on the given connection."""
        conn.execute(
            "SELECT set_config(%s, %s, true)",
            (TENANT_SETTING, self.tenant_id),
        )

    def ensure_guc(self, conn: psycopg.Connection) -> None:
        """Ensure the GUC is set on the given connection.

        Call this if you did not pass a connection to the constructor but
        want to set the GUC on a connection obtained inside the ``with`` block.
        """
        self._set_guc(conn)


@contextmanager
def tenant_context(
    tenant_id: str | UUID,
    conn: Optional[psycopg.Connection] = None,
) -> Iterator[str]:
    """Functional context manager for tenant scoping.

    This is the functional equivalent of :class:`TenantContext`.

    Parameters
    ----------
    tenant_id:
        The tenant UUID to scope operations to.
    conn:
        An optional psycopg connection to set the GUC on immediately.

    Yields
    ------
    str
        The canonical tenant UUID string.

    Examples
    --------
    .. code-block:: python

        with tenant_context(tenant_id, conn):
            rows = conn.execute("SELECT * FROM dcc.assets").fetchall()
    """
    canonical = parse_tenant_id(tenant_id)
    previous = TenantContextVar.get()
    TenantContextVar.set(canonical)
    if conn is not None:
        conn.execute(
            "SELECT set_config(%s, %s, true)",
            (TENANT_SETTING, canonical),
        )
    try:
        yield canonical
    finally:
        if previous is not None:
            TenantContextVar.set(previous)
        else:
            TenantContextVar.clear()
