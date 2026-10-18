"""Base classes for cloud provider compliance scanning."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class ProviderComplianceStatus(str, Enum):
    """Compliance status for a provider check."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass
class ProviderComplianceResult:
    """Result of a single provider compliance check."""
    check_id: str
    provider: str
    name: str
    status: ProviderComplianceStatus
    severity: str
    category: str
    detail: str = ""
    resource_id: str = ""
    resource_type: str = ""
    remediation_hint: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "provider": self.provider,
            "name": self.name,
            "status": self.status.value,
            "severity": self.severity,
            "category": self.category,
            "detail": self.detail,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "remediation_hint": self.remediation_hint,
            "evaluated_at": self.evaluated_at.isoformat(),
            "metadata": self.metadata,
        }


class CloudProviderCompliance(Protocol):
    """Protocol for cloud provider compliance modules."""

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        ...

    def get_compliance_checks(self) -> list[dict[str, Any]]:
        """Return all compliance checks for this provider."""
        ...

    def evaluate(self, resource: dict[str, Any]) -> ProviderComplianceResult:
        """Evaluate a single resource against provider compliance checks."""
        ...

    def evaluate_all(self, resources: list[dict[str, Any]]) -> list[ProviderComplianceResult]:
        """Evaluate all resources against provider compliance checks."""
        ...
