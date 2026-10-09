# Data Center Commander — SOC + AutoScaling + Container Stack

Security Operations Center (SOC) with custom container autoscaling, runtime threat detection, and vulnerability scanning.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOC + AutoScaling Stack                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Prometheus  │  │   Grafana    │  │   Alertmanager       │  │
│  │  :9090       │  │   :3000      │  │   :9093              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│  ┌──────┴─────────────────┴──────────────────────┴───────────┐  │
│  │              soc-monitoring Network                       │  │
│  └──────┬─────────────────┬──────────────────────┬───────────┘  │
│         │                 │                      │              │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────────┴───────────┐  │
│  │ Autoscaler   │  │ SOC Scanner  │  │ Falco (Runtime)      │  │
│  │ :9102        │  │ (On-demand)  │  │ (Optional)           │  │
│  └──────┬───────┘  └──────────────┘  └──────────────────────┘  │
│         │                                                       │
│  ┌──────┴───────────────────────────────────────────────────┐  │
│  │              Docker Socket (/var/run/docker.sock)         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Node Exporter│  │   cAdvisor   │  │ Trivy Server         │  │
│  │ :9100        │  │   :8080      │  │ (Optional) :4954     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Port | Description |
|-----------|------|-------------|
| Prometheus | 9090 | Metrics collection and alerting |
| Grafana | 3000 | Visualization and dashboards |
| Alertmanager | 9093 | Alert routing and notifications |
| Autoscaler | 9102 | Custom container autoscaler with Prometheus metrics |
| Node Exporter | 9100 | Host-level metrics |
| cAdvisor | 8080 | Container-level metrics |
| SOC Scanner | - | On-demand vulnerability and compliance scanning |
| Falco | - | Runtime threat detection (optional profile) |
| Trivy | 4954 | Image vulnerability scanner (optional profile) |

## Quick Start

### 1. Deploy the Stack

```bash
cd docker/soc
./scripts/deploy.sh deploy
```

Or manually:

```bash
cp .env.example .env
# Edit .env with your configuration
docker compose -f docker-compose.yml --env-file .env up -d --build
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### 3. Run Security Scan

```bash
./scripts/deploy.sh scan
```

### 4. View Logs

```bash
./scripts/deploy.sh logs
```

### 5. Stop Stack

```bash
./scripts/deploy.sh stop
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAFANA_ADMIN_USER` | admin | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | admin | Grafana admin password |
| `AUTOSCALER_INTERVAL` | 30 | Autoscaler check interval (seconds) |
| `AUTOSCALER_MIN_REPLICAS` | 2 | Minimum replicas per service |
| `AUTOSCALER_MAX_REPLICAS` | 10 | Maximum replicas per service |
| `AUTOSCALER_CPU_THRESHOLD` | 75 | CPU usage threshold (%) |
| `AUTOSCALER_MEMORY_THRESHOLD` | 80 | Memory usage threshold (%) |
| `SLACK_WEBHOOK_URL` | - | Slack webhook for alerts |
| `PAGERDUTY_KEY` | - | PagerDuty integration key |

### Profiles

The stack uses Docker Compose profiles for optional components:

- **default**: Core monitoring + autoscaling
- **scanning**: SOC Scanner (on-demand)
- **runtime-security**: Falco runtime threat detection
- **vulnerability**: Trivy server

Example with profiles:

```bash
docker compose --profile runtime-security --profile vulnerability up -d
```

## Autoscaler

The custom autoscaler monitors container metrics and scales services based on:

- **CPU usage**: Scales up when above threshold, down when below 50% of threshold
- **Memory usage**: Same logic as CPU
- **Bounds**: Respects min/max replica configuration
- **Metrics**: Exposes Prometheus metrics on port 9102

### Prometheus Metrics

| Metric | Description |
|--------|-------------|
| `autoscaler_current_replicas` | Current replica count per service |
| `autoscaler_max_replicas` | Maximum allowed replicas |
| `autoscaler_min_replicas` | Minimum allowed replicas |
| `autoscaler_scale_events_total` | Total scale events by direction |
| `autoscaler_cpu_usage_percent` | CPU usage per service |
| `autoscaler_memory_usage_percent` | Memory usage per service |

## SOC Scanner

The SOC scanner performs:

- **Vulnerability scanning**: Trivy image scanning
- **IaC compliance**: Checkov policy validation
- **Report generation**: Consolidated JSON reports
- **Metrics export**: Prometheus metrics for vulnerabilities

### Scan Reports

Reports are written to `/reports` (mounted as `soc-reports` volume):

- `soc-report.json`: Consolidated security report

## Alert Rules

Pre-configured alert rules in `prometheus/alert_rules.yml`:

- Container high CPU/memory usage
- Container down/restarting
- High severity vulnerabilities
- Falco security events
- Privileged containers
- Autoscaler capacity alerts
- Infrastructure alerts (disk, network, targets)

## Falco Rules

Custom Falco rules in `soc-tools/falco-rules.yaml`:

- Unauthorized privilege escalation
- Sensitive file access
- Unexpected outbound connections
- Cryptocurrency mining detection
- Reverse shell detection
- Container escape attempts

## Grafana Dashboards

Pre-configured dashboard `soc-autoscaling.json`:

- Container CPU/Memory usage timeseries
- Current replicas per service
- Critical vulnerabilities count
- Security events (5m)
- Vulnerability distribution pie chart

## Building Images

### SOC Tools Image

```bash
docker build -f Dockerfile.soc -t data-center-commander:soc .
```

### Autoscaler Image

```bash
docker build -f Dockerfile.autoscaler -t data-center-commander:autoscaler .
```

## Project Structure

```
docker/soc/
├── Dockerfile.soc              # SOC tools image
├── Dockerfile.autoscaler      # Autoscaler image
├── docker-compose.yml         # Main compose file
├── .env.example               # Environment template
├── prometheus/
│   ├── prometheus.yml         # Prometheus config
│   └── alert_rules.yml        # Alert rules
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/       # Datasource provisioning
│   │   └── dashboards/        # Dashboard provisioning
│   └── dashboards/
│       └── soc-autoscaling.json
├── alertmanager/
│   └── alertmanager.yml       # Alertmanager config
├── autoscaler/
│   ├── autoscaler.py          # Main autoscaler module
│   ├── scanner.py             # SOC scanner module
│   └── requirements.txt       # Python dependencies
├── soc-tools/
│   └── falco-rules.yaml       # Custom Falco rules
└── scripts/
    └── deploy.sh              # Deployment script
```

## License

MIT
