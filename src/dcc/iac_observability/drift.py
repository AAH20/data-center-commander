"""IaC drift detection: compare desired state vs actual state.

Detects configuration drift between IaC-defined desired state and
the actual runtime state of infrastructure resources. Supports
Terraform state files, CloudFormation stack drift, and Pulumi state.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class DriftType(str, Enum):
    """Types of configuration drift."""

    ADDED = "added"                    # Resource exists in actual but not in desired
    REMOVED = "removed"                # Resource exists in desired but not in actual
    MODIFIED = "modified"              # Resource exists in both but attributes differ
    TAG_DRIFT = "tag_drift"            # Tag changes only
    SIZE_DRIFT = "size_drift"          # Instance size / capacity changes
    NETWORK_DRIFT = "network_drift"    # Security group, subnet, VPC changes
    CREDENTIAL_DRIFT = "credential_drift"  # Key, certificate, or secret changes


class DriftSeverity(str, Enum):
    """Severity levels for detected drift."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ResourceDrift:
    """A single resource drift finding."""

    resource_type: str
    resource_id: str
    resource_name: str
    drift_type: DriftType
    severity: DriftSeverity
    desired_state: dict[str, Any] = field(default_factory=dict)
    actual_state: dict[str, Any] = field(default_factory=dict)
    changed_attributes: list[str] = field(default_factory=list)
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "desired_state": self.desired_state,
            "actual_state": self.actual_state,
            "changed_attributes": self.changed_attributes,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class DriftResult:
    """Aggregate result of a drift detection run."""

    total_desired: int = 0
    total_actual: int = 0
    total_drifted: int = 0
    drifts: list[ResourceDrift] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    drift_type_counts: dict[str, int] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_drift(self) -> bool:
        return self.total_drifted > 0

    @property
    def drift_rate(self) -> float:
        total = self.total_desired + self.total_actual
        return self.total_drifted / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_desired": self.total_desired,
            "total_actual": self.total_actual,
            "total_drifted": self.total_drifted,
            "drift_rate": round(self.drift_rate, 6),
            "has_drift": self.has_drift,
            "severity_counts": self.severity_counts,
            "drift_type_counts": self.drift_type_counts,
            "checked_at": self.checked_at.isoformat(),
            "drifts": [d.to_dict() for d in self.drifts],
        }


