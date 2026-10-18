# Data Center Commander — Kubernetes IaC

Kubernetes manifests for the Data Center Commander logging stack (ELK + Loki).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ingress (nginx)                          │
│  kibana.local  │  grafana.local  │  elasticsearch.local        │
└───────┬────────┴────────┬────────┴──────────────┬──────────────┘
        │                 │                       │
   ┌────▼────┐      ┌────▼────┐           ┌──────▼──────┐
   │ Kibana  │      │ Grafana │           │Elasticsearch│
   └────┬────┘      └────┬────┘           └──────┬──────┘
        │                 │                       │
        │                 │              ┌────────▼────────┐
        │                 │              │    Logstash     │
        │                 │              └────────┬────────┘
        │                 │                       │
        │          ┌──────▼──────┐         ┌──────▼──────┐
        │          │    Loki     │         │  Filebeat   │
        │          └──────┬──────┘         │  (DaemonSet)│
        │                 │                └──────┬──────┘
        │          ┌──────▼──────┐                │
        │          │  Promtail   │         ┌──────▼──────┐
        │          │ (DaemonSet) │         │   Fluentd   │
        │          └─────────────┘         │ (DaemonSet) │
        │                                  └─────────────┘
   ┌────▼─────────────┐
   │  Log Processor   │
   └──────────────────┘
```

## Components

| Component | Type | Description |
|-----------|------|-------------|
| Elasticsearch | Deployment | Search and analytics engine |
| Logstash | Deployment | Log processing pipeline |
| Kibana | Deployment | Visualization for Elasticsearch |
| Loki | Deployment | Log aggregation system |
| Promtail | DaemonSet | Log shipper for Loki |
| Grafana | Deployment | Visualization for Loki/ES |
| Filebeat | DaemonSet | Log shipper for Logstash |
| Fluentd | DaemonSet | Log forwarder/processor |
| Log Processor | Deployment | Custom log enrichment |

## Prerequisites

- Kubernetes cluster 1.25+
- NGINX Ingress Controller
- `kubectl` configured
- `kustomize` (optional, for building)

## Deployment

### Quick start

```bash
# Apply all manifests
kubectl apply -k k8s/iac/

# Or apply individually
kubectl apply -f k8s/iac/
```

### With Kustomize

```bash
# Build and apply
kustomize build k8s/iac/ | kubectl apply -f -

# Preview without applying
kustomize build k8s/iac/ | kubectl diff -f -
```

### Verify deployment

```bash
# Check all pods
kubectl get pods -n data-center-commander

# Check services
kubectl get svc -n data-center-commander

# Check ingress
kubectl get ingress -n data-center-commander

# View logs
kubectl logs -n data-center-commander -l app=elasticsearch
kubectl logs -n data-center-commander -l app=loki
kubectl logs -n data-center-commander -l app=grafana
```

## Access

Add to `/etc/hosts`:
```
127.0.0.1  kibana.local grafana.local elasticsearch.local
```

Or use port-forwarding:
```bash
kubectl port-forward -n data-center-commander svc/kibana 5601:5601
kubectl port-forward -n data-center-commander svc/grafana 3000:3000
kubectl port-forward -n data-center-commander svc/elasticsearch 9200:9200
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Kibana | http://kibana.local:5601 | None (security disabled) |
| Grafana | http://grafana.local:3000 | admin/admin |
| Elasticsearch | http://elasticsearch.local:9200 | None (security disabled) |

## Scaling

HPAs are configured for:
- Elasticsearch: 1-3 replicas (CPU 70%, Memory 80%)
- Logstash: 1-3 replicas (CPU 70%, Memory 80%)
- Kibana: 1-2 replicas (CPU 70%, Memory 80%)
- Loki: 1-3 replicas (CPU 70%, Memory 80%)
- Grafana: 1-2 replicas (CPU 70%, Memory 80%)

## High Availability

PDBs ensure at least 1 pod is always available during voluntary disruptions.

## Network Policies

Default-deny policies are in place. Only explicitly allowed traffic is permitted between components.

## Storage

| Component | PVC | Size |
|-----------|-----|------|
| Elasticsearch | elasticsearch-data | 20Gi |
| Loki | loki-data | 10Gi |
| Grafana | grafana-data | 5Gi |

## Cleanup

```bash
kubectl delete -k k8s/iac/
# or
kubectl delete namespace data-center-commander
```
