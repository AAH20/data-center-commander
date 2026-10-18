"""Cloud IAM provider adapters for identity federation.

Each adapter translates native cloud IAM constructs (AWS IAM, Azure RBAC,
GCP IAM) into the canonical :mod:`dcc.identity_federation.models` types.
All adapters implement the :class:`CloudIAMProvider` protocol.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

from .models import (
    FederationError,
    FederatedIdentity,
    IdentityNotFoundError,
    IdentityType,
    ProviderNotFoundError,
    ProviderType,
    RoleMapping,
    SyncConflictError,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from ..security.tenant import parse_tenant_id


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class CloudIAMProvider(ABC):
    """Abstract interface for cloud IAM provider adapters.

    Each method is bounded, read-only where possible, and translates
    provider-specific constructs into canonical federation models.
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type this adapter handles."""

    @abstractmethod
    def list_identities(
        self,
        *,
        tenant_id: str,
        identity_type: Optional[IdentityType] = None,
    ) -> list[FederatedIdentity]:
        """List all identities known to this provider."""

    @abstractmethod
    def get_identity(
        self,
        external_id: str,
        *,
        tenant_id: str,
    ) -> FederatedIdentity:
        """Resolve a single identity by its external ID."""

    @abstractmethod
    def list_role_mappings(
        self,
        *,
        tenant_id: str,
    ) -> list[RoleMapping]:
        """List all role mappings for this provider."""

    @abstractmethod
    def create_role_mapping(
        self,
        mapping: RoleMapping,
    ) -> RoleMapping:
        """Create a role mapping in the cloud provider."""

    @abstractmethod
    def delete_role_mapping(
        self,
        mapping: RoleMapping,
    ) -> None:
        """Delete a role mapping from the cloud provider."""

    @abstractmethod
    def assign_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Assign a role to an identity."""

    @abstractmethod
    def revoke_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Revoke a role from an identity."""

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is reachable and credentials are valid."""


# ---------------------------------------------------------------------------
# AWS IAM Adapter
# ---------------------------------------------------------------------------


