# Data Center Commander — Monitoring Stack

Prometheus + Grafana monitoring for the Data Center Commander API.

## Quick Start

```bash
cd monitoring
docker compose up -d
```

Access:
- **Grafana:** http://localhost:3000 (default: admin/admin)
- **Prometheus:** http://localhost:9090
- **Alertmanager:** http://localhost:9093
- **DCC Exporter:** http://localhost:8000/metrics

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  DCC API    │────▶│ dcc-exporter │────▶│ Prometheus │
│  :8790      │     │  :8000       │     │  :9090     │
└─────────────┘     └──────────────┘     └─────┬─────┘
                                               │
                         ┌─────────────────────┘
                         │
                   ┌─────▼─────┐     ┌──────────────┐
                   │  Grafana  │     │ Alertmanager │
                   │  :3000    │     │  :9093       │
                   └───────────┘     └──────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| prometheus | 9090 | Metrics collection and alerting |
| grafana | 3000 | Visualization dashboards |
| alertmanager | 9093 | Alert routing and notifications |
| dcc-exporter | 8000 | Custom DCC API metrics exporter |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAFANA_ADMIN_USER` | admin | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | admin | Grafana admin password |
| `DCC_API_URL` | http://host.docker.internal:8790 | DCC API base URL |
| `DCC_TENANT_ID` | dcc00000-0000-4000-8000-000000000001 | Tenant ID for API queries |
| `EXPORTER_PORT` | 8000 | Exporter listen port |
| `POLL_INTERVAL` | 15 | Seconds between API polls |

### Prometheus

- **Config:** `prometheus/prometheus.yml`
- **Alerts:** `prometheus/alerts.yml`
- **Retention:** 30 days

### Grafana

- **Datasource:** `grafana/datasources/prometheus.yml` (auto-provisioned)
- **Dashboards:** `grafana/dashboards/` (auto-provisioned)
- **Dashboard provider:** `grafana/dashboards/dashboards.yml`

### Alertmanager

- **Config:** `alertmanager/alertmanager.yml`
- Configure notification channels (email, Slack, PagerDuty, webhooks) in this file

## Metrics Exposed by dcc-exporter

| Metric | Type | Description |
|--------|------|-------------|
| `dcc_api_healthy` | gauge | 1 if DCC API /healthz responds |
| `dcc_api_mode` | gauge | 1 if API reports read_only mode |
| `dcc_database_ready` | gauge | 1 if /readyz reports ready |
| `dcc_database_schema_ok` | gauge | 1 if schema check passes |
| `dcc_database_rls_ok` | gauge | 1 if tenant RLS is enforced |
| `dcc_facility_count` | gauge | Number of active facilities |
| `dcc_open_workflows` | gauge | Number of open workflows |
| `dcc_kpi_count` | gauge | Number of KPI observations |
| `dcc_latest_telemetry_age_seconds` | gauge | Seconds since last telemetry ingested |

## Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| DCCAPIUnhealthy | `dcc_api_healthy == 0` for 1m | critical |
| DCCDatabaseUnhealthy | `dcc_database_ready == 0` for 1m | critical |
| DCCNoRecentTelemetry | telemetry age > 1h for 5m | warning |
| DCCExporterDown | exporter unreachable for 2m | warning |

## Stop

```bash
docker compose down
```

To also remove stored data:

```bash
docker compose down -v
```