class DriftDetector:
    """Detects configuration drift between desired and actual state.

    Compares IaC-defined desired state (e.g., Terraform plan output)
    against actual runtime state (e.g., cloud provider API responses).
    """

    # Attributes that are expected to differ and should be ignored
    IGNORED_ATTRIBUTES: set[str] = {
        "id", "arn", "created_at", "updated_at", "last_modified",
        "owner_id", "request_id", "version", "_meta",
    }

    # Severity mapping for different drift types
    SEVERITY_MAP: dict[DriftType, DriftSeverity] = {
        DriftType.ADDED: DriftSeverity.MEDIUM,
        DriftType.REMOVED: DriftSeverity.HIGH,
        DriftType.MODIFIED: DriftSeverity.MEDIUM,
        DriftType.TAG_DRIFT: DriftSeverity.LOW,
        DriftType.SIZE_DRIFT: DriftSeverity.HIGH,
        DriftType.NETWORK_DRIFT: DriftSeverity.CRITICAL,
        DriftType.CREDENTIAL_DRIFT: DriftSeverity.CRITICAL,
    }

    def __init__(
        self,
        ignored_attributes: set[str] | None = None,
        severity_overrides: dict[DriftType, DriftSeverity] | None = None,
    ) -> None:
        self.ignored_attributes = ignored_attributes or self.IGNORED_ATTRIBUTES
        self.severity_overrides = severity_overrides or {}

    def detect(
        self,
        desired_state: Mapping[str, Any],
        actual_state: Mapping[str, Any],
    ) -> DriftResult:
        """Detect drift between desired and actual state.

        Args:
            desired_state: IaC-defined desired state (resource_id -> attributes).
            actual_state: Actual runtime state (resource_id -> attributes).

        Returns:
            DriftResult with all detected drifts.
        """
        drifts: list[ResourceDrift] = []
        desired_ids = set(desired_state.keys())
        actual_ids = set(actual_state.keys())

        # Resources added (exist in actual but not in desired)
        for rid in actual_ids - desired_ids:
            attrs = actual_state[rid]
            drifts.append(ResourceDrift(
                resource_type=attrs.get("resource_type", "unknown"),
                resource_id=rid,
                resource_name=attrs.get("name", rid),
                drift_type=DriftType.ADDED,
                severity=self._severity_for(DriftType.ADDED),
                actual_state=dict(attrs),
                description=f"Resource {rid} exists in actual state but not in desired state",
            ))

        # Resources removed (exist in desired but not in actual)
        for rid in desired_ids - actual_ids:
            attrs = desired_state[rid]
            drifts.append(ResourceDrift(
                resource_type=attrs.get("resource_type", "unknown"),
                resource_id=rid,
                resource_name=attrs.get("name", rid),
                drift_type=DriftType.REMOVED,
                severity=self._severity_for(DriftType.REMOVED),
                desired_state=dict(attrs),
                description=f"Resource {rid} exists in desired state but not in actual state",
            ))

        # Resources modified (exist in both but differ)
        for rid in desired_ids & actual_ids:
            desired_attrs = desired_state[rid]
            actual_attrs = actual_state[rid]
            changed = self._find_changed_attributes(desired_attrs, actual_attrs)
            if changed:
                drift_type = self._classify_drift_type(changed)
                drifts.append(ResourceDrift(
                    resource_type=desired_attrs.get("resource_type", "unknown"),
                    resource_id=rid,
                    resource_name=desired_attrs.get("name", rid),
                    drift_type=drift_type,
                    severity=self._severity_for(drift_type),
                    desired_state=dict(desired_attrs),
                    actual_state=dict(actual_attrs),
                    changed_attributes=changed,
                    description=f"Resource {rid} has drifted: {', '.join(changed)}",
                ))

        # Build severity and type counts
        severity_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        for d in drifts:
            severity_counts[d.severity.value] += 1
            type_counts[d.drift_type.value] += 1

        return DriftResult(
            total_desired=len(desired_state),
            total_actual=len(actual_state),
            total_drifted=len(drifts),
            drifts=drifts,
            severity_counts=dict(severity_counts),
            drift_type_counts=dict(type_counts),
        )

    def _find_changed_attributes(
        self,
        desired: Mapping[str, Any],
        actual: Mapping[str, Any],
    ) -> list[str]:
        """Find attributes that differ between desired and actual."""
        changed: list[str] = []
        all_keys = set(desired.keys()) | set(actual.keys())
        for key in all_keys:
            if key in self.ignored_attributes:
                continue
            d_val = desired.get(key)
            a_val = actual.get(key)
            if d_val != a_val:
                changed.append(key)
        return changed

    def _classify_drift_type(self, changed_attrs: list[str]) -> DriftType:
        """Classify the type of drift based on changed attributes."""
        tag_attrs = {"tags", "tag", "labels", "label"}
        size_attrs = {"instance_type", "size", "capacity", "flavor", "machine_type", "tier"}
        network_attrs = {"security_group", "subnet", "vpc", "network", "firewall", "acl"}
        cred_attrs = {"key", "certificate", "secret", "password", "credential", "token"}

        attr_set = set(changed_attrs)
        if attr_set & cred_attrs:
            return DriftType.CREDENTIAL_DRIFT
        if attr_set & network_attrs:
            return DriftType.NETWORK_DRIFT
        if attr_set & size_attrs:
            return DriftType.SIZE_DRIFT
        if attr_set & tag_attrs:
            return DriftType.TAG_DRIFT
        return DriftType.MODIFIED

    def _severity_for(self, drift_type: DriftType) -> DriftSeverity:
        """Get severity for a drift type, with overrides."""
        return self.severity_overrides.get(drift_type, self.SEVERITY_MAP.get(drift_type, DriftSeverity.MEDIUM))


def detect_drift(
    desired_state: Mapping[str, Any],
    actual_state: Mapping[str, Any],
    **kwargs: Any,
) -> DriftResult:
    """Convenience function to detect drift between desired and actual state."""
    detector = DriftDetector(**kwargs)
    return detector.detect(desired_state, actual_state)


def summarize_drift(result: DriftResult) -> dict[str, Any]:
    """Create a summary of drift results for dashboard display."""
    return {
        "total_drifted": result.total_drifted,
        "drift_rate": round(result.drift_rate, 4),
        "has_drift": result.has_drift,
        "severity_counts": result.severity_counts,
        "drift_type_counts": result.drift_type_counts,
        "top_drifts": [
            {
                "resource_id": d.resource_id,
                "resource_name": d.resource_name,
                "drift_type": d.drift_type.value,
                "severity": d.severity.value,
                "description": d.description,
            }
            for d in sorted(
                result.drifts,
                key=lambda x: (
                    0 if x.severity == DriftSeverity.CRITICAL else
                    1 if x.severity == DriftSeverity.HIGH else
                    2 if x.severity == DriftSeverity.MEDIUM else 3
                ),
            )[:10]
        ],
    }
