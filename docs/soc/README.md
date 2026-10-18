# Data Center Commander — SOC, Auto Scaling & Container Documentation

> **Version:** 1.0.0  
> **Last Updated:** September 2026  
> **Project:** Data Center Commander

---

## Overview

This directory contains comprehensive documentation for the Security Operations Center (SOC), Auto Scaling, and Container orchestration components of the Data Center Commander platform. Together, these systems provide:

- **Real-time security monitoring** — Prometheus + Grafana dashboards tracking compliance scores, policy violations, and infrastructure drift
- **Automated incident response** — Alertmanager routing with severity-based escalation
- **Elastic auto scaling** — Kubernetes HPA with custom metrics and stabilization windows
- **Container security** — Network policies, RBAC, pod disruption budgets, and hardened container images

## Documentation Map

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | System architecture, component interactions, data flow |
| [api-reference.md](api-reference.md) | SOC API endpoints, metrics, alert rules, and exporter interface |
| [auto-scaling.md](auto-scaling.md) | HPA configuration, scaling policies, custom metrics, and tuning |
| [containers.md](containers.md) | Container images, security context, network policies, RBAC |
| [tutorials/getting-started.md](tutorials/getting-started.md) | Deploy the full SOC stack in 15 minutes |
| [tutorials/incident-response.md](tutorials/incident-response.md) | Respond to security alerts and compliance violations |
| [tutorials/auto-scaling-setup.md](tutorials/auto-scaling-setup.md) | Configure and test auto scaling policies |
| [tutorials/container-security.md](tutorials/container-security.md) | Harden containers and enforce network segmentation |

## Quick Start

```bash
# 1. Deploy the Kubernetes logging + monitoring stack
kubectl apply -k k8s/iac/

# 2. Deploy the monitoring stack (Prometheus + Grafana + Exporter)
cd monitoring/iac
cp .env.example .env
docker compose up -d

# 3. Verify SOC components are running
kubectl get pods -n data-center-commander
kubectl get hpa -n data-center-commander
kubectl get networkpolicies -n data-center-commander

# 4. Access dashboards
# Grafana:    http://grafana.local:3000 (admin/admin)
# Kibana:     http://kibana.local:5601
# Prometheus: http://localhost:9090
```

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Center Commander                         │
│                     SOC + Auto Scaling + Containers                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Prometheus  │  │  Alertmanager│  │       Grafana            │  │
│  │  (Metrics)   │  │  (Routing)   │  │  (Dashboards)            │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                      │                  │
│  ┌──────┴─────────────────┴──────────────────────┴───────────────┐  │
│  │                    IaC Exporter (Port 9091)                    │  │
│  │  - Checkov results  - Terraform drift  - Compliance score     │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
│                             │                                       │
│  ┌──────────────────────────┴────────────────────────────────────┐  │
│  │              Kubernetes Cluster (data-center-commander NS)     │  │
│  │                                                               │  │
│  │  ┌─────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐  │  │
│  │  │Elasticsearch│ │ Logstash │ │  Loki   │ │   Grafana    │  │  │
│  │  │  (HPA 1-3)  │ │(HPA 1-3) │ │(HPA 1-3)│ │  (HPA 1-2)   │  │  │
│  │  └─────────────┘ └──────────┘ └─────────┘ └──────────────┘  │  │
│  │  ┌─────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐  │  │
│  │  │   Kibana    │ │ Filebeat │ │ Fluentd │ │  Promtail    │  │  │
│  │  │  (HPA 1-2)  │ │(DS)      │ │  (DS)   │ │   (DS)       │  │  │
│  │  └─────────────┘ └──────────┘ └─────────┘ └──────────────┘  │  │
│  │                                                               │  │
│  │  Network Policies: Default-deny + explicit allow rules        │  │
│  │  PDBs: minAvailable=1 for all deployments                     │  │
│  │  RBAC: Filebeat SA with minimal permissions                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Logging Stack (Docker)                      │  │
│  │  Filebeat → Logstash → Elasticsearch → Kibana                 │  │
│  │  Promtail → Loki → Grafana                                    │  │
│  │  Fluentd → Elasticsearch + Loki (dual output)                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Compliance Mapping

| Framework | CIS | NIST 800-53 | PCI-DSS | SOC 2 | ISO 27001 |
|-----------|-----|-------------|---------|-------|-----------|
| SOC Monitoring | ✅ | ✅ | ✅ | ✅ | ✅ |
| Auto Scaling | ✅ | ✅ | ✅ | ✅ | ✅ |
| Container Security | ✅ | ✅ | ✅ | ✅ | ✅ |

## Related Documentation

- [Policy Framework](../policy/README.md) — AWS SCPs, Azure Policy, GCP Org Policies
- [Kubernetes IaC](../../k8s/iac/README.md) — Full K8s manifest reference
- [Monitoring Stack](../../monitoring/iac/README.md) — Prometheus + Grafana setup
- [Logging Stack](../../logging/iac/README.md) — ELK + Loki setup
- [IaC Benchmarks](../../BENCHMARKS-IAC.md) — Performance benchmarks
