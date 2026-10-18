# IBM Cloud Block Storage Module

Creates an IBM Cloud block storage volume with optional VSI attachment and customer-managed encryption.

## Usage

```hcl
module "block_storage" {
  source = "./modules/ibm/block-storage"

  name       = "data-volume-01"
  zone       = "us-south-1"
  capacity   = 500
  profile    = "10iops-tier"
  instance_id = module.vsi.instance_id
  tags       = ["production", "data"]
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| ibm | ~> 1.65 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Volume name | string | - | yes |
| zone | Zone | string | - | yes |
| capacity | Capacity (GB) | number | 100 | no |
| profile | Storage profile | string | 10iops-tier | no |
| instance_id | VSI to attach to | string | null | no |
| delete_on_instance_delete | Delete on instance delete | bool | false | no |
| encryption_key_crn | Encryption key CRN | string | null | no |
| resource_group_id | Resource group ID | string | null | no |
| tags | Resource tags | list(string) | [] | no |

## Outputs

| Name | Description |
|------|-------------|
| volume_id | Volume ID |
| volume_crn | Volume CRN |
| volume_name | Volume name |
| volume_capacity | Volume capacity (GB) |
| attachment_id | Attachment ID |
