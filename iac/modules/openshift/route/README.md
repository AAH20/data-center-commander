# OpenShift Route Module

Creates an OpenShift Route with optional TLS termination.

## Usage

```hcl
module "dcc_route" {
  source = "./modules/openshift/route"

  name         = "dcc-api"
  namespace    = "data-center-commander"
  host         = "dcc.example.com"
  service_name = "dcc-api"
  service_port = "http"

  tls_termination = "edge"
  insecure_policy = "Redirect"
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Route name | string | - | yes |
| namespace | Target namespace | string | - | yes |
| host | Route hostname | string | "" (auto) | no |
| path | Route path | string | / | no |
| service_name | Target Service name | string | - | yes |
| service_port | Target port on Service | string | http | no |
| tls_termination | TLS type (edge/passthrough/reencrypt) | string | edge | no |
| insecure_policy | Insecure traffic policy | string | Redirect | no |
| tls_certificate | TLS certificate (PEM) | string | null | no |
| tls_key | TLS private key (PEM) | string | null | no |
| tls_ca_certificate | TLS CA certificate (PEM) | string | null | no |
| destination_ca_certificate | Dest CA cert (reencrypt) | string | null | no |
| wildcard_policy | Wildcard policy | string | None | no |
| part_of | app.kubernetes.io/part-of label | string | data-center-commander | no |
| labels | Additional labels | map(string) | {} | no |
| annotations | Additional annotations | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| route_name | Route name |
| route_namespace | Route namespace |
| route_host | Route host |
| route_path | Route path |
| route_url | Full route URL |
| route_tls_termination | TLS termination type |
