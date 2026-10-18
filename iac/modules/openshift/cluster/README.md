# OpenShift Cluster Module

Provisions an OpenShift cluster using `openshift-install`.

## Prerequisites

- `openshift-install` binary in PATH (download from https://mirror.openshift.com)
- Cloud credentials configured in environment
- Pull secret from https://console.redhat.com/openshift/install/pull-secret
- SSH public key for node access

## Usage

```hcl
module "openshift_cluster" {
  source = "./modules/openshift/cluster"

  cluster_name       = "dcc-prod"
  base_domain        = "example.com"
  cloud_provider     = "aws"
  region             = "us-east-1"
  openshift_version = "4.15.0"
  pull_secret        = file("~/.openshift/pull-secret.json")
  ssh_public_key     = file("~/.ssh/id_rsa.pub")
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| cluster_name | Cluster name | string | - | yes |
| base_domain | Base DNS domain | string | - | yes |
| cloud_provider | Cloud provider (aws/azure/gcp) | string | aws | no |
| region | Cloud region | string | - | yes |
| openshift_version | OpenShift version | string | - | yes |
| pull_secret | Pull secret JSON | string | - | yes |
| ssh_public_key | SSH public key | string | - | yes |
| additional_install_flags | Extra openshift-install flags | string | "" | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| cluster_name | Cluster name |
| cluster_api_url | API server URL |
| cluster_console_url | Web console URL |
| cluster_kubeconfig_path | Path to kubeconfig |
| cluster_creds_path | Path to kubeadmin password |
