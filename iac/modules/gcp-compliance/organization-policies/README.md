# Organization Policies Module

Applies Google Cloud Organization Policy constraints to a project for security compliance.

## Usage

```hcl
module "org_policies" {
  source    = "./modules/gcp-compliance/organization-policies"
  project_id = "my-project-id"

  disable_serial_port      = true
  require_os_login         = true
  restrict_vm_external_ips = true
  require_shielded_vms     = true
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| google | ~> 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_id | GCP project ID | string | - | yes |
| disable_serial_port | Disable serial port access | bool | true | no |
| require_os_login | Require OS Login | bool | true | no |
| restrict_vm_external_ips | Restrict VM external IPs | bool | true | no |
| enforce_uniform_bucket_level_access | Enforce uniform bucket-level access | bool | true | no |
| restrict_public_ip_cloudsql | Restrict Cloud SQL public IPs | bool | true | no |
| disable_sa_key_creation | Disable SA key creation | bool | true | no |
| disable_sa_key_upload | Disable SA key upload | bool | true | no |
| require_vpc_flow_logs | Require VPC Flow Logs | bool | true | no |
| restrict_vpc_peering | Restrict VPC peering | bool | false | no |
| restrict_vpn_peer_ips | Restrict VPN peer IPs | bool | false | no |
| disable_default_network | Skip default network creation | bool | true | no |
| require_shielded_vms | Require Shielded VMs | bool | true | no |
| restrict_cloud_nat | Restrict Cloud NAT | bool | false | no |
| restrict_lb_creation | Restrict load balancer creation | bool | false | no |
| restrict_shared_vpc | Restrict shared VPC | bool | false | no |
| restrict_xpn_project_creation | Restrict XPN project creation | bool | false | no |
| custom_constraints | Custom org policy constraints | map(object) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| enabled_policies | Map of enabled policy constraint names to resource IDs |
