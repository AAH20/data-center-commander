# Runbook: Autoscaling Security Event
# Data Center Commander SOC
# Version: 1.0.0
# Severity: MEDIUM
# Last Updated: 2026-09-29

## Overview

This runbook describes the response procedure when a security event related to autoscaling is detected.

## Trigger

- HPA scaling anomaly detected
- Autoscaling policy violation
- Resource exhaustion risk
- SOC alert generated with severity MEDIUM

## Prerequisites

- Access to Kubernetes cluster
- Access to monitoring dashboards
- Access to HPA/VPA configuration
- Slack channel: #security-alerts

## Response Procedure

### 1. Immediate Actions (0-5 minutes)

1. **Acknowledge Alert**
   - Post acknowledgment in #security-alerts Slack channel
   - Create incident ticket

2. **Assess Situation**
   ```bash
   # Check HPA status
   kubectl get hpa -n data-center-commander
   kubectl describe hpa HPA_NAME -n data-center-commander

   # Check current replicas
   kubectl get pods -n data-center-commander -l app=APP_NAME

   # Check resource usage
   kubectl top pods -n data-center-commander
   kubectl top nodes
   ```

3. **Determine if scaling is legitimate**
   - Is there a traffic spike?
   - Is there a batch job running?
   - Is there a DDoS attack?

### 2. Containment (5-15 minutes)

1. **If scaling is legitimate:**
   - Monitor resource usage
   - Ensure resource limits are respected
   - Verify PDB is configured

2. **If scaling is not legitimate:**
   ```bash
   # Scale down manually
   kubectl scale deployment DEPLOYMENT_NAME -n data-center-commander --replicas=MIN_REPLICAS

   # Or pause HPA
   kubectl patch hpa HPA_NAME -n data-center-commander \
     -p '{"spec":{"minReplicas":CURRENT_REPLICAS}}'
   ```

3. **Check for resource exhaustion:**
   ```bash
   # Check node resources
   kubectl describe nodes

   # Check resource quotas
   kubectl get resourcequota -n data-center-commander
   kubectl describe resourcequota -n data-center-commander
   ```

### 3. Eradication (15-60 minutes)

1. **Fix autoscaling configuration:**
   ```bash
   # Update HPA
   kubectl apply -f - <<EOF
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: HPA_NAME
     namespace: data-center-commander
   spec:
     minReplicas: 2
     maxReplicas: 10
     metrics:
       - type: Resource
         resource:
           name: cpu
           target:
             type: Utilization
             averageUtilization: 70
   EOF
   ```

2. **Update VPA if needed:**
   ```bash
   kubectl patch vpa VPA_NAME -n data-center-commander \
     -p '{"spec":{"resourcePolicy":{"containerPolicies":[{"containerName":"CONTAINER","maxAllowed":{"cpu":"2","memory":"2Gi"}}]}}}'
   ```

3. **Verify PDB:**
   ```bash
   kubectl get pdb -n data-center-commander
   kubectl describe pdb PDB_NAME -n data-center-commander
   ```

### 4. Recovery (60-120 minutes)

1. **Restore normal operations:**
   ```bash
   # Restore HPA
   kubectl apply -f hpa-config.yaml

   # Verify scaling
   kubectl get hpa -n data-center-commander
   kubectl get pods -n data-center-commander -l app=APP_NAME
   ```

2. **Monitor for stability:**
   - Watch HPA metrics for 30 minutes
   - Verify no resource exhaustion
   - Check application performance

### 5. Post-Incident (120+ minutes)

1. **Document incident:**
   - Autoscaling event details
   - Root cause
   - Resolution
   - Action items

2. **Update autoscaling policies:**
   - Review HPA/VPA configuration
   - Update resource limits
   - Update scaling policies

3. **Close incident:**
   - Close incident ticket
   - Post summary in #security-alerts

## Escalation

- If not resolved within 1 hour: Escalate to Security Team Lead
- If service degradation: Escalate to SRE Team
- If data loss: Escalate to CISO

## References

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Kubernetes VPA Documentation](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [Pod Disruption Budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
