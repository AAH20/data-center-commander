# API Reference — SOC Monitoring & Alerting

> **Version:** 1.0.0  
> **Last Updated:** September 2026

---

## IaC Exporter API

The IaC Exporter is a custom Prometheus exporter that scans Checkov JSON output and Terraform plan files to expose security and compliance metrics.

### Endpoint

```
GET http://localhost:9091/metrics
```

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CHECKOV_OUTPUT_DIR` | `/data/checkov` | Directory containing Checkov JSON results |
| `TERRAFORM_PLAN_DIR` | `/data/terraform` | Directory containing Terraform plan JSON |
| `SCRAPE_INTERVAL` | `300` | Seconds between metric refreshes |
| `PROMETHEUS_PORT` | `9091` | Exporter listen port |

### Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `iac_checkov_passed` | Gauge | — | Total passed Checkov checks |
| `iac_checkov_failed` | Gauge | — | Total failed Checkov checks |
| `iac_checkov_failed_critical` | Gauge | — | Critical severity failures |
| `iac_checkov_failed_high` | Gauge | — | High severity failures |
| `iac_checkov_failed_medium` | Gauge | — | Medium severity failures |
| `iac_checkov_failed_low` | Gauge | — | Low severity failures |
| `iac_compliance_score` | Gauge | — | Overall compliance score (0-100) |
| `iac_policy_category_failures` | Gauge | `category` | Failures by policy category |
| `iac_terraform_drift_detected` | Gauge | — | Terraform drift count |
| `iac_unencrypted_resources` | Gauge | — | Unencrypted resources count |
| `iac_public_exposure` | Gauge | — | Publicly exposed resources count |
| `iac_last_scan_timestamp` | Gauge | — | Unix timestamp of last scan |
| `iac_exporter_info` | Info | — | Exporter metadata |

### Policy Category Labels

The exporter extracts categories from Checkov check IDs:

| Check ID Pattern | Category |
|-----------------|----------|
| `DC_NET_*` | `NET` |
| `DC_STORAGE_*` | `STORAGE` |
| `DC_CRYPTO_*` | `CRYPTO` |
| `DC_IAM_*` | `IAM` |
| `DC_COMPUTE_*` | `COMPUTE` |
| `DC_LOGGING_*` | `LOGGING` |
| `DC_COMPLIANCE_*` | `COMPLIANCE` |
| `DC_ENCRYPTION_*` | `ENCRYPTION` |
| `DC_TAGGING_*` | `TAGGING` |
| Other | `OTHER` |

### Example Prometheus Queries

```promql
# Compliance score over time
iac_compliance_score

# Critical findings count
iac_checkov_failed_critical

# Failures by category
sum by (category) (iac_policy_category_failures)

# Compliance score drop alert
iac_compliance_score < 80

# Unencrypted resources
iac_unencrypted_resources > 0

# Public exposure
iac_public_exposure > 0

# Terraform drift
iac_terraform_drift_detected > 0

# Scan staleness (no scan in last hour)
time() - iac_last_scan_timestamp > 3600
```

---

## Prometheus Alert Rules

### Security Alerts

| Alert | Expression | For | Severity | Description |
|-------|-----------|-----|----------|-------------|
| `IACCriticalFindings` | `iac_checkov_failed_critical > 0` | 5m | critical | Any critical finding |
| `IACHighFindings` | `iac_checkov_failed_high > 5` | 10m | warning | More than 5 high findings |
| `IACMediumFindingsSpike` | `iac_checkov_failed_medium > 20` | 15m | warning | More than 20 medium findings |
| `IACComplianceScoreDrop` | `iac_compliance_score < 80` | 5m | critical | Compliance below 80% |
| `IACUnencryptedResources` | `iac_unencrypted_resources > 0` | 5m | warning | Unencrypted resources detected |
| `IACPublicExposure` | `iac_public_exposure > 0` | 5m | critical | Publicly exposed resources |

### Platform Alerts

| Alert | Expression | For | Severity | Description |
|-------|-----------|-----|----------|-------------|
| `IACExporterDown` | `up{job="iac-exporter"} == 0` | 5m | critical | Exporter unreachable |
| `PrometheusTargetDown` | `up == 0` | 2m | warning | Any target down |
| `MonitoringHighCPU` | `rate(container_cpu_usage_seconds_total[5m]) > 0.85` | 5m | warning | CPU > 85% |
| `MonitoringDiskSpaceLow` | `(node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.15` | 5m | warning | Disk < 15% available |
| `MonitoringMemoryPressure` | `(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) < 0.10` | 5m | warning | Memory < 10% available |
| `PrometheusStorageGrowth` | `prometheus_tsdb_storage_size_bytes > 20e9` | 30m | info | TSDB > 20GB |

---

## Kubernetes API

### HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: elasticsearch
  namespace: data-center-commander
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: elasticsearch
  minReplicas: 1
  maxReplicas: 3
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

**API Operations:**

```bash
# List all HPAs
kubectl get hpa -n data-center-commander

# Describe HPA (shows current vs desired replicas)
kubectl describe hpa elasticsearch -n data-center-commander

# Get HPA in YAML
kubectl get hpa elasticsearch -n data-center-commander -o yaml

# Watch HPA changes
kubectl get hpa -n data-center-commander -w
```

### PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: elasticsearch
  namespace: data-center-commander
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: elasticsearch
```

**API Operations:**

```bash
# List all PDBs
kubectl get pdb -n data-center-commander

# Describe PDB
kubectl describe pdb elasticsearch -n data-center-commander
```

### NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-elasticsearch
  namespace: data-center-commander
spec:
  podSelector:
    matchLabels:
      app: elasticsearch
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: logstash
      ports:
        - protocol: TCP
          port: 9200
```

**API Operations:**

```bash
# List all network policies
kubectl get networkpolicies -n data-center-commander

# Describe policy
kubectl describe networkpolicy allow-elasticsearch -n data-center-commander
```

---

## Grafana API

### Datasource Provisioning

Grafana is provisioned with two datasources:

| Datasource | Type | URL | Default |
|-----------|------|-----|---------|
| Loki | loki | `http://loki:3100` | Yes |
| Elasticsearch | elasticsearch | `http://elasticsearch:9200` | No |

### Dashboard Provisioning

Dashboards are provisioned from `/var/lib/grafana/dashboards`:

| Dashboard | File | Description |
|-----------|------|-------------|
| IaC Security & Compliance | `iac-security.json` | Security findings, compliance score, drift |
| Monitoring Infrastructure | `monitoring-infra.json` | CPU, memory, disk, network I/O |

### Access

```bash
# Port-forward to Grafana
kubectl port-forward -n data-center-commander svc/grafana 3000:3000

# Default credentials
# Username: admin
# Password: admin
```

---

## Elasticsearch API

### Cluster Health

```bash
curl http://elasticsearch:9200/_cluster/health?pretty
```

### Indices

```bash
# List all indices
curl http://elasticsearch:9200/_cat/indices?v

# Search logs
curl http://elasticsearch:9200/logstash-*/_search?pretty -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "level": "ERROR"
    }
  }
}'
```

---

## Loki API

### Readiness

```bash
curl http://loki:3100/ready
```

### Query Logs

```bash
# Query logs via API
curl -G http://loki:3100/loki/api/v1/query_range \
  --data-urlencode 'query={job="varlogs"}' \
  --data-urlencode 'start=now-1h' \
  --data-urlencode 'end=now'
```
