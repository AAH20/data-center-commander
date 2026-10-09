# SOC + AutoScaling + Container Monitoring

Security Operations Center (SOC) monitoring stack for Data Center Commander, covering container security, runtime threat detection, autoscaling health, and infrastructure monitoring.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SOC Monitoring Stack                      │
├─────────────┬──────────────┬──────────────┬────────────────┤
│  Prometheus │ Alertmanager │   Grafana    │   Exporters    │
│  (metrics)  │  (routing)   │ (dashboards) │                │
├─────────────┴──────────────┴──────────────┼────────────────┤
│  • kube-state-metrics (HPA, PDB, pods)     │                │
│  • cAdvisor (container metrics)            │                │
│  • node-exporter (host metrics)            │                │
│  • kubelet (pod/container stats)           │                │
│  • falco-exporter (runtime security)       │                │
│  • cluster-autoscaler (scaling metrics)    │                │
└────────────────────────────────────────────┴────────────────┘
```

## Quick Start

```bash
cd monitoring/soc

# Copy and configure environment
cp .env.example .env
# Edit .env with your Slack/PagerDuty/webhook settings

# Start the stack
docker-compose up -d

# Access services
# Grafana:    http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
# Alertmanager: http://localhost:9093
```

## Alert Rules

### SOC Security Alerts (`soc_security_alerts`)
| Alert | Severity | Description |
|-------|----------|-------------|
| `ContainerPrivilegeEscalation` | critical | Possible privilege escalation detected |
| `ContainerCrashLoopBackOff` | critical | Container in CrashLoopBackOff state |
| `ContainerOOMKilled` | warning | Container killed by OOM |
| `ContainerCPUThrottlingHigh` | warning | >50% CPU throttling |
| `ContainerImagePullBackOff` | warning | Image pull failure |
| `ContainerUnusualEgress` | warning | >100MB/s egress (possible exfiltration) |
| `SensitiveHostPathMounted` | critical | Sensitive host path mounted |
| `PodRunningAsRoot` | warning | Pod running as root user |
| `NetworkPolicyViolation` | critical | Network policy violation detected |
| `FalcoSecurityAlert` | critical | Falco runtime security event |
| `KubernetesAuditAnomaly` | warning | Unusual K8s API activity on sensitive resources |

### AutoScaling Alerts (`autoscaling_alerts`)
| Alert | Severity | Description |
|-------|----------|-------------|
| `HPAMaxedOut` | warning | HPA at max replicas for 10m |
| `HPAUnableToScale` | critical | HPA cannot scale (metrics issue) |
| `HPAFlapping` | warning | HPA replica count oscillating |
| `ClusterAutoscalerUnableToScale` | critical | Unschedulable pods, CA can't add nodes |
| `NodeGroupNearCapacity` | warning | Node group >90% utilized |
| `ScaleDownStuck` | warning | Scale-down blocked for 30m |

### Container Health Alerts (`container_health_alerts`)
| Alert | Severity | Description |
|-------|----------|-------------|
| `PodNotReady` | warning | Pod not ready for 10m |
| `PodStuckInPhase` | warning | Pod stuck in Pending/Unknown for 15m |
| `ContainerReadinessProbeFailing` | warning | Running but failing readiness probes |
| `ContainerHighMemoryUsage` | warning | Memory >85% of limit |
| `ContainerDiskIOSaturation` | warning | Disk I/O >50MB/s |
| `ContainerZombieProcesses` | warning | Zombie processes detected |
| `ContainerFDLimitNear` | warning | FD usage >80% |

### Node Infrastructure Alerts (`node_infrastructure_alerts`)
| Alert | Severity | Description |
|-------|----------|-------------|
| `NodeHighCPU` | warning | Node CPU >90% for 10m |
| `NodeMemoryPressure` | critical | Node memory <5% available |
| `NodeDiskPressure` | critical | Node disk <10% available |
| `NodeNetworkSaturation` | warning | Network throughput >1GB/s |
| `KubeletDown` | critical | Kubelet unreachable |
| `EtcdLeaderChanges` | critical | etcd leader changes >3/hour |

## Grafana Dashboards

| Dashboard | UID | Description |
|-----------|-----|-------------|
| SOC Security & Container Health | `soc-security-dashboard` | Security posture, Falco events, container health |
| AutoScaling & Cluster Health | `autoscaling-dashboard` | HPA status, cluster autoscaler, node utilization |
| Container Health & Performance | `container-health-dashboard` | Pod status, container resources, I/O, restarts |

## Alert Routing

Alerts are routed by severity and team:

- **Critical + Security** → `#soc-critical` Slack + PagerDuty + webhook
- **Critical + Platform** → `#platform-critical` Slack + PagerDuty + webhook
- **Warning** → `#soc-warnings` Slack + webhook
- **Autoscaling** → `#autoscaling-alerts` Slack + webhook
- **Container** → `#container-alerts` Slack + webhook

Inhibition rules prevent alert fatigue:
- Critical inhibits warning for same alert/instance
- KubeletDown inhibits Pod/Container alerts on that node

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | `localhost:587` | SMTP server for email alerts |
| `SMTP_FROM` | `soc-alerts@datacenter.local` | From address |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASS` | — | SMTP password |
| `SLACK_WEBHOOK_URL` | — | Slack incoming webhook |
| `PAGERDUTY_KEY` | — | PagerDuty routing key |
| `PAGERDUTY_URL` | `https://events.pagerduty.com/v2/enqueue` | PagerDuty endpoint |
| `WEBHOOK_URL` | `http://localhost:5001/` | Default webhook |
| `SECURITY_WEBHOOK_URL` | `http://localhost:5001/security` | Security webhook |
| `CRITICAL_WEBHOOK_URL` | `http://localhost:5001/critical` | Critical webhook |
| `GRAFANA_ADMIN_USER` | `admin` | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana admin password |
| `GRAFANA_ROOT_URL` | `http://localhost:3000` | Grafana root URL |

## File Structure

```
monitoring/soc/
├── docker-compose.yml              # SOC monitoring stack
├── prometheus/
│   ├── prometheus.yml              # Prometheus config
│   └── soc_alert_rules.yml         # All alert rules
├── alertmanager/
│   └── alertmanager.yml            # Alert routing & receivers
├── grafana/
│   ├── datasources/
│   │   └── prometheus.yml          # Datasource config
│   ├── provisioning/
│   │   └── dashboards/
│   │       └── dashboards.yml      # Dashboard provider
│   └── dashboards/
│       ├── soc-security.json       # SOC security dashboard
│       ├── autoscaling.json        # AutoScaling dashboard
│       └── container-health.json   # Container health dashboard
├── .env.example                    # Environment template
└── README.md                       # This file
```

## Integration with Existing IaC

This SOC stack complements the existing `monitoring/iac/` stack:
- **IaC monitoring**: Checkov findings, Terraform drift, compliance scores
- **SOC monitoring**: Runtime security, container health, autoscaling, node infrastructure

Both stacks share the same Grafana instance and Prometheus datasource for unified observability.
