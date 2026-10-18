# Kubernetes

## Overview

Kubernetes is the recommended production orchestration platform for Data Center
Commander. The `k8s/` directory contains a complete set of manifests for
deploying the API with high availability, auto-scaling, and network policies.

## Architecture

```
                    ┌──────────────┐
                    │   Ingress    │  (nginx, TLS termination)
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │   Service    │  ClusterIP :80
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────┴───┐  ┌────┴───┐  ┌────┴───┐
         │ API    │  │ API    │  │ API    │  (HPA: 2-10 replicas)
         │ Pod    │  │ Pod    │  │ Pod    │
         └────┬───┘  └────┬───┘  └────┬───┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────┴───────┐
                    │  PostgreSQL  │  (external or separate StatefulSet)
                    └──────────────┘
```

## Prerequisites

- Kubernetes 1.25+ cluster
- `kubectl` configured with cluster access
- An existing PostgreSQL database (or deploy one separately)
- An ingress controller (e.g. nginx-ingress) installed in the cluster

## Quick Start

### 1. Build and Push the Container Image

```bash
docker build -t data-center-commander:latest .
docker tag data-center-commander:latest your-registry/data-center-commander:latest
docker push your-registry/data-center-commander:latest
```

Update the image in `kustomization.yaml` or `04-deployment.yaml` to match your registry.

### 2. Configure Secrets

Edit `02-secret.yaml` and replace the placeholder `DCC_DATABASE_URL` with a
base64-encoded PostgreSQL connection string:

```bash
echo -n 'postgresql://user:password@host:5432/data_center_commander' | base64
```

For production, use an external secret manager (External Secrets Operator,
AWS Secrets Manager, HashiCorp Vault) instead of committing secrets.

### 3. Configure Ingress

Edit `06-ingress.yaml`:
- Replace `dcc.example.com` with your domain
- Create a TLS secret: `kubectl create secret tls dcc-tls --cert=tls.crt --key=tls.key -n data-center-commander`
- Adjust `kubernetes.io/ingress.class` if not using nginx

### 4. Apply Manifests

Using Kustomize (recommended):

```bash
kubectl apply -k k8s/
```

Or apply individually:

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secret.yaml
kubectl apply -f k8s/03-serviceaccount.yaml
kubectl apply -f k8s/04-deployment.yaml
kubectl apply -f k8s/05-service.yaml
kubectl apply -f k8s/06-ingress.yaml
kubectl apply -f k8s/07-hpa.yaml
kubectl apply -f k8s/08-pdb.yaml
kubectl apply -f k8s/09-networkpolicy.yaml
```

### 5. Verify

```bash
kubectl get all -n data-center-commander
kubectl get pods -n data-center-commander -w
kubectl logs -n data-center-commander -l app.kubernetes.io/component=api -f
```

## Manifest Reference

| File | Purpose |
|---|---|
| `00-namespace.yaml` | Namespace `data-center-commander` |
| `01-configmap.yaml` | Non-sensitive configuration |
| `02-secret.yaml` | Database connection string (replace before applying) |
| `03-serviceaccount.yaml` | ServiceAccount for the API pods |
| `04-deployment.yaml` | API Deployment (2 replicas, rolling update) |
| `05-service.yaml` | ClusterIP Service |
| `06-ingress.yaml` | Ingress with TLS and rate limiting |
| `07-hpa.yaml` | HorizontalPodAutoscaler (2-10 replicas) |
| `08-pdb.yaml` | PodDisruptionBudget (minAvailable: 1) |
| `09-networkpolicy.yaml` | NetworkPolicy (restrict ingress/egress) |
| `kustomization.yaml` | Kustomize overlay for `kubectl apply -k` |

## Deployment Details

### Deployment (`04-deployment.yaml`)

```yaml
spec:
  replicas: 2
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

- **2 replicas** minimum for high availability
- **Rolling update** with `maxUnavailable: 0` ensures zero-downtime deployments
- **maxSurge: 1** allows one extra pod during rollout

### Pod Security

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 999
  runAsGroup: 999
  fsGroup: 999
  seccompProfile:
    type: RuntimeDefault
```

- Non-root container (UID 999)
- Read-only root filesystem
- No privilege escalation
- All capabilities dropped
- Seccomp profile set to RuntimeDefault

### Resource Requests and Limits

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

Adjust these based on your workload. The API is lightweight; these values
work well for moderate traffic.

### Probes

| Probe | Path | Initial Delay | Period | Timeout | Failure Threshold |
|---|---|---|---|---|---|
| Liveness | `/healthz` | 10s | 30s | 5s | 3 |
| Readiness | `/readyz` | 5s | 10s | 5s | 3 |
| Startup | `/healthz` | 5s | 5s | 3s | 12 |

The startup probe gives the application up to 60 seconds (12 × 5s) to start
before the liveness probe begins.

### Topology Spread

```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: ScheduleAnyway
```

Distributes pods across availability zones for fault tolerance.

## Scaling

### HorizontalPodAutoscaler (`07-hpa.yaml`)

```yaml
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dcc-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

- Scales 2–10 replicas based on CPU (70%) and memory (80%) utilization
- Scale-up: 2 pods per 60 seconds after 60s stabilization
- Scale-down: 1 pod per 120 seconds after 300s stabilization

### PodDisruptionBudget (`08-pdb.yaml`)

```yaml
spec:
  minAvailable: 1
```

Ensures at least 1 pod remains during voluntary disruptions (node drains,
cluster upgrades).

## Networking

### Service (`05-service.yaml`)

