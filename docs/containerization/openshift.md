# OpenShift

## Overview

OpenShift is Red Hat's enterprise Kubernetes platform, adding developer and
operations tooling, built-in CI/CD (Tekton), integrated image registry (Quay),
and enhanced security (SCC, RBAC) on top of Kubernetes.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     OpenShift Cluster                         │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Web       │  │   API        │  │   Integrated       │  │
│  │   Console   │  │   Server     │  │   Registry (Quay)  │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              OpenShift Projects (Namespaces)            │  │
│  │                                                        │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │   Build     │  │   Deploy     │  │   Route      │  │  │
│  │  │   (S2I)     │  │   (DC)       │  │   (HAProxy)  │  │  │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  │  │
│  │                                                        │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │   Image     │  │   Config     │  │   Secret     │  │  │
│  │  │   Stream    │  │   Map        │  │              │  │  │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Operators (OLM)                            │  │
│  │  - PostgreSQL Operator                                  │  │
│  │  - Prometheus Operator                                   │  │
│  │  - External Secrets Operator                            │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Prerequisites

- OpenShift 4.x cluster
- `oc` CLI configured with cluster access
- Cluster-admin or project-admin permissions

## Quick Start

### 1. Login to OpenShift

```bash
oc login --token=<token> --server=https://api.cluster.example.com:6443
```

### 2. Create a Project

```bash
oc new-project data-center-commander
```

### 3. Create Secret

```bash
oc create secret generic dcc-secrets \
  --from-literal=DCC_DATABASE_URL="postgresql://user:password@postgres:5432/data_center_commander"
```

### 4. Create ConfigMap

```bash
oc create configmap dcc-config \
  --from-literal=DCC_LOG_LEVEL=INFO \
  --from-literal=DCC_PORT=8790 \
  --from-literal=DCC_HOST=0.0.0.0 \
  --from-literal=DCC_DEMO_MODE=false \
  --from-literal=DCC_READ_ONLY=true
```

### 5. Deploy from Dockerfile (Source-to-Image)

```bash
oc new-app https://github.com/AAH20/data-center-commander.git \
  --name=dcc-api \
  --strategy=docker \
  --env=DCC_LOG_LEVEL=INFO
```

### 6. Expose the Service

```bash
oc expose svc/dcc-api
```

### 7. Verify

```bash
oc get all
oc get pods -w
oc logs -f deployment/dcc-api
```

## Deployment Strategies

### Source-to-Image (S2I)

S2I builds images from source code inside the cluster:

```bash
oc new-app python:3.11~https://github.com/AAH20/data-center-commander.git \
  --name=dcc-api \
  --strategy=source
```

### Docker Strategy

Uses the existing `Dockerfile`:

```bash
oc new-app https://github.com/AAH20/data-center-commander.git \
  --name=dcc-api \
  --strategy=docker
```

### From Existing Image

```bash
oc new-app your-registry/data-center-commander:latest \
  --name=dcc-api
```

### From Kubernetes Manifests

```bash
oc apply -f k8s/00-namespace.yaml
oc apply -f k8s/01-configmap.yaml
oc apply -f k8s/02-secret.yaml
oc apply -f k8s/03-serviceaccount.yaml
oc apply -f k8s/04-deployment.yaml
oc apply -f k8s/05-service.yaml
oc apply -f k8s/06-ingress.yaml
oc apply -f k8s/07-hpa.yaml
oc apply -f k8s/08-pdb.yaml
oc apply -f k8s/09-networkpolicy.yaml
```

## OpenShift-Specific Resources

### BuildConfig

```yaml
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: dcc-api
  namespace: data-center-commander
spec:
  source:
    type: Git
    git:
      uri: https://github.com/AAH20/data-center-commander.git
      ref: main
    contextDir: /
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Dockerfile
  output:
    to:
      kind: ImageStreamTag
      name: dcc-api:latest
  triggers:
    - type: ConfigChange
    - type: ImageChange
```

### ImageStream

