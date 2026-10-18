"""IaC compliance dashboard: policy compliance checking and reporting.

Evaluates infrastructure resources against compliance policies (CIS benchmarks,
organizational standards, regulatory requirements) and produces compliance
dashboard data.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


class ComplianceStatus(str, Enum):
    """Compliance check result status."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class ComplianceSeverity(str, Enum):
    """Severity levels for compliance failures."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ComplianceCheck:
    """A single compliance check definition."""

    check_id: str
    name: str
    description: str
    severity: ComplianceSeverity
    category: str  # e.g., "security", "cost", "reliability", "tagging"
    # A function that takes a resource dict and returns (passed: bool, detail: str)
    evaluator: Callable[[dict[str, Any]], tuple[bool, str]] | None = None
    # Simple attribute-based check (alternative to evaluator function)
    attribute: str | None = None
    expected_value: Any = None
    operator: str = "eq"  # eq, neq, contains, regex, exists, not_exists

    def evaluate(self, resource: dict[str, Any]) -> ComplianceResult:
        """Evaluate this check against a resource."""
        if self.evaluator:
            try:
                passed, detail = self.evaluator(resource)
                return ComplianceResult(
                    check_id=self.check_id,
                    name=self.name,
                    status=ComplianceStatus.PASS if passed else ComplianceStatus.FAIL,
                    severity=self.severity,
                    category=self.category,
                    detail=detail,
                    resource_id=resource.get("id", resource.get("resource_id", "unknown")),
                    resource_type=resource.get("resource_type", "unknown"),
                )
            except Exception as exc:
                return ComplianceResult(
                    check_id=self.check_id,
                    name=self.name,
                    status=ComplianceStatus.UNKNOWN,
                    severity=self.severity,
                    category=self.category,
                    detail=f"Evaluation error: {exc}",
                    resource_id=resource.get("id", resource.get("resource_id", "unknown")),
                    resource_type=resource.get("resource_type", "unknown"),
                )

        # Attribute-based evaluation
        return self._evaluate_attribute(resource)

    def _evaluate_attribute(self, resource: dict[str, Any]) -> ComplianceResult:
        """Evaluate using simple attribute comparison."""
        attr = self.attribute
        if attr is None:
            return ComplianceResult(
                check_id=self.check_id,
                name=self.name,
                status=ComplianceStatus.UNKNOWN,
                severity=self.severity,
                category=self.category,
                detail="No evaluator or attribute configured",
                resource_id=resource.get("id", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
            )

        value = resource.get(attr)
        passed = False
        detail = ""

        if self.operator == "exists":
            passed = value is not None
            detail = f"Attribute '{attr}' {'exists' if passed else 'does not exist'}"
        elif self.operator == "not_exists":
            passed = value is None
            detail = f"Attribute '{attr}' {'does not exist' if passed else 'exists'}"
        elif self.operator == "eq":
            passed = value == self.expected_value
            detail = f"Attribute '{attr}' is {value!r}, expected {self.expected_value!r}"
        elif self.operator == "neq":
            passed = value != self.expected_value
            detail = f"Attribute '{attr}' is {value!r}, expected not {self.expected_value!r}"
        elif self.operator == "contains":
            if isinstance(value, str) and isinstance(self.expected_value, str):
                passed = self.expected_value in value
            elif isinstance(value, (list, tuple)):
                passed = self.expected_value in value
            else:
                passed = False
            detail = f"Attribute '{attr}' {'contains' if passed else 'does not contain'} {self.expected_value!r}"
        elif self.operator == "regex":
            if isinstance(value, str) and isinstance(self.expected_value, str):
                passed = bool(re.search(self.expected_value, value))
            else:
                passed = False
            detail = f"Attribute '{attr}' {'matches' if passed else 'does not match'} pattern {self.expected_value!r}"
        else:
            detail = f"Unknown operator: {self.operator}"

        return ComplianceResult(
            check_id=self.check_id,
            name=self.name,
            status=ComplianceStatus.PASS if passed else ComplianceStatus.FAIL,
            severity=self.severity,
            category=self.category,
            detail=detail,
            resource_id=resource.get("id", resource.get("resource_id", "unknown")),
            resource_type=resource.get("resource_type", "unknown"),
        )


@dataclass
class ComplianceResult:
    """Result of a single compliance check against a resource."""

    check_id: str
    name: str
    status: ComplianceStatus
    severity: ComplianceSeverity
    category: str
    detail: str = ""
    resource_id: str = "unknown"
    resource_type: str = "unknown"
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "severity": self.severity.value,
            "category": self.category,
            "detail": self.detail,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass
class ComplianceReport:
    """Aggregate compliance report."""

    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    not_applicable: int = 0
    unknown: int = 0
    results: list[ComplianceResult] = field(default_factory=list)
    category_summary: dict[str, dict[str, int]] = field(default_factory=dict)
    severity_summary: dict[str, int] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def compliance_rate(self) -> float:
        applicable = self.total_checks - self.not_applicable
        return self.passed / applicable if applicable > 0 else 0.0

    @property
    def overall_status(self) -> ComplianceStatus:
        if self.failed > 0:
            return ComplianceStatus.FAIL
        if self.warnings > 0:
            return ComplianceStatus.WARNING
        if self.unknown > 0:
            return ComplianceStatus.UNKNOWN
        return ComplianceStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "not_applicable": self.not_applicable,
            "unknown": self.unknown,
            "compliance_rate": round(self.compliance_rate, 4),
            "overall_status": self.overall_status.value,
            "category_summary": self.category_summary,
            "severity_summary": self.severity_summary,
            "generated_at": self.generated_at.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }


class ComplianceEngine:
    """Engine for evaluating compliance checks against resources."""

    def __init__(self, checks: Sequence[ComplianceCheck] | None = None) -> None:
        self.checks: list[ComplianceCheck] = list(checks) if checks else []

    def add_check(self, check: ComplianceCheck) -> None:
        """Add a compliance check."""
        self.checks.append(check)

    def evaluate(
        self,
        resources: Sequence[dict[str, Any]],
    ) -> ComplianceReport:
        """Evaluate all checks against all resources."""
        results: list[ComplianceResult] = []
        for resource in resources:
            for check in self.checks:
                result = check.evaluate(resource)
                results.append(result)

        # Build summaries
        category_summary: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        severity_summary: dict[str, int] = defaultdict(int)
        passed = failed = warnings = na = unknown = 0

        for r in results:
            category_summary[r.category][r.status.value] += 1
            severity_summary[r.severity.value] += 1
            if r.status == ComplianceStatus.PASS:
                passed += 1
            elif r.status == ComplianceStatus.FAIL:
                failed += 1
            elif r.status == ComplianceStatus.WARNING:
                warnings += 1
            elif r.status == ComplianceStatus.NOT_APPLICABLE:
                na += 1
            else:
                unknown += 1

        return ComplianceReport(
            total_checks=len(results),
            passed=passed,
            failed=failed,
            warnings=warnings,
            not_applicable=na,
            unknown=unknown,
            results=results,
            category_summary={k: dict(v) for k, v in category_summary.items()},
            severity_summary=dict(severity_summary),
        )


def evaluate_compliance(
    resources: Sequence[dict[str, Any]],
    checks: Sequence[ComplianceCheck],
) -> ComplianceReport:
    """Convenience function to evaluate compliance."""
    engine = ComplianceEngine(checks)
    return engine.evaluate(resources)


def build_compliance_dashboard(report: ComplianceReport) -> dict[str, Any]:
    """Build dashboard-ready compliance data."""
    return {
        "compliance_rate": round(report.compliance_rate * 100, 1),
        "overall_status": report.overall_status.value,
        "summary": {
            "total": report.total_checks,
            "passed": report.passed,
            "failed": report.failed,
            "warnings": report.warnings,
            "not_applicable": report.not_applicable,
        },
        "by_category": report.category_summary,
        "by_severity": report.severity_summary,
        "top_failures": [
            {
                "check_id": r.check_id,
                "name": r.name,
                "severity": r.severity.value,
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "detail": r.detail,
            }
            for r in sorted(
                [r for r in report.results if r.status == ComplianceStatus.FAIL],
                key=lambda x: (
                    0 if x.severity == ComplianceSeverity.CRITICAL else
                    1 if x.severity == ComplianceSeverity.HIGH else
                    2 if x.severity == ComplianceSeverity.MEDIUM else 3
                ),
            )[:20]
        ],
    }


# ---------------------------------------------------------------------------
# Pre-built compliance checks
# ---------------------------------------------------------------------------

def _check_encryption_at_rest(resource: dict[str, Any]) -> tuple[bool, str]:
    encrypted = resource.get("encrypted", resource.get("encryption_at_rest", False))
    if encrypted:
        return True, "Encryption at rest is enabled"
    return False, "Encryption at rest is not enabled"


def _check_public_access(resource: dict[str, Any]) -> tuple[bool, str]:
    public = resource.get("publicly_accessible", resource.get("public_access", False))
    if not public:
        return True, "Resource is not publicly accessible"
    return False, "Resource is publicly accessible"


def _check_backup_enabled(resource: dict[str, Any]) -> tuple[bool, str]:
    backup = resource.get("backup_enabled", resource.get("backup", False))
    if backup:
        return True, "Backup is enabled"
    return False, "Backup is not enabled"


def _check_tags_present(resource: dict[str, Any]) -> tuple[bool, str]:
    tags = resource.get("tags", {})
    if isinstance(tags, dict) and len(tags) > 0:
        return True, f"Resource has {len(tags)} tags"
    return False, "Resource has no tags"


def _check_monitoring_enabled(resource: dict[str, Any]) -> tuple[bool, str]:
    monitoring = resource.get("monitoring_enabled", resource.get("monitoring", False))
    if monitoring:
        return True, "Monitoring is enabled"
    return False, "Monitoring is not enabled"


def _check_environment_tag(resource: dict[str, Any]) -> tuple[bool, str]:
    tags = resource.get("tags", {})
    if isinstance(tags, dict) and "environment" in tags:
        return True, f"Environment tag present: {tags['environment']}"
    return False, "Environment tag missing"


def _check_cost_center_tag(resource: dict[str, Any]) -> tuple[bool, str]:
    tags = resource.get("tags", {})
    if isinstance(tags, dict) and "cost_center" in tags:
        return True, f"Cost center tag present: {tags['cost_center']}"
    return False, "Cost center tag missing"


def _check_owner_tag(resource: dict[str, Any]) -> tuple[bool, str]:
    tags = resource.get("tags", {})
    if isinstance(tags, dict) and "owner" in tags:
        return True, f"Owner tag present: {tags['owner']}"
    return False, "Owner tag missing"


def _check_versioning(resource: dict[str, Any]) -> tuple[bool, str]:
    versioning = resource.get("versioning_enabled", resource.get("versioning", False))
    if versioning:
        return True, "Versioning is enabled"
    return False, "Versioning is not enabled"


def _check_logging_enabled(resource: dict[str, Any]) -> tuple[bool, str]:
    logging_enabled = resource.get("logging_enabled", resource.get("logging", False))
    if logging_enabled:
        return True, "Logging is enabled"
    return False, "Logging is not enabled"


def _check_least_privilege(resource: dict[str, Any]) -> tuple[bool, str]:
    policy = resource.get("policy", resource.get("iam_policy", ""))
    if isinstance(policy, str):
        if "*" in policy and "Effect\": \"Allow\"" in policy:
            return False, "Policy contains wildcard permissions"
        return True, "Policy does not contain wildcard permissions"
    return True, "No policy to evaluate"


def get_default_checks() -> list[ComplianceCheck]:
    """Get a set of default compliance checks."""
    return [
        ComplianceCheck(
            check_id="CIS-1.1",
            name="Encryption at Rest",
            description="Ensure all storage resources have encryption at rest enabled",
            severity=ComplianceSeverity.HIGH,
            category="security",
            evaluator=_check_encryption_at_rest,
        ),
        ComplianceCheck(
            check_id="CIS-1.2",
            name="No Public Access",
            description="Ensure resources are not publicly accessible",
            severity=ComplianceSeverity.CRITICAL,
            category="security",
            evaluator=_check_public_access,
        ),
        ComplianceCheck(
            check_id="CIS-2.1",
            name="Backup Enabled",
            description="Ensure backup is enabled for stateful resources",
            severity=ComplianceSeverity.HIGH,
            category="reliability",
            evaluator=_check_backup_enabled,
        ),
        ComplianceCheck(
            check_id="ORG-1.1",
            name="Tags Present",
            description="Ensure all resources have tags",
            severity=ComplianceSeverity.LOW,
            category="tagging",
            evaluator=_check_tags_present,
        ),
        ComplianceCheck(
            check_id="ORG-1.2",
            name="Environment Tag",
            description="Ensure all resources have an environment tag",
            severity=ComplianceSeverity.MEDIUM,
            category="tagging",
            evaluator=_check_environment_tag,
        ),
        ComplianceCheck(
            check_id="ORG-1.3",
            name="Cost Center Tag",
            description="Ensure all resources have a cost center tag",
            severity=ComplianceSeverity.MEDIUM,
            category="tagging",
            evaluator=_check_cost_center_tag,
        ),
        ComplianceCheck(
            check_id="ORG-1.4",
            name="Owner Tag",
            description="Ensure all resources have an owner tag",
            severity=ComplianceSeverity.MEDIUM,
            category="tagging",
            evaluator=_check_owner_tag,
        ),
        ComplianceCheck(
            check_id="CIS-3.1",
            name="Monitoring Enabled",
            description="Ensure monitoring is enabled for all resources",
            severity=ComplianceSeverity.MEDIUM,
            category="reliability",
            evaluator=_check_monitoring_enabled,
        ),
        ComplianceCheck(
            check_id="CIS-4.1",
            name="Versioning Enabled",
            description="Ensure versioning is enabled for storage resources",
            severity=ComplianceSeverity.LOW,
            category="reliability",
            evaluator=_check_versioning,
        ),
        ComplianceCheck(
            check_id="CIS-5.1",
            name="Logging Enabled",
            description="Ensure logging is enabled for all resources",
            severity=ComplianceSeverity.HIGH,
            category="security",
            evaluator=_check_logging_enabled,
        ),
        ComplianceCheck(
            check_id="CIS-6.1",
            name="Least Privilege",
            description="Ensure IAM policies follow least privilege principle",
            severity=ComplianceSeverity.CRITICAL,
            category="security",
            evaluator=_check_least_privilege,
        ),
    ]
