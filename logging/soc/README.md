# Data Center Commander — SOC + AutoScaling + Container Logging

Security Operations Center (SOC) with auto-scaling and container-level log aggregation using Fluent Bit, Loki, and Elasticsearch.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ingress (nginx)                          │
│  soc-grafana.local  │  soc-elasticsearch.local                   │
└───────┬─────────────┴──────────────┬────────────────────────────┘
        │                            │
   ┌────▼────┐                ┌──────▼──────┐
   │ Grafana │                │Elasticsearch│
   └────┬────┘                └──────┬──────┘
        │                            │
   ┌────▼────┐                ┌──────▼──────┐
   │  Loki   │                │ Fluent Bit  │
   └────┬────┘                │ (DaemonSet) │
        │                     └──────┬──────┘
   ┌────▼────┐                       │
   │ Fluent  │◀──────────────────────┘
   │  Bit    │
   └─────────┘
```

## Components

| Component | Type | Description |
|-----------|------|-------------|
| Fluent Bit | DaemonSet | Container and host log collection, parsing, and routing |
| Loki | Deployment | Log aggregation and storage (30-day retention) |
| Elasticsearch | Deployment | Full-text log search and analytics |
| Grafana | Deployment | Unified SOC dashboards (Loki + Elasticsearch) |
| PrometheusRule | CRD | SOC alerting rules for security events |

## Features

### Container Logging
- Fluent Bit tails `/var/log/containers/*.log` with Docker JSON parser
- Kubernetes metadata enrichment (pod, namespace, container, host)
- Dual output: Loki (for Grafana) and Elasticsearch (for search)
- Host system logs via syslog parser

### SOC Alerting
- High error rate detection per container
- Crash loop detection
- Resource usage monitoring (CPU, memory)
- Network anomaly detection
- Log ingestion lag monitoring
- Elasticsearch heap monitoring
- Fluent Bit buffer overflow detection

### AutoScaling
- **Elasticsearch**: 1-3 replicas (CPU 70%, Memory 80%)
- **Loki**: 1-3 replicas (CPU 70%, Memory 80%)
- **Grafana**: 1-2 replicas (CPU 70%, Memory 80%)
- **Fluent Bit**: 1-5 replicas (CPU 70%, Memory 80%)
- Scale-up stabilization: 60s
- Scale-down stabilization: 300s

### High Availability
- PodDisruptionBudgets for all deployments
- Default-deny network policies with explicit allow rules
- RBAC with least-privilege access

## Prerequisites

- Kubernetes cluster 1.25+
- NGINX Ingress Controller
- `kubectl` configured
- `kustomize` (optional, for building)
- Prometheus Operator (for alerting rules)

## Deployment

### Quick start

```bash
# Apply all manifests
kubectl apply -k logging/soc/

# Or apply individually
kubectl apply -f logging/soc/
```

### With Kustomize

```bash
# Build and apply
kustomize build logging/soc/ | kubectl apply -f -

# Preview without applying
kustomize build logging/soc/ | kubectl diff -f -
```

### Verify deployment

```bash
# Check all pods
kubectl get pods -n soc

# Check services
kubectl get svc -n soc

# Check ingress
kubectl get ingress -n soc

# Check HPAs
kubectl get hpa -n soc

# View logs
kubectl logs -n soc -l app=fluent-bit
kubectl logs -n soc -l app=loki
kubectl logs -n soc -l app=grafana
kubectl logs -n soc -l app=elasticsearch
```

## Access

Add to `/etc/hosts`:
```
127.0.0.1  soc-grafana.local soc-elasticsearch.local
```

Or use port-forwarding:
```bash
kubectl port-forward -n soc svc/grafana 3000:3000
kubectl port-forward -n soc svc/elasticsearch 9200:9200
kubectl port-forward -n soc svc/loki 3100:3100
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://soc-grafana.local:3000 | admin/admin |
| Elasticsearch | http://soc-elasticsearch.local:9200 | None (security disabled) |
| Loki | http://localhost:3100 | None |
| Fluent Bit Metrics | http://localhost:2020 | None |

## SOC Dashboards

The SOC Overview dashboard includes:
- Log volume by namespace
- Error rate by container
- Top network talkers
- Pod restart statistics
- Log level distribution
- Active alerts table

## Alerting

Alerts are defined in `12-soc-rules.yaml` and require Prometheus Operator. Key alerts:

| Alert | Severity | Description |
|-------|----------|-------------|
| HighErrorRate | warning | >10% error rate for 5m |
| ContainerCrashLooping | critical | >5 restarts in 15m |
| HighMemoryUsage | warning | >85% memory for 10m |
| HighCPUUsage | warning | >80% CPU for 10m |
| PodNotReady | critical | Pod not ready for 15m |
| SuspiciousNetworkActivity | warning | >100MB/s network for 5m |
| LokiIngestionRateHigh | warning | >10MB/s ingestion |
| ElasticsearchHeapHigh | critical | >85% heap for 10m |
| FluentBitBufferOverflow | warning | Records being dropped |
| LogIngestionLag | warning | >5m ingestion delay |

## Storage

| Component | PVC | Size |
|-----------|-----|------|
| Elasticsearch | elasticsearch-data | 20Gi |
| Loki | loki-data | 10Gi |
| Grafana | grafana-data | 5Gi |

## Network Policies

Default-deny policies are in place. Only explicitly allowed traffic is permitted:
- Fluent Bit → Loki (3100), Elasticsearch (9200)
- Grafana → Loki (3100), Elasticsearch (9200)
- Ingress → Grafana (3000), Elasticsearch (9200), Fluent Bit (2020)

## Cleanup

```bash
kubectl delete -k logging/soc/
# or
kubectl delete namespace soc
```

## License

MIT
