"""Access review engine.

Manages the full lifecycle of access reviews: creation, assignment,
review, and reporting. Supports automated review campaigns with
configurable review periods and escalation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from .models import (
    AccessReview,
    AccessReviewError,
    AccessReviewItem,
    FederatedIdentity,
    IdentityType,
    ReviewDecision,
    ReviewStatus,
    RoleMapping,
    default_review_due_date,
)
from ..security.tenant import parse_tenant_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Review configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ReviewConfig:
    """Configuration for an access review campaign.

    Attributes
    ----------
    name:
        Human-readable review name.
    tenant_id:
        The tenant this review belongs to.
    review_period_days:
        Number of days before the review is due.
    auto_approve_if_unused:
        If True, automatically approve identities with no recent activity.
    unused_threshold_days:
        Number of days of inactivity before auto-approval.
    escalate_if_overdue:
        If True, escalate overdue reviews to administrators.
    reviewer_count:
        Number of reviewers required per item.
    identity_types:
        Which identity types to include in the review.
    roles:
        Specific roles to review (empty = all roles).
    resources:
        Specific resources to review (empty = all resources).
    """

    name: str = ""
    tenant_id: str = ""
    review_period_days: int = 30
    auto_approve_if_unused: bool = False
    unused_threshold_days: int = 90
    escalate_if_overdue: bool = True
    reviewer_count: int = 1
    identity_types: list[IdentityType] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.tenant_id:
            object.__setattr__(self, "tenant_id", parse_tenant_id(self.tenant_id))
        if self.reviewer_count < 1:
            raise ValueError("reviewer_count must be at least 1")


# ---------------------------------------------------------------------------
# Review engine
# ---------------------------------------------------------------------------


class AccessReviewEngine:
    """Engine for managing access review campaigns.

    Usage
    -----
    .. code-block:: python

        engine = AccessReviewEngine()
        config = ReviewConfig(
            name="Q4-2026-access-review",
            tenant_id="...",
            review_period_days=30,
        )
        review = engine.create_review(config)
        engine.assign_reviewers(review.id)
        # ... reviewers complete their work ...
        report = engine.generate_report(review.id)
    """

    def __init__(self) -> None:
        self._reviews: dict[UUID, AccessReview] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_review(self, config: ReviewConfig) -> AccessReview:
        """Create a new access review campaign.

        Parameters
        ----------
        config:
            The review configuration.

        Returns
        -------
        AccessReview
            The created review.
        """
        review = AccessReview(
            id=uuid4(),
            name=config.name,
            tenant_id=config.tenant_id,
            status=ReviewStatus.PENDING,
            due_date=default_review_due_date(config.review_period_days),
            created_by="system",
            metadata={
                "review_period_days": config.review_period_days,
                "auto_approve_if_unused": config.auto_approve_if_unused,
                "unused_threshold_days": config.unused_threshold_days,
                "escalate_if_overdue": config.escalate_if_overdue,
                "reviewer_count": config.reviewer_count,
            },
        )
        self._reviews[review.id] = review
        logger.info("created access review %s (%s)", review.id, review.name)
        return review

    def get_review(self, review_id: UUID) -> AccessReview:
        """Retrieve a review by ID."""
        review = self._reviews.get(review_id)
        if review is None:
            raise AccessReviewError(f"review {review_id} not found")
        return review

    def list_reviews(
        self,
        *,
        tenant_id: str = "",
        status: Optional[ReviewStatus] = None,
    ) -> list[AccessReview]:
        """List access reviews, optionally filtered."""
        results = []
        for review in self._reviews.values():
            if tenant_id and review.tenant_id != tenant_id:
                continue
            if status and review.status != status:
                continue
            results.append(review)
        return results

    def cancel_review(self, review_id: UUID) -> AccessReview:
        """Cancel an access review."""
        review = self.get_review(review_id)
        review.status = ReviewStatus.CANCELLED
        review.completed_at = datetime.now(timezone.utc)
        logger.info("cancelled access review %s", review_id)
        return review

    # ------------------------------------------------------------------
    # Review items
    # ------------------------------------------------------------------

    def add_review_item(
        self,
        review_id: UUID,
        *,
        identity: FederatedIdentity,
        role: str,
        resource: str = "",
        reviewer_ids: Optional[list[UUID]] = None,
    ) -> AccessReviewItem:
        """Add a review item to an access review.

        Parameters
        ----------
        review_id:
            The review to add the item to.
        identity:
            The identity being reviewed.
        role:
            The DCC role being reviewed.
        resource:
            The resource the role grants access to.
        reviewer_ids:
            List of identity IDs assigned to review this item.

        Returns
        -------
        AccessReviewItem
            The created review item.
        """
        review = self.get_review(review_id)
        item = AccessReviewItem(
            identity=identity,
            role=role,
            resource=resource,
            reviewer_ids=reviewer_ids or [],
        )
        review.items.append(item)
        return item

    def add_review_items_from_mappings(
        self,
        review_id: UUID,
        *,
        identities: list[FederatedIdentity],
        mappings: list[RoleMapping],
        reviewer_ids: Optional[list[UUID]] = None,
    ) -> list[AccessReviewItem]:
        """Bulk-add review items from identities and role mappings.

        Creates a review item for each (identity, mapping) pair.
        """
        items = []
        for identity in identities:
            for mapping in mappings:
                if mapping.provider != identity.provider:
                    continue
                item = self.add_review_item(
                    review_id,
                    identity=identity,
                    role=mapping.dcc_role,
                    resource=mapping.external_role_id,
                    reviewer_ids=reviewer_ids,
                )
                items.append(item)
        return items

    # ------------------------------------------------------------------
    # Reviewer assignment
    # ------------------------------------------------------------------

    def assign_reviewers(
        self,
        review_id: UUID,
        *,
        reviewer_pool: Optional[list[UUID]] = None,
    ) -> None:
        """Assign reviewers to all pending items in a review.

        Parameters
        ----------
        review_id:
            The review to assign reviewers for.
        reviewer_pool:
            Pool of reviewer identity IDs to assign from.
            If None, reviewers must be assigned manually.
        """
        review = self.get_review(review_id)
        if not reviewer_pool:
            logger.warning(
                "no reviewer pool provided for review %s", review_id
            )
            return

        for item in review.items:
            if item.status != ReviewStatus.PENDING:
                continue
            # Simple round-robin assignment
            item.reviewer_ids = reviewer_pool[:]

    # ------------------------------------------------------------------
    # Review decisions
    # ------------------------------------------------------------------

    def submit_decision(
        self,
        review_id: UUID,
        item_id: UUID,
        *,
        decision: ReviewDecision,
        reviewed_by: str,
        justification: str = "",
    ) -> AccessReviewItem:
        """Submit a review decision for a review item.

        Parameters
        ----------
        review_id:
            The review the item belongs to.
        item_id:
            The review item ID.
        decision:
            The review decision (approve, deny, abstain).
        reviewed_by:
            Who is submitting the decision.
        justification:
            Optional justification for the decision.

        Returns
        -------
        AccessReviewItem
            The updated review item.
        """
        review = self.get_review(review_id)
        item = None
        for i in review.items:
            if i.id == item_id:
                item = i
                break
        if item is None:
            raise AccessReviewError(
                f"review item {item_id} not found in review {review_id}"
            )

        item.decision = decision
        item.reviewed_by = reviewed_by
        item.justification = justification
        item.reviewed_at = datetime.now(timezone.utc)
        item.status = ReviewStatus.COMPLETED

        # Check if the entire review is now complete
        if all(
            i.status in (ReviewStatus.COMPLETED, ReviewStatus.CANCELLED)
            for i in review.items
        ):
            review.status = ReviewStatus.COMPLETED
            review.completed_at = datetime.now(timezone.utc)
            logger.info("access review %s completed", review_id)

        return item

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_report(self, review_id: UUID) -> dict[str, Any]:
        """Generate a summary report for an access review.

        Returns
        -------
        dict
            Report data including counts by decision, completion status,
            and overdue information.
        """
        review = self.get_review(review_id)

        decisions: dict[str, int] = {}
        for item in review.items:
            key = item.decision.value
            decisions[key] = decisions.get(key, 0) + 1

        return {
            "review_id": str(review_id),
            "name": review.name,
            "status": review.status.value,
            "progress": review.progress,
            "total_items": len(review.items),
            "completed_items": sum(
                1 for i in review.items
                if i.status == ReviewStatus.COMPLETED
            ),
            "pending_items": len(review.pending_items),
            "decisions": decisions,
            "is_overdue": review.is_overdue,
            "due_date": review.due_date.isoformat() if review.due_date else None,
            "created_at": review.created_at.isoformat(),
            "completed_at": (
                review.completed_at.isoformat()
                if review.completed_at else None
            ),
        }

    def get_overdue_reviews(
        self,
        *,
        tenant_id: str = "",
    ) -> list[AccessReview]:
        """Return all overdue access reviews."""
        return [
            r for r in self.list_reviews(tenant_id=tenant_id)
            if r.is_overdue
        ]
