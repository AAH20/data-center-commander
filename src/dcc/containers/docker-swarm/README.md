# Docker Swarm Integration — Data Center Commander

## Overview

This directory contains the complete Docker Swarm integration for Data Center Commander (DCC), including stack deployment, rolling updates, secrets management, health monitoring, and rollback capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Swarm Cluster                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        dcc_frontend (overlay)                        │   │
│  │  ┌─────────────┐                                                    │   │
│  │  │   nginx     │  :80, :443                                         │   │
│  │  │  (replica)  │  Reverse proxy, rate limiting, security headers    │   │
│  │  └──────┬──────┘                                                    │   │
│  └─────────┼───────────────────────────────────────────────────────────┘   │
│            │                                                                │
│  ┌─────────┼───────────────────────────────────────────────────────────┐   │
│  │         │              dcc_backend (overlay, encrypted)              │   │
│  │  ┌──────┴──────┐  ┌──────────────┐  ┌─────────────────────────┐    │   │
│  │  │  app        │  │  db          │  │  otel-collector         │    │   │
│  │  │  (2 repl)   │  │  (1 repl)    │  │  (1 repl)               │    │   │
│  │  │  :8790     │  │  postgres:16 │  │  :4317, :4318, :8888    │    │   │
│  │  └─────────────┘  └──────────────┘  └─────────────────────────┘    │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐                                │   │
│  │  │  prometheus  │  │  grafana     │                                │   │
│  │  │  (1 repl)   │  │  (1 repl)    │                                │   │
│  │  │  :9090      │  │  :3000       │                                │   │
│  │  └──────────────┘  └──────────────┘                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Volumes: db_data, prometheus_data, grafana_data                           │
│  Secrets: db_password, db_url, grafana_admin_user, grafana_admin_password  │
│  Configs: db_init_*, app_config, nginx_*, otel_config, prometheus_config,   │
│           grafana_*                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Initialize Docker Swarm

```bash
# On the manager node
docker swarm init

# On worker nodes (run the join command from manager)
docker swarm join --token <token> <manager-ip>:2377
```

### 2. Create Secrets

```bash
# Interactive setup
./scripts/setup-secrets.sh

# Or manually
echo "your-secure-password" | docker secret create db_password -
echo "postgresql://dcc:your-secure-password@db:5432/data_center_commander" | docker secret create db_url -
echo "admin" | docker secret create grafana_admin_user -
echo "your-grafana-password" | docker secret create grafana_admin_password -
```

### 3. Create Configs

```bash
# Interactive setup
./scripts/setup-configs.sh

# Or manually
docker config create db_init_schema database/schema.sql
docker config create db_init_migration_001 database/migrations/001_cost_intelligence.sql
docker config create db_init_migration_002 database/migrations/002_lifecycle_rollup_fix.sql
docker config create db_init_migration_003 database/migrations/003_estimate_price_link_validation.sql
docker config create db_init_migration_004 database/migrations/004_placement_comparison_snapshots.sql
docker config create app_config configs/app.env
docker config create nginx_conf configs/nginx.conf
docker config create nginx_dcc_conf configs/dcc.conf
docker config create otel_config configs/otel-collector.yaml
docker config create prometheus_config configs/prometheus.yml
docker config create grafana_datasources configs/grafana-datasources.yml
docker config create grafana_dashboards configs/grafana-dashboards.yml
```

### 4. Deploy Stack

```bash
# Build the image first
docker build -t data-center-commander:latest .

# Deploy
./scripts/deploy.sh

# Or manually
docker stack deploy -c stack.yml dcc
```

### 5. Verify

```bash
# Check services
docker stack services dcc

# Check tasks
docker stack ps dcc

# Health check
./scripts/health-check.sh

# View logs
docker service logs -f dcc_app
```

## Rolling Updates

### Using the script

```bash
# Build and deploy new version
./scripts/update.sh dcc app

# Or specify an image
./scripts/update.sh dcc app data-center-commander:v2.0.0
```

### Using Docker directly

```bash
# Update with rolling update
docker service update \
  --image data-center-commander:v2.0.0 \
  --update-parallelism 1 \
  --update-delay 10s \
  --update-failure-action rollback \
  --update-monitor 60s \
  --update-max-failure-ratio 0.3 \
  --update-order start-first \
  dcc_app
```

### Using Python

```python
from dcc.containers.docker_swarm.swarm import update_service_image

result = update_service_image(
    service_name="dcc_app",
    new_image="data-center-commander:v2.0.0",
    update_parallelism=1,
    update_delay=10,
    update_failure_action="rollback",
    update_monitor=60,
    max_failure_ratio=0.3,
    update_order="start-first",
    wait_for_completion=True,
    timeout_seconds=300,
)

if result.success:
    print(f"Update completed in {result.duration_seconds:.1f}s")
else:
    print(f"Update failed: {result.message}")
```

## Rollback

### Using the script

```bash
./scripts/rollback.sh dcc app
```

### Using Docker directly

```bash
docker service update --rollback dcc_app
```

### Using Python

```python
from dcc.containers.docker_swarm.swarm import rollback_service

result = rollback_service(
    service_name="dcc_app",
    wait_for_completion=True,
    timeout_seconds=300,
)

if result.success:
    print("Rollback completed successfully")
else:
    print(f"Rollback failed: {result.message}")
```

## Health Monitoring

### Using the script

```bash
./scripts/health-check.sh
```

### Using Python

