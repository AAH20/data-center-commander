"""SOC2-CC7.1 must expand a histogram family's derived series -- and only those.

The control compares the metric names alert rules reference against the names this
repository exports. Export names were collected by scanning string literals in the
publishing source, and a Prometheus histogram never carries its derived series as a
literal: ``record_latency("api_request_duration_seconds", ...)`` is the only spelling
in the code, while ``/metrics`` emits ``api_request_duration_seconds_bucket``,
``_sum`` and ``_count``. ``monitoring/prometheus/rules/dcc-alerts.yml``'s
``DCCHighLatency`` reads the bucket series, so the control reported a rule that works
as backed by a metric nothing exports, and SOC2-CC7.1 failed on a false positive.

The opposite error is worse than that one -- a control that accepts any name reports
nothing -- so the tests below pin both directions. Derived suffixes are granted only
to a family whose TYPE a real registration call states. A gauge or counter family
gets nothing derived from it, and a family that exists only in prose gets nothing
either, because a call written inside a docstring is not a declaration.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from dcc.compliance import observables

REPO_ROOT = Path(__file__).resolve().parents[2]
LATENCY_FAMILY = "api_request_duration_seconds"


def _rule_root(tmp_path: Path, expr: str) -> Path:
    (tmp_path / "rules.yml").write_text(
        textwrap.dedent(
            f"""
            groups:
              - name: probe
                rules:
                  - alert: ProbeAlert
                    expr: {expr}
                    labels:
                      severity: warning
            """
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(scope="module")
def exposition() -> str:
    """The real ``/metrics`` body, driven through an unmatched route.

    An unmatched path needs no database and still records one latency observation,
    which is what materialises the histogram family.
    """
    from fastapi.testclient import TestClient

    from dcc.api_async import app

    client = TestClient(app)
    client.get("/definitely-not-a-route-for-the-histogram-test")
    response = client.get("/metrics")
    assert response.status_code == 200
    return response.text


def _sample_names(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        names.add(line.split("{")[0].split(" ")[0])
    return names


# ---------------------------------------------------------------------------
# The reproduction: reality versus what the control believed
# ---------------------------------------------------------------------------


def test_the_app_really_publishes_the_bucket_series(exposition: str) -> None:
    """Grounds the fix in the exposition itself, not in the renderer's intent.

    If this fails the fix is pointless: the rule would be reading a series the app
    does not publish, and CC7.1 would be right to fail.
    """
    assert f"# TYPE {LATENCY_FAMILY} histogram" in exposition, (
        f"{LATENCY_FAMILY} is not declared a histogram in /metrics"
    )
    bucket_lines = [
        line
        for line in exposition.splitlines()
        if line.startswith(f"{LATENCY_FAMILY}_bucket{{")
    ]
    assert bucket_lines, f"/metrics publishes no {LATENCY_FAMILY}_bucket sample"
    assert any('le="+Inf"' in line for line in bucket_lines), (
        "the histogram has no +Inf bucket, so histogram_quantile cannot be computed"
    )

    samples = _sample_names(exposition)
    for suffix in ("_bucket", "_sum", "_count"):
        assert f"{LATENCY_FAMILY}{suffix}" in samples, (
            f"/metrics does not publish {LATENCY_FAMILY}{suffix}"
        )


def test_exported_series_match_the_exposition_for_the_latency_family(
    exposition: str,
) -> None:
    """The control's exported set agrees with the scraped body for this family."""
    exported = observables._exported_metrics()
    samples = _sample_names(exposition)
    for suffix in ("_bucket", "_sum", "_count"):
        name = f"{LATENCY_FAMILY}{suffix}"
        assert name in samples
        assert name in exported, (
            f"{name} is in /metrics but the control does not consider it exported"
        )


# ---------------------------------------------------------------------------
# Direction 1: a bucket reference for an exported histogram is satisfied
# ---------------------------------------------------------------------------


def test_the_repository_latency_rule_is_not_reported_as_unbacked() -> None:
    """The control's own verdict over this checkout's rules.

    ``DCCHighLatency`` is the rule that made the control fail. It reads a bucket
    series the app publishes, so the measurement must not name it as unbacked.
    """
    measurement = observables.measure_alert_coverage()

    unbacked_alerts = {u["alert"] for u in measurement.detail["unbacked"]}
    missing = sorted({m for u in measurement.detail["unbacked"] for m in u["missing_metrics"]})
    assert "DCCHighLatency" not in unbacked_alerts, (
        f"DCCHighLatency still reported unbacked; missing metrics: {missing}"
    )
    assert f"{LATENCY_FAMILY}_bucket" not in missing
    assert measurement.verdict is True, measurement.statement


def test_a_bucket_rule_over_an_exported_histogram_passes(tmp_path: Path) -> None:
    root = _rule_root(
        tmp_path,
        f'histogram_quantile(0.95, sum(rate({LATENCY_FAMILY}_bucket[5m])) by (le, route)) > 0.5',
    )
    measurement = observables.measure_alert_coverage(root=root)

    assert measurement.detail["unbacked"] == []
    assert measurement.verdict is True, measurement.statement


# ---------------------------------------------------------------------------
# Direction 2: a bucket for a family nothing declares is still missing
# ---------------------------------------------------------------------------


def test_a_bucket_for_an_absent_family_is_still_missing(tmp_path: Path) -> None:
    """The half that proves the check was not removed along with the false positive."""
    absent = "dcc_imaginary_histogram_seconds_bucket"
    root = _rule_root(tmp_path, f"rate({absent}[5m]) > 0")

    measurement = observables.measure_alert_coverage(root=root)

    assert measurement.verdict is False
    assert absent in measurement.statement
    assert measurement.detail["unbacked"] == [
        {"alert": "ProbeAlert", "missing_metrics": [absent]}
    ]


