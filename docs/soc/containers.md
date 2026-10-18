# Container Security & Orchestration

> **Version:** 1.0.0  
> **Last Updated:** September 2026

---

## Overview

The Data Center Commander runs a containerized logging and monitoring stack on Kubernetes. This document covers container images, security contexts, network policies, RBAC, and hardening recommendations.

## Container Images

### Production Images

| Component | Image | Version | Pull Policy |
|-----------|-------|---------|-------------|
| Elasticsearch | `docker.elastic.co/elasticsearch/elasticsearch` | 8.15.0 | IfNotPresent |
| Logstash | `docker.elastic.co/logstash/logstash` | 8.15.0 | IfNotPresent |
| Kibana | `docker.elastic.co/kibana/kibana` | 8.15.0 | IfNotPresent |
| Loki | `grafana/loki` | 3.2.0 | IfNotPresent |
| Promtail | `grafana/promtail` | 3.2.0 | IfNotPresent |
| Grafana | `grafana/grafana` | 11.2.0 | IfNotPresent |
| Filebeat | `docker.elastic.co/beats/filebeat` | 8.15.0 | IfNotPresent |
| Fluentd | `fluent/fluentd` | v1.17-1 | IfNotPresent |
| Log Processor | `python` | 3.12-slim | IfNotPresent |

### Image Security

```bash
# Scan images with Trivy
trivy image docker.elastic.co/elasticsearch/elasticsearch:8.15.0
trivy image grafana/loki:3.2.0
trivy image grafana/grafana:11.2.0

# Scan with Grype
grype docker.elastic.co/elasticsearch/elasticsearch:8.15.0
```

## Resource Allocation

### Requests and Limits

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| Elasticsearch | 500m | 1000m | 1Gi | 2Gi |
| Logstash | 250m | 500m | 512Mi | 1Gi |
| Kibana | 250m | 500m | 512Mi | 1Gi |
| Loki | 100m | 250m | 256Mi | 512Mi |
| Grafana | 100m | 250m | 256Mi | 512Mi |
| Filebeat | 50m | 100m | 100Mi | 200Mi |
| Fluentd | 50m | 100m | 128Mi | 256Mi |
| Promtail | 50m | 100m | 128Mi | 256Mi |
| Log Processor | 50m | 100m | 128Mi | 256Mi |

### JVM Settings

| Component | JVM Options |
|-----------|-------------|
| Elasticsearch | `-Xms512m -Xmx512m` |
| Logstash | `-Xms256m -Xmx256m` |

## Health Checks

### Readiness Probes

| Component | Probe Type | Path | Port | Initial Delay | Period |
|-----------|-----------|------|------|---------------|--------|
| Elasticsearch | HTTP GET | `/_cluster/health` | 9200 | 30s | 10s |
| Logstash | HTTP GET | `/` | 9600 | 30s | 10s |
| Kibana | HTTP GET | `/api/status` | 5601 | 30s | 10s |
| Loki | HTTP GET | `/ready` | 3100 | 15s | 10s |
| Grafana | HTTP GET | `/api/health` | 3000 | 15s | 10s |

### Liveness Probes

| Component | Probe Type | Path | Port | Initial Delay | Period |
|-----------|-----------|------|------|---------------|--------|
| Elasticsearch | HTTP GET | `/_cluster/health` | 9200 | 60s | 15s |
| Kibana | HTTP GET | `/api/status` | 5601 | 60s | 15s |
| Loki | HTTP GET | `/ready` | 3100 | 30s | 15s |
| Grafana | HTTP GET | `/api/health` | 3000 | 30s | 15s |

## Network Policies

### Default Deny

```yaml
# Deny all ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: data-center-commander
spec:
  podSelector: {}
  policyTypes:
    - Ingress

# Deny all egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: data-center-commander
spec:
  podSelector: {}
  policyTypes:
    - Egress
```

### Allowed Traffic Matrix

| From → To | Port | Protocol | Policy Name |
|-----------|------|----------|-------------|
| Ingress Controller → Kibana | 5601 | TCP | `allow-kibana` |
| Ingress Controller → Grafana | 3000 | TCP | `allow-grafana` |
| Ingress Controller → Elasticsearch | 9200 | TCP | `allow-elasticsearch` |
| Logstash → Elasticsearch | 9200 | TCP | `allow-elasticsearch` |
| Kibana → Elasticsearch | 9200 | TCP | `allow-elasticsearch` |
| Log Processor → Elasticsearch | 9200 | TCP | `allow-elasticsearch` |
| Filebeat → Logstash | 5044 | TCP | `allow-logstash` |
| Fluentd → Logstash | 5044 | TCP | `allow-logstash` |
| Filebeat → Fluentd | 24224 | TCP/UDP | `allow-fluentd` |
| Fluentd → Elasticsearch | 9200 | TCP | `allow-fluentd` |
| Promtail → Loki | 3100 | TCP | `allow-loki` |
| Grafana → Loki | 3100 | TCP | `allow-grafana` |
| Grafana → Elasticsearch | 9200 | TCP | `allow-grafana` |
| Log Processor → Loki | 3100 | TCP | `allow-loki` |
| Elasticsearch (inter-pod) | 9300 | TCP | `allow-elasticsearch` |

