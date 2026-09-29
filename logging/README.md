# Centralized Logging Stack

Centralized logging for Data Center Commander using **Loki + Promtail + Grafana** (default) or **Elasticsearch + Logstash + Kibana** (optional ELK).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Center Commander                     │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ App Logs │  │ API Logs │  │  Errors  │  │  Audit   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │         │
│       └──────────────┴──────────────┴──────────────┘         │
│                              │                                │
│                    ┌─────────▼─────────┐                     │
│                    │  JSON Formatter   │                     │
│                    │  + Context Vars   │                     │
│                    └─────────┬─────────┘                     │
│                              │                                │
│                    ┌─────────▼─────────┐                     │
│                    │   Rotating Files  │                     │
│                    │   logs/{app,...}/ │                     │
│                    └─────────┬─────────┘                     │
└──────────────────────────────┼──────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │      Promtail       │
                    │  (log shipping)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │        Loki         │
                    │  (log aggregation)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │      Grafana        │
                    │  (visualization)    │
                    └─────────────────────┘
```

## Quick Start

```bash
cd logging/
chmod +x setup.sh
./setup.sh
```

Or manually:

```bash
cd logging/
docker-compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Grafana | 3000 | Log visualization and dashboards |
| Loki | 3100 | Log aggregation and storage |
| Promtail | 9080 | Log shipping agent |

## Log Types

| Type | Directory | Description |
|------|-----------|-------------|
| Application | `logs/app/` | General application logs |
| API Access | `logs/api/` | HTTP request/response logs |
| Errors | `logs/errors/` | Error and exception logs |
| Audit | `logs/audit/` | Security and audit events |

## Configuration

### Environment Variables

Copy `.env` and customize:

```bash
DCC_ENV=development
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
DCC_LOG_LEVEL=INFO
DCC_STRUCTURED_LOGGING=true
```

### Loki Retention

Default retention is 30 days (720 hours). Edit `loki-config.yml`:

```yaml
table_manager:
  retention_deletes_enabled: true
  retention_period: 720h  # Change as needed
```

## Querying Logs

### Grafana

1. Open http://localhost:3000
2. Navigate to **Explore** > **Loki**
3. Use LogQL queries:

```logql
# All application logs
{job="dcc-application"}

# Logs for a specific tenant
{job="dcc-application", tenant_id="550e8400-e29b-41d4-a716-446655440000"}

# Error logs only
{job="dcc-errors"}

# API access logs
{job="dcc-api-access"}

# Audit events
{job="dcc-audit"}

# Combined query
{job=~"dcc-.*"} |= "error"
```

### Loki API

```bash
# Query logs
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  -G --data-urlencode 'query={job="dcc-application"}' \
  --data-urlencode 'start=now-1h' \
  --data-urlencode 'limit=100'
```

## Application Integration

The logging module is at `src/dcc/logging.py`:

```python
from dcc.logging import get_logger, LogContext, set_tenant_context

logger = get_logger(__name__)

# Basic logging
logger.info("Processing started")

# With tenant context
with LogContext(tenant_id="550e8400-e29b-41d4-a716-446655440000"):
    logger.info("Processing telemetry for tenant")

# Audit logging
from dcc.logging import get_audit_logger
audit = get_audit_logger()
audit.info("User login", extra={"user": "admin", "ip": "10.0.0.1"})
```

## ELK Stack (Optional)

To use Elasticsearch + Logstash + Kibana instead of Loki:

1. Uncomment the ELK services in `docker-compose.yml`
2. Comment out the Loki/Promtail services
3. Update `grafana-datasources.yml` to use Elasticsearch
4. Run `docker-compose up -d`

## Log Format

All logs are structured JSON:

```json
{
  "timestamp": "2024-01-15T10:30:00+00:00",
  "level": "INFO",
  "logger": "dcc.api",
  "message": "Request processed",
  "module": "api",
  "function": "do_GET",
  "line": 123,
  "thread": 12345,
  "thread_name": "MainThread",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "req-abc123"
}
```

## Troubleshooting

### Check service health

```bash
docker-compose ps
docker-compose logs loki
docker-compose logs promtail
```

### Verify log files are being written

```bash
tail -f ../logs/app/application.log
tail -f ../logs/errors/error.log
```

### Test Loki is receiving logs

```bash
curl -s "http://localhost:3100/loki/api/v1/labels"
```

### Reset the stack

```bash
docker-compose down -v
docker-compose up -d
```

## Maintenance

### Log rotation

Logs are rotated automatically:
- Max file size: 10 MB
- Backup count: 5-10 files
- Loki retention: 30 days (configurable)

### Backup

```bash
# Backup Loki data
docker run --rm -v dcc-loki-data:/data -v $(pwd):/backup alpine tar czf /backup/loki-backup.tar.gz -C /data .
```

### Cleanup

```bash
# Remove old log files
find ../logs -name "*.log.*" -mtime +30 -delete

# Reset Loki data
docker-compose down -v
```
