# Monitoring

Prometheus + Grafana monitoring stack for Data Center Commander.

## Components

- **Prometheus** — metrics collection and alerting
- **Grafana** — dashboards and visualization
- **Alertmanager** — alert routing (optional)

## Quick Start

```bash
# Start the monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Access Grafana
open http://localhost:3000

# Access Prometheus
open http://localhost:9090
```

## Dashboards

Import `grafana/dashboards/dcc-overview.json` into Grafana for a pre-built
overview of API health, request rates, and database connectivity.

## Alerts

Prometheus alerting rules are defined in `prometheus/rules/dcc-alerts.yml`.
Key alerts:

- `DCCAPIDown` — API not responding for 1 minute
- `DCCDatabaseUnavailable` — database connectivity lost for 2 minutes
- `DCCHighErrorRate` — 5xx rate exceeds 5% over 5 minutes
- `DCCHighLatency` — p95 latency exceeds 500ms over 5 minutes

## Metrics Exposed

The DCC API exposes a `/metrics` endpoint (Prometheus format) when the
`DCC_ENABLE_METRICS` environment variable is set to `true`.

| Metric | Type | Description |
|---|---|---|
| `dcc_api_requests_total` | Counter | Total API requests by route and status |
| `dcc_api_request_duration_seconds` | Histogram | Request latency by route |
| `dcc_database_connections` | Gauge | Active database pool connections |
| `dcc_database_errors_total` | Counter | Total database errors |
