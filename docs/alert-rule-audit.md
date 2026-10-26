# Alert rule audit

Measured 2026-10-26 against `c0c29ab`. Every claim below is from commands run on this tree,
quoted inline.

## Why an alert that cannot fire is worse than no alert

An alert rule is a control. If its expression references a series no producer emits, the rule
evaluates to nothing, stays silent forever, and appears in the configuration as coverage. A
dashboard full of green panels and a rules file full of named alerts read as monitoring while
providing none. This audit exists to separate rules that can fire from rules that cannot.

## Rule files and whether anything loads them

```
$ find . -name prometheus.yml | xargs grep -A6 rule_files
  docker/soc/prometheus/prometheus.yml      -> alert_rules.yml
  monitoring/iac/prometheus/prometheus.yml  -> alert_rules.yml
  monitoring/prometheus/prometheus.yml      -> alerts.yml, rules/dcc-alerts.yml
  monitoring/soc/prometheus/prometheus.yml  -> soc_alert_rules.yml
```

| Rule file | Alerts | Status |
|---|---|---|
| `monitoring/prometheus/alerts.yml` | 4 | **loaded** by `monitoring/prometheus/prometheus.yml` |
| `monitoring/prometheus/rules/dcc-alerts.yml` | 4 | **loaded**, and mounted by `monitoring/docker-compose.yml` |
| `monitoring/soc/prometheus/soc_alert_rules.yml` | 30 | **loaded** by `monitoring/soc/prometheus/prometheus.yml` |
| `monitoring/iac/prometheus/alert_rules.yml` | 13 | **loaded** by `monitoring/iac/prometheus/prometheus.yml` |
| `docker/soc/prometheus/alert_rules.yml` | 13 | **loaded** by `docker/soc/prometheus/prometheus.yml` |
| `logging/soc/12-soc-rules.yaml` | 10 | **loaded in-cluster**: a `monitoring.coreos.com/v1 PrometheusRule` referenced by `logging/soc/kustomization.yaml` |
| `tracing/soc/alerts/prometheus-rules.yaml` | 15 | **manual import only** |
| `security/soc/alerts/alert-rules.yaml` | 12 | **manual import only** |

The last two are bare `groups:` files that no `prometheus.yml` references. Their own READMEs
describe them as something an operator imports by hand:

```
tracing/soc/README.md:231   - Import alert rules from `tracing/soc/alerts/prometheus-rules.yaml`
security/soc/README.md:194  Deploy the alert rules from `alerts/alert-rules.yaml` to Prometheus.
```

That is documented behaviour rather than a hidden gap, so it is recorded here rather than
treated as a defect. It is still a deployment step nothing verifies: a cluster can run for
months with those 27 alerts never imported and no signal that they were skipped. Closing it
means mounting them like the others, which is a deployment decision, not a test fix.

## Rules whose series no producer emits

`tests/unit/test_alert_rule_contract.py` already refuses to let application-owned series
(`dcc_*`, `api_*`) be allowlisted, and reports third-party series it cannot confirm. Eight
names are in the unverified set:

```
container_file_descriptors_max        kube_hostpath_volume_info
container_file_descriptors_open       kube_pod_security_context
container_processes_state             kubernetes_audit_events_total
etcd_server_leader_changes_seen_total network_policy_violations_total
```

They are referenced in `monitoring/soc/prometheus/soc_alert_rules.yml`, which **is** loaded. So
the file is active and these specific rules are not.

### What the SOC stack actually scrapes

```
$ grep job_name monitoring/soc/prometheus/prometheus.yml
  prometheus, node-exporter, kube-state-metrics, cadvisor, kubelet,
  kubernetes-apiserver, kubernetes-pods, falco-exporter, cluster-autoscaler, grafana
```

So cAdvisor, kube-state-metrics, node-exporter, kubelet and the apiserver all have producers.
Two do not:

**`etcd_server_leader_changes_seen_total` cannot exist here.** There is no `etcd` job. On a
managed control plane (EKS, GKE, AKS) etcd is not reachable by the cluster's own Prometheus at
all, so an alert on it is inert by construction, not merely unconfigured. It needs replacing
with the provider's managed-equivalent signal, or deleting.

**`network_policy_violations_total` has no producer.** It is emitted by Cilium or Calico, and
neither appears in the scrape configuration. It is inert until a CNI with policy-verdict
metrics is deployed and scraped.

The remaining six names belong to exporters that *are* scraped, but the exact series names may
not exist in current versions. This audit does not claim they are emitted — it claims only that
a producer is configured. Confirming the metric names requires a live cluster, which was not
available, so they stay in the unverified list rather than being promoted to verified.

## What would make this trustworthy

1. A `promtool check rules` run in CI over every rules file. It catches malformed expressions
   at commit time; it cannot catch a valid expression over a series that does not exist.
2. A cluster-side check: `count by (__name__)` over the scraped series, diffed against the
   names the rules reference. That turns "no producer is configured" into "the series is
   absent from the last scrape", which is the assertion that actually matters.
3. Either mount the two manual-import files or delete them. A rules file whose deployment is a
   README instruction will drift from the cluster.

None of the three is implemented. Recording them here is the honest state; writing an alert
that cannot fire and calling it monitoring is not.