```yaml
spec:
  type: ClusterIP
  ports:
    - name: http
      port: 80
      targetPort: http
```

ClusterIP service exposing port 80 → container port 8790.

### Ingress (`06-ingress.yaml`)

```yaml
annotations:
  kubernetes.io/ingress.class: nginx
  nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/proxy-body-size: "1m"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "30"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "30"
  nginx.ingress.kubernetes.io/limit-rps: "10"
  nginx.ingress.kubernetes.io/limit-connections: "5"
  nginx.ingress.kubernetes.io/enable-cors: "false"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - dcc.example.com
      secretName: dcc-tls
```

- TLS termination at the ingress
- Rate limiting: 10 requests/second, 5 concurrent connections
- CORS disabled by default
- 1MB max body size

### NetworkPolicy (`09-networkpolicy.yaml`)

```yaml
spec:
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8790
    - from:
        - podSelector: {}
      ports:
        - protocol: TCP
          port: 8790
  egress:
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: postgres
      ports:
        - protocol: TCP
          port: 5432
    - to: []
      ports:
        - protocol: TCP
          port: 443
```

- **Ingress:** Only from ingress controller and same-namespace pods
- **Egress:** DNS (53), PostgreSQL (5432), HTTPS (443)

## Configuration

### ConfigMap (`01-configmap.yaml`)

```yaml
data:
  DCC_LOG_LEVEL: "INFO"
  DCC_PORT: "8790"
  DCC_HOST: "0.0.0.0"
  DCC_DEMO_MODE: "false"
  DCC_READ_ONLY: "true"
```

Non-sensitive configuration only. `DCC_DATABASE_URL` is injected via the Secret.

### Secret (`02-secret.yaml`)

```yaml
stringData:
  DCC_DATABASE_URL: "postgresql://user:password@postgres.data-center-commander.svc.cluster.local:5432/data_center_commander"
```

Replace with your actual connection string. For production, use an external
secret manager.

## Kustomize Overlays

### Development Overlay

Create `k8s/overlays/dev/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: data-center-commander-dev
resources:
  - ../../base
patches:
  - path: deployment-patch.yaml
  - path: ingress-patch.yaml
configMapGenerator:
  - name: dcc-config
    behavior: merge
    literals:
      - DCC_LOG_LEVEL=DEBUG
      - DCC_DEMO_MODE=true
```

### Production Overlay

Create `k8s/overlays/prod/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: data-center-commander
resources:
  - ../../base
patches:
  - path: deployment-patch.yaml
  - path: hpa-patch.yaml
  - path: ingress-patch.yaml
```

## Operations

### Rolling Update

```bash
# Update image
kubectl set image deployment/dcc-api api=data-center-commander:v1.1.0 -n data-center-commander

# Watch rollout
kubectl rollout status deployment/dcc-api -n data-center-commander

# Rollback
kubectl rollout undo deployment/dcc-api -n data-center-commander
```

### Scaling Manually

```bash
# Scale to 5 replicas
kubectl scale deployment/dcc-api --replicas=5 -n data-center-commander

# Or edit HPA
kubectl edit hpa dcc-api -n data-center-commander
```

### Drain a Node

```bash
# Cordon node
kubectl cordon <node-name>

# Drain node
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Uncordon after maintenance
kubectl uncordon <node-name>
```

### View Logs

```bash
# All pods
kubectl logs -n data-center-commander -l app.kubernetes.io/component=api -f

# Specific pod
kubectl logs -n data-center-commander <pod-name> -f

# Previous container (if restarted)
kubectl logs -n data-center-commander <pod-name> --previous
```

### Port Forwarding (Debugging)

```bash
kubectl port-forward -n data-center-commander svc/dcc-api 8790:80
```

## Monitoring

### Prometheus Metrics

The deployment has `prometheus.io/scrape: "false"` by default. To enable:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8790"
  prometheus.io/path: "/metrics"
```

### Grafana Dashboard

Import a dashboard with panels for:
- Request rate, error rate, duration (RED)
- Pod CPU/memory utilization
- HPA replica count
- Database connection pool

## Security

### RBAC

The ServiceAccount `dcc-api` has no automounted token:

```yaml
automountServiceAccountToken: false
```

### Pod Security Standards

Apply restricted Pod Security Standards:

```bash
kubectl label namespace data-center-commander pod-security.kubernetes.io/enforce=restricted
```

### Secrets Management

For production, use External Secrets Operator:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: dcc-secrets
  namespace: data-center-commander
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: dcc-secrets
  data:
    - secretKey: DCC_DATABASE_URL
      remoteRef:
        key: data-center-commander
        property: database-url
```

## Troubleshooting

### Pod Stuck in Pending

```bash
kubectl describe pod <pod-name> -n data-center-commander
# Check: insufficient CPU/memory, node selector mismatch, taints
```

### Pod Stuck in CrashLoopBackOff

```bash
kubectl logs <pod-name> -n data-center-commander --previous
# Check: database connection, environment variables, config errors
```

### Ingress Not Working

```bash
kubectl describe ingress dcc-api -n data-center-commander
# Check: TLS secret exists, ingress class correct, backend service healthy
```

### Network Policy Blocking Traffic

```bash
kubectl describe networkpolicy dcc-api -n data-center-commander
# Temporarily allow all traffic for debugging
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-all
  namespace: data-center-commander
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - {}
  egress:
    - {}
EOF
```

## Next Steps

- [Docker](docker.md) — Local development
- [Podman](podman.md) — Rootless alternative
- [containerd](containerd.md) — Lightweight runtime
- [OpenShift](openshift.md) — Enterprise platform
