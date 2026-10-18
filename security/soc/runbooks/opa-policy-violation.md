# Runbook: OPA Policy Violation
# Data Center Commander SOC
# Version: 1.0.0
# Severity: HIGH
# Last Updated: 2026-09-29

## Overview

This runbook describes the response procedure when an OPA policy violation is detected during admission control.

## Trigger

- OPA policy evaluation returns DENY
- Kubernetes admission webhook rejects resource creation
- SOC alert generated with severity HIGH

## Prerequisites

- Access to Kubernetes cluster
- Access to OPA logs
- Access to Trivy scan results
- Slack channel: #security-alerts

## Response Procedure

### 1. Immediate Actions (0-5 minutes)

1. **Acknowledge Alert**
   - Post acknowledgment in #security-alerts Slack channel
   - Create incident ticket

2. **Identify Violation**
   ```bash
   # Check OPA logs
   kubectl logs -n data-center-commander -l app=opa-agent --tail=100

   # Check admission webhook logs
   kubectl logs -n data-center-commander -l app=opa-agent | grep "admission"

   # Get policy evaluation details
   curl -X POST -H "Content-Type: application/json" \
     -d '{"input": {"resource": "RESOURCE_NAME", "namespace": "NAMESPACE"}}' \
     http://opa.opa.svc.cluster.local:8181/v1/data/container-security
   ```

3. **Assess Violation Type**
   - Vulnerability threshold exceeded?
   - Misconfiguration detected?
   - Secret found in image?
   - Registry not allowed?
   - Missing security context?

### 2. Containment (5-15 minutes)

1. **If resource was not created:**
   - No immediate action needed
   - Identify requester and notify

2. **If resource was created before policy update:**
   ```bash
   # Identify non-compliant resource
   kubectl get pods -n data-center-commander -o json | \
     jq '.items[] | select(.metadata.annotations["security.data-center-commander/policy"] != "enforced") | .metadata.name'

   # Add annotation
   kubectl annotate pod POD_NAME -n data-center-commander \
     security.data-center-commander/policy-violation="true" \
     security.data-center-commander/violation-type="VIOLATION_TYPE"

   # If critical, delete resource
   kubectl delete pod POD_NAME -n data-center-commander
   ```

### 3. Eradication (15-60 minutes)

1. **Fix policy violation:**
   - Update resource to comply with policy
   - Re-scan image with Trivy
   - Verify OPA policy allows

2. **Update OPA policy if needed:**
   ```bash
   # Edit policy
   kubectl edit configmap opa-policies -n data-center-commander

   # Restart OPA to pick up changes
   kubectl rollout restart deployment/opa-agent -n data-center-commander
   ```

### 4. Recovery (60-120 minutes)

1. **Re-apply resource:**
   ```bash
   # Apply updated resource
   kubectl apply -f updated-resource.yaml

   # Verify compliance
   kubectl get pod POD_NAME -n data-center-commander -o json | \
     jq '.metadata.annotations["security.data-center-commander/policy"]'
   ```

2. **Verify service health:**
   ```bash
   kubectl get pods -n data-center-commander -l app=APP_NAME
   kubectl logs -n data-center-commander -l app=APP_NAME --tail=100
   ```

### 5. Post-Incident (120+ minutes)

1. **Document incident:**
   - Policy that was violated
   - Root cause
   - Resolution
   - Action items

2. **Update policies:**
   - Review and update OPA policies
   - Update Trivy configuration
   - Update security baselines

3. **Close incident:**
   - Close incident ticket
   - Post summary in #security-alerts

## Escalation

- If not resolved within 1 hour: Escalate to Security Team Lead
- If repeated violations: Escalate to CISO

## References

- [OPA Documentation](https://www.openpolicyagent.org/docs/)
- [Gatekeeper Documentation](https://open-policy-agent.github.io/gatekeeper/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
