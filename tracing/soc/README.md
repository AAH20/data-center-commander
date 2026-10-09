# SOC Tracing Architecture — Data Center Commander
# OpenTelemetry + Jaeger + Tempo + AutoScaling + Container Tracing

## Overview

This module provides end-to-end distributed tracing with SOC (Security Operations Center) integration for the Data Center Commander platform. It enables:

1. **Distributed Tracing** — OpenTelemetry Collector receives traces from all services via OTLP
2. **Trace Storage** — Jaeger (query UI) + Tempo (long-term storage, Grafana-native)
3. **SOC Integration** — Real-time threat detection from trace spans, alerting, and SIEM export
4. **AutoScaling** — HPA with custom metrics derived from trace data (request rate, error rate, latency)
5. **Container Tracing** — DaemonSet-based node-level trace collection with k8s metadata enrichment

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Applications                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │   App A  │  │   App B  │  │   App C  │  │   App D  │            │
│  │ (OTel SDK)│  │ (OTel SDK)│  │ (OTel SDK)│  │ (OTel SDK)│            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │              │              │              │                   │
│       └──────────────┴──────────────┴──────────────┘                   │
│                              │                                        │
│                         OTLP (gRPC/HTTP)                              │
│                              │                                        │
│  ┌───────────────────────────┴───────────────────────────┐            │
│  │              OTel Collector (Deployment)               │            │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │            │
│  │  │  Receiver   │→ │  Processor   │→ │  Exporter    │  │            │
│  │  │  (OTLP)     │  │  (tail samp) │  │  (multi)     │  │            │
│  │  └─────────────┘  └──────────────┘  └──────┬───────┘  │            │
│  │                                           │          │            │
│  │  ┌────────────────────────────────────────┼───────┐  │            │
│  │  │         Container Agent (DaemonSet)    │       │  │            │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │            │
│  │  │  │ Filelog  │  │ K8s Attr │  │ Resource │    │  │            │
│  │  │  └──────────┘  └──────────┘  └──────────┘    │  │            │
│  │  └───────────────────────────────────────────────┘  │            │
│  └──────────────────────────────────────────────────────┘            │
│                              │                                        │
│         ┌────────────────────┼────────────────────┐                   │
│         │                    │                    │                   │
│         ▼                    ▼                    ▼                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐             │
│  │   Jaeger    │     │    Tempo    │     │  SOC Proc   │             │
│  │  (Query UI) │     │  (Storage)  │     │  (Webhook)  │             │
│  │  :16686     │     │  :3200      │     │  :8080      │             │
│  └─────────────┘     └─────────────┘     └──────┬──────┘             │
│                                                 │                     │
│                                    ┌────────────┼────────────┐        │
│                                    │            │            │        │
│                                    ▼            ▼            ▼        │
│                             ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│                             │   SIEM   │ │  Alert   │ │  Threat  │   │
│                             │  (ES)    │ │ Webhook  │ │  Score   │   │
│                             └──────────┘ └──────────┘ └──────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    AutoScaling (HPA + KEDA)                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │    │
│  │  │  Trace   │  │  Error   │  │ Latency  │  │  KEDA    │      │    │
│  │  │  Volume  │  │  Rate    │  │  P99     │  │  Scaler  │      │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │    │
│  └──────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. OpenTelemetry Collector (`k8s/otel-collector.yaml`)
- Receives OTLP traces from applications
- Tail sampling: keeps all errors, spans >500ms, 10% probabilistic
- Exports to Jaeger, Tempo, and SOC webhook
- Resource processor adds `environment`, `cluster`, `soc.tier` labels

### 2. Jaeger (`k8s/jaeger.yaml`)
- All-in-one deployment for dev/test
- OTLP-enabled receiver
- Ingress at `jaeger.data-center.local`
- Memory storage (use Elasticsearch for production)

### 3. Tempo (`k8s/tempo.yaml`)
- Distributed tracing backend
- OTLP + Zipkin receivers
- Local storage with 24h block retention
- Metrics generator for span-metrics and service-graphs

### 4. Container Tracing (`k8s/container-tracing.yaml`)
- DaemonSet on every node
- Filelog receiver for container logs
- K8s attributes processor for pod/node metadata
- NetworkPolicy restricting egress to OTel Collector

### 5. SOC Processor (`soc/trace_processor.py`)
- Receives trace batches via webhook
- Enriches spans with threat scores
- Detects: SQL injection, XSS, path traversal, command injection, SSRF
- Exports to Elasticsearch SIEM
- Sends alerts for high-threat spans (score >= 50)

### 6. AutoScaling (`k8s/hpa-custom-metrics.yaml`)
- HPA with trace-based custom metrics:
  - `traces_span_count` — request rate per pod
  - `traces_span_errors` — error rate per pod
  - `traces_latency_p99` — P99 latency per pod
- KEDA ScaledObject for event-driven scaling
- Scale-up: fast (30s stabilization, 100% increase)
- Scale-down: conservative (300s stabilization, 25% decrease)

### 7. Dashboards (`dashboards/`)
- **tracing-overview.json** — Trace volume, latency, error rate by service
- **soc-security.json** — Threat scores, attack pattern detection
- **autoscaling.json** — HPA replica counts, scaling events
- **container-tracing.json** — Container/pod/node trace distribution

