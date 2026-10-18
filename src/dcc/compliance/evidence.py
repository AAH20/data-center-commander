"""Evidence collection engine for compliance scanning.

Provides structured evidence collection during compliance scans. Evidence
is collected, timestamped, and attached to findings to support audit
requirements.

Supports:
- Log-based evidence (system logs, audit logs)
- Metric-based evidence (performance metrics, thresholds)
- Configuration evidence (environment variables, config files)
- API response evidence (external service responses)
- File evidence (file contents, checksums)
- Database evidence (query results, row counts)
- Manual evidence (user-provided attestations)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .models import Evidence, EvidenceType, Finding


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EvidenceCollectionError(RuntimeError):
    """Base exception for evidence collection errors."""


class EvidenceSourceError(EvidenceCollectionError):
    """Raised when an evidence source is unavailable."""


# ---------------------------------------------------------------------------
# Evidence collector
# ---------------------------------------------------------------------------


class EvidenceCollector:
    """Collects and manages evidence during compliance scans.

    Parameters
    ----------
    enabled:
        Whether evidence collection is enabled.
    max_evidence_per_finding:
        Maximum number of evidence items to attach to a single finding.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_evidence_per_finding: int = 10,
    ) -> None:
        self._enabled = enabled
        self._max_per_finding = max_evidence_per_finding
        self._collected: list[Evidence] = []
        self._collectors: dict[EvidenceType, Callable[..., Evidence]] = {
            EvidenceType.LOG: self._collect_log_evidence,
            EvidenceType.METRIC: self._collect_metric_evidence,
            EvidenceType.CONFIG: self._collect_config_evidence,
            EvidenceType.SNAPSHOT: self._collect_snapshot_evidence,
            EvidenceType.API_RESPONSE: self._collect_api_evidence,
            EvidenceType.FILE: self._collect_file_evidence,
            EvidenceType.DATABASE: self._collect_database_evidence,
            EvidenceType.MANUAL: self._collect_manual_evidence,
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def collected(self) -> list[Evidence]:
        """Return all collected evidence."""
        return list(self._collected)

    def collect(
        self,
        evidence_type: EvidenceType,
        source: str,
        content: Any,
        **metadata: Any,
    ) -> Evidence:
        """Collect a piece of evidence.

        Parameters
        ----------
        evidence_type:
            The type of evidence.
        source:
            Where the evidence came from.
        content:
            The evidence content.
        **metadata:
            Additional metadata.

        Returns
        -------
        Evidence
            The collected evidence.
        """
        if not self._enabled:
            return Evidence(
                evidence_type=evidence_type,
                source=source,
                content=None,
                metadata={"disabled": True},
            )

        evidence = Evidence(
            evidence_type=evidence_type,
            source=source,
            content=content,
            metadata=metadata,
        )
        self._collected.append(evidence)
        return evidence

    def collect_many(
        self,
        evidence_type: EvidenceType,
        source: str,
        contents: Sequence[Any],
        **metadata: Any,
    ) -> list[Evidence]:
        """Collect multiple pieces of evidence of the same type."""
        return [
            self.collect(evidence_type, source, content, **metadata)
            for content in contents
        ]

    def attach_to_finding(self, finding: Finding, evidence: Evidence) -> Finding:
        """Attach evidence to a finding, respecting the max limit."""
        current = list(finding.evidence)
        if len(current) < self._max_per_finding:
            current.append(evidence)
        return Finding(
            control_id=finding.control_id,
            status=finding.status,
            severity=finding.severity,
            message=finding.message,
            evidence=tuple(current),
            remediation_hint=finding.remediation_hint,
            metadata=finding.metadata,
        )

    def clear(self) -> None:
        """Clear all collected evidence."""
        self._collected.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize all collected evidence."""
        return {
            "total": len(self._collected),
            "evidence": [e.to_dict() for e in self._collected],
        }

    # ------------------------------------------------------------------
    # Typed collectors
    # ------------------------------------------------------------------

    def collect_log(
        self,
        source: str,
        log_content: str,
        **metadata: Any,
    ) -> Evidence:
        """Collect log-based evidence."""
        return self.collect(EvidenceType.LOG, source, log_content, **metadata)

    def collect_metric(
        self,
        source: str,
        metric_name: str,
        metric_value: float,
        threshold: float | None = None,
        **metadata: Any,
    ) -> Evidence:
        """Collect metric-based evidence."""
        content = {
            "metric_name": metric_name,
            "value": metric_value,
            "threshold": threshold,
            "unit": metadata.get("unit", ""),
        }
        return self.collect(EvidenceType.METRIC, source, content, **metadata)

    def collect_config(
        self,
        source: str,
        config: dict[str, Any],
        **metadata: Any,
    ) -> Evidence:
        """Collect configuration evidence."""
        return self.collect(EvidenceType.CONFIG, source, config, **metadata)

    def collect_file(
        self,
        path: str | Path,
        *,
        include_content: bool = True,
        include_checksum: bool = True,
        **metadata: Any,
    ) -> Evidence:
        """Collect file-based evidence.

        Parameters
        ----------
        path:
            Path to the file.
        include_content:
            Whether to include the file content.
        include_checksum:
            Whether to include a SHA-256 checksum.
        """
        path = Path(path)
        if not path.exists():
            raise EvidenceSourceError(f"file not found: {path}")

        content: dict[str, Any] = {"path": str(path)}
        if include_content:
            try:
                content["content"] = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                content["content"] = None
                content["binary"] = True
        if include_checksum:
            content["sha256"] = _file_checksum(path)

        return self.collect(EvidenceType.FILE, str(path), content, **metadata)

    def collect_database(
        self,
        source: str,
        query: str,
        result: Any,
        **metadata: Any,
    ) -> Evidence:
        """Collect database query evidence."""
        content = {
            "query": query,
            "result": result,
        }
        return self.collect(EvidenceType.DATABASE, source, content, **metadata)

    def collect_api_response(
        self,
        endpoint: str,
        response: Any,
        **metadata: Any,
    ) -> Evidence:
        """Collect API response evidence."""
        return self.collect(EvidenceType.API_RESPONSE, endpoint, response, **metadata)

    def collect_manual(
        self,
        source: str,
        attestation: str,
        **metadata: Any,
    ) -> Evidence:
        """Collect manual attestation evidence."""
        return self.collect(EvidenceType.MANUAL, source, attestation, **metadata)

    # ------------------------------------------------------------------
    # Internal collectors
    # ------------------------------------------------------------------

    def _collect_log_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.LOG, source, content, **metadata)

    def _collect_metric_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.METRIC, source, content, **metadata)

    def _collect_config_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.CONFIG, source, content, **metadata)

    def _collect_snapshot_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.SNAPSHOT, source, content, **metadata)

    def _collect_api_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.API_RESPONSE, source, content, **metadata)

    def _collect_file_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.FILE, source, content, **metadata)

    def _collect_database_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.DATABASE, source, content, **metadata)

    def _collect_manual_evidence(self, source: str, content: Any, **metadata: Any) -> Evidence:
        return self.collect(EvidenceType.MANUAL, source, content, **metadata)


# ---------------------------------------------------------------------------
# Evidence store
# ---------------------------------------------------------------------------


class EvidenceStore:
    """Persistent store for compliance evidence.

    Stores evidence on disk in a structured directory layout for
    long-term retention and audit purposes.

    Parameters
    ----------
    base_path:
        Base directory for evidence storage.
    """

    def __init__(self, base_path: str | Path) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    @property
    def base_path(self) -> Path:
        return self._base_path

    def store(self, evidence: Evidence, *, report_id: str | None = None) -> Path:
        """Store a piece of evidence to disk.

        Returns the path where the evidence was stored.
        """
        # Create directory structure: base/report_id/evidence_type/
        report_dir = report_id or "default"
        evidence_dir = self._base_path / report_dir / evidence.evidence_type.value
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from timestamp and source hash
        timestamp = evidence.collected_at.strftime("%Y%m%d_%H%M%S_%f")
        source_hash = hashlib.sha256(evidence.source.encode()).hexdigest()[:8]
        filename = f"{timestamp}_{source_hash}.json"

        filepath = evidence_dir / filename
        filepath.write_text(
            json.dumps(evidence.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        return filepath

    def store_many(
        self,
        evidence_list: Iterable[Evidence],
        *,
        report_id: str | None = None,
    ) -> list[Path]:
        """Store multiple evidence items."""
        return [self.store(e, report_id=report_id) for e in evidence_list]

    def load(self, path: str | Path) -> Evidence:
        """Load evidence from disk."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Evidence.from_dict(data)

    def list_evidence(
        self,
        *,
        report_id: str | None = None,
        evidence_type: EvidenceType | None = None,
    ) -> list[Path]:
        """List stored evidence files."""
        search_path = self._base_path
        if report_id:
            search_path = search_path / report_id
        if evidence_type:
            search_path = search_path / evidence_type.value

        if not search_path.exists():
            return []

        return sorted(search_path.rglob("*.json"))

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about stored evidence."""
        stats: dict[str, Any] = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {},
        }

        for json_file in self._base_path.rglob("*.json"):
            stats["total_files"] += 1
            stats["total_size_bytes"] += json_file.stat().st_size

            # Determine type from path
            rel_path = json_file.relative_to(self._base_path)
            parts = rel_path.parts
            if len(parts) >= 2:
                ev_type = parts[1]
                stats["by_type"][ev_type] = stats["by_type"].get(ev_type, 0) + 1

        return stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_checksum(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