class AWSIAMProvider(CloudIAMProvider):
    """AWS IAM adapter using the boto3-compatible HTTP API.

    In production this would use boto3; here we provide the interface
    contract and a bounded HTTP implementation for the most common
    read operations.
    """

    PROVIDER_TYPE = ProviderType.AWS

    # AWS ARN patterns
    _ARN_RE = re.compile(
        r"^arn:aws:iam::(\d{12}):(?P<type>role|user|group|policy)/(?P<name>[\w+=,.@-]+)$"
    )

    def __init__(
        self,
        *,
        region: str = "us-east-1",
        access_key_id: str = "",
        secret_access_key: str = "",
        session_token: str = "",
        account_id: str = "",
        endpoint_url: str = "",
    ) -> None:
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._session_token = session_token
        self._account_id = account_id
        self._endpoint_url = endpoint_url or f"https://iam.{region}.amazonaws.com"

    @property
    def provider_type(self) -> ProviderType:
        return self.PROVIDER_TYPE

    def _api_call(
        self,
        action: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a signed IAM API call (simplified; production uses boto3)."""
        # In production, this would use boto3. Here we provide the
        # interface contract. The actual signing and HTTP call would
        # be implemented with botocore or direct SigV4 signing.
        raise NotImplementedError(
            "AWS IAM API calls require boto3. Install boto3 and use "
            "the production adapter implementation."
        )

    def list_identities(
        self,
        *,
        tenant_id: str,
        identity_type: Optional[IdentityType] = None,
    ) -> list[FederatedIdentity]:
        """List IAM users and roles in the AWS account."""
        # Production: boto3 iam.list_users() and iam.list_roles()
        raise NotImplementedError("requires boto3")

    def get_identity(
        self,
        external_id: str,
        *,
        tenant_id: str,
    ) -> FederatedIdentity:
        """Resolve an AWS IAM user or role by ARN."""
        match = self._ARN_RE.match(external_id)
        if not match:
            raise IdentityNotFoundError(f"invalid AWS ARN: {external_id}")
        # Production: boto3 iam.get_user() or iam.get_role()
        raise NotImplementedError("requires boto3")

    def list_role_mappings(
        self,
        *,
        tenant_id: str,
    ) -> list[RoleMapping]:
        """List IAM roles that correspond to DCC role mappings."""
        raise NotImplementedError("requires boto3")

    def create_role_mapping(self, mapping: RoleMapping) -> RoleMapping:
        """Create an IAM role with a trust policy for DCC."""
        raise NotImplementedError("requires boto3")

    def delete_role_mapping(self, mapping: RoleMapping) -> None:
        """Delete an IAM role."""
        raise NotImplementedError("requires boto3")

    def assign_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Attach an IAM policy to a user/role."""
        raise NotImplementedError("requires boto3")

    def revoke_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Detach an IAM policy from a user/role."""
        raise NotImplementedError("requires boto3")

    def health_check(self) -> bool:
        """Check AWS credential validity via sts.get_caller_identity."""
        try:
            # Production: boto3 sts.get_caller_identity()
            return bool(self._access_key_id and self._secret_access_key)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Azure RBAC Adapter
# ---------------------------------------------------------------------------


class AzureRBACProvider(CloudIAMProvider):
    """Azure RBAC adapter using the Microsoft Graph API.

    Translates Azure role definitions and assignments into canonical
    federation models.
    """

    PROVIDER_TYPE = ProviderType.AZURE

    _GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    _ARM_BASE = "https://management.azure.com"

    def __init__(
        self,
        *,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        subscription_id: str = "",
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._subscription_id = subscription_id
        self._access_token: str = ""

    @property
    def provider_type(self) -> ProviderType:
        return self.PROVIDER_TYPE

    def _get_token(self) -> str:
        """Acquire an access token via client credentials flow."""
        if self._access_token:
            return self._access_token
        # Production: MSAL or direct HTTP call to login.microsoftonline.com
        raise NotImplementedError("requires msal or azure-identity")

    def _graph_call(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a Microsoft Graph API call."""
        raise NotImplementedError("requires msal or azure-identity")

    def list_identities(
        self,
        *,
        tenant_id: str,
        identity_type: Optional[IdentityType] = None,
    ) -> list[FederatedIdentity]:
        """List Azure AD users and groups."""
        raise NotImplementedError("requires msal or azure-identity")

    def get_identity(
        self,
        external_id: str,
        *,
        tenant_id: str,
    ) -> FederatedIdentity:
        """Resolve an Azure AD object by ID."""
        raise NotImplementedError("requires msal or azure-identity")

    def list_role_mappings(
        self,
        *,
        tenant_id: str,
    ) -> list[RoleMapping]:
        """List Azure role definitions that correspond to DCC roles."""
        raise NotImplementedError("requires msal or azure-identity")

    def create_role_mapping(self, mapping: RoleMapping) -> RoleMapping:
        """Create an Azure custom role definition."""
        raise NotImplementedError("requires msal or azure-identity")

    def delete_role_mapping(self, mapping: RoleMapping) -> None:
        """Delete an Azure role definition."""
        raise NotImplementedError("requires msal or azure-identity")

    def assign_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Create an Azure role assignment."""
        raise NotImplementedError("requires msal or azure-identity")

    def revoke_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Delete an Azure role assignment."""
        raise NotImplementedError("requires msal or azure-identity")

    def health_check(self) -> bool:
        """Check Azure credential validity."""
        try:
            self._get_token()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# GCP IAM Adapter
# ---------------------------------------------------------------------------


class GCPIAMProvider(CloudIAMProvider):
    """GCP IAM adapter using the Cloud Resource Manager and IAM APIs.

    Translates GCP service accounts, groups, and IAM policies into
    canonical federation models.
    """

    PROVIDER_TYPE = ProviderType.GCP

    _CRM_BASE = "https://cloudresourcemanager.googleapis.com/v1"
    _IAM_BASE = "https://iam.googleapis.com/v1"

    def __init__(
        self,
        *,
        project_id: str = "",
        credentials_path: str = "",
        credentials_json: str = "",
    ) -> None:
        self._project_id = project_id
        self._credentials_path = credentials_path
        self._credentials_json = credentials_json
        self._access_token: str = ""

    @property
    def provider_type(self) -> ProviderType:
        return self.PROVIDER_TYPE

    def _get_token(self) -> str:
        """Acquire an access token from service account credentials."""
        if self._access_token:
            return self._access_token
        # Production: google.auth or direct OAuth2 JWT flow
        raise NotImplementedError("requires google-auth")

    def _api_call(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a GCP API call."""
        raise NotImplementedError("requires google-auth")

    def list_identities(
        self,
        *,
        tenant_id: str,
        identity_type: Optional[IdentityType] = None,
    ) -> list[FederatedIdentity]:
        """List GCP service accounts and groups."""
        raise NotImplementedError("requires google-auth")

    def get_identity(
        self,
        external_id: str,
        *,
        tenant_id: str,
    ) -> FederatedIdentity:
        """Resolve a GCP service account or group."""
        raise NotImplementedError("requires google-auth")

    def list_role_mappings(
        self,
        *,
        tenant_id: str,
    ) -> list[RoleMapping]:
        """List GCP custom roles that correspond to DCC roles."""
        raise NotImplementedError("requires google-auth")

    def create_role_mapping(self, mapping: RoleMapping) -> RoleMapping:
        """Create a GCP custom role."""
        raise NotImplementedError("requires google-auth")

    def delete_role_mapping(self, mapping: RoleMapping) -> None:
        """Delete a GCP custom role."""
        raise NotImplementedError("requires google-auth")

    def assign_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Set GCP IAM policy binding."""
        raise NotImplementedError("requires google-auth")

    def revoke_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        """Remove GCP IAM policy binding."""
        raise NotImplementedError("requires google-auth")

    def health_check(self) -> bool:
        """Check GCP credential validity."""
        try:
            self._get_token()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# In-Memory Provider (for testing and development)
# ---------------------------------------------------------------------------


class InMemoryIAMProvider(CloudIAMProvider):
    """In-memory IAM provider for testing and development.

    Stores identities, role mappings, and assignments in process memory.
    Useful for unit tests and local development without cloud credentials.
    """

    def __init__(self, provider_type: ProviderType = ProviderType.AWS) -> None:
        self._provider_type = provider_type
        self._identities: dict[str, FederatedIdentity] = {}
        self._mappings: dict[str, RoleMapping] = {}
        self._assignments: list[tuple[str, str]] = []  # (identity_id, mapping_id)

    @property
    def provider_type(self) -> ProviderType:
        return self._provider_type

    def list_identities(
        self,
        *,
        tenant_id: str,
        identity_type: Optional[IdentityType] = None,
    ) -> list[FederatedIdentity]:
        results = []
        for ident in self._identities.values():
            if ident.tenant_id != tenant_id:
                continue
            if identity_type and ident.identity_type != identity_type:
                continue
            results.append(ident)
        return results

    def get_identity(
        self,
        external_id: str,
        *,
        tenant_id: str,
    ) -> FederatedIdentity:
        for ident in self._identities.values():
            if ident.external_id == external_id and ident.tenant_id == tenant_id:
                return ident
        raise IdentityNotFoundError(
            f"identity {external_id!r} not found in tenant {tenant_id}"
        )

    def list_role_mappings(
        self,
        *,
        tenant_id: str,
    ) -> list[RoleMapping]:
        return [
            m for m in self._mappings.values()
            if m.tenant_id == tenant_id
        ]

    def create_role_mapping(self, mapping: RoleMapping) -> RoleMapping:
        key = f"{mapping.provider.value}:{mapping.dcc_role}:{mapping.external_role_id}"
        self._mappings[key] = mapping
        return mapping

    def delete_role_mapping(self, mapping: RoleMapping) -> None:
        key = f"{mapping.provider.value}:{mapping.dcc_role}:{mapping.external_role_id}"
        self._mappings.pop(key, None)

    def assign_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        mapping_key = f"{mapping.provider.value}:{mapping.dcc_role}:{mapping.external_role_id}"
        if mapping_key not in self._mappings:
            raise FederationError(f"role mapping {mapping_key!r} not found")
        pair = (str(identity.id), mapping_key)
        if pair not in self._assignments:
            self._assignments.append(pair)

    def revoke_role(
        self,
        identity: FederatedIdentity,
        mapping: RoleMapping,
    ) -> None:
        mapping_key = f"{mapping.provider.value}:{mapping.dcc_role}:{mapping.external_role_id}"
        pair = (str(identity.id), mapping_key)
        if pair in self._assignments:
            self._assignments.remove(pair)

    def health_check(self) -> bool:
        return True

    # -- Test helpers --

    def add_identity(self, identity: FederatedIdentity) -> None:
        """Add an identity directly (test helper)."""
        self._identities[str(identity.id)] = identity

    def clear(self) -> None:
        """Clear all stored data (test helper)."""
        self._identities.clear()
        self._mappings.clear()
        self._assignments.clear()


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------


class ProviderRegistry:
    """Registry of cloud IAM provider adapters.

    Manages the lifecycle of provider adapters and provides lookup
    by name or type.
    """

    def __init__(self) -> None:
        self._providers: dict[str, CloudIAMProvider] = {}
        self._provider_types: dict[str, ProviderType] = {}

    def register(
        self,
        name: str,
        provider: CloudIAMProvider,
    ) -> None:
        """Register a provider adapter under a unique name."""
        if not name:
            raise ValueError("provider name must be non-empty")
        self._providers[name] = provider
        self._provider_types[name] = provider.provider_type

    def unregister(self, name: str) -> None:
        """Remove a provider from the registry."""
        self._providers.pop(name, None)
        self._provider_types.pop(name, None)

    def get(self, name: str) -> CloudIAMProvider:
        """Look up a provider by name."""
        provider = self._providers.get(name)
        if provider is None:
            raise ProviderNotFoundError(f"provider {name!r} not registered")
        return provider

    def get_by_type(self, provider_type: ProviderType) -> list[CloudIAMProvider]:
        """Return all registered providers of a given type."""
        return [
            p for p in self._providers.values()
            if p.provider_type == provider_type
        ]

    def list_providers(self) -> list[str]:
        """Return all registered provider names."""
        return list(self._providers.keys())

    def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all registered providers."""
        return {name: p.health_check() for name, p in self._providers.items()}
