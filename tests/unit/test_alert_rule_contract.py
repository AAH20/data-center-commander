"""Contract test: alert rules may only reference metrics this repository publishes.

An alert rule is not a control. ``expr: dcc_api_requests_total{status=~"5.."} > 0``
is inert when nothing publishes ``dcc_api_requests_total``: no series match, the
expression evaluates to the empty vector, and the alert never fires. The dashboard
stays green, the pager stays silent, and the result is indistinguishable from a
healthy system. That was the state of ``monitoring/prometheus/rules/dcc-alerts.yml``
before this test existed.

How the test keeps the two sides in sync:

* **Published names are collected from the code that publishes them**, not
  hardcoded -- the app's ``/metrics`` exposition (scraped through the real app) plus
  the metric registrations in ``monitoring/exporter/`` and
  ``monitoring/iac/exporter/``. Adding a metric therefore never requires editing
  this file.
* **Referenced names are collected by parsing every rule file** under
  ``monitoring/**/prometheus/`` and scraping the PromQL for series names.
* **Anything in between is a failure**, reported with the metric name, the alert
  and the file it lives in.

Series produced by a third-party exporter (node-exporter, kube-state-metrics,
cAdvisor, ...) cannot be verified against a cluster from a unit test. Those names
must be declared in ``EXTERNAL_METRICS`` (verified: a scrape job in this repository
collects them) or ``UNVERIFIED_EXTERNAL_METRICS`` (no producer confirmed; reported
as a gap rather than silently accepted). Application-owned names -- ``dcc_*``,
``api_*`` -- can never be allowlisted: an excuse for one of those is exactly the
defect this test exists to catch.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Directories holding Prometheus rule files. Every ``*.yml``/``*.yaml`` under these
#: that is a rule document (has a top-level ``groups:``) is parsed.
RULE_DIRECTORIES = (
    REPO_ROOT / "monitoring" / "prometheus",
    REPO_ROOT / "monitoring" / "iac" / "prometheus",
    REPO_ROOT / "monitoring" / "soc" / "prometheus",
)

#: Metric namespaces this repository is responsible for emitting. A rule over one of
#: these must be backed by this repository's code, never by an allowlist entry.
OWNED_PREFIXES = ("dcc_", "api_")

#: Series published by an exporter that this repository configures as a scrape
#: target. Value = the producer and the scrape job that collects it, so the
#: dependency is checkable by hand rather than implied.
EXTERNAL_METRICS: dict[str, str] = {
    # node-exporter -- job "node-exporter" in monitoring/iac and monitoring/soc
    "node_cpu_seconds_total": "node-exporter (job node-exporter), host CPU seconds by mode",
    "node_memory_MemAvailable_bytes": "node-exporter (job node-exporter), available memory",
    "node_memory_MemTotal_bytes": "node-exporter (job node-exporter), total memory",
    "node_filesystem_avail_bytes": "node-exporter (job node-exporter), filesystem bytes available",
    "node_filesystem_size_bytes": "node-exporter (job node-exporter), filesystem size",
    "node_network_receive_bytes_total": "node-exporter (job node-exporter), interface bytes received",
    "node_network_transmit_bytes_total": "node-exporter (job node-exporter), interface bytes sent",
    # kube-state-metrics -- job "kube-state-metrics" in monitoring/soc
    "kube_pod_container_info": "kube-state-metrics (job kube-state-metrics), container metadata",
    "kube_pod_container_status_running": "kube-state-metrics (job kube-state-metrics), container running flag",
    "kube_pod_container_status_ready": "kube-state-metrics (job kube-state-metrics), container readiness",
    "kube_pod_container_status_restarts_total": "kube-state-metrics (job kube-state-metrics), restart counter",
    "kube_pod_container_status_waiting_reason": "kube-state-metrics (job kube-state-metrics), waiting reason",
    "kube_pod_container_status_last_terminated_reason": "kube-state-metrics (job kube-state-metrics), last termination reason",
    "kube_pod_status_ready": "kube-state-metrics (job kube-state-metrics), pod readiness condition",
    "kube_pod_status_phase": "kube-state-metrics (job kube-state-metrics), pod phase",
    "kube_node_info": "kube-state-metrics (job kube-state-metrics), node metadata",
    "kube_node_spec_unschedulable": "kube-state-metrics (job kube-state-metrics), node cordon flag",
    "kube_horizontalpodautoscaler_status_current_replicas": "kube-state-metrics (job kube-state-metrics), HPA current replicas",
    "kube_horizontalpodautoscaler_status_desired_replicas": "kube-state-metrics (job kube-state-metrics), HPA desired replicas",
    "kube_horizontalpodautoscaler_spec_max_replicas": "kube-state-metrics (job kube-state-metrics), HPA max replicas",
    "kube_horizontalpodautoscaler_status_condition": "kube-state-metrics (job kube-state-metrics), HPA condition",
    # cAdvisor -- job "cadvisor" in monitoring/soc
    "container_cpu_cfs_periods_total": "cAdvisor (job cadvisor), CFS period counter",
    "container_cpu_cfs_throttled_periods_total": "cAdvisor (job cadvisor), CFS throttled periods",
    "container_memory_working_set_bytes": "cAdvisor (job cadvisor), container working set",
    "container_spec_memory_limit_bytes": "cAdvisor (job cadvisor), container memory limit",
    "container_fs_reads_bytes_total": "cAdvisor (job cadvisor), filesystem bytes read",
    "container_fs_writes_bytes_total": "cAdvisor (job cadvisor), filesystem bytes written",
    "container_network_transmit_bytes_total": "cAdvisor (job cadvisor), container bytes sent",
    # cluster-autoscaler -- job "cluster-autoscaler" in monitoring/soc
    "cluster_autoscaler_unneeded_nodes_count": "cluster-autoscaler (job cluster-autoscaler), unneeded node count",
    "cluster_autoscaler_unschedulable_pods_count": "cluster-autoscaler (job cluster-autoscaler), unschedulable pod count",
    # falco-exporter -- job "falco-exporter" in monitoring/soc
    "falco_events_total": "falco-exporter (job falco-exporter), runtime security events",
    # Prometheus scraping itself -- job "prometheus"
    "prometheus_tsdb_storage_blocks_bytes": "Prometheus (job prometheus), TSDB block storage size",
}

# ``up`` is deliberately absent from the dict above: Prometheus synthesises it for
# every scrape target, so it is part of the published set (see
# published_metric_names), not an external dependency to be excused.

#: Names no producer in this repository's scrape configuration is known to publish,
#: or whose existence in the upstream exporter's catalogue is doubtful. They are
#: listed rather than removed because deleting a security alert is worse than
#: admitting it is inert -- but the test emits a warning listing them so they cannot
#: be mistaken for coverage. Resolving each needs a decision, not a rule edit:
#: either point the rule at a series that exists, or add the exporter that emits it.
UNVERIFIED_EXTERNAL_METRICS: dict[str, str] = {
    "container_file_descriptors_open": (
        "cAdvisor catalogues only container_file_descriptors; neither _open nor _max "
        "is published, so ContainerFDLimitNear cannot fire as written"
    ),
    "container_file_descriptors_max": (
        "cAdvisor catalogues only container_file_descriptors; there is no per-container "
        "descriptor limit series, so ContainerFDLimitNear has no denominator"
    ),
    "container_processes_state": (
        "cAdvisor publishes container_processes and container_tasks_state "
        "(sleeping/running/stopped/uninterruptible/ioawaiting); there is no zombie state, "
        "so ContainerZombieProcesses cannot fire"
    ),
    "kube_pod_security_context": (
        "kube-state-metrics publishes no such family (adding it is an open KEP), and the "
        "runasnonroot label this rule selects on exists nowhere, so PodRunningAsRoot is inert"
    ),
    "kube_hostpath_volume_info": (
        "no kube-state-metrics family of this name is known; KSM models volumes as "
        "kube_pod_spec_volumes_*, so SensitiveHostPathMounted is likely inert"
    ),
    "etcd_server_leader_changes_seen_total": (
        "real etcd metric, but no etcd scrape target exists in monitoring/soc/prometheus.yml, "
        "so EtcdLeaderChanges cannot fire in this deployment"
    ),
    "kubernetes_audit_events_total": (
        "no audit-log exporter is configured anywhere in this repository, so "
        "KubernetesAuditAnomaly cannot fire"
    ),
    "network_policy_violations_total": (
        "no calico/cilium metrics target is configured; the rule is a documented "
        "placeholder ('if calico/cilium metrics available') with nothing behind it"
    ),
}

# PromQL tokens that are functions, keywords, aggregation operators or durations --
# never series names.
_PROMQL_NOISE = {
    "abs", "absent", "absent_over_time", "and", "avg", "avg_over_time", "bool",
    "bottomk", "by", "ceil", "changes", "clamp_max", "clamp_min", "count",
    "count_over_time", "day_of_month", "day_of_week", "days_in_month", "delta",
    "deriv", "exp", "floor", "group", "group_left", "group_right",
    "histogram_quantile", "hour", "idelta", "ignoring", "increase", "info",
    "irate", "label_replace", "last_over_time", "le", "limit_ratio", "limitk",
    "ln", "log2", "log10", "max", "max_over_time", "min", "min_over_time",
    "minute", "month", "offset", "on", "or", "predict_linear",
    "present_over_time", "quantile", "rate", "resets", "round", "scalar",
    "sort", "sort_desc", "sqrt", "stddev", "stddev_over_time", "sum",
    "sum_over_time", "time", "topk", "unless", "vector", "without", "year",
}

_STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_LABEL_SELECTOR = re.compile(r"\{[^{}]*\}")
_RANGE_SELECTOR = re.compile(r"\[[^\]]*\]")
_MODIFIER_CLAUSE = re.compile(
    r"\b(?:by|without|on|ignoring|group_left|group_right)\s*\([^)]*\)"
)
_IDENTIFIER = re.compile(r"[a-zA-Z_][a-zA-Z0-9_:]*")

#: Legal Prometheus metric name. The app currently emits histogram families named
#: after route templates ("/v2/assets"), which Prometheus cannot ingest at all --
#: those are excluded here and reported by the exposition, not counted as published.
_VALID_METRIC_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_:]*$")


# ---------------------------------------------------------------------------
# Rule side
# ---------------------------------------------------------------------------


def rule_files() -> list[Path]:
    """Every Prometheus rule document under RULE_DIRECTORIES."""
    found: list[Path] = []
    for directory in RULE_DIRECTORIES:
        for path in sorted(directory.rglob("*")):
            if path.suffix not in {".yml", ".yaml"}:
                continue
            try:
                document = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:  # a rule file that does not load is a finding
                raise AssertionError(f"{path} is not valid YAML: {exc}") from exc
            if isinstance(document, dict) and isinstance(document.get("groups"), list):
                found.append(path)
    return found


def rules() -> list[dict]:
    """Every alerting rule, flattened across files and groups."""
    collected: list[dict] = []
    for path in rule_files():
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for group in document["groups"]:
            for rule in (group or {}).get("rules") or []:
                if isinstance(rule, dict) and rule.get("alert"):
                    collected.append(
                        {
                            "alert": str(rule["alert"]),
                            "expr": str(rule.get("expr", "")),
                            "file": str(path.relative_to(REPO_ROOT)),
                            "group": str((group or {}).get("name", "")),
                        }
                    )
    return collected


def metric_names_in(expr: str) -> set[str]:
    """Series names referenced by a PromQL expression.

    Label selectors, range selectors and ``by``/``without``/``on`` clauses are
    removed first; what remains is identifiers that are not function calls and not
    PromQL syntax. Durations (``5m``) never match because an identifier cannot
    start with a digit.
    """
    text = _STRING_LITERAL.sub(" ", expr)
    text = _LABEL_SELECTOR.sub(" ", text)
    text = _RANGE_SELECTOR.sub(" ", text)
    previous = None
    while previous != text:
        previous = text
        text = _MODIFIER_CLAUSE.sub(" ", text)

    names: set[str] = set()
    for match in _IDENTIFIER.finditer(text):
        name = match.group(0)
        if name in _PROMQL_NOISE:
            continue
        if text[match.end():].lstrip().startswith("("):
            continue  # function or aggregation call, not a series
        names.add(name)
    return names


# ---------------------------------------------------------------------------
# Publisher side
# ---------------------------------------------------------------------------


def application_metric_names() -> set[str]:
    """Metric names the served application exposes at /metrics.

    Scraped through the real app rather than read from a list, so a new metric is
    picked up automatically. Histograms contribute their ``_bucket``/``_sum``/
    ``_count`` children, which is how PromQL refers to them.

    The scrape drives both a successful request and a failing one because the
    engine only creates a counter family when it is first incremented: a
    zero-traffic ``api_errors_total`` does not exist in the exposition yet, and a
    rule over it is not broken -- it simply has nothing to fire on until an error
    happens. Both families must therefore be materialised before the exposition is
    read, or the test would report a working rule as unsourced.
    """
    from fastapi.testclient import TestClient

    from dcc.api_async import app

    client = TestClient(app)
    client.get("/openapi.json")  # 200 -> api_requests_total{route=...}
    client.get("/contract-test-no-such-route")  # 404 -> api_errors_total{route,type}
    body = client.get("/metrics").text

    published: set[str] = set()
    for line in body.splitlines():
        match = re.match(r"# TYPE (\S+) (counter|gauge|histogram|summary)", line)
        if not match:
            continue
        name, kind = match.group(1), match.group(2)
        if not _VALID_METRIC_NAME.match(name):
            # Not addressable in PromQL; the exposition itself needs fixing.
            continue
        published.add(name)
        if kind == "histogram":
            published |= {f"{name}_bucket", f"{name}_sum", f"{name}_count"}
        elif kind == "summary":
            published |= {f"{name}_sum", f"{name}_count"}
    return published


def exporter_metric_names() -> set[str]:
    """Metric names the exporters under monitoring/ register, read from source.

    ``monitoring/exporter/dcc_exporter.py`` writes plain ``_metrics["name"]`` keys;
    ``monitoring/iac/exporter/exporter.py`` registers prometheus_client objects.
    """
    names: set[str] = set()

    dcc_exporter = REPO_ROOT / "monitoring" / "exporter" / "dcc_exporter.py"
    names |= set(
        re.findall(
            r"_metrics\[\s*[\"']([a-zA-Z_][a-zA-Z0-9_]*)[\"']\s*\]",
            dcc_exporter.read_text(encoding="utf-8"),
        )
    )

    iac_exporter = REPO_ROOT / "monitoring" / "iac" / "exporter" / "exporter.py"
    names |= set(
        re.findall(
            r"\b(?:Gauge|Counter|Histogram|Summary|Info|Enum)\(\s*[\"']([a-zA-Z_][a-zA-Z0-9_]*)[\"']",
            iac_exporter.read_text(encoding="utf-8"),
        )
    )
    return names


def published_metric_names() -> set[str]:
    """Everything this repository emits, plus series Prometheus synthesises."""
    return application_metric_names() | exporter_metric_names() | {"up"}


def referenced_metric_names() -> dict[str, set[str]]:
    """Referenced metric name -> alerts that reference it."""
    references: dict[str, set[str]] = {}
    for rule in rules():
        for name in metric_names_in(rule["expr"]):
            references.setdefault(name, set()).add(rule["alert"])
    return references


def allowlisted() -> set[str]:
    return set(EXTERNAL_METRICS) | set(UNVERIFIED_EXTERNAL_METRICS)


# ---------------------------------------------------------------------------
# Extractor sanity
# ---------------------------------------------------------------------------


class TestExtractor:
    """If the extractor is wrong the whole contract is decoration."""

    def test_reads_a_bare_series(self):
        assert metric_names_in("dcc_api_healthy == 0") == {"dcc_api_healthy"}

    def test_ignores_labels_ranges_and_durations(self):
        found = metric_names_in('sum(rate(dcc_api_requests_total{status=~"5.."}[5m]))')
        assert found == {"dcc_api_requests_total"}

    def test_ignores_function_names_and_aggregation_clauses(self):
        found = metric_names_in(
            "count by (namespace, pod) (kube_pod_status_phase{phase=~\"Pending|Unknown\"} == 1)"
        )
        assert found == {"kube_pod_status_phase"}

    def test_reads_both_sides_of_a_boolean_or(self):
        found = metric_names_in(
            "dcc_latest_telemetry_age_seconds > 3600 or dcc_latest_telemetry_age_seconds < 0"
        )
        assert found == {"dcc_latest_telemetry_age_seconds"}

    def test_histogram_quantile_keeps_the_bucket_series(self):
        found = metric_names_in(
            "histogram_quantile(0.95, sum(rate(some_duration_seconds_bucket[5m])) by (le, route))"
        )
        assert found == {"some_duration_seconds_bucket"}


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


class TestAlertRuleContract:
    def test_rule_files_are_discovered(self):
        """Guards against a green suite that parsed nothing."""
        files = rule_files()
        assert files, f"no Prometheus rule files found under {RULE_DIRECTORIES}"
        assert len(rules()) >= 40, (
            f"only {len(rules())} alert rules parsed from {len(files)} file(s); the "
            "extractor is not seeing the rule set it is supposed to police"
        )

    def test_rule_files_are_valid_yaml(self):
        for path in rule_files():
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert isinstance(document["groups"], list), f"{path}: groups must be a list"

    def test_every_rule_expression_references_at_least_one_metric(self):
        """An expression that names no series cannot be monitored either."""
        for rule in rules():
            assert metric_names_in(rule["expr"]), (
                f"{rule['file']}: {rule['alert']} has an expression with no series name: "
                f"{rule['expr']!r}"
            )

    def test_every_referenced_metric_is_published_or_declared(self):
        """The contract: no rule may point at a series nothing produces."""
        published = published_metric_names()
        declared = allowlisted()

        unbacked: list[str] = []
        for name, alerts in sorted(referenced_metric_names().items()):
            if name in published or name in declared:
                continue
            where = ", ".join(sorted(alerts))
            unbacked.append(f"{name} (referenced by {where})")

        assert not unbacked, (
            "Alert rules reference metric(s) that nothing publishes, so the rules can "
            "never fire -- a permanently silent alert looks exactly like a healthy "
            "system:\n  " + "\n  ".join(unbacked) + "\n\nEither point the rule at a "
            "series this repository emits, mark the rule INACTIVE with the reason, or "
            "declare the series in EXTERNAL_METRICS if a configured exporter produces it."
        )

    def test_application_metrics_cannot_be_allowlisted(self):
        """An excuse for an app-owned name is the defect itself."""
        owned = sorted(n for n in allowlisted() if n.startswith(OWNED_PREFIXES))
        assert not owned, (
            f"allowlist entries in an application-owned namespace: {owned}. "
            "dcc_*/api_* series must be emitted by this repository's code; "
            "allowlisting one hides a rule that can never fire."
        )

    def test_allowlist_entries_are_documented(self):
        for name, reason in {**EXTERNAL_METRICS, **UNVERIFIED_EXTERNAL_METRICS}.items():
            assert isinstance(reason, str) and len(reason) >= 20, (
                f"allowlist entry {name!r} needs a reason naming the exporter that "
                f"publishes it; got {reason!r}"
            )

    def test_allowlist_entries_are_still_referenced(self):
        """A stale allowlist entry silently pre-authorises a future broken rule."""
        referenced = referenced_metric_names()
        stale = sorted(n for n in allowlisted() if n not in referenced)
        assert not stale, (
            f"allowlisted metrics no rule references any more: {stale}. Remove them, "
            "otherwise a later rule can reference them and pass unnoticed."
        )

    def test_allowlist_does_not_shadow_published_metrics(self):
        """If the repo now emits an allowlisted name, it is no longer external."""
        published = published_metric_names()
        shadowed = sorted(n for n in allowlisted() if n in published)
        assert not shadowed, (
            f"metrics are both published and allowlisted: {shadowed}. Drop them from "
            "the allowlist so the emitter, not the excuse, is what guarantees them."
        )

    def test_inactive_rules_are_marked_in_the_rule_files(self):
        """A rule disabled for lack of a series must say so where it lives."""
        disabled = [
            rule
            for rule in rules()
            if "INACTIVE" in rule["expr"] or "INACTIVE" in rule["alert"]
        ]
        assert not disabled, f"rule still active despite being marked INACTIVE: {disabled}"

        # And the annotation must exist where a commented-out rule used to be: every
        # file that comments rules out carries the marker next to them.
        marker = "INACTIVE:"
        commented_out = 0
        for path in rule_files():
            text = path.read_text(encoding="utf-8")
            commented_out += len(re.findall(r"^\s*#\s*-\s*alert:", text, re.MULTILINE))
            if re.search(r"^\s*#\s*-\s*alert:", text, re.MULTILINE):
                assert marker in text, (
                    f"{path.relative_to(REPO_ROOT)} disables rules without an "
                    f"'# INACTIVE:' reason -- a reader cannot tell it from active cover"
                )
        assert commented_out >= 2, (
            "expected the rules with no backing series to be retained, commented out, "
            f"in the rule files; found {commented_out}"
        )


class TestSabotageIsCaught:
    """Proves the contract is load-bearing, permanently.

    The regression that motivated this file: dcc_api_requests_total, a name the API
    has never emitted, sat in an alert expression for as long as the file existed.
    """

    @staticmethod
    def _unbacked(names: set[str]) -> set[str]:
        return names - published_metric_names() - allowlisted()

    def test_the_original_defect_would_fail(self):
        bad = metric_names_in(
            'sum(rate(dcc_api_requests_total{status=~"5.."}[5m])) '
            "/ sum(rate(dcc_api_requests_total[5m])) > 0.05"
        )
        assert self._unbacked(bad) == {"dcc_api_requests_total"}

    def test_the_other_two_defects_would_fail(self):
        assert self._unbacked(
            {"dcc_api_request_duration_seconds_bucket"}
        ) == {"dcc_api_request_duration_seconds_bucket"}
        assert self._unbacked({"dcc_database_errors_total"}) == {"dcc_database_errors_total"}

    def test_the_replacement_expressions_pass(self):
        fixed = metric_names_in(
            'sum(rate(api_errors_total{type=~"internal|timeout"}[5m])) '
            "/ sum(rate(api_requests_total[5m])) > 0.05"
        )
        assert self._unbacked(fixed) == set()


def test_unverified_external_metrics_are_reported():
    """Known gaps are surfaced, not quietly accepted.

    These are third-party series no test here can verify against a live cluster.
    They stay in the rules (deleting a security alert is worse than admitting it is
    inert) but they are named in a warning on every run of this module.
    """
    assert UNVERIFIED_EXTERNAL_METRICS, "the unverified set is gone -- did someone allowlist it silently?"
    warnings.warn(
        "alert rules reference series no producer in this repository is known to emit "
        f"({len(UNVERIFIED_EXTERNAL_METRICS)}): "
        + ", ".join(sorted(UNVERIFIED_EXTERNAL_METRICS))
        + " -- see UNVERIFIED_EXTERNAL_METRICS in tests/unit/test_alert_rule_contract.py",
        UserWarning,
        stacklevel=2,
    )
