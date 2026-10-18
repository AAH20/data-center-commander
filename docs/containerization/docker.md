# Docker

## Overview

Docker is the primary containerization technology for Data Center Commander.
The project includes a production-ready multi-stage `Dockerfile` and a
`docker-compose.yml` for local development.

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  Docker Host                      │
│                                                  │
│  ┌──────────────┐         ┌──────────────────┐  │
│  │  db service  │◄────────│   app service    │  │
│  │  postgres:16 │  dcc-net│  dcc:latest      │  │
│  │  :5432       │         │  :8790           │  │
│  └──────────────┘         └──────────────────┘  │
│         │                        │               │
│    db_data volume          port 8790 → host     │
└──────────────────────────────────────────────────┘
```

## Dockerfile

The `Dockerfile` uses a multi-stage build to minimize the final image size.

### Build Stage

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[postgres,tracing]"
```

- Uses `python:3.11-slim` as the base (smaller than full Python image)
- Creates a virtual environment at `/opt/venv`
- Installs build dependencies, then the package with `postgres` and `tracing` extras
- `--no-cache-dir` prevents pip from caching packages, reducing layer size

### Runtime Stage

```dockerfile
FROM python:3.11-slim AS runtime
RUN groupadd --system dcc && useradd --system --gid dcc --home /app dcc
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --chown=dcc:dcc src ./src
COPY --chown=dcc:dcc ui ./ui
COPY --chown=dcc:dcc database ./database
COPY --chown=dcc:dcc scripts ./scripts
COPY --chown=dcc:dcc tracing ./tracing
COPY --chown=dcc:dcc pyproject.toml ./
USER dcc
ENV DCC_DATABASE_URL="" DCC_TRACING_ENABLED="false" ...
EXPOSE 8790
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:8790/healthz || exit 1
ENTRYPOINT ["python", "scripts/run-local.py"]
CMD ["--host", "0.0.0.0", "--port", "8790"]
```

Key security and operational features:

| Feature | Implementation | Purpose |
|---|---|---|
| Non-root user | `USER dcc` (UID 999) | Prevents container escape to root |
| Minimal base | `python:3.11-slim` | Reduced attack surface |
| No build tools | Only `libpq5` and `curl` in runtime | Smaller image, fewer vulnerabilities |
| Health check | `HEALTHCHECK` directive | Docker monitors container health |
| Read-only env | `PYTHONUNBUFFERED=1` | Immediate log output |
| No bytecode | `PYTHONDONTWRITEBYTECODE=1` | Prevents `.pyc` writes |

## Building the Image

### Basic Build

```bash
docker build -t data-center-commander:latest .
```

### Build with Specific Tag

```bash
docker build -t data-center-commander:v1.0.0 .
```

### Build with No Cache

```bash
docker build --no-cache -t data-center-commander:latest .
```

### Build for Multiple Platforms

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t data-center-commander:latest .
```

## Running the Container

### Quick Start (with Docker Compose)

```bash
docker-compose up -d
```

### Manual Run

```bash
docker run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  -e DCC_TRACING_ENABLED="false" \
  data-center-commander:latest
```

### Run with Volume for Persistent Data

```bash
docker run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  -v dcc-logs:/app/logs \
  data-center-commander:latest
```

### Run with Custom Configuration

```bash
docker run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  -e DCC_LOG_LEVEL="DEBUG" \
  -e DCC_DEMO_MODE="true" \
  -e DCC_READ_ONLY="true" \
  -e DCC_OTLP_ENDPOINT="http://otel-collector:4317" \
  -e DCC_SERVICE_NAME="data-center-commander" \
  -e DCC_TRACE_SAMPLE_RATE="1.0" \
  data-center-commander:latest
```

## Docker Compose

The `docker-compose.yml` defines two services: `db` and `app`.

### Starting the Stack

```bash
# Start in detached mode
docker-compose up -d

# Start with build
docker-compose up -d --build

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f app
```

### Stopping the Stack

```bash
# Stop containers (keep volumes)
docker-compose stop

# Stop and remove containers (keep volumes)
docker-compose down

# Stop and remove containers + volumes (WARNING: deletes database)
docker-compose down -v
```

### Scaling the App Service

```bash
docker-compose up -d --scale app=3
```

### Health Checks

The `db` service includes a health check:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U dcc -d data_center_commander"]
  interval: 10s
  timeout: 5s
  retries: 5
```

The `app` service uses `depends_on` with `condition: service_healthy` to wait
for the database to be ready before starting.

### Database Initialization

The `db` service mounts SQL files into `/docker-entrypoint-initdb.d/`:

```yaml
volumes:
  - ./database/schema.sql:/docker-entrypoint-initdb.d/01_schema.sql:ro
  - ./database/migrations/001_cost_intelligence.sql:/docker-entrypoint-initdb.d/002_migration_001.sql:ro
  - ./database/migrations/002_lifecycle_rollup_fix.sql:/docker-entrypoint-initdb.d/003_migration_002.sql:ro
  - ./database/migrations/003_estimate_price_link_validation.sql:/docker-entrypoint-initdb.d/004_migration_003.sql:ro
  - ./database/migrations/004_placement_comparison_snapshots.sql:/docker-entrypoint-initdb.d/005_migration_004.sql:ro
```

These run automatically on first container start when the data directory is empty.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DCC_DATABASE_URL` | `""` | PostgreSQL connection string (required) |
| `DCC_TRACING_ENABLED` | `"false"` | Enable OpenTelemetry tracing |
| `DCC_OTLP_ENDPOINT` | `"http://localhost:4317"` | OTLP collector endpoint |
| `DCC_JAEGER_ENDPOINT` | `"http://localhost:14250"` | Jaeger agent endpoint |
| `DCC_SERVICE_NAME` | `"data-center-commander"` | Service name for tracing |
| `DCC_TRACE_SAMPLE_RATE` | `"1.0"` | Trace sampling rate (0.0–1.0) |
| `DCC_LOG_LEVEL` | `"INFO"` | Logging level |
| `DCC_PORT` | `"8790"` | API port |
| `DCC_HOST` | `"0.0.0.0"` | API bind address |
| `DCC_DEMO_MODE` | `"false"` | Enable synthetic demo data |
| `DCC_READ_ONLY` | `"true"` | Enable read-only mode |

## Networking

### Default Bridge Network

The compose file creates a `dcc-net` bridge network:

```yaml
networks:
  dcc-net:
    driver: bridge
```

Both services attach to this network, allowing the app to reach the database
using the service name `db` as the hostname.

### Custom Network

```yaml
networks:
  dcc-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### External Network

```yaml
networks:
  dcc-net:
    external: true
    name: my-existing-network
```

## Volumes

### Named Volume

```yaml
volumes:
  db_data:
```

The `db_data` volume persists PostgreSQL data across container restarts.

### Bind Mount (Development)

```yaml
services:
  db:
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
```

## Security Best Practices

### 1. Use Non-Root User

The Dockerfile already creates and uses a non-root user (`dcc`, UID 999).

### 2. Scan for Vulnerabilities

```bash
docker scan data-center-commander:latest
```

### 3. Use Read-Only Root Filesystem

```bash
docker run -d --read-only --tmpfs /tmp data-center-commander:latest
```

### 4. Drop Capabilities

```bash
docker run -d --cap-drop=ALL --cap-add=NET_BIND_SERVICE data-center-commander:latest
```

### 5. Set Resource Limits

```bash
docker run -d \
  --memory="512m" \
  --cpus="1.0" \
  data-center-commander:latest
```

### 6. Use Secrets for Sensitive Data

```bash
echo "postgresql://user:password@host:5432/db" | docker secret create dcc_db_url -
docker service create --secret dcc_db_url data-center-commander:latest
```

## Production Deployment

### Docker Swarm

```bash
# Initialize swarm (on manager node)
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml dcc

# Verify
docker service ls
docker service logs dcc_app
```

### Docker Compose with Production Overrides

Create `docker-compose.prod.yml`:

```yaml
services:
  app:
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
    environment:
      DCC_LOG_LEVEL: "WARNING"
      DCC_READ_ONLY: "true"
```

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs dcc

# Check exit code
docker inspect dcc --format='{{.State.ExitCode}}'

# Run interactively
docker run --rm -it data-center-commander:latest /bin/bash
```

### Database Connection Issues

```bash
# Test database connectivity from container
docker exec -it dcc ping db
docker exec -it dcc nc -zv db 5432

# Check database logs
docker-compose logs db
```

### Health Check Failing

```bash
# Check health status
docker inspect dcc --format='{{.State.Health.Status}}'

# Manual health check
docker exec dcc curl -sf http://127.0.0.1:8790/healthz
```

### Image Too Large

```bash
# Check image size
docker images data-center-commander

# Check layer history
docker history data-center-commander:latest

# Use docker-slim or dive to analyze
dive data-center-commander:latest
```

## Image Size Optimization

The multi-stage build keeps the final image small:

| Component | Size |
|---|---|
| `python:3.11-slim` base | ~45 MB |
| `libpq5` + `curl` | ~10 MB |
| Python venv (app + deps) | ~80–120 MB |
| Application code | ~5 MB |
| **Total estimated** | **~140–180 MB** |

## Next Steps

- [Kubernetes](kubernetes.md) — Production orchestration
- [Podman](podman.md) — Rootless, daemonless alternative
- [containerd](containerd.md) — Lightweight runtime
- [OpenShift](openshift.md) — Enterprise platform
