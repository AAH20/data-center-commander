# Tutorial: Getting Started with the SOC Stack

> **Estimated Time:** 15 minutes  
> **Prerequisites:** Docker, Docker Compose, kubectl, kustomize

---

## Overview

In this tutorial, you will deploy the complete SOC monitoring stack, including:

- Prometheus + Grafana + Alertmanager for metrics and alerting
- IaC Exporter for security and compliance metrics
- ELK + Loki logging stack on Kubernetes
- Auto scaling with HPA
- Network policies and RBAC

## Step 1: Clone and Navigate

```bash
cd /Users/ahmedhassan/data-center-commander
```

## Step 2: Deploy the Monitoring Stack

```bash
cd monitoring/iac

# Copy environment template
cp .env.example .env

# Edit .env with your settings (optional)
# vi .env

# Start the stack
docker compose up -d

# Verify services are running
docker compose ps
```

Expected output:

```
NAME                    STATUS         PORTS
grafana                 running        0.0.0.0:3000->3000/tcp
prometheus              running        0.0.0.0:9090->9090/tcp
alertmanager            running        0.0.0.0:9093->9093/tcp
iac-exporter            running        0.0.0.0:9091->9091/tcp
node-exporter           running        0.0.0.0:9100->9100/tcp
```

## Step 3: Verify Prometheus

```bash
# Check Prometheus targets
curl http://localhost:9090/targets

# Expected: All targets should be "up"
```

Open http://localhost:9090 in your browser to access Prometheus.

## Step 4: Verify Grafana

```bash
# Check Grafana health
curl http://localhost:3000/api/health
```

Open http://localhost:3000 in your browser.

**Default credentials:** `admin` / `admin`

You should see two provisioned dashboards:
- **IaC Security & Compliance** — Security findings, compliance score, drift detection
- **Monitoring Infrastructure** — CPU, memory, disk, network I/O

## Step 5: Deploy the Kubernetes Logging Stack

```bash
cd /Users/ahmedhassan/data-center-commander

# Apply all manifests
kubectl apply -k k8s/iac/

# Verify pods are running
kubectl get pods -n data-center-commander

# Expected output:
# NAME                            READY   STATUS    RESTARTS   AGE
# elasticsearch-xxxxx             1/1     Running   0          30s
# filebeat-xxxxx                  1/1     Running   0          30s
# fluentd-xxxxx                   1/1     Running   0          30s
# grafana-xxxxx                   1/1     Running   0          30s
# kibana-xxxxx                    1/1     Running   0          30s
# log-processor-xxxxx             1/1     Running   0          30s
# logstash-xxxxx                  1/1     Running   0          30s
# loki-xxxxx                      1/1     Running   0          30s
# promtail-xxxxx                  1/1     Running   0          30s
```

## Step 6: Verify Auto Scaling

```bash
# Check HPA status
kubectl get hpa -n data-center-commander

# Expected output:
# NAME            REFERENCE                  TARGETS   MINPODS   MAXPODS   REPLICAS
# elasticsearch   Deployment/elasticsearch   0%/70%    1         3         1
# logstash        Deployment/logstash        0%/70%    1         3         1
# kibana          Deployment/kibana          0%/70%    1         2         1
# loki            Deployment/loki            0%/70%    1         3         1
# grafana         Deployment/grafana         0%/70%    1         2         1
```

## Step 7: Verify Network Policies

```bash
# List network policies
kubectl get networkpolicies -n data-center-commander

# Expected output:
# NAME                    POD-SELECTOR   AGE
# default-deny-ingress    <none>         30s
# default-deny-egress     <none>         30s
# allow-elasticsearch     app=elasticsearch  30s
# allow-logstash          app=logstash       30s
# allow-kibana            app=kibana         30s
# allow-loki              app=loki           30s
# allow-grafana           app=grafana        30s
# allow-fluentd           app=fluentd        30s
```

## Step 8: Access the Dashboards

### Option A: Port Forwarding

```bash
# Grafana
kubectl port-forward -n data-center-commander svc/grafana 3000:3000

# Kibana
kubectl port-forward -n data-center-commander svc/kibana 5601:5601

# Elasticsearch
kubectl port-forward -n data-center-commander svc/elasticsearch 9200:9200
```

### Option B: Ingress (if configured)

Add to `/etc/hosts`:

```
127.0.0.1  kibana.local grafana.local elasticsearch.local
```

Then open:
- http://kibana.local:5601
- http://grafana.local:3000
- http://elasticsearch.local:9200

## Step 9: Feed Data to the Exporter

### Run Checkov

```bash
# Create output directory
mkdir -p /tmp/checkov-results

# Run Checkov with custom policies
checkov -d /path/to/terraform \
  --external-checks-dir policies/checkov/terraform/ \
  --output json \
  --output-file-path /tmp/checkov-results/

# Copy to the exporter's data directory
cp /tmp/checkov-results/*.json monitoring/iac/data/checkov/
```

### Generate Terraform Plan

```bash
# Create output directory
mkdir -p /tmp/tf-plans

# Generate plan
cd /path/to/terraform
terraform plan -out=tfplan
terraform show -json tfplan > /tmp/tf-plans/plan.json

# Copy to the exporter's data directory
cp /tmp/tf-plans/*.json monitoring/iac/data/terraform/
```

The exporter will pick up the new files on its next scrape interval (default: 300s).

## Step 10: Verify Metrics

```bash
# Query the exporter directly
curl http://localhost:9091/metrics | grep iac_

# Expected output:
# iac_checkov_passed 150
# iac_checkov_failed 3
# iac_checkov_failed_critical 0
# iac_checkov_failed_high 1
# iac_checkov_failed_medium 2
# iac_compliance_score 98.04
# iac_terraform_drift_detected 0
```

## Troubleshooting

### Pods Stuck in Pending

```bash
# Check events
kubectl get events -n data-center-commander --sort-by='.lastTimestamp'

# Check pod details
kubectl describe pod <pod-name> -n data-center-commander
```

### Exporter Not Updating

```bash
# Check exporter logs
docker compose -f monitoring/iac/docker-compose.yml logs -f iac-exporter

# Verify data directories exist
ls -la monitoring/iac/data/checkov/
ls -la monitoring/iac/data/terraform/
```

### HPA Not Scaling

```bash
# Check if metrics are available
kubectl top pods -n data-center-commander

# Check HPA events
kubectl describe hpa -n data-center-commander
```

## Next Steps

- [Incident Response Tutorial](incident-response.md) — Learn to respond to security alerts
- [Auto Scaling Setup Tutorial](auto-scaling-setup.md) — Configure and test scaling policies
- [Container Security Tutorial](container-security.md) — Harden your containers
