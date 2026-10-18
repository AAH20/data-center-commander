# IaC Monitoring Stack

Prometheus + Grafana monitoring for Data Center Commander Infrastructure as Code.

## Quick Start

```bash
cd monitoring/iac

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Start the stack
docker compose up -d

# View logs
docker compose logs -f
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Prometheus | 9090 | Metrics collection & alerting |
| Grafana | 3000 | Dashboards & visualization |
| Alertmanager | 9093 | Alert routing & notifications |
| IaC Exporter | 9091 | Custom Checkov/Terraform metrics |
| Node Exporter | 9100 | Host-level metrics |

## Dashboards

### IaC Security & Compliance (`iac-security-dashboard`)
- Critical/High/Medium/Low findings (stat panels)
- Compliance score gauge
- Findings over time (time series)
- Check results distribution (pie chart)
- Failures by policy category (table)
- Terraform drift detection
- Unencrypted resources count
- Public exposure count
- Exporter status

### Monitoring Infrastructure (`monitoring-infra-dashboard`)
- CPU usage per instance
- Memory usage
- Disk usage per mountpoint
- Network I/O (RX/TX)
- Prometheus TSDB storage growth
- Active time series count

## Metrics Exposed by IaC Exporter

| Metric | Type | Description |
|--------|------|-------------|
| `iac_checkov_passed` | Gauge | Total passed checks |
| `iac_checkov_failed` | Gauge | Total failed checks |
| `iac_checkov_failed_critical` | Gauge | Critical severity failures |
| `iac_checkov_failed_high` | Gauge | High severity failures |
| `iac_checkov_failed_medium` | Gauge | Medium severity failures |
| `iac_checkov_failed_low` | Gauge | Low severity failures |
| `iac_compliance_score` | Gauge | Overall compliance (0-100) |
| `iac_policy_category_failures` | Gauge | Failures by category (labeled) |
| `iac_terraform_drift_detected` | Gauge | Terraform drift count |
| `iac_unencrypted_resources` | Gauge | Unencrypted resources |
| `iac_public_exposure` | Gauge | Publicly exposed resources |
| `iac_last_scan_timestamp` | Gauge | Last scan time |

## Alert Rules

### Security Alerts
- **IACCriticalFindings**: Any critical finding for 5m
- **IACHighFindings**: >5 high findings for 10m
- **IACMediumFindingsSpike**: >20 medium findings for 15m
- **IACComplianceScoreDrop**: Score below 80%
- **IACUnencryptedResources**: Any unencrypted resource
- **IACPublicExposure**: Any public exposure

### Platform Alerts
- **IACExporterDown**: Exporter unreachable for 5m
- **PrometheusTargetDown**: Any target down for 2m
- **MonitoringHighCPU**: CPU >85% for 5m
- **MonitoringDiskSpaceLow**: Disk <15% available
- **MonitoringMemoryPressure**: Memory <10% available
- **PrometheusStorageGrowth**: TSDB >20GB

## Feeding Data to the Exporter

### Checkov
Run Checkov and output JSON to the mounted volume:

```bash
checkov -d /path/to/terraform \
  --external-checks-dir ../../policies/checkov/terraform/ \
  --output json \
  --output-file-path /data/checkov/
```

### Terraform Plan
Generate plan JSON and place in the mounted directory:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > /data/terraform/plan.json
```

## Project Structure

```
monitoring/iac/
├── docker-compose.yml          # Stack orchestration
├── .env.example                # Environment template
├── prometheus/
│   ├── prometheus.yml          # Scrape config
│   └── alert_rules.yml         # Alert definitions
├── grafana/
│   ├── datasources/
│   │   └── prometheus.yml      # Datasource provisioning
│   ├── dashboards/
│   │   ├── iac-security.json   # Security dashboard
│   │   └── monitoring-infra.json # Infra dashboard
│   └── provisioning/
│       └── dashboards/
│           └── dashboards.yml  # Dashboard provider
├── alertmanager/
│   └── alertmanager.yml        # Alert routing config
└── exporter/
    ├── Dockerfile              # Exporter container
    └── exporter.py             # Custom Prometheus exporter
```

## License

MIT
