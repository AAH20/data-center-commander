# OpenShift Deployment Module

Creates a complete OpenShift deployment with ConfigMap, Secret, Service, HPA, and PDB.

## Usage

```hcl
module "dcc_api" {
  source = "./modules/openshift/deployment"

  name      = "dcc-api"
  namespace = "data-center-commander"
  image     = "data-center-commander:latest"

  replicas = 2

  config_data = {
    "DCC_LOG_LEVEL" = "info"
    "DCC_PORT"      = "8790"
  }

  secret_data = {
    "DCC_DATABASE_URL" = "postgresql://user:***@host:5432/dcc"
  }

  enable_hpa = true
  hpa_min_replicas = 2
  hpa_max_replicas = 10

  enable_pdb = true
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Deployment name | string | - | yes |
| namespace | Target namespace | string | - | yes |
| image | Container image | string | - | yes |
| image_pull_policy | Image pull policy | string | IfNotPresent | no |
| replicas | Number of replicas | number | 2 | no |
| part_of | app.kubernetes.io/part-of label | string | data-center-commander | no |
| labels | Additional labels | map(string) | {} | no |
| annotations | Additional annotations | map(string) | {} | no |
| pod_annotations | Pod annotations | map(string) | {} | no |
| service_account_name | Service account name | string | default | no |
| container_port | Container port | number | 8790 | no |
| run_as_user | Container UID | number | 999 | no |
| run_as_group | Container GID | number | 999 | no |
| fs_group | FS group | number | 999 | no |
| cpu_request | CPU request | string | 100m | no |
| memory_request | Memory request | string | 128Mi | no |
| cpu_limit | CPU limit | string | 500m | no |
| memory_limit | Memory limit | string | 256Mi | no |
| max_surge | Rolling update max surge | string | 1 | no |
| max_unavailable | Rolling update max unavailable | string | 0 | no |
| config_data | ConfigMap data | map(string) | {} | no |
| secret_data | Secret data | map(string) | {} | no |
| env_vars | Plain env vars | map(string) | {} | no |
| secret_env_vars | Env vars from secrets | map(string) | {} | no |
| volume_mounts | Volume mounts | map(string) | {} | no |
| liveness_probe_path | Liveness probe path | string | /healthz | no |
| liveness_initial_delay | Liveness initial delay | number | 10 | no |
| liveness_period | Liveness period | number | 30 | no |
| liveness_timeout | Liveness timeout | number | 5 | no |
| liveness_failure_threshold | Liveness failure threshold | number | 3 | no |
| readiness_probe_path | Readiness probe path | string | /readyz | no |
| readiness_initial_delay | Readiness initial delay | number | 5 | no |
| readiness_period | Readiness period | number | 10 | no |
| readiness_timeout | Readiness timeout | number | 5 | no |
| readiness_failure_threshold | Readiness failure threshold | number | 3 | no |
| enable_metrics | Enable Prometheus scraping | bool | false | no |
| metrics_path | Metrics endpoint path | string | /metrics | no |
| enable_hpa | Enable HPA | bool | false | no |
| hpa_min_replicas | HPA min replicas | number | 2 | no |
| hpa_max_replicas | HPA max replicas | number | 10 | no |
| hpa_cpu_target | HPA CPU target | number | 70 | no |
| hpa_memory_target | HPA memory target | number | 80 | no |
| enable_pdb | Enable PDB | bool | false | no |
| pdb_min_available | PDB min available | string | 1 | no |
| topology_spread_constraints | Topology spread constraints | list(object) | [...] | no |

## Outputs

| Name | Description |
|------|-------------|
| deployment_name | Deployment name |
| deployment_namespace | Deployment namespace |
| service_name | Service name |
| service_cluster_ip | Service ClusterIP |
| config_map_name | ConfigMap name (if created) |
| secret_name | Secret name (if created) |
| hpa_name | HPA name (if enabled) |
| pdb_name | PDB name (if enabled) |
