# Tutorial: Container Security Hardening

> **Estimated Time:** 30 minutes  
> **Prerequisites:** [Getting Started](getting-started.md) completed, `kubectl` configured

---

## Overview

This tutorial covers hardening the container security posture of the Data Center Commander stack. You will learn to:

- Add security contexts to pods and containers
- Enforce Pod Security Standards
- Enable Elasticsearch security
- Use external secrets
- Verify network policies
- Scan container images for vulnerabilities

## Step 1: Add Security Contexts

### Pod-Level Security Context

Add to every Deployment/DaemonSet pod template:

```yaml
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: elasticsearch
          # ... existing config ...
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            privileged: false
            capabilities:
              drop:
                - ALL
```

### Apply to Elasticsearch

```bash
kubectl patch deployment elasticsearch -n data-center-commander --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/securityContext",
    "value": {
      "runAsNonRoot": true,
      "runAsUser": 1000,
      "runAsGroup": 1000,
      "fsGroup": 1000,
      "seccompProfile": {"type": "RuntimeDefault"}
    }
  }
]'
```

### Apply to All Deployments

```bash
for deploy in elasticsearch logstash kibana loki grafana log-processor; do
  kubectl patch deployment $deploy -n data-center-commander --type='json' -p='[
    {
      "op": "add",
      "path": "/spec/template/spec/securityContext",
      "value": {
        "runAsNonRoot": true,
        "runAsUser": 1000,
        "runAsGroup": 1000,
        "fsGroup": 1000,
        "seccompProfile": {"type": "RuntimeDefault"}
      }
    }
  ]'
done
```

## Step 2: Enforce Pod Security Standards

```bash
# Label the namespace with restricted PSS
kubectl label namespace data-center-commander \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted \
  --overwrite
```

Verify:

```bash
kubectl get namespace data-center-commander --show-labels
```

## Step 3: Enable Elasticsearch Security

### Update Elasticsearch Deployment

```bash
kubectl patch deployment elasticsearch -n data-center-commander --type='json' -p='[
  {
    "op": "replace",
    "path": "/spec/template/spec/containers/0/env",
    "value": [
      {"name": "discovery.type", "value": "single-node"},
      {"name": "xpack.security.enabled", "value": "true"},
      {"name": "xpack.security.enrollment.enabled", "value": "true"},
      {"name": "xpack.security.http.ssl.enabled", "value": "true"},
      {"name": "xpack.security.transport.ssl.enabled", "value": "true"},
      {"name": "ES_JAVA_OPTS", "value": "-Xms512m -Xmx512m"},
      {"name": "cluster.routing.allocation.disk.threshold_enabled", "value": "false"}
    ]
  }
]'
```

### Set Elasticsearch Password

```bash
# Exec into Elasticsearch and set passwords
kubectl exec -it deployment/elasticsearch -n data-center-commander -- \
  bin/elasticsearch-reset-password -u elastic -b -y
```

## Step 4: Use External Secrets

### Create a Kubernetes Secret

```bash
kubectl create secret generic grafana-credentials \
  --from-literal=admin-password='YourSecurePassword123!' \
  -n data-center-commander
```

### Update Grafana to Use Secret

```bash
kubectl patch deployment grafana -n data-center-commander --type='json' -p='[
  {
    "op": "replace",
    "path": "/spec/template/spec/containers/0/env",
    "value": [
      {"name": "GF_SECURITY_ADMIN_USER", "value": "admin"},
      {"name": "GF_SECURITY_ADMIN_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "grafana-credentials", "key": "admin-password"}}},
      {"name": "GF_AUTH_ANONYMOUS_ENABLED", "value": "true"},
      {"name": "GF_AUTH_ANONYMOUS_ORG_ROLE", "value": "Viewer"},
      {"name": "GF_INSTALL_PLUGINS", "value": "grafana-lokiexplore-app"}
    ]
  }
]'
```

## Step 5: Verify Network Policies

### Test Default Deny

```bash
# Create a test pod that should NOT be able to reach Elasticsearch
kubectl run test-deny -n data-center-commander --rm -i --tty \
  --image=busybox -- sh -c "wget -q -O- --timeout=5 http://elasticsearch:9200 || echo 'BLOCKED (expected)'"

# Expected: "BLOCKED (expected)" or timeout
```

