# Containerization Integration Module

Docker-based containerization for Data Center Commander.

## Overview

This module provisions a complete container runtime environment:

- **Docker Network**: Isolated bridge network with custom subnet
- **Service Containers**: Configurable map of services with healthchecks
- **Traefik Reverse Proxy**: Automatic TLS, load balancing, dashboard
- **Monitoring Stack**: Prometheus + Grafana for observability
- **Local Registry**: Build and store service images locally

## Usage

```hcl
module "containerization" {
  source = "../integration/containerization"

  project_name = "datacenter"
  environment  = "prod"

  services = {
    api = {
      image               = "datacenter-api"
      tag                 = "latest"
      build_context       = "../../src/api"
      dockerfile          = "Dockerfile"
      internal_port       = 8080
      external_port       = 8080
      env                 = ["ENV=production", "LOG_LEVEL=info"]
      data_path           = "/opt/datacenter/data/api"
      container_data_path = "/data"
      healthcheck_command = ["CMD", "curl", "-f", "http://localhost:8080/health"]
    }
  }
}
```

## Requirements

- Docker Engine 24.0+
- Docker provider configured (local socket or remote TCP)

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project_name | Project name prefix | string | required |
| environment | Environment label | string | dev |
| network_subnet | Docker network subnet | string | 172.20.0.0/16 |
| registry_name | Local registry name | string | datacenter-registry |
| services | Service definitions map | map | {} |
| enable_traefik | Deploy Traefik | bool | true |
| traefik_acme_email | Let's Encrypt email | string | admin@datacenter.local |
| traefik_config_path | Traefik config path | string | /opt/datacenter/traefik |
| traefik_certs_path | Certificates path | string | /opt/datacenter/certs |
| enable_monitoring | Deploy monitoring | bool | true |
| monitoring_config_path | Monitoring config path | string | /opt/datacenter/monitoring |
| monitoring_data_path | Monitoring data path | string | /opt/datacenter/monitoring-data |
| grafana_admin_user | Grafana admin user | string | admin |
| grafana_admin_password | Grafana admin password | string | admin |
| labels | Container labels | map | {} |

## Outputs

| Name | Description |
|------|-------------|
| network_id | Docker network ID |
| network_name | Docker network name |
| service_container_ids | Service → container ID map |
| service_container_names | Service → container name map |
| traefik_container_id | Traefik container ID |
| prometheus_container_id | Prometheus container ID |
| grafana_container_id | Grafana container ID |
