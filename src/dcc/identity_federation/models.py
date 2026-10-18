"""Core data models for the identity federation engine.

These types represent the canonical internal representation of identities,
role mappings, federation providers, and access reviews. Cloud-specific
adapters translate their native IAM constructs into these models.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional
from uuid import UUID, uuid4

from ..security.authz import Permission, Role
from ..security.tenant import parse_tenant_id


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FederationError(Exception):
    """Base exception for identity federation operations."""


class ProviderNotFoundError(FederationError):
    """Raised when a federation provider is not registered."""


class IdentityNotFoundError(FederationError):
    """Raised when an identity cannot be resolved."""


class RoleMappingError(FederationError):
    """Raised when a role mapping is invalid or conflicts."""


class SSOMetadataError(FederationError):
    """Raised when SSO metadata is invalid or unavailable."""


class AccessReviewError(FederationError):
    """Raised when an access review operation fails."""


class SyncConflictError(FederationError):
    """Raised when RBAC synchronization encounters an unresolvable conflict."""


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ProviderType(str, Enum):
    """Supported cloud IAM provider types."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    OKTA = "okta"
    AUTH0 = "auth0"
    GENERIC_OIDC = "generic_oidc"
    GENERIC_SAML = "generic_saml"


class IdentityType(str, Enum):
    """Types of federated identities."""

    USER = "user"
    GROUP = "group"
    SERVICE_ACCOUNT = "service_account"
    WORKLOAD_IDENTITY = "workload_identity"


class ReviewStatus(str, Enum):
    """Status of an access review."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class ReviewDecision(str, Enum):
    """Decision on an access review item."""

    APPROVE = "approve"
    DENY = "deny"
    ABSTAIN = "abstain"
    NOT_REVIEWED = "not_reviewed"


class SyncDirection(str, Enum):
    """Direction of RBAC synchronization."""

    PUSH = "push"          # DCC -> cloud provider
    PULL = "pull"          # cloud provider -> DCC
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    """Status of a sync operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ---------------------------------------------------------------------------
# Core value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FederatedIdentity:
    """A canonical representation of an identity across cloud providers.

    Attributes
    ----------
    id:
        Unique internal identifier (UUID).
    external_id:
        The provider-specific identifier (e.g. AWS ARN, Azure object ID).
    provider:
        The cloud provider this identity originates from.
    identity_type:
        Whether this is a user, group, service account, or workload identity.
    display_name:
        Human-readable name.
    email:
        Email address, if available.
    tenant_id:
        The tenant this identity belongs to.
    metadata:
        Additional provider-specific attributes.
    """

    id: UUID
    external_id: str
    provider: ProviderType
    identity_type: IdentityType
    display_name: str = ""
    email: str = ""
    tenant_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.external_id:
            raise ValueError("external_id must be non-empty")
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))

    @property
    def qualified_name(self) -> str:
        """Return a globally unique qualified name for this identity."""
        return f"{self.provider.value}:{self.identity_type.value}:{self.external_id}"


@dataclass(frozen=True, slots=True)
class RoleMapping:
    """Maps a DCC role to one or more cloud-provider-specific role ARNs.

    A single DCC role can map to different ARNs in different clouds.
    For example, the DCC ``operator`` role might map to
    ``arn:aws:iam::123456789012:role/DCCOperator`` in AWS and
    ``f45da3b6-...`` (Azure role definition ID) in Azure.

    Attributes
    ----------
    dcc_role:
        The DCC-internal role name.
    provider:
        The cloud provider.
    external_role_id:
        The provider-specific role identifier (ARN, ID, etc.).
    external_role_name:
        Human-readable name in the provider.
    tenant_id:
        The tenant this mapping applies to.
    conditions:
        Optional conditions (e.g. time-bound, IP-restricted).
    """

    dcc_role: str
    provider: ProviderType
    external_role_id: str
    external_role_name: str = ""
    tenant_id: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dcc_role:
            raise ValueError("dcc_role must be non-empty")
        if not self.external_role_id:
            raise ValueError("external_role_id must be non-empty")
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))


@dataclass(frozen=True, slots=True)
class FederationProvider:
    """Configuration for a cloud IAM provider.

    Attributes
    ----------
    name:
        Unique provider name (e.g. ``"aws-prod"``).
    provider_type:
        The type of cloud provider.
    tenant_id:
        The tenant this provider is associated with.
    config:
        Provider-specific configuration (endpoints, credentials refs, etc.).
    enabled:
        Whether this provider is currently active.
    """

    name: str
    provider_type: ProviderType
    tenant_id: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("provider name must be non-empty")
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))