### Test Allowed Traffic

```bash
# Create a test pod with the logstash label (should be allowed)
kubectl run test-allow -n data-center-commander --rm -i --tty \
  --labels="app=logstash" \
  --image=busybox -- sh -c "wget -q -O- --timeout=5 http://elasticsearch:9200 || echo 'ALLOWED (expected)'"

# Expected: Elasticsearch JSON response
```

### List All Policies

```bash
kubectl get networkpolicies -n data-center-commander -o custom-columns=\
NAME:.metadata.name,\
POLICY_TYPES:.spec.policyTypes,\
POD_SELECTOR:.spec.podSelector.matchLabels
```

## Step 6: Scan Container Images

### Install Trivy

```bash
brew install trivy  # macOS
# or
apt install trivy   # Linux
```

### Scan All Images

```bash
#!/bin/bash
IMAGES=(
  "docker.elastic.co/elasticsearch/elasticsearch:8.15.0"
  "docker.elastic.co/logstash/logstash:8.15.0"
  "docker.elastic.co/kibana/kibana:8.15.0"
  "grafana/loki:3.2.0"
  "grafana/promtail:3.2.0"
  "grafana/grafana:11.2.0"
  "docker.elastic.co/beats/filebeat:8.15.0"
  "fluent/fluentd:v1.17-1"
  "python:3.12-slim"
)

for img in "${IMAGES[@]}"; do
  echo "=== Scanning $img ==="
  trivy image --severity HIGH,CRITICAL --quiet "$img"
  echo ""
done
```

### Review Results

```bash
# Scan with full output
trivy image docker.elastic.co/elasticsearch/elasticsearch:8.15.0

# Scan with JSON output
trivy image --format json -o report.json docker.elastic.co/elasticsearch/elasticsearch:8.15.0
```

## Step 7: Add Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: data-center-commander-quota
  namespace: data-center-commander
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
    services: "10"
    persistentvolumeclaims: "10"
```

```bash
kubectl apply -f resource-quota.yaml
```

## Step 8: Add Limit Range

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: data-center-commander-limits
  namespace: data-center-commander
spec:
  limits:
    - type: Container
      default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      max:
        cpu: "2"
        memory: 4Gi
      min:
        cpu: 50m
        memory: 64Mi
```

```bash
kubectl apply -f limit-range.yaml
```

## Step 9: Verify Hardening

### Check Security Contexts

```bash
kubectl get deployment elasticsearch -n data-center-commander -o jsonpath='{.spec.template.spec.securityContext}'
```

### Check Pod Security Standards

```bash
kubectl auth can-i create pods --as=system:serviceaccount:default:default -n data-center-commander
# Should be denied for privileged pods
```

### Check Network Policies

```bash
kubectl get networkpolicies -n data-center-commander
```

### Check Resource Quotas

```bash
kubectl describe resourcequota data-center-commander-quota -n data-center-commander
```

## Step 10: Clean Up Test Resources

```bash
# Remove test pods
kubectl delete pod test-deny -n data-center-commander --ignore-not-found
kubectl delete pod test-allow -n data-center-commander --ignore-not-found

# Remove resource quota and limit range (if not needed)
kubectl delete resourcequota data-center-commander-quota -n data-center-commander
kubectl delete limitrange data-center-commander-limits -n data-center-commander
```

## Security Checklist

- [ ] Pod securityContext added to all deployments
- [ ] Container securityContext added to all containers
- [ ] Pod Security Standards enforced (restricted)
- [ ] Elasticsearch security enabled
- [ ] External secrets used for credentials
- [ ] Network policies verified (default-deny + explicit allow)
- [ ] Container images scanned for vulnerabilities
- [ ] Resource quotas configured
- [ ] Limit ranges configured
- [ ] RBAC reviewed (least privilege)
- [ ] TLS enabled for all ingress
- [ ] Audit logging enabled

## Next Steps

- [Getting Started](getting-started.md)
- [Incident Response](incident-response.md)
- [Auto Scaling Setup](auto-scaling-setup.md)