```yaml
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: dcc-api
  namespace: data-center-commander
spec:
  lookupPolicy:
    local: false
  tags:
    - name: latest
      from:
        kind: DockerImage
        name: your-registry/data-center-commander:latest
```

### DeploymentConfig

```yaml
apiVersion: apps.openshift.io/v1
kind: DeploymentConfig
metadata:
  name: dcc-api
  namespace: data-center-commander
spec:
  replicas: 2
  selector:
    app: dcc-api
  strategy:
    type: Rolling
    rollingParams:
      updatePeriodSeconds: 1
      intervalSeconds: 1
      timeoutSeconds: 600
      maxUnavailable: 25%
      maxSurge: 25%
  template:
    metadata:
      labels:
        app: dcc-api
    spec:
      containers:
        - name: api
          image: image-registry.openshift-image-registry.svc:5000/data-center-commander/dcc-api:latest
          ports:
            - containerPort: 8790
          envFrom:
            - configMapRef:
                name: dcc-config
          env:
            - name: DCC_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: dcc-secrets
                  key: DCC_DATABASE_URL
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8790
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8790
            initialDelaySeconds: 5
            periodSeconds: 10
  triggers:
    - type: ConfigChange
    - type: ImageChange
      imageChangeParams:
        automatic: true
        containerNames:
          - api
        from:
          kind: ImageStreamTag
          name: dcc-api:latest
```

### Route

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: dcc-api
  namespace: data-center-commander
spec:
  host: dcc.apps.cluster.example.com
  to:
    kind: Service
    name: dcc-api
  port:
    targetPort: 8790
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
```

### SecurityContextConstraints (SCC)

OpenShift uses SCCs instead of Pod Security Standards. The `restricted` SCC
is applied by default:

```bash
# Verify SCC
oc get scc restricted -o yaml

# Create custom SCC if needed
oc create -f - <<EOF
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: dcc-scc
allowPrivilegedContainer: false
allowContainerPrivileges: false
allowedCapabilities: []
defaultAddCapabilities: []
requiredDropCapabilities:
  - ALL
volumes:
  - configMap
  - secret
  - emptyDir
  - projected
runAsUser:
  type: MustRunAsRange
  uidRangeMin: 1000
  uidRangeMax: 2000
seLinuxContext:
  type: MustRunAs
fsGroup:
  type: MustRunAs
  ranges:
    - min: 1000
      max: 2000
supplementalGroups:
  type: RunAsAny
EOF
```

## Operators

### PostgreSQL Operator

Deploy a managed PostgreSQL instance:

```bash
# Install PostgreSQL Operator (Crunchy Data)
oc apply -f https://raw.githubusercontent.com/CrunchyData/postgres-operator/v5.5.0/installers/kubectl/postgres-operator.yml

# Create PostgreSQL cluster
oc create -f - <<EOF
apiVersion: postgres-operator.crunchydata.com/v1beta1
kind: PostgresCluster
metadata:
  name: dcc-db
  namespace: data-center-commander
spec:
  postgresVersion: 16
  instances:
    - name: instance1
      replicas: 2
      dataVolumeClaimSpec:
        accessModes:
          - "ReadWriteOnce"
        resources:
          requests:
            storage: 1Gi
      resources:
        requests:
          cpu: 100m
          memory: 256Mi
        limits:
          cpu: 500m
          memory: 512Mi
  backups:
    pgbackrest:
      repos:
        - name: repo1
          volume:
            volumeClaimSpec:
              accessModes:
                - "ReadWriteOnce"
              resources:
                requests:
                  storage: 1Gi
EOF
```

### External Secrets Operator

```bash
# Install External Secrets Operator
oc apply -f https://raw.githubusercontent.com/external-secrets/external-secrets/v0.9.9/deploy/crds/bundle.yaml

# Create ClusterSecretStore
oc create -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "dcc-role"
EOF
```

## CI/CD with Tekton

### Pipeline

```yaml
apiVersion: tekton.dev/v1beta1
kind: Pipeline
metadata:
  name: dcc-pipeline
  namespace: data-center-commander