@dataclass(frozen=True, slots=True)
class SSOConnection:
    """Represents a configured SSO connection.

    Attributes
    ----------
    id:
        Unique connection identifier.
    name:
        Human-readable name.
    protocol:
        ``saml`` or ``oidc``.
    provider_type:
        The identity provider type.
    entity_id:
        SAML entity ID or OIDC issuer URL.
    sso_url:
        SAML SSO URL or OIDC authorization endpoint.
    slo_url:
        SAML single logout URL (optional).
    certificate_fingerprint:
        Fingerprint of the signing certificate for validation.
    tenant_id:
        The tenant this connection serves.
    enabled:
        Whether this connection is active.
    """

    id: UUID
    name: str
    protocol: str  # "saml" or "oidc"
    provider_type: ProviderType
    entity_id: str = ""
    sso_url: str = ""
    slo_url: str = ""
    certificate_fingerprint: str = ""
    signing_certificates: list[str] = field(default_factory=list)
    tenant_id: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")
        if self.protocol not in ("saml", "oidc"):
            raise ValueError(f"unsupported SSO protocol: {self.protocol}")
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))


@dataclass(slots=True)
class AccessReviewItem:
    """A single item within an access review.

    Represents one identity's access to one resource/role that needs
    to be reviewed and approved/denied.

    Attributes
    ----------
    id:
        Unique item identifier.
    identity:
        The identity being reviewed.
    role:
        The DCC role being reviewed.
    resource:
        The resource the role grants access to.
    reviewer_ids:
        List of identity IDs assigned to review this item.
    status:
        Current review status.
    decision:
        The review decision.
    reviewed_at:
        When the review was completed.
    reviewed_by:
        Who completed the review.
    justification:
        Optional justification for the decision.
    """

    id: UUID = field(default_factory=uuid4)
    identity: Optional[FederatedIdentity] = None
    role: str = ""
    resource: str = ""
    reviewer_ids: list[UUID] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    decision: ReviewDecision = ReviewDecision.NOT_REVIEWED
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    justification: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccessReview:
    """A complete access review campaign.

    Attributes
    ----------
    id:
        Unique review identifier.
    name:
        Human-readable name.
    tenant_id:
        The tenant this review belongs to.
    status:
        Overall review status.
    items:
        Individual review items.
    created_at:
        When the review was created.
    due_date:
        Deadline for completion.
    started_at:
        When review work began.
    completed_at:
        When the review was completed.
    created_by:
        Who created the review.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    tenant_id: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    items: list[AccessReviewItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))

    @property
    def progress(self) -> float:
        """Return completion percentage (0.0 - 1.0)."""
        if not self.items:
            return 0.0
        reviewed = sum(
            1 for item in self.items
            if item.status in (ReviewStatus.COMPLETED, ReviewStatus.CANCELLED)
        )
        return reviewed / len(self.items)

    @property
    def is_overdue(self) -> bool:
        """Return True if the review is past its due date and not completed."""
        if self.status == ReviewStatus.COMPLETED:
            return False
        if self.due_date is None:
            return False
        return datetime.now(timezone.utc) > self.due_date

    @property
    def pending_items(self) -> list[AccessReviewItem]:
        """Return items still pending review."""
        return [item for item in self.items if item.status == ReviewStatus.PENDING]


@dataclass(slots=True)
class SyncResult:
    """Result of an RBAC synchronization operation.

    Attributes
    ----------
    id:
        Unique sync run identifier.
    provider:
        The provider that was synced.
    direction:
        The sync direction.
    status:
        Overall sync status.
    started_at:
        When the sync started.
    completed_at:
        When the sync finished.
    roles_created:
        Number of roles created.
    roles_updated:
        Number of roles updated.
    roles_removed:
        Number of roles removed.
    assignments_created:
        Number of role assignments created.
    assignments_removed:
        Number of role assignments removed.
    errors:
        List of error messages encountered.
    details:
        Additional sync details.
    """

    id: UUID = field(default_factory=uuid4)
    provider: ProviderType = ProviderType.AWS
    direction: SyncDirection = SyncDirection.PUSH
    status: SyncStatus = SyncStatus.PENDING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    roles_created: int = 0
    roles_updated: int = 0
    roles_removed: int = 0
    assignments_created: int = 0
    assignments_removed: int = 0
    errors: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def total_changes(self) -> int:
        """Return the total number of changes made."""
        return (
            self.roles_created
            + self.roles_updated
            + self.roles_removed
            + self.assignments_created
            + self.assignments_removed
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Return the sync duration in seconds, or None if not completed."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def generate_federation_id() -> UUID:
    """Generate a new unique federation identifier."""
    return uuid4()


def compute_identity_hash(identity: FederatedIdentity) -> str:
    """Compute a stable hash for an identity for deduplication."""
    key = identity.qualified_name
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def default_review_due_date(days: int = 30) -> datetime:
    """Return a default due date *days* from now."""
    return datetime.now(timezone.utc) + timedelta(days=days)
