# Data Center Commander — Distributed Tracing

## Overview

This tracing stack provides end-to-end distributed tracing for Data Center Commander using:

- **OpenTelemetry** — vendor-neutral instrumentation and context propagation
- **Jaeger** — trace storage and visualization UI
- **OpenTelemetry Collector** — trace processing and routing
- **Prometheus** — span metrics collection
- **Grafana** — dashboards and visualization

## Architecture

```
┌─────────────┐     OTLP/gRPC      ┌──────────────────┐     ┌──────────┐
│  DCC App    │ ──────────────────► │ OTel Collector   │ ──► │  Jaeger  │
│  (Python)   │                     │                  │     │  (UI)    │
└─────────────┘                     │  - batch         │     └──────────┘
                                    │  - resource      │
                                    │  - memory limit  │     ┌──────────┐
                                    │                  │ ──► │Prometheus│
                                    └──────────────────┘     └──────────┘
                                                                │
                                                                ▼
                                                           ┌──────────┐
                                                           │ Grafana  │
                                                           │ (UI)     │
                                                           └──────────┘
```

## Quick Start

### 1. Install dependencies

```bash
pip install -e '.[tracing]'
```

### 2. Start the tracing stack

```bash
docker compose -f docker-compose.yml -f tracing/docker-compose.tracing.yml up -d
```

### 3. Enable tracing in the app

Set environment variables:

```bash
export DCC_TRACING_ENABLED=true
export DCC_OTLP_ENDPOINT=http://localhost:4317
export DCC_JAEGER_ENDPOINT=http://localhost:14250
export DCC_SERVICE_NAME=data-center-commander
export DCC_TRACE_SAMPLE_RATE=1.0
```

Or use the provided `.env.example`:

```bash
cp tracing/.env.example .env
```

### 4. Run the application

```bash
python scripts/run-local.py --host 127.0.0.1 --port 8790
```

### 5. View traces

- **Jaeger UI**: http://localhost:16686
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DCC_TRACING_ENABLED` | `false` | Enable/disable tracing |
| `DCC_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint |
| `DCC_JAEGER_ENDPOINT` | `http://localhost:14250` | Jaeger gRPC endpoint |
| `DCC_SERVICE_NAME` | `data-center-commander` | Service name in traces |
| `DCC_TRACE_SAMPLE_RATE` | `1.0` | Trace sample rate (0.0-1.0) |
| `DCC_DEPLOYMENT_ENV` | `development` | Deployment environment tag |

### Sampling

Control trace volume with `DCC_TRACE_SAMPLE_RATE`:

- `1.0` — sample all traces (development)
- `0.1` — sample 10% of traces (production)
- `0.0` — disable sampling

## Usage in Code

### Decorator

```python
from dcc.observability import trace

@trace("fetch_azure_prices")
def fetch_azure_retail_prices(...):
    ...
```

### Context Manager

```python
from dcc.observability import span, SpanKind

with span("database.query", span_kind=SpanKind.CLIENT, attributes={
    "db.system": "postgresql",
    "db.statement": "SELECT * FROM assets",
}):
    rows = conn.execute("SELECT * FROM assets")
```

### HTTP Request Tracing

```python
from dcc.observability import trace_request

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with trace_request(self, "GET /v1/assets"):
            # ... handle request ...
            pass
```

### Context Propagation

```python
from dcc.observability import inject_context, extract_context

# Inject trace context into outgoing HTTP headers
headers = {}
inject_context(headers)
# headers now contains 'traceparent' and optionally 'tracestate'

# Extract trace context from incoming HTTP headers
ctx = extract_context(headers)
```

## Files

```
tracing/
├── docker-compose.tracing.yml   # Docker Compose override for tracing services
├── otel-config.yaml             # OpenTelemetry Collector configuration
├── prometheus.yml               # Prometheus scrape configuration
├── grafana-datasources.yml      # Grafana data source provisioning
├── .env.example                 # Example environment variables
└── README.md                    # This file

src/dcc/observability/
├── tracing.py                   # Core tracing engine (spans, traces, context)
├── middleware.py                # HTTP request tracing middleware
└── __init__.py                  # Public API exports

scripts/
└── setup-tracing.py             # Tracing initialization script

tests/
└── test_tracing_middleware.py   # Middleware and context propagation tests
```

## W3C Trace Context

The implementation follows the [W3C Trace Context](https://www.w3.org/TR/trace-context/) specification:

- `traceparent` header: `{version}-{trace-id}-{span-id}-{trace-flags}`
- `tracestate` header: vendor-specific key-value pairs

This ensures interoperability with other OpenTelemetry-instrumented services.

## Production Considerations

1. **Sampling**: Use a lower sample rate (`0.01`-`0.1`) in production to reduce overhead.
2. **Batching**: The OTel Collector batches spans before export to reduce network overhead.
3. **Memory limits**: The collector has a memory limiter to prevent OOM.
4. **Security**: In production, use TLS for OTLP and Jaeger endpoints.
5. **Retention**: Configure Jaeger storage retention based on your needs.
6. **High availability**: Run multiple collector instances behind a load balancer.

## Troubleshooting

### No traces appearing in Jaeger

1. Check that `DCC_TRACING_ENABLED=true` is set
2. Verify the OTLP endpoint is reachable: `curl http://localhost:4317`
3. Check collector logs: `docker compose logs otel-collector`
4. Verify the app is running with tracing: `docker compose logs app`

### High memory usage

1. Reduce `DCC_TRACE_SAMPLE_RATE`
2. Lower the collector's `memory_limiter` settings
3. Reduce `send_batch_size` in the collector config

### Spans not correlating

1. Ensure all services use the same `service.name`
2. Verify W3C trace context headers are propagated
3. Check that `traceparent` headers are forwarded through proxies
