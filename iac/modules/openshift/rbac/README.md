# OpenShift RBAC Module

Creates a ServiceAccount with Role/ClusterRole and bindings.

## Usage

```hcl
module "dcc_rbac" {
  source = "./modules/openshift/rbac"

  name      = "dcc-api"
  namespace = "data-center-commander"

  role_rules = [
    {
      api_groups = [""]
      resources  = ["configmaps", "secrets"]
      verbs      = ["get", "list", "watch"]
    },
    {
      api_groups = ["apps"]
      resources  = ["deployments"]
      verbs      = ["get", "list", "watch"]
    }
  ]

  cluster_role_rules = [
    {
      api_groups = [""]
      resources  = ["namespaces"]
      verbs      = ["get", "list"]
    }
  ]
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | ServiceAccount name | string | - | yes |
| namespace | Target namespace | string | - | yes |
| part_of | app.kubernetes.io/part-of label | string | data-center-commander | no |
| labels | Additional labels | map(string) | {} | no |
| annotations | Additional annotations | map(string) | {} | no |
| automount_token | Automount SA token | bool | false | no |
| role_rules | Namespace Role rules | list(object) | [] | no |
| cluster_role_rules | ClusterRole rules | list(object) | [] | no |
| additional_role_bindings | Extra Role bindings | map(object) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| service_account_name | ServiceAccount name |
| service_account_namespace | ServiceAccount namespace |
| role_name | Role name (if created) |
| cluster_role_name | ClusterRole name (if created) |
| role_binding_name | RoleBinding name (if created) |
| cluster_role_binding_name | ClusterRoleBinding name (if created) |
