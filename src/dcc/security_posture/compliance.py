"""Compliance posture assessment and reporting.

Evaluates compliance against frameworks (SOC 2, ISO 27001, NIST 800-53,
PCI DSS, HIPAA) by mapping security controls to framework requirements
and tracking control status over time.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks."""
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    NIST_800_53 = "nist_800_53"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    CUSTOM = "custom"


class ComplianceControlStatus(str, Enum):
    """Status of a compliance control."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


# Framework display names
_FRAMEWORK_NAMES: dict[ComplianceFramework, str] = {
    ComplianceFramework.SOC2: "SOC 2",
    ComplianceFramework.ISO27001: "ISO/IEC 27001",
    ComplianceFramework.NIST_800_53: "NIST SP 800-53",
    ComplianceFramework.PCI_DSS: "PCI DSS",
    ComplianceFramework.HIPAA: "HIPAA",
    ComplianceFramework.CUSTOM: "Custom",
}


@dataclass
class ComplianceControl:
    """A single compliance control mapping to a framework requirement.

    Attributes
    ----------
    id:
        Unique control identifier (e.g., "CC6.1" for SOC 2).
    framework:
        The compliance framework this control belongs to.
    title:
        Short title of the control.
    description:
        Detailed description of the requirement.
    status:
        Current compliance status.
    evidence:
        Evidence supporting the control status.
    related_vulnerabilities:
        IDs of related vulnerabilities.
    assessed_at:
        ISO timestamp of the last assessment.
    assessor:
        Who or what performed the assessment.
    notes:
        Additional notes.
    """

    id: str
    framework: ComplianceFramework
    title: str
    description: str = ""
    status: ComplianceControlStatus = ComplianceControlStatus.NOT_ASSESSED
    evidence: dict[str, Any] = field(default_factory=dict)
    related_vulnerabilities: list[str] = field(default_factory=list)
    assessed_at: str = ""
    assessor: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.assessed_at:
            self.assessed_at = dt.datetime.now(dt.timezone.utc).isoformat()

    @property
    def is_compliant(self) -> bool:
        return self.status == ComplianceControlStatus.COMPLIANT

    @property
    def is_non_compliant(self) -> bool:
        return self.status == ComplianceControlStatus.NON_COMPLIANT

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "framework": self.framework.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "evidence": self.evidence,
            "related_vulnerabilities": self.related_vulnerabilities,
            "assessed_at": self.assessed_at,
            "assessor": self.assessor,
            "notes": self.notes,
        }


@dataclass
class ComplianceAssessment:
    """A compliance assessment for a specific framework.

    Attributes
    ----------
    framework:
        The compliance framework being assessed.
    controls:
        List of compliance controls.
    started_at:
        ISO timestamp when the assessment started.
    completed_at:
        ISO timestamp when the assessment completed.
    metadata:
        Arbitrary metadata.
    """

    framework: ComplianceFramework
    controls: list[ComplianceControl] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = dt.datetime.now(dt.timezone.utc).isoformat()

    @property
    def framework_name(self) -> str:
        return _FRAMEWORK_NAMES.get(self.framework, self.framework.value)

    @property
    def total_controls(self) -> int:
        return len(self.controls)

    @property
    def compliant_count(self) -> int:
        return sum(1 for c in self.controls if c.status == ComplianceControlStatus.COMPLIANT)

    @property
    def non_compliant_count(self) -> int:
        return sum(1 for c in self.controls if c.status == ComplianceControlStatus.NON_COMPLIANT)

    @property
    def partial_count(self) -> int:
        return sum(1 for c in self.controls if c.status == ComplianceControlStatus.PARTIAL)

    @property
    def not_assessed_count(self) -> int:
        return sum(1 for c in self.controls if c.status == ComplianceControlStatus.NOT_ASSESSED)

    @property
    def not_applicable_count(self) -> int:
        return sum(1 for c in self.controls if c.status == ComplianceControlStatus.NOT_APPLICABLE)

    @property
    def compliance_percentage(self) -> float:
        """Return compliance percentage (0-100).

        Not-applicable controls are excluded from the denominator.
        """
        applicable = self.total_controls - self.not_applicable_count
        if applicable == 0:
            return 0.0
        return round((self.compliant_count / applicable) * 100, 2)

    @property
    def is_compliant(self) -> bool:
        """Check if all applicable controls are compliant."""
        return self.compliance_percentage == 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework.value,
            "framework_name": self.framework_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_controls": self.total_controls,
            "compliant_count": self.compliant_count,
            "non_compliant_count": self.non_compliant_count,
            "partial_count": self.partial_count,
            "not_assessed_count": self.not_assessed_count,
            "not_applicable_count": self.not_applicable_count,
            "compliance_percentage": self.compliance_percentage,
            "is_compliant": self.is_compliant,
            "controls": [c.to_dict() for c in self.controls],
            "metadata": self.metadata,
        }


@dataclass
class ComplianceReport:
    """Aggregated compliance report across multiple frameworks.

    Attributes
    ----------
    assessments:
        List of compliance assessments per framework.
    generated_at:
        ISO timestamp when the report was generated.
    metadata:
        Arbitrary metadata.
    """

    assessments: list[ComplianceAssessment] = field(default_factory=list)
    generated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = dt.datetime.now(dt.timezone.utc).isoformat()

    @property
    def overall_compliance_percentage(self) -> float:
        """Return overall compliance percentage across all frameworks."""
        applicable = sum(
            a.total_controls - a.not_applicable_count for a in self.assessments
        )
        if applicable == 0:
            return 0.0
        compliant = sum(a.compliant_count for a in self.assessments)
        return round((compliant / applicable) * 100, 2)

    @property
    def frameworks_compliant(self) -> int:
        """Number of fully compliant frameworks."""
        return sum(1 for a in self.assessments if a.is_compliant)

    @property
    def frameworks_non_compliant(self) -> int:
        """Number of non-compliant frameworks."""
        return sum(1 for a in self.assessments if not a.is_compliant)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall_compliance_percentage": self.overall_compliance_percentage,
            "frameworks_compliant": self.frameworks_compliant,
            "frameworks_non_compliant": self.frameworks_non_compliant,
            "assessments": [a.to_dict() for a in self.assessments],
            "metadata": self.metadata,
        }


class ComplianceEngine:
    """Evaluates compliance posture across frameworks.

    Manages compliance controls and produces compliance reports.
    """

    def __init__(self) -> None:
        self._controls: dict[ComplianceFramework, dict[str, ComplianceControl]] = {
            fw: {} for fw in ComplianceFramework
        }

    def add_control(self, control: ComplianceControl) -> None:
        """Add or update a compliance control."""
        self._controls[control.framework][control.id] = control

    def add_controls(self, controls: Iterable[ComplianceControl]) -> None:
        """Add multiple compliance controls."""
        for control in controls:
            self.add_control(control)

    def get_control(
        self,
        framework: ComplianceFramework,
        control_id: str,
    ) -> ComplianceControl | None:
        """Retrieve a specific control."""
        return self._controls[framework].get(control_id)

    def get_controls(
        self,
        framework: ComplianceFramework,
    ) -> list[ComplianceControl]:
        """Get all controls for a framework."""
        return list(self._controls[framework].values())

    def assess(
        self,
        framework: ComplianceFramework,
        metadata: dict[str, Any] | None = None,
    ) -> ComplianceAssessment:
        """Produce a compliance assessment for a framework."""
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        controls = list(self._controls[framework].values())
        return ComplianceAssessment(
            framework=framework,
            controls=controls,
            started_at=now,
            completed_at=now,
            metadata=metadata or {},
        )

    def generate_report(
        self,
        frameworks: Iterable[ComplianceFramework] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ComplianceReport:
        """Generate a compliance report across frameworks."""
        frameworks = list(frameworks) if frameworks else list(ComplianceFramework)
        assessments = [self.assess(fw) for fw in frameworks]
        return ComplianceReport(
            assessments=assessments,
            metadata=metadata or {},
        )
