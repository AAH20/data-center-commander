# Architecture — SOC, Auto Scaling & Containers

> **Version:** 1.0.0  
> **Last Updated:** September 2026

---

## System Architecture

The Data Center Commander SOC is a layered security operations platform that combines real-time monitoring, automated alerting, elastic scaling, and container isolation into a unified defense-in-depth architecture.

### Design Principles

1. **Defense in Depth** — Multiple overlapping security controls (network policies, RBAC, Pod Disruption Budgets, resource limits)
2. **Least Privilege** — Each component has only the minimum permissions required
3. **Observability First** — Every component emits metrics, logs, and traces
4. **Elastic by Default** — All stateless components scale horizontally via HPA
5. **Immutable Infrastructure** — Container images are versioned and reproducible

### Component Layers

```
Layer 5: Visualization & Alerting
┌─────────────────────────────────────────────────────┐
│  Grafana (Dashboards)  │  Alertmanager (Routing)    │
│  Kibana (Log Explorer) │  Prometheus (Alert Rules)  │
└─────────────────────────────────────────────────────┘
                         │
Layer 4: Metrics & Monitoring
┌─────────────────────────────────────────────────────┐
│  IaC Exporter (9091)  │  Node Exporter (9100)       │
│  Prometheus (9090)    │  Alertmanager (9093)        │
└─────────────────────────────────────────────────────┘
                         │
Layer 3: Policy Enforcement
┌─────────────────────────────────────────────────────┐
│  OPA/Rego (Admission)  │  Checkov (IaC Scan)        │
│  Azure Policy           │  AWS SCPs                  │
│  GCP Org Policies       │  Sentinel                  │
└─────────────────────────────────────────────────────┘
                         │
Layer 2: Compute & Orchestration
┌─────────────────────────────────────────────────────┐
│  Kubernetes (EKS/GKE/AKS)                           │
│  ├── HPA (Auto Scaling)                             │
│  ├── PDB (Disruption Budgets)                       │
│  ├── NetworkPolicies (Segmentation)                 │
│  └── RBAC (Access Control)                          │
└─────────────────────────────────────────────────────┘
                         │
Layer 1: Infrastructure
┌─────────────────────────────────────────────────────┐
│  Terraform (Multi-cloud IaC)                        │
│  Docker (Container Runtime)                         │
│  Docker Compose (Local Dev)                         │
└─────────────────────────────────────────────────────┘
```

## Data Flow

### Metrics Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Checkov  │────▶│  IaC     │────▶│Prometh- │────▶│ Grafana  │
│ JSON     │     │ Exporter │     │  eus     │     │Dashboard │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                 │
┌──────────┐     ┌────┴─────┐     ┌────┴─────┐
│Terraform │────▶│  IaC     │     │Alert-   │
│ Plan     │     │ Exporter │     │ manager  │
└──────────┘     └──────────┘     └──────────┘
```

### Log Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Filebeat │────▶│ Logstash │────▶│Elastic-  │────▶│  Kibana  │
│ (DS)     │     │          │     │ search   │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │
┌──────────┐     ┌────┴─────┐     ┌──────────┐     ┌──────────┐
│ Promtail │────▶│          │────▶│   Loki   │────▶│  Grafana │
│ (DS)     │     │          │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘

┌──────────┐     ┌──────────┐     ┌──────────┐
│ Fluentd  │────▶│   Dual   │────▶│ ES + Loki│
│ (DS)     │     │  Output  │     │          │
└──────────┘     └──────────┘     └──────────┘
```

### Alert Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Prometheus│────▶│ Alert-   │────▶│  Email   │     │  Pager   │
│ Rules    │     │ manager  │────▶│  Slack   │────▶│  Duty    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │
                 ┌────┴─────┐
                 │ Webhook  │
                 │ (Custom) │
                 └──────────┘
```

## Auto Scaling Architecture

### Horizontal Pod Autoscaler (HPA)

The HPA controller runs a control loop (default: 15s) that:

1. Fetches metrics from the metrics API (resource metrics: CPU/memory)
2. Calculates desired replicas: `desiredReplicas = ceil(currentReplicas × (currentMetricValue / desiredMetricValue))`
3. Applies scale-up/scale-down behavior policies
4. Updates the target Deployment's replica count

### Scaling Decision Matrix

| Component | Min | Max | CPU Target | Memory Target | Scale Up Stabilization | Scale Down Stabilization |
|-----------|-----|-----|------------|---------------|----------------------|------------------------|
| Elasticsearch | 1 | 3 | 70% | 80% | 60s | 300s |
| Logstash | 1 | 3 | 70% | 80% | 60s | 300s |
| Kibana | 1 | 2 | 70% | 80% | None | None |
| Loki | 1 | 3 | 70% | 80% | None | None |
| Grafana | 1 | 2 | 70% | 80% | None | None |

### Scale-Up Behavior

```yaml
scaleUp:
  stabilizationWindowSeconds: 60
  policies:
    - type: Percent
      value: 50
      periodSeconds: 60
