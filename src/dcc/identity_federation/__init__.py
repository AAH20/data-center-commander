"""Identity federation engine for Data Center Commander.

Provides cross-cloud IAM federation, SSO connection management,
RBAC synchronization, and access review campaigns.

Modules
-------
- :mod:`dcc.identity_federation.models` — Core data models
- :mod:`dcc.identity_federation.providers` — Cloud IAM provider adapters
- :mod:`dcc.identity_federation.sync` — RBAC synchronization engine
- :mod:`dcc.identity_federation.sso` — SSO connection management
- :mod:`dcc.identity_federation.reviews` — Access review engine
"""
from __future__ import annotations

from .models import (
    AccessReview,
    AccessReviewError,
    AccessReviewItem,
    FederationError,
    FederatedIdentity,
    FederationProvider,
    IdentityNotFoundError,
    IdentityType,
    ProviderNotFoundError,
    ProviderType,
    ReviewDecision,
    ReviewStatus,
    RoleMapping,
    RoleMappingError,
    SSOConnection,
    SSOMetadataError,
    SyncConflictError,
    SyncDirection,
    SyncResult,
    SyncStatus,
    compute_identity_hash,
    default_review_due_date,
    generate_federation_id,
)
from .providers import (
    AWSIAMProvider,
    AzureRBACProvider,
    CloudIAMProvider,
    GCPIAMProvider,
    InMemoryIAMProvider,
    ProviderRegistry,
)
from .sync import RBACSyncEngine, SyncConfig
from .sso import (
    OIDCDiscoveryDocument,
    SAMLMetadata,
    SSOConnectionManager,
    fetch_oidc_discovery,
    parse_saml_metadata,
)
from .reviews import AccessReviewEngine, ReviewConfig

__all__ = [
    # Models
    "AccessReview",
    "AccessReviewError",
    "AccessReviewItem",
    "FederationError",
    "FederatedIdentity",
    "FederationProvider",
    "IdentityNotFoundError",
    "IdentityType",
    "ProviderNotFoundError",
    "ProviderType",
    "ReviewDecision",
    "ReviewStatus",
    "RoleMapping",
    "RoleMappingError",
    "SSOConnection",
    "SSOMetadataError",
    "SyncConflictError",
    "SyncDirection",
    "SyncResult",
    "SyncStatus",
    "compute_identity_hash",
    "default_review_due_date",
    "generate_federation_id",
    # Providers
    "AWSIAMProvider",
    "AzureRBACProvider",
    "CloudIAMProvider",
    "GCPIAMProvider",
    "InMemoryIAMProvider",
    "ProviderRegistry",
    # Sync
    "RBACSyncEngine",
    "SyncConfig",
    # SSO
    "OIDCDiscoveryDocument",
    "SAMLMetadata",
    "SSOConnectionManager",
    "fetch_oidc_discovery",
    "parse_saml_metadata",
    # Reviews
    "AccessReviewEngine",
    "ReviewConfig",
]
