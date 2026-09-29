# Kubernetes Manifests — Data Center Commander

## Overview

These manifests deploy the Data Center Commander API to a Kubernetes cluster.
The deployment is read-only, non-root, and uses a PostgreSQL backend.

## Prerequisites

- Kubernetes 1.25+ cluster
- `kubectl` configured
- An existing PostgreSQL database (or deploy one separately)
- An ingress controller (e.g. nginx-ingress) installed in the cluster

## Quick Start

### 1. Build and push the container image

```bash
docker build -t data-center-commander:latest .
docker tag data-center-commander:latest your-registry/data-center-commander:latest
docker push your-registry/data-center-commander:latest
```

Update the image in `kustomization.yaml` or `04-deployment.yaml` to match your registry.

### 2. Configure secrets

Edit `02-secret.yaml` and replace the placeholder `DCC_DATABASE_URL` with a
base64-encoded PostgreSQL connection string:

```bash
echo -n 'postgresql://user:pass@host:5432/data_center_commander' | base64
```

For production, use an external secret manager (External Secrets Operator,
AWS Secrets Manager, HashiCorp Vault) instead of committing secrets.

### 3. Configure ingress

Edit `06-ingress.yaml`:
- Replace `dcc.example.com` with your domain
- Create a TLS secret: `kubectl create secret tls dcc-tls --cert=tls.crt --key=tls.key -n data-center-commander`
- Adjust `kubernetes.io/ingress.class` if not using nginx

### 4. Apply manifests

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

## Security

- Non-root container (UID 999)
- Read-only root filesystem
- No privilege escalation
- All capabilities dropped
- NetworkPolicy restricts ingress/egress
- ServiceAccount with no automounted token
- Secrets injected via Kubernetes Secret (use external secrets in production)

## Scaling

The HPA scales 2-10 replicas based on CPU (70%) and memory (80%) utilization.
The PDB ensures at least 1 pod remains during voluntary disruptions.

## Files

| File | Purpose |
|------|---------|
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
