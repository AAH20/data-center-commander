"""Tests for evidence collection."""
from __future__ import annotations

import pytest

from dcc.compliance.evidence import (
    EvidenceCollector,
    EvidenceCollectionError,
    EvidenceSourceError,
    EvidenceStore,
)
from dcc.compliance.models import (
    ComplianceStatus,
    Evidence,
    EvidenceType,
    Finding,
    Severity,
)


class TestEvidenceCollector:
    def test_collect_evidence(self) -> None:
        collector = EvidenceCollector()
        ev = collector.collect(EvidenceType.CONFIG, "test-source", {"key": "val"})
        assert ev.evidence_type == EvidenceType.CONFIG
        assert ev.source == "test-source"
        assert ev.content == {"key": "val"}
        assert len(collector.collected) == 1

    def test_disabled_collector(self) -> None:
        collector = EvidenceCollector(enabled=False)
        ev = collector.collect(EvidenceType.CONFIG, "test", {"key": "val"})
        assert ev.content is None
        assert ev.metadata.get("disabled") is True

    def test_collect_many(self) -> None:
        collector = EvidenceCollector()
        items = collector.collect_many(EvidenceType.LOG, "src", ["a", "b", "c"])
        assert len(items) == 3
        assert len(collector.collected) == 3

    def test_attach_to_finding(self) -> None:
        collector = EvidenceCollector()
        ev = collector.collect(EvidenceType.CONFIG, "test", {})
        finding = Finding(
            control_id="T1",
            status=ComplianceStatus.PASS,
            severity=Severity.INFO,
            message="OK",
        )
        updated = collector.attach_to_finding(finding, ev)
        assert len(updated.evidence) == 1

    def test_attach_respects_max(self) -> None:
        collector = EvidenceCollector(max_evidence_per_finding=2)
        finding = Finding(
            control_id="T1",
            status=ComplianceStatus.PASS,
            severity=Severity.INFO,
            message="OK",
        )
        for _ in range(5):
            ev = collector.collect(EvidenceType.CONFIG, "test", {})
            finding = collector.attach_to_finding(finding, ev)
        assert len(finding.evidence) == 2

    def test_clear(self) -> None:
        collector = EvidenceCollector()
        collector.collect(EvidenceType.CONFIG, "test", {})
        assert len(collector.collected) == 1
        collector.clear()
        assert len(collector.collected) == 0

    def test_typed_collectors(self) -> None:
        collector = EvidenceCollector()
        log_ev = collector.collect_log("app.log", "error line")
        assert log_ev.evidence_type == EvidenceType.LOG

        metric_ev = collector.collect_metric("cpu", "usage", 75.0, threshold=80.0)
        assert metric_ev.evidence_type == EvidenceType.METRIC
        assert metric_ev.content["value"] == 75.0

        config_ev = collector.collect_config("env", {"DEBUG": "true"})
        assert config_ev.evidence_type == EvidenceType.CONFIG

    def test_collect_file(self, tmp_path) -> None:
        collector = EvidenceCollector()
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        ev = collector.collect_file(f)
        assert ev.evidence_type == EvidenceType.FILE
        assert ev.content["content"] == "hello world"
        assert "sha256" in ev.content

    def test_collect_file_missing(self) -> None:
        collector = EvidenceCollector()
        with pytest.raises(EvidenceSourceError):
            collector.collect_file("/nonexistent/path/file.txt")

    def test_collect_database(self) -> None:
        collector = EvidenceCollector()
        ev = collector.collect_database("db", "SELECT 1", [{"id": 1}])
        assert ev.evidence_type == EvidenceType.DATABASE
        assert ev.content["query"] == "SELECT 1"

    def test_collect_api_response(self) -> None:
        collector = EvidenceCollector()
        ev = collector.collect_api_response("/api/v1/status", {"status": "ok"})
        assert ev.evidence_type == EvidenceType.API_RESPONSE

    def test_collect_manual(self) -> None:
        collector = EvidenceCollector()
        ev = collector.collect_manual("auditor", "Verified on 2024-01-01")
        assert ev.evidence_type == EvidenceType.MANUAL


class TestEvidenceStore:
    def test_store_and_load(self, tmp_path) -> None:
        store = EvidenceStore(tmp_path / "evidence")
        ev = Evidence(
            evidence_type=EvidenceType.CONFIG,
            source="test",
            content={"key": "val"},
        )
        path = store.store(ev, report_id="report-1")
        assert path.exists()

        loaded = store.load(path)
        assert loaded.source == ev.source
        assert loaded.content == ev.content

    def test_store_many(self, tmp_path) -> None:
        store = EvidenceStore(tmp_path / "evidence")
        items = [
            Evidence(evidence_type=EvidenceType.LOG, source=f"s{i}", content=f"c{i}")
            for i in range(3)
        ]
        paths = store.store_many(items, report_id="r1")
        assert len(paths) == 3
        assert all(p.exists() for p in paths)

    def test_list_evidence(self, tmp_path) -> None:
        store = EvidenceStore(tmp_path / "evidence")
        ev = Evidence(evidence_type=EvidenceType.CONFIG, source="test", content={})
        store.store(ev, report_id="r1")
        store.store(ev, report_id="r2")

        all_files = store.list_evidence()
        assert len(all_files) == 2

        r1_files = store.list_evidence(report_id="r1")
        assert len(r1_files) == 1

    def test_get_stats(self, tmp_path) -> None:
        store = EvidenceStore(tmp_path / "evidence")
        ev = Evidence(evidence_type=EvidenceType.CONFIG, source="test", content={})
        store.store(ev, report_id="r1")
        stats = store.get_stats()
        assert stats["total_files"] == 1
        assert stats["total_size_bytes"] > 0
