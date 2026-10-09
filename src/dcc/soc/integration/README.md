# SOC + AutoScaling + Container — Unified Integration

Monitoring and alerting only. No automated remediation actions.

## Components

### Unified Dashboard (`unified_dashboard.json`)

Single Grafana dashboard combining all three domains:

| Section | Panels |
|---------|--------|
| **Security Stats** | Critical vulnerabilities, Falco events, privileged containers, down targets |
| **Container Health** | CPU/memory usage timeseries, container restarts |
| **AutoScaling** | Current replicas, scale events, per-service CPU/memory, HPA replicas |
| **Infrastructure** | Network traffic, disk usage |
| **Distributions** | Vulnerability severity pie, Falco events by status |

**UID:** `soc-unified-dashboard`

### Unified Alert Rules (`unified_alert_rules.yml`)

24 alert rules across 4 groups:

| Group | Rules | Severity |
|-------|-------|----------|
| `soc_security_alerts` | 8 | critical, warning |
| `autoscaling_alerts` | 7 | warning, info |
| `container_health_alerts` | 5 | critical, warning |
| `infrastructure_alerts` | 4 | critical, warning |

Key alerts:
- `CriticalVulnerabilitiesDetected` — Trivy CRITICAL vulns
- `FalcoSecurityEventSpike` — >10 Falco events in 5m
- `ContainerEscapeAttempt` — Falco container escape
- `ReverseShellDetected` — Falco reverse shell
- `CryptocurrencyMiningDetected` — Falco crypto mining
- `AutoscalerAtMaxCapacity` — Replicas at max for 5m
- `HPAMaxedOut` — HPA at max replicas
- `ContainerMemoryNearLimit` — >95% memory for 2m
- `PrometheusTargetDown` — Target down for 1m

### Alertmanager Config (`unified_alertmanager.yml`)

Routes alerts by team and severity:

| Receiver | Channel | Severity Filter |
|----------|---------|-----------------|
| `critical-alerts` | #dcc-critical + PagerDuty | critical |
| `soc-team` | #soc-security + email | team=soc |
| `platform-team` | #platform-alerts + email | team=platform |
| `info-alerts` | #dcc-info | info |

Inhibition rules prevent alert storms (e.g., node down suppresses container alerts).

### Prometheus Scrape Config (`prometheus_unified_scrape.yml`)

Scrape targets for all components:

| Job | Target | Interval |
|-----|--------|----------|
| `prometheus` | localhost:9090 | default |
| `node-exporter` | localhost:9100 | default |
| `cadvisor` | localhost:8080 | default |
| `autoscaler` | autoscaler:9102 | 30s |
| `docker` | localhost:9323 | 30s |
| `kube-state-metrics` | kube-state-metrics:8080 | 30s |
| `trivy-exporter` | trivy:4954 | 300s |
| `falco-exporter` | falco-exporter:9370 | 30s |
| `checkov-exporter` | checkov-exporter:8081 | 600s |
| `otel-collector` | otel-collector:8888 | 15s |
| `jaeger` | jaeger:14269 | 15s |
| `tempo` | tempo:3200 | 15s |
| `soc-scanner` | soc-scanner:9103 | 600s |

## Usage

### Import Dashboard

1. Grafana → Dashboards → Import
2. Upload `unified_dashboard.json`
3. Select Prometheus datasource
4. Import

### Deploy Alert Rules

```bash
# Copy to Prometheus config directory
cp unified_alert_rules.yml docker/soc/prometheus/

# Reload Prometheus
docker compose -f docker/soc/docker-compose.yml exec prometheus kill -HUP 1
```

### Deploy Alertmanager Config

```bash
cp unified_alertmanager.yml docker/soc/alertmanager/
docker compose -f docker/soc/docker-compose.yml restart alertmanager
```

### Merge Scrape Config

Merge `prometheus_unified_scrape.yml` into your existing `prometheus.yml` under `scrape_configs`.

## Requirements

- Prometheus 2.40+
- Grafana 9.0+
- Alertmanager 0.25+
- Existing DCC SOC stack (Prometheus, Grafana, Alertmanager, Autoscaler, Falco, Trivy)

## License

MIT