## RBAC

### Filebeat ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: filebeat
  namespace: data-center-commander
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: filebeat
rules:
  - apiGroups: [""]
    resources:
      - namespaces
      - pods
      - nodes
    verbs:
      - get
      - watch
      - list
  - apiGroups: [""]
    resources:
      - nodes/stats
    verbs:
      - get
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: filebeat
subjects:
  - kind: ServiceAccount
    name: filebeat
    namespace: data-center-commander
roleRef:
  kind: ClusterRole
  name: filebeat
  apiGroup: rbac.authorization.k8s.io
```

## Persistent Storage

| Component | PVC Name | Size | Access Mode | Storage Class |
|-----------|----------|------|-------------|---------------|
| Elasticsearch | `elasticsearch-data` | 20Gi | ReadWriteOnce | standard |
| Loki | `loki-data` | 10Gi | ReadWriteOnce | standard |
| Grafana | `grafana-data` | 5Gi | ReadWriteOnce | standard |

## Security Hardening

### Recommended Pod Security Context

Add to every pod spec:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  privileged: false
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault
```

### Recommended Container Security Context

```yaml
containers:
  - name: elasticsearch
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL
```

### Pod Security Standards

Enforce at namespace level:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: data-center-commander
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

### Enable Elasticsearch Security

```yaml
env:
  - name: xpack.security.enabled
    value: "true"
  - name: xpack.security.http.ssl.enabled
    value: "true"
  - name: xpack.security.transport.ssl.enabled
    value: "true"
```

### Use External Secrets

```yaml
# Instead of plaintext env vars
env:
  - name: GF_SECURITY_ADMIN_PASSWORD
    valueFrom:
      secretKeyRef:
        name: grafana-credentials
        key: admin-password
```

## Ingress Configuration

### NGINX Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: kibana
  namespace: data-center-commander
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/proxy-body-size: "0"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
spec:
  ingressClassName: nginx
  rules:
    - host: kibana.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: kibana
                port:
                  number: 5601
```

### Ingress Hosts

| Host | Service | Port |
|------|---------|------|
| `kibana.local` | Kibana | 5601 |
| `grafana.local` | Grafana | 3000 |
| `elasticsearch.local` | Elasticsearch | 9200 |

## DaemonSets

### Filebeat DaemonSet

- Runs on every node
- Ships container logs and system logs to Logstash
- Uses `hostNetwork: true` for node-level log collection
- Mounts `/var/log` and `/var/lib/docker/containers`

### Fluentd DaemonSet

- Runs on every node
- Receives logs from Filebeat on port 24224
- Dual output: Elasticsearch and Loki
- Mounts `/var/log` for system log tailing

### Promtail DaemonSet

- Runs on every node
- Ships logs to Loki
- Mounts `/var/log` and `/var/lib/docker/containers`
- Uses `emptyDir` for positions file

## Logging Configuration

### Logstash Pipeline

```conf
input {
  beats { port => 5044 }
  tcp { port => 5000, codec => json_lines }
  udp { port => 5000, codec => json_lines }
}
filter {
  if [message] {
    grok {
      match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:msg}" }
    }
    date { match => ["timestamp", "ISO8601"], target => "@timestamp" }
  }
  mutate { remove_field => ["@version", "host", "agent", "ecs", "input", "log", "tags"] }
}
output {
  elasticsearch { hosts => ["http://elasticsearch:9200"], index => "logstash-%{+YYYY.MM.dd}" }
  stdout { codec => rubydebug }
}
```

### Loki Configuration

```yaml
auth_enabled: false
server:
  http_listen_port: 3100
common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 16
  ingestion_burst_size_mb: 32
```

## Cleanup

```bash
# Delete all resources
kubectl delete -k k8s/iac/

# Delete namespace (cascading)
kubectl delete namespace data-center-commander

# Delete specific component
kubectl delete deployment elasticsearch -n data-center-commander
kubectl delete hpa elasticsearch -n data-center-commander
kubectl delete pdb elasticsearch -n data-center-commander
```