def test_a_bucket_suffix_is_not_granted_to_a_gauge_family(tmp_path: Path) -> None:
    """``iac_compliance_score`` is registered as a Gauge; it has no bucket series.

    Granting ``_bucket`` to every known name would make this test pass the rule, which
    is exactly the false negative this control is supposed to catch.
    """
    assert "iac_compliance_score" in observables._exported_metrics(), (
        "precondition: the gauge family must be a known exported name"
    )
    assert "iac_compliance_score_bucket" not in observables._exported_metrics()

    root = _rule_root(tmp_path, "rate(iac_compliance_score_bucket[5m]) > 0")
    measurement = observables.measure_alert_coverage(root=root)

    assert measurement.verdict is False
    assert "iac_compliance_score_bucket" in measurement.statement


def test_a_counter_family_does_not_gain_a_bucket(tmp_path: Path) -> None:
    """Counters are counters: ``api_requests_total`` publishes no ``_bucket``."""
    exported = observables._exported_metrics()
    assert "api_requests_total" in exported
    assert "api_requests_total_bucket" not in exported

    root = _rule_root(tmp_path, "rate(api_requests_total_bucket[5m]) > 0")
    assert observables.measure_alert_coverage(root=root).verdict is False


# ---------------------------------------------------------------------------
# Where the type knowledge comes from
# ---------------------------------------------------------------------------


def test_a_docstring_example_does_not_declare_a_histogram() -> None:
    """``MetricsEngine``'s docstring shows ``record_latency("api_request", ...)``.

    Prose is not a call site. If it counted, a rule over ``api_request_bucket`` would
    pass while nothing emits that series -- a false negative manufactured by the fix.
    """
    assert "api_request" in observables._exported_metrics(), (
        "precondition: the literal scanner still sees the docstring name"
    )
    assert "api_request_bucket" not in observables._exported_metrics()


def test_declared_families_reads_calls_and_ignores_prose(tmp_path: Path) -> None:
    module = tmp_path / "producer.py"
    module.write_text(
        textwrap.dedent(
            '''
            """Example: record_latency("prose_only", 0.1)."""

            from prometheus_client import Gauge, Histogram, Summary

            METRICS.record_latency("app_histogram_seconds", 0.1, labels={})
            METRICS.register_histogram("app_registered_seconds")
            Gauge("app_gauge", "a gauge")
            Histogram("exporter_histogram_seconds", "a histogram")
            Summary("exporter_summary_seconds", "a summary")
            '''
        ),
        encoding="utf-8",
    )

    families = observables._declared_families([module])

    assert families["app_histogram_seconds"] == frozenset({"_bucket", "_sum", "_count"})
    assert families["app_registered_seconds"] == frozenset({"_bucket", "_sum", "_count"})
    assert families["exporter_histogram_seconds"] == frozenset(
        {"_bucket", "_sum", "_count"}
    )
    assert families["exporter_summary_seconds"] == frozenset({"_sum", "_count"})
    assert "prose_only" not in families
    assert "app_gauge" not in families


def test_a_gauge_renders_a_bare_sample_and_no_derived_names() -> None:
    """A gauge has no derived series; the renderer agrees with the rule."""
    from dcc.observability.metrics import MetricsEngine, render_prometheus_text

    engine = MetricsEngine()
    engine.set_gauge("iac_test_gauge", 1.0)
    body = render_prometheus_text(engine.registry)

    samples = _sample_names(body)
    assert "iac_test_gauge" in samples
    assert "iac_test_gauge_bucket" not in samples
    assert "iac_test_gauge_sum" not in samples
    assert "iac_test_gauge_count" not in samples


def test_rendered_histogram_carries_exactly_the_declared_suffixes() -> None:
    """Cross-check the suffix rule against the renderer rather than an assumption."""
    from dcc.observability.metrics import MetricsEngine, render_prometheus_text

    engine = MetricsEngine()
    engine.record_latency("iac_test_histogram_seconds", 0.02)
    engine.set_gauge("iac_test_gauge_seconds", 1.0)
    body = render_prometheus_text(engine.registry)

    samples = _sample_names(body)
    assert "iac_test_histogram_seconds_bucket" in samples
    assert "iac_test_histogram_seconds_sum" in samples
    assert "iac_test_histogram_seconds_count" in samples
    assert "iac_test_histogram_seconds" not in samples, (
        "a histogram emits derived series only; a bare sample would be a distinct series"
    )
    assert "iac_test_gauge_seconds" in samples
    assert "iac_test_gauge_seconds_bucket" not in samples


def test_an_unparseable_source_declares_nothing(tmp_path: Path) -> None:
    """A file that will not parse must not license suffixes for anything."""
    broken = tmp_path / "broken.py"
    broken.write_text('record_latency("app_histogram_seconds"\n', encoding="utf-8")

    assert observables._declared_families([broken]) == {}


# ---------------------------------------------------------------------------
# The neighbouring rule in the same expression is still checked
# ---------------------------------------------------------------------------


def test_a_rule_mixing_an_exported_family_with_an_absent_one_still_fails(
    tmp_path: Path,
) -> None:
    """Satisfying the bucket reference must not excuse the other names in the rule."""
    root = _rule_root(
        tmp_path,
        f"rate({LATENCY_FAMILY}_bucket[5m]) > 0 and rate(dcc_imaginary_errors_total[5m]) > 0",
    )
    measurement = observables.measure_alert_coverage(root=root)

    assert measurement.verdict is False
    assert measurement.detail["unbacked"] == [
        {"alert": "ProbeAlert", "missing_metrics": ["dcc_imaginary_errors_total"]}
    ]