```python
from dcc.containers.docker_swarm.swarm import health_check_service

result = health_check_service("dcc_app")

if result.healthy:
    print(f"All {result.healthy_tasks}/{result.total_tasks} tasks healthy")
else:
    print(f"Unhealthy: {result.unhealthy_tasks} unhealthy, {result.failed_tasks} failed")
    for task in result.details["tasks"]:
        if task["health"] != "healthy":
            print(f"  {task['name']}: {task['state']} - {task['error']}")
```

## Scaling

```bash
# Scale app to 4 replicas
docker service scale dcc_app=4

# Or using Python
from dcc.containers.docker_swarm.swarm import scale_service
scale_service("dcc_app", 4)
```

## Teardown

```bash
# Remove stack only
./scripts/teardown.sh

# Remove stack + volumes
./scripts/teardown.sh dcc --remove-volumes

# Remove everything
./scripts/teardown.sh dcc --remove-volumes --remove-secrets --remove-configs
```

## Configuration

### Stack Configuration (`stack.yml`)

| Service | Image | Replicas | Ports | Networks |
|---------|-------|----------|-------|----------|
| db | postgres:16-alpine | 1 | - | dcc_backend |
| app | data-center-commander:latest | 2 | 8790 | dcc_backend, dcc_frontend |
| nginx | nginx:1.27-alpine | 1 | 80, 443 | dcc_frontend |
| otel-collector | otel/opentelemetry-collector-contrib:0.96.0 | 1 | 4317, 4318, 8888 | dcc_backend |
| prometheus | prom/prometheus:v2.51.0 | 1 | 9090 | dcc_backend |
| grafana | grafana/grafana:10.4.0 | 1 | 3000 | dcc_backend |

### Rolling Update Configuration

Default rolling update settings (configurable in `stack.yml`):

| Parameter | Value | Description |
|-----------|-------|-------------|
| parallelism | 1 | Number of tasks updated simultaneously |
| delay | 10s | Delay between task updates |
| failure_action | rollback | Action on update failure |
| monitor | 60s | Duration to monitor each task |
| max_failure_ratio | 0.3 | Max failure ratio before rollback |
| order | start-first | Start new tasks before stopping old |

### Resource Limits

| Service | CPU Limit | Memory Limit | CPU Reservation | Memory Reservation |
|---------|-----------|--------------|-----------------|-------------------|
| db | 1.0 | 512M | 0.25 | 128M |
| app | 0.5 | 256M | 0.1 | 64M |
| nginx | 0.25 | 64M | 0.05 | 16M |
| otel-collector | 0.25 | 128M | 0.05 | 32M |
| prometheus | 0.25 | 256M | 0.05 | 64M |
| grafana | 0.25 | 256M | 0.05 | 64M |

## Security

- **Secrets**: All sensitive data (passwords, connection strings) stored as Docker secrets
- **Encrypted networks**: Backend network uses overlay encryption
- **Non-root containers**: All services run as non-root users
- **Resource limits**: CPU and memory limits prevent resource exhaustion
- **Health checks**: All services have health checks configured
- **Rate limiting**: Nginx configured with rate limiting
- **Security headers**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

## Monitoring

- **Prometheus**: Metrics collection at `http://localhost:9090`
- **Grafana**: Visualization at `http://localhost:3000`
- **OpenTelemetry**: Distributed tracing via OTLP
- **Health endpoints**: `/healthz` on app and nginx

## Files

| File | Purpose |
|------|---------|
| `stack.yml` | Main stack definition |
| `swarm.py` | Python API for Swarm operations |
| `__init__.py` | Package initialization |
| `configs/` | Configuration files for services |
| `scripts/deploy.sh` | Stack deployment script |
| `scripts/update.sh` | Rolling update script |
| `scripts/rollback.sh` | Rollback script |
| `scripts/health-check.sh` | Health check script |
| `scripts/setup-secrets.sh` | Secrets setup script |
| `scripts/setup-configs.sh` | Configs setup script |
| `scripts/teardown.sh` | Teardown script |

## Python API

The `swarm.py` module provides a complete Python API:

```python
from dcc.containers.docker_swarm.swarm import (
    # Status checks
    is_swarm_active,
    require_swarm,
    
    # Service operations
    list_services,
    get_service,
    list_tasks,
    scale_service,
    
    # Stack operations
    deploy_stack,
    remove_stack,
    get_stack_status,
    
    # Rolling updates
    update_service_image,
    rollback_service,
    
    # Health checks
    health_check_service,
    
    # Secrets & configs
    create_secret,
    create_config,
    list_secrets,
    list_configs,
    remove_secret,
    remove_config,
    
    # Logs
    get_service_logs,
    
    # Exceptions
    DockerSwarmError,
    SwarmNotActiveError,
    ServiceNotFoundError,
    RollingUpdateError,
)
```

## Troubleshooting

### Service won't start

```bash
# Check service status
docker service ps dcc_app --no-trunc

# Check logs
docker service logs dcc_app

# Check service inspect
docker service inspect dcc_app
```

### Rolling update stuck

```bash
# Check update status
docker service inspect dcc_app --format '{{.ServiceStatus.UpdateStatus}}'

# Pause update
docker service update --update-failure-action pause dcc_app

# Rollback
./scripts/rollback.sh dcc app
```

### Health check failing

```bash
# Check container health
docker inspect <container-id> --format '{{.State.Health}}'

# Manual health check
docker exec <container-id> curl -sf http://127.0.0.1:8790/healthz
```

### Database connection issues

```bash
# Test connectivity from app container
docker exec -it $(docker ps -q -f name=dcc_app) nc -zv db 5432

# Check database logs
docker service logs dcc_db
```

## Next Steps

- [Kubernetes](../k8s/) — Kubernetes deployment
- [Docker Compose](../../../docker-compose.yml) — Local development
- [Monitoring](../../monitoring/) — Monitoring stack
