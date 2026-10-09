# Tutorial: Auto Scaling Setup & Testing

> **Estimated Time:** 25 minutes  
> **Prerequisites:** [Getting Started](getting-started.md) completed, `kubectl` configured

---

## Overview

This tutorial covers configuring, testing, and tuning Kubernetes Horizontal Pod Autoscaler (HPA) policies for the Data Center Commander stack. You will learn to:

- Understand HPA configuration
- Generate load to trigger scaling
- Monitor scaling events
- Tune scaling policies for different workloads

## Step 1: Review Current HPA Configuration

```bash
# List all HPAs
kubectl get hpa -n data-center-commander

# View detailed configuration
kubectl get hpa elasticsearch -n data-center-commander -o yaml
```

Key parameters to note:

| Parameter | Elasticsearch | Logstash | Kibana | Loki | Grafana |
|-----------|--------------|----------|--------|------|---------|
| minReplicas | 1 | 1 | 1 | 1 | 1 |
| maxReplicas | 3 | 3 | 2 | 3 | 2 |
| CPU Target | 70% | 70% | 70% | 70% | 70% |
| Memory Target | 80% | 80% | 80% | 80% | 80% |

## Step 2: Verify Metrics Are Available

```bash
# Check if metrics-server is running
kubectl top nodes
kubectl top pods -n data-center-commander
```

If `kubectl top` fails, install metrics-server:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

## Step 3: Generate Load to Trigger Scale-Up

### Method 1: CPU Load on Logstash

```bash
# Exec into Logstash and generate CPU load
kubectl exec -it deployment/logstash -n data-center-commander -- \
  sh -c "for i in \$(seq 1 4); do while true; do :; done & done"
```

### Method 2: Memory Load on Elasticsearch

```bash
# Exec into Elasticsearch and allocate memory
kubectl exec -it deployment/elasticsearch -n data-center-commander -- \
  sh -c "tail -c 500M /dev/urandom | gzip > /dev/null &"
```

### Method 3: HTTP Load (if ingress is configured)

```bash
# Install hey (HTTP load generator)
brew install hey  # macOS
# or
apt install hey   # Linux

# Generate load against Kibana
hey -z 5m -c 50 http://kibana.local:5601
```

## Step 4: Monitor Scaling in Real-Time

```bash
# Watch HPA status
kubectl get hpa -n data-center-commander -w

# Watch pods being created
kubectl get pods -n data-center-commander -w

# Watch events
kubectl get events -n data-center-commander --sort-by='.lastTimestamp' -w
```

Expected sequence:

```
# Initial state
elasticsearch   Deployment/elasticsearch   0%/70%    1    3    1

# After load generation (CPU > 70%)
elasticsearch   Deployment/elasticsearch   85%/70%   1    3    1

# After stabilization window (60s)
elasticsearch   Deployment/elasticsearch   85%/70%   1    3    2

# Eventually stabilizes
elasticsearch   Deployment/elasticsearch   45%/70%   1    3    2
```

## Step 5: Verify Scale-Down

```bash
# Kill the load generation processes
kubectl exec -it deployment/logstash -n data-center-commander -- pkill -f "while true"

# Wait for scale-down stabilization window (300s = 5 minutes)
# Then check
kubectl get hpa -n data-center-commander
```

## Step 6: Customize HPA for Your Workload

### High-Throughput Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: logstash
  namespace: data-center-commander
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: logstash
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 600
      policies:
        - type: Percent
          value: 25
          periodSeconds: 120
```

Apply:

```bash
kubectl apply -f custom-hpa.yaml
```

### Cost-Optimized Configuration

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
  maxReplicas: 2
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 120
      policies:
        - type: Percent
          value: 50
          periodSeconds: 120
    scaleDown:
      stabilizationWindowSeconds: 600
      policies:
        - type: Percent
          value: 25
          periodSeconds: 120
```

## Step 7: Test Scaling with Custom Metrics (Advanced)

### Install Prometheus Adapter

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring \
  --set prometheus.url=http://prometheus.monitoring.svc \
  --set prometheus.port=9090
```

### Create Custom Metrics HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: logstash-custom
  namespace: data-center-commander
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: logstash
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Pods
      pods:
        metric:
          name: logstash_queue_size
        target:
          type: AverageValue
          averageValue: "1000"
```

## Step 8: Verify PDB Interaction

```bash
# Check PDB status
kubectl get pdb -n data-center-commander

# Try to drain a node (should be blocked by PDB)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Expected: Some pods will not be evicted due to PDB
```

## Step 9: Load Testing with Realistic Traffic

### Create a Load Generator Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: load-generator
  namespace: data-center-commander
spec:
  replicas: 1
  selector:
    matchLabels:
      app: load-generator
  template:
    metadata:
      labels:
        app: load-generator
    spec:
      containers:
        - name: load
          image: busybox
          command:
            - sh
            - -c
            - |
              while true; do
                wget -q -O- http://logstash:5000 2>/dev/null || true
                sleep 0.1
              done
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
```

```bash
kubectl apply -f load-generator.yaml
kubectl get hpa -n data-center-commander -w
```

## Step 10: Clean Up

```bash
# Remove load generator
kubectl delete deployment load-generator -n data-center-commander

# Remove custom HPA (if created)
kubectl delete hpa logstash-custom -n data-center-commander

# Verify all HPAs return to normal
kubectl get hpa -n data-center-commander
```

## Troubleshooting

### HPA Not Scaling

```bash
# Check HPA conditions
kubectl describe hpa elasticsearch -n data-center-commander

# Common issues:
# 1. Metrics not available -> Install metrics-server
# 2. Pods have no resource requests -> Add resources to deployment
# 3. Stabilization window too long -> Reduce stabilizationWindowSeconds
```

### Pods Not Being Created

```bash
# Check cluster capacity
kubectl describe nodes

# Check for resource quotas
kubectl get resourcequota -n data-center-commander

# Check for limit ranges
kubectl get limitrange -n data-center-commander
```

### Scale-Down Not Happening

```bash
# Verify load has stopped
kubectl top pods -n data-center-commander

# Check stabilization window (default 300s for scale-down)
kubectl get hpa elasticsearch -n data-center-commander -o jsonpath='{.spec.behavior.scaleDown.stabilizationWindowSeconds}'

# Manually scale down if needed
kubectl scale deployment elasticsearch -n data-center-commander --replicas=1
```

## Next Steps

- [Container Security Tutorial](container-security.md)
- [Getting Started](getting-started.md)
