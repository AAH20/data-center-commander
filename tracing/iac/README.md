# Data Center Commander — Tracing Stack IaC

## Overview

OpenTofu configuration for deploying the OpenTelemetry + Jaeger tracing stack to Kubernetes. Complements the Docker Compose setup in the parent `tracing/` directory.

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

```bash
cd tracing/iac/

# Initialize
tofu init

# Review plan
tofu plan

# Deploy
tofu apply

# View outputs
tofu output
```

## Configuration

Copy `terraform.tfvars.example` to `terraform.tfvars` and adjust:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `namespace` | `tracing` | Kubernetes namespace |
| `jaeger_version` | `1.53` | Jaeger version |
| `jaeger_storage_type` | `memory` | Storage backend |
| `jaeger_enable_persistence` | `false` | Enable PVC |
| `jaeger_enable_ingress` | `false` | Enable ingress |
| `jaeger_ingress_host` | `jaeger.example.com` | Ingress hostname |
| `otel_collector_version` | `0.91.0` | Collector version |
| `prometheus_enable_persistence` | `true` | Enable PVC |
| `grafana_anonymous_enabled` | `true` | Anonymous access |
| `grafana_enable_ingress` | `false` | Enable ingress |

## Components

### Jaeger
- All-in-one deployment (agent + collector + query + UI)
- OTLP gRPC (4317) and HTTP (4318) receivers
- Jaeger gRPC (14250) and HTTP (14268) endpoints
- UI on port 16686
- Optional persistent storage via PVC

### OpenTelemetry Collector
- OTLP gRPC and HTTP receivers
- Batch, resource, and memory limiter processors
- Exports to Jaeger and Prometheus
- Health check on port 13133
- Prometheus metrics on port 8889

### Prometheus
- Scrapes OTel Collector metrics (15s interval)
- Filters for `dcc_*` metrics
- Optional persistent storage
- 15-day retention

### Grafana
- Pre-configured Jaeger and Prometheus data sources
- Anonymous access enabled by default
- Optional persistent storage
- Node graph enabled for Jaeger

## Outputs

| Output | Description |
|---|---|
| `jaeger_ui_url` | Jaeger UI URL |
| `jaeger_query_endpoint` | Jaeger query API |
| `jaeger_grpc_endpoint` | Jaeger gRPC endpoint |
| `otel_collector_otlp_grpc_endpoint` | OTLP gRPC endpoint |
| `otel_collector_otlp_http_endpoint` | OTLP HTTP endpoint |
| `prometheus_endpoint` | Prometheus endpoint |
| `grafana_endpoint` | Grafana endpoint |

## Production Considerations

1. **Persistence**: Enable PVCs for Jaeger, Prometheus, and Grafana
2. **Ingress**: Configure ingress with TLS for external access
3. **Security**: Disable anonymous Grafana access; use OIDC or LDAP
4. **Resources**: Adjust CPU/memory requests and limits based on load
5. **Retention**: Configure Jaeger storage retention policies
6. **High Availability**: Run multiple replicas of critical components
7. **Monitoring**: Add alert rules for tracing pipeline health

## Files

```
tracing/iac/
├── main.tf                      # Root configuration
├── variables.tf                 # Variable definitions
├── outputs.tf                   # Output definitions
├── terraform.tfvars.example     # Example variable values
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
├── modules/
│   ├── jaeger/                  # Jaeger module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── otel-collector/          # OTel Collector module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── config.yaml.tpl
│   ├── prometheus/              # Prometheus module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── prometheus.yml.tpl
│   └── grafana/                 # Grafana module
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── grafana.ini.tpl
│       └── datasources.yml.tpl
└── k8s/                         # Raw Kubernetes manifests
    ├── namespace.yaml
    ├── jaeger.yaml
    ├── otel-collector.yaml
    ├── prometheus.yaml
    └── grafana.yaml
```
