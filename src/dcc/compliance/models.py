"""Core data models for the compliance-as-code framework.

Defines the types used throughout the compliance engine: controls, results,
evidence, findings, and reports. All models are serialisable dataclasses so
they can be persisted, exported, and audited.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ComplianceStatus(str, Enum):
    """Outcome status for a single control evaluation."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class Severity(str, Enum):
    """Severity level for a compliance finding."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Framework(str, Enum):
    """Supported compliance frameworks."""

    SOC2 = "soc2"
    ISO27001 = "iso27001"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    NIST_800_53 = "nist_800_53"
    CUSTOM = "custom"


class RemediationStatus(str, Enum):
    """Lifecycle status of a remediation action."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EvidenceType(str, Enum):
    """Type of evidence collected during a scan."""

    LOG = "log"
    METRIC = "metric"
    CONFIG = "config"
    SNAPSHOT = "snapshot"
    API_RESPONSE = "api_response"
    FILE = "file"
    DATABASE = "database"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    """A single piece of evidence collected during a compliance scan.

    Attributes
    ----------
    evidence_type:
        The category of evidence.
    source:
        Where the evidence came from (file path, API endpoint, etc.).
    content:
        The actual evidence data (serialisable).
    collected_at:
        UTC timestamp when the evidence was collected.
    metadata:
        Additional context (e.g. query parameters, row counts).
    """

    evidence_type: EvidenceType
    source: str
    content: Any
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "source": self.source,
            "content": self.content,
            "collected_at": self.collected_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(
            evidence_type=EvidenceType(data["evidence_type"]),
            source=data["source"],
            content=data["content"],
            collected_at=datetime.fromisoformat(data["collected_at"]),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """A single compliance finding produced by a control evaluation.

    Attributes
    ----------
    control_id:
        Identifier of the control that produced this finding.
    status:
        The compliance status (pass/fail/skip/error).
    severity:
        How severe the finding is.
    message:
        Human-readable description.
    evidence:
        Supporting evidence for the finding.
    remediation_hint:
        Suggested remediation steps.
    """

    control_id: str
    status: ComplianceStatus
    severity: Severity
    message: str
    evidence: tuple[Evidence, ...] = ()
    remediation_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": [e.to_dict() for e in self.evidence],
            "remediation_hint": self.remediation_hint,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            control_id=data["control_id"],
            status=ComplianceStatus(data["status"]),
            severity=Severity(data["severity"]),
            message=data["message"],
            evidence=tuple(Evidence.from_dict(e) for e in data.get("evidence", [])),
            remediation_hint=data.get("remediation_hint", ""),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Control result
# ---------------------------------------------------------------------------


@dataclass
class ControlResult:
    """The full result of evaluating a single compliance control.

    Attributes
    ----------
    control_id:
        Unique identifier for the control.
    framework:
        Which compliance framework this control belongs to.
    title:
        Human-readable control title.
    description:
        What the control checks.
    status:
        Overall status after evaluation.
    findings:
        Individual findings from the control evaluation.
    duration_ms:
        How long the evaluation took in milliseconds.
    evaluated_at:
        UTC timestamp of evaluation.
    tags:
        Arbitrary tags for filtering and grouping.
    """

    control_id: str
    framework: Framework
    title: str
    description: str = ""
    status: ComplianceStatus = ComplianceStatus.SKIP
    findings: list[Finding] = field(default_factory=list)
    duration_ms: float = 0.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == ComplianceStatus.PASS

    @property
    def failed(self) -> bool:
        return self.status == ComplianceStatus.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "framework": self.framework.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
            "duration_ms": self.duration_ms,
            "evaluated_at": self.evaluated_at.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlResult:
        return cls(
            control_id=data["control_id"],
            framework=Framework(data["framework"]),
            title=data["title"],
            description=data.get("description", ""),
            status=ComplianceStatus(data["status"]),
            findings=[Finding.from_dict(f) for f in data.get("findings", [])],
            duration_ms=data.get("duration_ms", 0.0),
            evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# Compliance report
# ---------------------------------------------------------------------------


@dataclass
class ComplianceReport:
    """A complete compliance scan report.

    Aggregates all control results and provides summary statistics.

    Attributes
    ----------
    report_id:
        Unique identifier for this report.
    framework:
        The compliance framework that was scanned.
    started_at:
        When the scan started.
    completed_at:
        When the scan completed.
    results:
        All control results from the scan.
    tenant_id:
        Optional tenant scope for the scan.
    metadata:
        Arbitrary metadata (e.g. scan configuration).
    """

    report_id: UUID = field(default_factory=uuid4)
    framework: Framework = Framework.CUSTOM
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    results: list[ControlResult] = field(default_factory=list)
    tenant_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_controls(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == ComplianceStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == ComplianceStatus.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == ComplianceStatus.SKIP)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == ComplianceStatus.ERROR)

    @property
    def compliance_score(self) -> float:
        """Return compliance score as a percentage (0-100)."""
        if not self.results:
            return 0.0
        applicable = [r for r in self.results if r.status != ComplianceStatus.NOT_APPLICABLE]
        if not applicable:
            return 100.0
        return (len(applicable) - self.failed) / len(applicable) * 100.0

    @property
    def duration_seconds(self) -> float:
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": str(self.report_id),
            "framework": self.framework.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": [r.to_dict() for r in self.results],
            "tenant_id": self.tenant_id,
            "metadata": self.metadata,
            "summary": {
                "total_controls": self.total_controls,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "errors": self.errors,
                "compliance_score": round(self.compliance_score, 2),
                "duration_seconds": round(self.duration_seconds, 3),
            },
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save(self, path: str | Path) -> Path:
        """Save the report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplianceReport:
        return cls(
            report_id=UUID(data.get("report_id", str(uuid4()))),
            framework=Framework(data.get("framework", "custom")),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            results=[ControlResult.from_dict(r) for r in data.get("results", [])],
            tenant_id=data.get("tenant_id"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def load(cls, path: str | Path) -> ComplianceReport:
        """Load a report from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# Remediation action
# ---------------------------------------------------------------------------


@dataclass
class RemediationAction:
    """A single remediation action for a failed control.

    Attributes
    ----------
    action_id:
        Unique identifier for this action.
    control_id:
        The control this action remediates.
    title:
        Short description of the action.
    description:
        Detailed description of what needs to be done.
    status:
        Current lifecycle status.
    automated:
        Whether this action can be automated.
    command:
        Optional command to run for automated remediation.
    created_at:
        When the action was created.
    completed_at:
        When the action was completed.
    result:
        Result of executing the action.
    """

    action_id: UUID = field(default_factory=uuid4)
    control_id: str = ""
    title: str = ""
    description: str = ""
    status: RemediationStatus = RemediationStatus.PENDING
    automated: bool = False
    command: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": str(self.action_id),
            "control_id": self.control_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "automated": self.automated,
            "command": self.command,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RemediationAction:
        return cls(
            action_id=UUID(data.get("action_id", str(uuid4()))),
            control_id=data.get("control_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=RemediationStatus(data.get("status", "pending")),
            automated=data.get("automated", False),
            command=data.get("command", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            result=data.get("result", ""),
        )


# ---------------------------------------------------------------------------
# Control definition
# ---------------------------------------------------------------------------


@dataclass
class ControlDefinition:
    """Definition of a compliance control.

    A control is a single check that can be evaluated against the system.
    It has an evaluator function that returns findings.

    Attributes
    ----------
    control_id:
        Unique identifier (e.g. "SOC2-CC6.1").
    framework:
        The compliance framework this belongs to.
    title:
        Human-readable title.
    description:
        What the control checks.
    severity:
        Default severity for findings from this control.
    evaluator:
        Callable that performs the check and returns a list of findings.
    tags:
        Tags for filtering and grouping.
    version:
        Control definition version.
    """

    control_id: str
    framework: Framework
    title: str
    description: str = ""
    severity: Severity = Severity.MEDIUM
    evaluator: Callable[[], list[Finding]] | None = None
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "framework": self.framework.value,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "tags": self.tags,
            "version": self.version,
        }
