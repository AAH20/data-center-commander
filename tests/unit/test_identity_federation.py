"""Tests for the identity federation engine."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dcc.identity_federation import (
    AccessReviewEngine,
    AccessReviewError,
    AccessReviewItem,
    AWSIAMProvider,
    AzureRBACProvider,
    CloudIAMProvider,
    FederationError,
    FederatedIdentity,
    GCPIAMProvider,
    IdentityNotFoundError,
    IdentityType,
    InMemoryIAMProvider,
    ProviderNotFoundError,
    ProviderRegistry,
    ProviderType,
    RBACSyncEngine,
    ReviewConfig,
    ReviewDecision,
    ReviewStatus,
    RoleMapping,
    SSOConnection,
    SSOConnectionManager,
    SSOMetadataError,
    SyncConfig,
    SyncDirection,
    SyncStatus,
    parse_saml_metadata,
    fetch_oidc_discovery,
)
from dcc.identity_federation.models import (
    AccessReview,
    FederationProvider,
    SyncResult,
    default_review_due_date,
    generate_federation_id,
    compute_identity_hash,
)
from dcc.security.authz import Role, Permission, create_default_roles


# ---------------------------------------------------------------------------
# Models tests
# ---------------------------------------------------------------------------


class TestFederatedIdentity:
    def test_create_identity(self):
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/test-user",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            display_name="Test User",
            email="test@example.com",
            tenant_id="12345678-1234-1234-1234-123456789012",
        )
        assert identity.qualified_name == "aws:user:arn:aws:iam::123456789012:user/test-user"

    def test_empty_external_id_raises(self):
        with pytest.raises(ValueError, match="external_id"):
            FederatedIdentity(
                id=uuid4(),
                external_id="",
                provider=ProviderType.AWS,
                identity_type=IdentityType.USER,
            )

    def test_invalid_tenant_id_raises(self):
        with pytest.raises(ValueError, match="UUID"):
            FederatedIdentity(
                id=uuid4(),
                external_id="arn:aws:iam::123456789012:user/test",
                provider=ProviderType.AWS,
                identity_type=IdentityType.USER,
                tenant_id="not-a-uuid",
            )


class TestRoleMapping:
    def test_create_mapping(self):
        mapping = RoleMapping(
            dcc_role="operator",
            provider=ProviderType.AWS,
            external_role_id="arn:aws:iam::123456789012:role/DCC-operator",
            external_role_name="DCC-operator",
            tenant_id="12345678-1234-1234-1234-123456789012",
        )
        assert mapping.dcc_role == "operator"
        assert mapping.provider == ProviderType.AWS

    def test_empty_dcc_role_raises(self):
        with pytest.raises(ValueError, match="dcc_role"):
            RoleMapping(
                dcc_role="",
                provider=ProviderType.AWS,
                external_role_id="arn:aws:iam::123456789012:role/test",
            )


class TestAccessReview:
    def test_review_progress(self):
        review = AccessReview(
            name="test-review",
            tenant_id="12345678-1234-1234-1234-123456789012",
        )
        assert review.progress == 0.0

        # Add items
        review.items = [
            AccessReviewItem(status=ReviewStatus.COMPLETED),
            AccessReviewItem(status=ReviewStatus.PENDING),
            AccessReviewItem(status=ReviewStatus.PENDING),
        ]
        assert review.progress == pytest.approx(1 / 3)

    def test_review_overdue(self):
        review = AccessReview(
            name="overdue-review",
            tenant_id="12345678-1234-1234-1234-123456789012",
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert review.is_overdue

        review.status = ReviewStatus.COMPLETED
        assert not review.is_overdue

    def test_pending_items(self):
        review = AccessReview(
            name="test",
            tenant_id="12345678-1234-1234-1234-123456789012",
        )
        review.items = [
            AccessReviewItem(status=ReviewStatus.PENDING),
            AccessReviewItem(status=ReviewStatus.COMPLETED),
            AccessReviewItem(status=ReviewStatus.PENDING),
        ]
        assert len(review.pending_items) == 2


class TestSyncResult:
    def test_total_changes(self):
        result = SyncResult(
            roles_created=2,
            roles_updated=1,
            roles_removed=3,
            assignments_created=10,
            assignments_removed=5,
        )
        assert result.total_changes == 21

    def test_duration(self):
        result = SyncResult()
        assert result.duration_seconds is None

        result.completed_at = result.started_at + timedelta(seconds=30)
        assert result.duration_seconds == pytest.approx(30.0)


class TestUtilityFunctions:
    def test_generate_federation_id(self):
        id1 = generate_federation_id()
        id2 = generate_federation_id()
        assert id1 != id2

    def test_compute_identity_hash(self):
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/test",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
        )
        hash1 = compute_identity_hash(identity)
        hash2 = compute_identity_hash(identity)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_default_review_due_date(self):
        due = default_review_due_date(30)
        now = datetime.now(timezone.utc)
        assert due > now
        delta = due - now
        assert 29 <= delta.days <= 30


# ---------------------------------------------------------------------------
# Provider tests
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = InMemoryIAMProvider(ProviderType.AWS)
        registry.register("aws-test", provider)

        assert registry.get("aws-test") is provider
        assert "aws-test" in registry.list_providers()

    def test_get_nonexistent_raises(self):
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get("nonexistent")

    def test_get_by_type(self):
        registry = ProviderRegistry()
        aws = InMemoryIAMProvider(ProviderType.AWS)
        azure = InMemoryIAMProvider(ProviderType.AZURE)
        registry.register("aws", aws)
        registry.register("azure", azure)

        aws_providers = registry.get_by_type(ProviderType.AWS)
        assert len(aws_providers) == 1
        assert aws_providers[0] is aws

    def test_health_check_all(self):
        registry = ProviderRegistry()
        registry.register("aws", InMemoryIAMProvider(ProviderType.AWS))
        registry.register("azure", InMemoryIAMProvider(ProviderType.AZURE))

        results = registry.health_check_all()
        assert results == {"aws": True, "azure": True}

    def test_unregister(self):
        registry = ProviderRegistry()
        registry.register("test", InMemoryIAMProvider())
        registry.unregister("test")
        assert registry.list_providers() == []


class TestInMemoryIAMProvider:
    def setup_method(self):
        self.provider = InMemoryIAMProvider(ProviderType.AWS)
        self.tenant_id = "12345678-1234-1234-1234-123456789012"

    def test_add_and_list_identities(self):
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/alice",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        self.provider.add_identity(identity)

        identities = self.provider.list_identities(tenant_id=self.tenant_id)
        assert len(identities) == 1
        assert identities[0].external_id == "arn:aws:iam::123456789012:user/alice"

    def test_list_identities_filter_by_type(self):
        user = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/alice",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        sa = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/sa",
            provider=ProviderType.AWS,
            identity_type=IdentityType.SERVICE_ACCOUNT,
            tenant_id=self.tenant_id,
        )
        self.provider.add_identity(user)
        self.provider.add_identity(sa)

        users = self.provider.list_identities(
            tenant_id=self.tenant_id,
            identity_type=IdentityType.USER,
        )
        assert len(users) == 1
        assert users[0].identity_type == IdentityType.USER

    def test_get_identity(self):
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/bob",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        self.provider.add_identity(identity)

        found = self.provider.get_identity(
            "arn:aws:iam::123456789012:user/bob",
            tenant_id=self.tenant_id,
        )
        assert found.id == identity.id

    def test_get_identity_not_found(self):
        with pytest.raises(IdentityNotFoundError):
            self.provider.get_identity(
                "arn:aws:iam::123456789012:user/ghost",
                tenant_id=self.tenant_id,
            )

    def test_role_mapping_crud(self):
        mapping = RoleMapping(
            dcc_role="operator",
            provider=ProviderType.AWS,
            external_role_id="arn:aws:iam::123456789012:role/DCC-operator",
            tenant_id=self.tenant_id,
        )
        self.provider.create_role_mapping(mapping)

        mappings = self.provider.list_role_mappings(tenant_id=self.tenant_id)
        assert len(mappings) == 1

        self.provider.delete_role_mapping(mapping)
        mappings = self.provider.list_role_mappings(tenant_id=self.tenant_id)
        assert len(mappings) == 0

    def test_assign_and_revoke_role(self):
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/carol",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        self.provider.add_identity(identity)

        mapping = RoleMapping(
            dcc_role="viewer",
            provider=ProviderType.AWS,
            external_role_id="arn:aws:iam::123456789012:role/DCC-viewer",
            tenant_id=self.tenant_id,
        )
        self.provider.create_role_mapping(mapping)

        self.provider.assign_role(identity, mapping)
        # Verify assignment was recorded
        assert len(self.provider._assignments) == 1

        self.provider.revoke_role(identity, mapping)
        assert len(self.provider._assignments) == 0

    def test_health_check(self):
        assert self.provider.health_check() is True

    def test_clear(self):
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/dave",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        self.provider.add_identity(identity)
        self.provider.clear()
        assert self.provider.list_identities(tenant_id=self.tenant_id) == []


# ---------------------------------------------------------------------------
# Sync engine tests
# ---------------------------------------------------------------------------


class TestRBACSyncEngine:
    def setup_method(self):
        self.registry = ProviderRegistry()
        self.provider = InMemoryIAMProvider(ProviderType.AWS)
        self.registry.register("aws-test", self.provider)
        self.engine = RBACSyncEngine(self.registry)
        self.tenant_id = "12345678-1234-1234-1234-123456789012"

    def test_sync_push_dry_run(self):
        config = SyncConfig(
            provider_name="aws-test",
            tenant_id=self.tenant_id,
            direction=SyncDirection.PUSH,
            dry_run=True,
        )
        result = self.engine.sync(config)
        assert result.status == SyncStatus.COMPLETED
        assert result.total_changes > 0  # Should create default roles

    def test_sync_push(self):
        config = SyncConfig(
            provider_name="aws-test",
            tenant_id=self.tenant_id,
            direction=SyncDirection.PUSH,
            dry_run=False,
        )
        result = self.engine.sync(config)
        assert result.status == SyncStatus.COMPLETED
        assert result.roles_created > 0

        # Verify roles were created in the provider
        mappings = self.provider.list_role_mappings(tenant_id=self.tenant_id)
        assert len(mappings) > 0

    def test_sync_with_custom_roles(self):
        custom_role = Role(
            name="custom-role",
            permissions=frozenset([Permission("read", "custom")]),
        )
        self.engine.add_dcc_role(custom_role)

        config = SyncConfig(
            provider_name="aws-test",
            tenant_id=self.tenant_id,
            direction=SyncDirection.PUSH,
            dry_run=True,
        )
        result = self.engine.sync(config)
        assert result.status == SyncStatus.COMPLETED

    def test_sync_invalid_conflict_resolution(self):
        with pytest.raises(ValueError, match="conflict_resolution"):
            SyncConfig(
                provider_name="aws-test",
                tenant_id=self.tenant_id,
                conflict_resolution="invalid",
            )

    def test_sync_nonexistent_provider(self):
        config = SyncConfig(
            provider_name="nonexistent",
            tenant_id=self.tenant_id,
        )
        result = self.engine.sync(config)
        assert result.status == SyncStatus.FAILED
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# SSO tests
# ---------------------------------------------------------------------------


class TestSAMLMetadata:
    def test_parse_valid_metadata(self):
        xml = """<?xml version="1.0"?>
        <md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
                             entityID="https://idp.example.com/metadata">
          <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
            <md:KeyDescriptor use="signing">
              <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:X509Data>
                  <ds:X509Certificate>MIIDXTCCAkWgAwIBAgIJAKoK...</ds:X509Certificate>
                </ds:X509Data>
              </ds:KeyInfo>
            </md:KeyDescriptor>
            <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                                    Location="https://idp.example.com/sso"/>
            <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                                   Location="https://idp.example.com/slo"/>
          </md:IDPSSODescriptor>
        </md:EntityDescriptor>
        """
        metadata = parse_saml_metadata(xml)
        assert metadata.entity_id == "https://idp.example.com/metadata"
        assert metadata.sso_url == "https://idp.example.com/sso"
        assert metadata.slo_url == "https://idp.example.com/slo"
        assert len(metadata.signing_certificates) == 1

    def test_parse_invalid_xml(self):
        with pytest.raises(SSOMetadataError):
            parse_saml_metadata("not xml at all")

    def test_parse_missing_entity_id(self):
        xml = """<?xml version="1.0"?>
        <md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata">
          <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
          </md:IDPSSODescriptor>
        </md:EntityDescriptor>
        """
        with pytest.raises(SSOMetadataError, match="entityID"):
            parse_saml_metadata(xml)


class TestSSOConnectionManager:
    def setup_method(self):
        self.manager = SSOConnectionManager()
        self.tenant_id = "12345678-1234-1234-1234-123456789012"

    def test_create_connection(self):
        conn = self.manager.create_connection(
            name="okta-prod",
            protocol="saml",
            provider_type=ProviderType.OKTA,
            entity_id="http://www.okta.com/exk123",
            sso_url="https://example.okta.com/app/dcc/sso/saml",
            tenant_id=self.tenant_id,
        )
        assert conn.name == "okta-prod"
        assert conn.protocol == "saml"
        assert conn.tenant_id == self.tenant_id

    def test_get_connection(self):
        conn = self.manager.create_connection(
            name="test",
            protocol="oidc",
            provider_type=ProviderType.AUTH0,
        )
        found = self.manager.get_connection(conn.id)
        assert found.id == conn.id

    def test_get_nonexistent_connection(self):
        with pytest.raises(SSOMetadataError):
            self.manager.get_connection(uuid4())

    def test_list_connections(self):
        self.manager.create_connection(
            name="conn1",
            protocol="saml",
            provider_type=ProviderType.OKTA,
            tenant_id=self.tenant_id,
        )
        self.manager.create_connection(
            name="conn2",
            protocol="oidc",
            provider_type=ProviderType.AUTH0,
            tenant_id=self.tenant_id,
        )
        self.manager.create_connection(
            name="conn3",
            protocol="saml",
            provider_type=ProviderType.GENERIC_SAML,
            tenant_id="87654321-4321-4321-4321-210987654321",
        )

        all_conns = self.manager.list_connections()
        assert len(all_conns) == 3

        tenant_conns = self.manager.list_connections(tenant_id=self.tenant_id)
        assert len(tenant_conns) == 2

        saml_conns = self.manager.list_connections(
            provider_type=ProviderType.OKTA,
        )
        assert len(saml_conns) == 1

    def test_update_connection(self):
        conn = self.manager.create_connection(
            name="test",
            protocol="saml",
            provider_type=ProviderType.OKTA,
        )
        self.manager.update_connection(conn.id, name="updated")
        assert conn.name == "updated"

    def test_delete_connection(self):
        conn = self.manager.create_connection(
            name="test",
            protocol="saml",
            provider_type=ProviderType.OKTA,
        )
        self.manager.delete_connection(conn.id)
        with pytest.raises(SSOMetadataError):
            self.manager.get_connection(conn.id)

    def test_validate_connection(self):
        conn = self.manager.create_connection(
            name="test",
            protocol="saml",
            provider_type=ProviderType.OKTA,
            entity_id="https://idp.example.com",
            sso_url="https://idp.example.com/sso",
            metadata={"signing_certificates": ["MIIDXTCCAkWgAwIBAgIJAKoK..."]},
        )
        # Manually set signing_certificates for validation
        object.__setattr__(conn, "signing_certificates", ["MIIDXTCCAkWgAwIBAgIJAKoK..."])
        result = self.manager.validate_connection(conn.id)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_connection_missing_fields(self):
        conn = self.manager.create_connection(
            name="test",
            protocol="saml",
            provider_type=ProviderType.OKTA,
        )
        result = self.manager.validate_connection(conn.id)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_invalid_protocol(self):
        with pytest.raises(ValueError, match="protocol"):
            self.manager.create_connection(
                name="test",
                protocol="invalid",
                provider_type=ProviderType.OKTA,
            )


# ---------------------------------------------------------------------------
# Access review tests
# ---------------------------------------------------------------------------


class TestAccessReviewEngine:
    def setup_method(self):
        self.engine = AccessReviewEngine()
        self.tenant_id = "12345678-1234-1234-1234-123456789012"

    def test_create_review(self):
        config = ReviewConfig(
            name="Q4-2026-review",
            tenant_id=self.tenant_id,
            review_period_days=30,
        )
        review = self.engine.create_review(config)
        assert review.name == "Q4-2026-review"
        assert review.status == ReviewStatus.PENDING
        assert review.due_date is not None

    def test_get_review(self):
        config = ReviewConfig(name="test", tenant_id=self.tenant_id)
        review = self.engine.create_review(config)
        found = self.engine.get_review(review.id)
        assert found.id == review.id

    def test_get_nonexistent_review(self):
        with pytest.raises(AccessReviewError):
            self.engine.get_review(uuid4())

    def test_list_reviews(self):
        self.engine.create_review(ReviewConfig(name="r1", tenant_id=self.tenant_id))
        self.engine.create_review(ReviewConfig(name="r2", tenant_id=self.tenant_id))
        self.engine.create_review(ReviewConfig(
            name="r3",
            tenant_id="87654321-4321-4321-4321-210987654321",
        ))

        all_reviews = self.engine.list_reviews()
        assert len(all_reviews) == 3

        tenant_reviews = self.engine.list_reviews(tenant_id=self.tenant_id)
        assert len(tenant_reviews) == 2

    def test_cancel_review(self):
        review = self.engine.create_review(
            ReviewConfig(name="test", tenant_id=self.tenant_id)
        )
        cancelled = self.engine.cancel_review(review.id)
        assert cancelled.status == ReviewStatus.CANCELLED
        assert cancelled.completed_at is not None

    def test_add_review_item(self):
        review = self.engine.create_review(
            ReviewConfig(name="test", tenant_id=self.tenant_id)
        )
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/alice",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        item = self.engine.add_review_item(
            review.id,
            identity=identity,
            role="operator",
            resource="arn:aws:iam::123456789012:role/DCC-operator",
        )
        assert item.role == "operator"
        assert item.status == ReviewStatus.PENDING

    def test_submit_decision(self):
        review = self.engine.create_review(
            ReviewConfig(name="test", tenant_id=self.tenant_id)
        )
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/bob",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        item = self.engine.add_review_item(
            review.id,
            identity=identity,
            role="viewer",
        )
        updated = self.engine.submit_decision(
            review.id,
            item.id,
            decision=ReviewDecision.APPROVE,
            reviewed_by="admin@example.com",
            justification="Still needed for project",
        )
        assert updated.decision == ReviewDecision.APPROVE
        assert updated.status == ReviewStatus.COMPLETED
        assert updated.reviewed_by == "admin@example.com"

    def test_submit_decision_completes_review(self):
        review = self.engine.create_review(
            ReviewConfig(name="test", tenant_id=self.tenant_id)
        )
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/carol",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        item = self.engine.add_review_item(
            review.id,
            identity=identity,
            role="viewer",
        )
        self.engine.submit_decision(
            review.id,
            item.id,
            decision=ReviewDecision.APPROVE,
            reviewed_by="admin@example.com",
        )
        # Review should be auto-completed when all items are done
        updated_review = self.engine.get_review(review.id)
        assert updated_review.status == ReviewStatus.COMPLETED

    def test_generate_report(self):
        review = self.engine.create_review(
            ReviewConfig(name="test", tenant_id=self.tenant_id)
        )
        identity = FederatedIdentity(
            id=uuid4(),
            external_id="arn:aws:iam::123456789012:user/dave",
            provider=ProviderType.AWS,
            identity_type=IdentityType.USER,
            tenant_id=self.tenant_id,
        )
        item = self.engine.add_review_item(
            review.id,
            identity=identity,
            role="viewer",
        )
        self.engine.submit_decision(
            review.id,
            item.id,
            decision=ReviewDecision.APPROVE,
            reviewed_by="admin@example.com",
        )

        report = self.engine.generate_report(review.id)
        assert report["review_id"] == str(review.id)
        assert report["total_items"] == 1
        assert report["completed_items"] == 1
        assert report["decisions"]["approve"] == 1

    def test_get_overdue_reviews(self):
        # Create an overdue review
        review = AccessReview(
            name="overdue",
            tenant_id=self.tenant_id,
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        self.engine._reviews[review.id] = review

        overdue = self.engine.get_overdue_reviews(tenant_id=self.tenant_id)
        assert len(overdue) == 1
        assert overdue[0].name == "overdue"

    def test_add_review_items_from_mappings(self):
        review = self.engine.create_review(
            ReviewConfig(name="test", tenant_id=self.tenant_id)
        )
        identities = [
            FederatedIdentity(
                id=uuid4(),
                external_id="arn:aws:iam::123456789012:user/eve",
                provider=ProviderType.AWS,
                identity_type=IdentityType.USER,
                tenant_id=self.tenant_id,
            ),
            FederatedIdentity(
                id=uuid4(),
                external_id="arn:aws:iam::123456789012:user/frank",
                provider=ProviderType.AWS,
                identity_type=IdentityType.USER,
                tenant_id=self.tenant_id,
            ),
        ]
        mappings = [
            RoleMapping(
                dcc_role="viewer",
                provider=ProviderType.AWS,
                external_role_id="arn:aws:iam::123456789012:role/DCC-viewer",
                tenant_id=self.tenant_id,
            ),
            RoleMapping(
                dcc_role="operator",
                provider=ProviderType.AWS,
                external_role_id="arn:aws:iam::123456789012:role/DCC-operator",
                tenant_id=self.tenant_id,
            ),
        ]
        items = self.engine.add_review_items_from_mappings(
            review.id,
            identities=identities,
            mappings=mappings,
        )
        assert len(items) == 4  # 2 identities x 2 mappings

    def test_invalid_reviewer_count(self):
        with pytest.raises(ValueError, match="reviewer_count"):
            ReviewConfig(reviewer_count=0)
