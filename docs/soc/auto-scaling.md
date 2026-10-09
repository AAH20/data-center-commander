# Auto Scaling — Configuration & Operations

> **Version:** 1.0.0  
> **Last Updated:** September 2026

---

## Overview

The Data Center Commander uses Kubernetes Horizontal Pod Autoscaler (HPA) to dynamically scale components based on CPU and memory utilization. All stateless components are configured with appropriate min/max replica counts and scaling behaviors.

## HPA Configuration Reference

### Elasticsearch HPA

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
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| `minReplicas` | 1 | Minimum number of pods |
| `maxReplicas` | 3 | Maximum number of pods |
| CPU Target | 70% | Target average CPU utilization |
| Memory Target | 80% | Target average memory utilization |
| Scale Up Stabilization | 60s | Lookback window for scale-up decisions |
| Scale Down Stabilization | 300s | Lookback window for scale-down decisions |
| Scale Up Policy | 50% per 60s | Max 50% increase per minute |
| Scale Down Policy | 50% per 60s | Max 50% decrease per minute |

### Logstash HPA

Identical to Elasticsearch HPA (min: 1, max: 3, CPU: 70%, Memory: 80%).

### Kibana HPA

```yaml
minReplicas: 1
maxReplicas: 2
metrics:
  - cpu: 70%
  - memory: 80%
# No custom behavior (uses defaults)
```

### Loki HPA

```yaml
minReplicas: 1
maxReplicas: 3
metrics:
  - cpu: 70%
  - memory: 80%
# No custom behavior (uses defaults)
```

### Grafana HPA

```yaml
minReplicas: 1
maxReplicas: 2
metrics:
  - cpu: 70%
  - memory: 80%
# No custom behavior (uses defaults)
```

## Scaling Behavior Deep Dive

### How HPA Calculates Desired Replicas

```
desiredReplicas = ceil[currentReplicas × (currentMetricValue / desiredMetricValue)]
```

**Example:** If current CPU is 91% and target is 70% with 2 replicas:
```
desiredReplicas = ceil[2 × (91 / 70)] = ceil[2.6] = 3
```

### Scale-Up Stabilization Window

The stabilization window prevents the HPA from thrashing by looking at historical metrics:

- **Window**: 60 seconds
- **Behavior**: The HPA uses the **highest** desired replica count from the window
- **Effect**: A single spike won't trigger immediate scale-up; the spike must persist

### Scale-Down Stabilization Window

- **Window**: 300 seconds (5 minutes)
- **Behavior**: The HPA uses the **lowest** desired replica count from the window
- **Effect**: Temporary drops in utilization won't trigger scale-down

### Scaling Policies

| Policy | Type | Value | Period | Effect |
|--------|------|-------|--------|--------|
| Scale Up | Percent | 50 | 60s | Add up to 50% more replicas per minute |
| Scale Down | Percent | 50 | 60s | Remove up to 50% of replicas per minute |

**Example scale-up sequence (starting at 2 replicas):**
- Minute 1: 2 → 3 (2 × 1.5 = 3)
- Minute 2: 3 → 4 (3 × 1.5 = 4.5, capped at maxReplicas=3)
- Result: Capped at 3

**Example scale-down sequence (starting at 3 replicas):**
- Minute 1: 3 → 2 (3 × 0.5 = 1.5, rounded up to 2)
- Minute 2: 2 → 1 (2 × 0.5 = 1)
- Result: 1 (minReplicas)

## Custom Metrics (Future)

The current HPA uses resource metrics (CPU/memory). To scale on custom metrics:

```yaml
metrics:
  - type: Pods
    pods:
      metric:
        name: logstash_queue_size
      target:
        type: AverageValue
        averageValue: "1000"
```

This requires the Prometheus Adapter to be installed in the cluster.

## Pod Disruption Budgets

All deployments have PDBs to ensure availability during voluntary disruptions:

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

| Component | PDB Name | minAvailable |
|-----------|----------|-------------|
| Elasticsearch | `elasticsearch` | 1 |
| Logstash | `logstash` | 1 |
| Kibana | `kibana` | 1 |
| Loki | `loki` | 1 |
| Grafana | `grafana` | 1 |

## Operations

### Check HPA Status

```bash
# List all HPAs with current vs desired replicas
kubectl get hpa -n data-center-commander

# Detailed view
kubectl describe hpa -n data-center-commander
```

### Manual Scaling

```bash
# Scale a deployment manually (overrides HPA)
kubectl scale deployment elasticsearch -n data-center-commander --replicas=2

# Edit HPA directly
kubectl edit hpa elasticsearch -n data-center-commander
```

### View Scaling Events

```bash
# Watch HPA events
kubectl get events -n data-center-commander --sort-by='.lastTimestamp' | grep -i hpa

# View deployment rollout history
kubectl rollout history deployment/elasticsearch -n data-center-commander
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| HPA not scaling | Metrics not available | Check `kubectl top pods -n data-center-commander` |
| HPA at max but still high CPU | maxReplicas too low | Increase `maxReplicas` |
| Pods pending | Insufficient cluster resources | Check `kubectl describe pod <pod>` for scheduling errors |
| Scale-down too slow | Stabilization window too long | Reduce `stabilizationWindowSeconds` |
| Scale-up too slow | Stabilization window too short | Increase `stabilizationWindowSeconds` |
| PDB blocking eviction | minAvailable too high | Lower `minAvailable` or add replicas |

## Tuning Guide

### For High-Throughput Log Processing

```yaml
# Increase max replicas for Logstash
maxReplicas: 5
# Lower CPU target for faster scale-up
cpu target: 60%
# Faster scale-up
scaleUp:
  stabilizationWindowSeconds: 30
  policies:
    - type: Pods
      value: 2
      periodSeconds: 60
```

### For Cost-Sensitive Environments

```yaml
# Reduce max replicas
maxReplicas: 2
# Higher CPU target (pack more per pod)
cpu target: 80%
# Slower scale-down
scaleDown:
  stabilizationWindowSeconds: 600
  policies:
    - type: Percent
      value: 25
      periodSeconds: 120
```

### For Burst Traffic

```yaml
# Use absolute pod count for faster scale-up
scaleUp:
  stabilizationWindowSeconds: 0
  policies:
    - type: Pods
      value: 4
      periodSeconds: 60
```

## Testing Auto Scaling

### Load Testing

```bash
# Install a load generator
kubectl run load-generator -n data-center-commander --rm -i --tty \
  --image=busybox -- sh -c "while true; do wget -q -O- http://logstash:5000; done"

# Watch HPA react
kubectl get hpa -n data-center-commander -w
```

### Simulate CPU Load

```bash
# Exec into a pod and generate CPU load
kubectl exec -it deployment/logstash -n data-center-commander -- \
  sh -c "while true; do :; done"
```

### Verify Scale-Down

```bash
# Wait for stabilization window (5 min)
# Then check replica count
kubectl get deployment elasticsearch -n data-center-commander
```