```

- **Stabilization window**: 60 seconds — the HPA looks back 60s and picks the highest replica count to prevent thrashing
- **Policy**: Add up to 50% more replicas per 60-second period
- **Example**: 2 replicas → max 3 replicas in one scale-up event (2 × 1.5 = 3)

### Scale-Down Behavior

```yaml
scaleDown:
  stabilizationWindowSeconds: 300
  policies:
    - type: Percent
      value: 50
      periodSeconds: 60
```

- **Stabilization window**: 300 seconds (5 minutes) — conservative to avoid premature scale-down
- **Policy**: Remove up to 50% of replicas per 60-second period
- **Example**: 3 replicas → min 2 replicas in one scale-down event (3 × 0.5 = 1.5, rounded up to 2)

## Container Security Architecture

### Network Segmentation

The namespace implements a **default-deny** posture with explicit allow rules:

```
┌─────────────────────────────────────────────────────────────┐
│                  data-center-commander NS                    │
│                                                             │
│  ┌─────────────┐         ┌─────────────┐                   │
│  │  Kibana     │◀────────│  Ingress    │ (nginx)           │
│  │  :5601      │         │  Controller │                   │
│  └──────┬──────┘         └─────────────┘                   │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐         ┌─────────────┐                   │
│  │Elasticsearch│◀────────│  Logstash   │◀── Filebeat       │
│  │  :9200      │         │  :5044      │    (DS)            │
│  │  :9300      │         │  :5000      │                   │
│  └──────┬──────┘         └─────────────┘                   │
│         │                    ▲                              │
│         │                    │                              │
│  ┌──────┴──────┐      ┌──────┴──────┐                      │
│  │  Grafana    │      │  Fluentd    │◀── Filebeat          │
│  │  :3000      │      │  :24224     │    (DS)              │
│  └──────┬──────┘      └─────────────┘                      │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │    Loki     │◀── Promtail (DS)                          │
│  │  :3100      │                                           │
│  └─────────────┘                                           │
│                                                             │
│  Default Deny: All ingress + egress blocked                 │
│  Explicit Allow: Only the arrows shown above                │
└─────────────────────────────────────────────────────────────┘
```

### RBAC Model

| ServiceAccount | ClusterRole | Permissions |
|---------------|-------------|-------------|
| `filebeat` | `filebeat` | `get`, `watch`, `list` on namespaces, pods, nodes, nodes/stats |
| `default` | — | No explicit permissions (relies on default) |

### Pod Disruption Budgets

All deployments have `minAvailable: 1`, ensuring at least one pod survives voluntary disruptions (node drains, cluster upgrades).

## Deployment Modes

### Local Development (Docker Compose)

```bash
cd monitoring/iac
docker compose up -d
```

- Full stack: Prometheus, Grafana, Alertmanager, IaC Exporter, Node Exporter
- No Kubernetes required
- Checkov/Terraform output mounted as volumes

### Kubernetes (Production)

```bash
kubectl apply -k k8s/iac/
```

- Full ELK + Loki stack with HPA, PDBs, NetworkPolicies
- NGINX Ingress for external access
- Persistent volumes for Elasticsearch, Loki, Grafana

### Hybrid (Terraform)

```bash
cd logging/iac/terraform/environments/prod
terraform init && terraform apply
```

- Deploys logging infrastructure to cloud provider
- Supports dev and prod environments
- Prod includes TLS + authentication

## Security Considerations

### Current Posture

| Control | Status | Notes |
|---------|--------|-------|
| Network Policies | ✅ Enabled | Default-deny + explicit allow |
| RBAC | ✅ Enabled | Filebeat SA with minimal perms |
| Pod Disruption Budgets | ✅ Enabled | minAvailable=1 for all |
| Resource Limits | ✅ Enabled | All containers have requests/limits |
| Readiness Probes | ✅ Enabled | All deployments |
| Liveness Probes | ✅ Enabled | All deployments |
| Security Context | ⚠️ Partial | No `securityContext` on containers |
| TLS | ⚠️ Dev only | Prod uses Terraform with TLS |
| Authentication | ⚠️ Dev only | Grafana admin/admin, ES security disabled |
| Secrets Management | ⚠️ Basic | K8s Secrets for Grafana credentials |

### Recommended Hardening

1. **Add securityContext to all pods:**
   ```yaml
   securityContext:
     runAsNonRoot: true
     runAsUser: 1000
     readOnlyRootFilesystem: true
     allowPrivilegeEscalation: false
     capabilities:
       drop: ["ALL"]
   ```

2. **Enable TLS everywhere** — Use cert-manager or Terraform prod environment

3. **Use external secrets** — AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault

4. **Enable Elasticsearch security** — Set `xpack.security.enabled: true`

5. **Network policy for egress** — Restrict outbound traffic to specific CIDRs

6. **Pod Security Standards** — Enforce `restricted` PSS at namespace level