### 8. Alerts (`alerts/prometheus-rules.yaml`)
- Pipeline health: OTel Collector, Jaeger, Tempo down
- Volume anomalies: spike/drop detection
- Error rate: >5% threshold
- Latency: P99 > 1000ms
- Threats: high threat score, SQL injection, XSS, path traversal
- AutoScaling: HPA maxed out, scale-down stuck
- Container: agent down, trace gap

### 9. Policies (`policies/`)
- **tracing.rego** — OPA policies enforcing trace requirements
- **checkov_tracing.py** — Checkov custom policies for IaC scanning

## Deployment

```bash
# Deploy all tracing infrastructure
kubectl apply -k tracing/soc/k8s/

# Or deploy individually
kubectl apply -f tracing/soc/k8s/jaeger.yaml
kubectl apply -f tracing/soc/k8s/tempo.yaml
kubectl apply -f tracing/soc/k8s/otel-collector.yaml
kubectl apply -f tracing/soc/k8s/container-tracing.yaml
kubectl apply -f tracing/soc/k8s/hpa-custom-metrics.yaml
kubectl apply -f tracing/soc/k8s/soc-processor.yaml
```

## Configuration

### Environment Variables (SOC Processor)
| Variable | Default | Description |
|----------|---------|-------------|
| `SIEM_URL` | `http://elasticsearch:9200` | Elasticsearch endpoint |
| `SIEM_INDEX` | `soc-traces` | SIEM index name |
| `ALERT_WEBHOOK` | (empty) | Webhook for high-threat alerts |
| `TRACE_RETENTION_DAYS` | `30` | Trace retention period |
| `PORT` | `8080` | HTTP listen port |

### OTel Collector Sampling
- **Errors**: 100% sampled
- **Latency > 500ms**: 100% sampled
- **Other**: 10% probabilistic

### AutoScaling Thresholds
| Metric | Scale Up | Scale Down |
|--------|----------|------------|
| Trace volume | > 1000 spans/sec/pod | < 500 spans/sec/pod |
| Error rate | > 50 errors/sec/pod | < 25 errors/sec/pod |
| P99 latency | > 500ms | < 200ms |

## Application Instrumentation

Applications must:
1. Use OpenTelemetry SDK (auto-instrumentation preferred)
2. Export to `otel-collector:4317` (gRPC) or `otel-collector:4318` (HTTP)
3. Include `service.name` resource attribute
4. Propagate trace context via `traceparent` header

### Example (Python)
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
```

### Example (Java)
```yaml
# Add to deployment env
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: "http://otel-collector:4317"
- name: OTEL_SERVICE_NAME
  value: "my-service"
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "environment=production,soc.tier=critical"
```

## SOC Integration

### Threat Detection
The SOC processor analyzes span attributes for:
- **SQL Injection**: `'`, `union`, `select`, `drop`, `insert`, `delete`, `--`
- **XSS**: `<script`, `javascript:`, `onerror=`, `onload=`
- **Path Traversal**: `../`, `..\\`, `/etc/passwd`, `/etc/shadow`
- **Command Injection**: `;`, `|`, `&`, `$()`, `` ` ``, `&&`, `||`
- **SSRF**: `http://169.254`, `http://localhost`, `http://127.0.0.1`

### Threat Score Calculation
- Error status: +30
- Sensitive attribute present: +5 each
- Attack pattern match: +25 each
- Long duration (>10s): +15
- Server span GET: +5
- **Max score: 100**

### Alerting
- Score >= 50: Alert sent to webhook
- Score >= 70: Critical severity
- Score < 50: Warning severity

## Monitoring

### Grafana
- Import dashboards from `tracing/soc/dashboards/`
- Configure Jaeger and Tempo datasources
- Set refresh to 30s

### Prometheus
- Import alert rules from `tracing/soc/alerts/prometheus-rules.yaml`
- Configure Alertmanager for notification routing

### Jaeger UI
- Access at `http://jaeger.data-center.local` (via Ingress)
- Or port-forward: `kubectl port-forward svc/jaeger-ui 16686:16686`

### Tempo
- Query via Grafana Tempo datasource
- Or API: `http://tempo:3200/api/search`

## Production Considerations

1. **Jaeger Storage**: Replace memory storage with Elasticsearch
2. **Tempo Storage**: Use S3/GCS for long-term trace storage
3. **OTel Collector**: Run as DaemonSet for node-level collection + Deployment for cluster-level
4. **Sampling**: Adjust tail sampling policies based on trace volume
5. **Retention**: Configure ILM in Elasticsearch for trace retention
6. **Security**: Enable mTLS between OTel components
7. **High Availability**: Run OTel Collector with >= 2 replicas
8. **Resource Limits**: Monitor memory usage; adjust `memory_limiter` processor

## Troubleshooting

### No traces in Jaeger/Tempo
1. Check OTel Collector logs: `kubectl logs -l app=otel-collector`
2. Verify apps are sending to correct endpoint
3. Check NetworkPolicies allow traffic
4. Verify tail sampling isn't dropping all spans

### SOC processor not receiving traces
1. Check webhook endpoint: `kubectl logs -l app=soc-processor`
2. Verify OTel Collector webhook exporter config
3. Check NetworkPolicy allows OTel Collector → SOC processor

### HPA not scaling
1. Verify custom metrics are being exposed: `kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1`
2. Check Prometheus is scraping OTel Collector metrics
3. Verify HPA metrics config matches metric names

### Container traces missing k8s metadata
1. Check DaemonSet is running on all nodes: `kubectl get ds -l app=otel-container-agent`
2. Verify k8sattributes processor config
3. Check service account has RBAC for k8s API
