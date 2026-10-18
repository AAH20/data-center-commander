"""RBAC synchronization engine.

Synchronizes DCC roles and role assignments with cloud IAM providers.
Supports push (DCC -> cloud), pull (cloud -> DCC), and bidirectional sync.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from .models import (
    FederatedIdentity,
    IdentityType,
    ProviderType,
    RoleMapping,
    SyncConflictError,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from .providers import CloudIAMProvider, ProviderRegistry
from ..security.authz import Role, create_default_roles
from ..security.tenant import parse_tenant_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SyncConfig:
    """Configuration for an RBAC sync operation.

    Attributes
    ----------
    provider_name:
        The registered provider name to sync with.
    tenant_id:
        The tenant to scope the sync to.
    direction:
        Push, pull, or bidirectional.
    dry_run:
        If True, compute changes but do not apply them.
    conflict_resolution:
        How to resolve conflicts: ``dcc_wins``, ``provider_wins``, or ``fail``.
    create_missing_roles:
        If True, create roles in the provider that exist in DCC but not remotely.
    remove_orphaned_roles:
        If True, remove roles in the provider that no longer exist in DCC.
    identity_filter:
        Optional filter to sync only specific identity types.
    """

    provider_name: str = ""
    tenant_id: str = ""
    direction: SyncDirection = SyncDirection.PUSH
    dry_run: bool = False
    conflict_resolution: str = "dcc_wins"  # dcc_wins | provider_wins | fail
    create_missing_roles: bool = True
    remove_orphaned_roles: bool = False
    identity_filter: Optional[IdentityType] = None

    def __post_init__(self) -> None:
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))
        if self.conflict_resolution not in ("dcc_wins", "provider_wins", "fail"):
            raise ValueError(
                f"invalid conflict_resolution: {self.conflict_resolution}"
            )


# ---------------------------------------------------------------------------
# Sync engine
# ---------------------------------------------------------------------------


class RBACSyncEngine:
    """Engine for synchronizing RBAC state between DCC and cloud providers.

    The engine compares the desired state (DCC roles and assignments)
    with the current state in the cloud provider, computes a diff,
    and applies the necessary changes.

    Usage
    -----
    .. code-block:: python

        engine = RBACSyncEngine(registry)
        config = SyncConfig(
            provider_name="aws-prod",
            tenant_id="...",
            direction=SyncDirection.PUSH,
        )
        result = engine.sync(config)
        if result.status == SyncStatus.COMPLETED:
            print(f"Synced {result.total_changes} changes")
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        dcc_roles: Optional[list[Role]] = None,
    ) -> None:
        self._registry = registry
        self._dcc_roles: dict[str, Role] = {}
        if dcc_roles:
            for role in dcc_roles:
                self._dcc_roles[role.name] = role
        else:
            for role in create_default_roles():
                self._dcc_roles[role.name] = role

    @property
    def dcc_roles(self) -> dict[str, Role]:
        """Return the current DCC role definitions."""
        return dict(self._dcc_roles)

    def add_dcc_role(self, role: Role) -> None:
        """Register a DCC role for synchronization."""
        self._dcc_roles[role.name] = role

    def remove_dcc_role(self, name: str) -> None:
        """Remove a DCC role from synchronization."""
        self._dcc_roles.pop(name, None)

    def sync(self, config: SyncConfig) -> SyncResult:
        """Execute an RBAC synchronization.

        Parameters
        ----------
        config:
            The sync configuration.

        Returns
        -------
        SyncResult
            The result of the sync operation.
        """
        result = SyncResult(
            direction=config.direction,
            status=SyncStatus.RUNNING,
        )

        try:
            provider = self._registry.get(config.provider_name)
            result.provider = provider.provider_type

            if config.direction in (SyncDirection.PUSH, SyncDirection.BIDIRECTIONAL):
                self._push_to_provider(provider, config, result)

            if config.direction in (SyncDirection.PULL, SyncDirection.BIDIRECTIONAL):
                self._pull_from_provider(provider, config, result)

            result.status = (
                SyncStatus.PARTIAL if result.errors else SyncStatus.COMPLETED
            )
        except Exception as exc:
            logger.exception("RBAC sync failed")
            result.status = SyncStatus.FAILED
            result.errors.append(str(exc))

        result.completed_at = datetime.now(timezone.utc)
        return result

    # ------------------------------------------------------------------
    # Push: DCC -> Cloud Provider
    # ------------------------------------------------------------------

    def _push_to_provider(
        self,
        provider: CloudIAMProvider,
        config: SyncConfig,
        result: SyncResult,
    ) -> None:
        """Push DCC roles and assignments to the cloud provider."""
        # 1. Sync role definitions
        self._sync_role_definitions(provider, config, result)

        # 2. Sync role assignments
        self._sync_role_assignments(provider, config, result)

    def _sync_role_definitions(
        self,
        provider: CloudIAMProvider,
        config: SyncResult,
        result: SyncResult,
    ) -> None:
        """Create/update/delete role definitions in the provider."""
        try:
            remote_mappings = provider.list_role_mappings(tenant_id=config.tenant_id)
        except NotImplementedError:
            logger.warning(
                "Provider %s does not support listing role mappings",
                provider.provider_type.value,
            )
            return

        remote_roles: dict[str, RoleMapping] = {}
        for mapping in remote_mappings:
            remote_roles[mapping.dcc_role] = mapping

        # Create missing roles
        if config.create_missing_roles:
            for role_name in self._dcc_roles:
                if role_name not in remote_roles:
                    if config.dry_run:
                        result.roles_created += 1
                        continue
                    try:
                        mapping = RoleMapping(
                            dcc_role=role_name,
                            provider=provider.provider_type,
                            external_role_id=self._generate_external_role_id(
                                provider.provider_type, role_name
                            ),
                            external_role_name=f"DCC-{role_name}",
                            tenant_id=config.tenant_id,
                        )
                        provider.create_role_mapping(mapping)
                        result.roles_created += 1
                    except NotImplementedError:
                        logger.warning(
                            "Provider %s does not support role creation",
                            provider.provider_type.value,
                        )
                        break
                    except Exception as exc:
                        result.errors.append(
                            f"failed to create role {role_name}: {exc}"
                        )

        # Remove orphaned roles
        if config.remove_orphaned_roles:
            for role_name, mapping in remote_roles.items():
                if role_name not in self._dcc_roles:
                    if config.dry_run:
                        result.roles_removed += 1
                        continue
                    try:
                        provider.delete_role_mapping(mapping)
                        result.roles_removed += 1
                    except Exception as exc:
                        result.errors.append(
                            f"failed to remove role {role_name}: {exc}"
                        )

    def _sync_role_assignments(
        self,
        provider: CloudIAMProvider,
        config: SyncConfig,
        result: SyncResult,
    ) -> None:
        """Sync role assignments between DCC and the provider."""
        try:
            identities = provider.list_identities(
                tenant_id=config.tenant_id,
                identity_type=config.identity_filter,
            )
        except NotImplementedError:
            logger.warning(
                "Provider %s does not support listing identities",
                provider.provider_type.value,
            )
            return

        for identity in identities:
            try:
                self._sync_identity_assignments(
                    provider, identity, config, result
                )
            except Exception as exc:
                result.errors.append(
                    f"failed to sync assignments for {identity.external_id}: {exc}"
                )

    def _sync_identity_assignments(
        self,
        provider: CloudIAMProvider,
        identity: FederatedIdentity,
        config: SyncConfig,
        result: SyncResult,
    ) -> None:
        """Sync role assignments for a single identity."""
        # This would compare desired assignments (from DCC) with
        # current assignments (from provider) and apply changes.
        # The exact logic depends on how assignments are tracked in DCC.
        pass

    # ------------------------------------------------------------------
    # Pull: Cloud Provider -> DCC
    # ------------------------------------------------------------------

    def _pull_from_provider(
        self,
        provider: CloudIAMProvider,
        config: SyncConfig,
        result: SyncResult,
    ) -> None:
        """Pull roles and assignments from the cloud provider into DCC."""
        try:
            remote_mappings = provider.list_role_mappings(tenant_id=config.tenant_id)
        except NotImplementedError:
            logger.warning(
                "Provider %s does not support listing role mappings",
                provider.provider_type.value,
            )
            return

        for mapping in remote_mappings:
            if mapping.dcc_role not in self._dcc_roles:
                if config.conflict_resolution == "fail":
                    raise SyncConflictError(
                        f"remote role {mapping.dcc_role!r} has no DCC equivalent"
                    )
                elif config.conflict_resolution == "provider_wins":
                    # Create a new DCC role from the remote mapping
                    self._dcc_roles[mapping.dcc_role] = Role(
                        name=mapping.dcc_role,
                        permissions=frozenset(),
                        description=f"Imported from {provider.provider_type.value}",
                    )
                    result.roles_created += 1
                # dcc_wins: skip roles that don't exist in DCC

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_external_role_id(
        self,
        provider_type: ProviderType,
        role_name: str,
    ) -> str:
        """Generate a provider-specific role identifier."""
        if provider_type == ProviderType.AWS:
            return f"arn:aws:iam::123456789012:role/DCC-{role_name}"
        elif provider_type == ProviderType.AZURE:
            return f"/subscriptions/00000000-0000-0000-0000-000000000000/providers/Microsoft.Authorization/roleDefinitions/{role_name}"
        elif provider_type == ProviderType.GCP:
            return f"projects/my-project/roles/dcc_{role_name}"
        else:
            return f"dcc-{role_name}"