spec:
  params:
    - name: git-url
      type: string
    - name: git-revision
      type: string
    - name: image-tag
      type: string
  workspaces:
    - name: source
  tasks:
    - name: fetch-source
      taskRef:
        name: git-clone
      params:
        - name: url
          value: $(params.git-url)
        - name: revision
          value: $(params.git-revision)
      workspaces:
        - name: output
          workspace: source
    - name: build-image
      taskRef:
        name: buildah
      params:
        - name: IMAGE
          value: image-registry.openshift-image-registry.svc:5000/data-center-commander/dcc-api:$(params.image-tag)
      workspaces:
        - name: source
          workspace: source
    - name: deploy
      taskRef:
        name: openshift-client
      params:
        - name: SCRIPT
          value: |
            oc set image deployment/dcc-api api=image-registry.openshift-image-registry.svc:5000/data-center-commander/dcc-api:$(params.image-tag)
            oc rollout status deployment/dcc-api
```

## Monitoring

### Prometheus ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: dcc-api
  namespace: data-center-commander
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: data-center-commander
  endpoints:
    - port: http
      interval: 30s
      path: /metrics
```

### Grafana Dashboard

OpenShift includes Grafana out of the box. Import a dashboard with panels for:
- Request rate, error rate, duration
- Pod CPU/memory utilization
- HPA replica count
- Database connection pool

## Logging

### OpenShift Logging (EFK/PLG Stack)

```bash
# View logs via OpenShift Logging
oc logs -f deployment/dcc-api -n data-center-commander

# Or via Kibana/Loki
# Access via: Applications → Logging → Kibana
```

## Scaling

### HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dcc-api
  namespace: data-center-commander
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
```

### Cluster Autoscaler

```bash
# Enable cluster autoscaler
oc create -f - <<EOF
apiVersion: autoscaling.openshift.io/v1
kind: ClusterAutoscaler
metadata:
  name: default
spec:
  podPriorityThreshold: -10
  resourceLimits:
    maxNodesTotal: 20
    cores:
      min: 8
      max: 128
    memory:
      min: 4
      max: 512
  scaleDown:
    enabled: true
    delayAfterAdd: 10m
    delayAfterDelete: 5m
    delayAfterFailure: 30s
    unneededTime: 10m
EOF
```

## Backup and Disaster Recovery

### Velero

```bash
# Install Velero
velero install \
  --provider aws \
  --bucket dcc-backups \
  --secret-file ./credentials

# Create backup
velero backup create dcc-backup --include-namespaces data-center-commander

# Restore
velero restore create --from-backup dcc-backup
```

## Security Best Practices

### 1. Use Restricted SCC

```bash
oc adm policy add-scc-to-user restricted -z default -n data-center-commander
```

### 2. Enable Network Policies

```bash
oc apply -f k8s/09-networkpolicy.yaml
```

### 3. Use External Secrets

```bash
# Never commit secrets to Git
# Use External Secrets Operator with Vault
```

### 4. Image Scanning

```bash
# Use OpenShift's built-in image scanning
oc get images -n data-center-commander
```

### 5. Pod Disruption Budgets

```bash
oc apply -f k8s/08-pdb.yaml
```

## Troubleshooting

### Pod Stuck in Pending

```bash
oc describe pod <pod-name> -n data-center-commander
# Check: SCC, resource quotas, node selector
```

### Build Failures

```bash
oc logs build/dcc-api-1 -n data-center-commander
oc describe build dcc-api-1 -n data-center-commander
```

### Route Not Working

```bash
oc describe route dcc-api -n data-center-commander
# Check: TLS certificate, backend service, route host
```

### Image Pull Errors

```bash
oc describe pod <pod-name> -n data-center-commander | grep -i "image\|pull"
# Check: ImagePullBackOff, registry credentials
```

## Next Steps

- [Docker](docker.md) — Local development
- [Kubernetes](kubernetes.md) — Production orchestration
- [Podman](podman.md) — Rootless alternative
- [containerd](containerd.md) — Lightweight runtime
