# IBM Cloud VSI Module

Creates an IBM Cloud Virtual Server Instance (VSI) with boot volume, optional data volumes, and floating IP.

## Usage

```hcl
module "vsi" {
  source = "./modules/ibm/vsi"

  name       = "web-server-01"
  vpc_id     = module.vpc.vpc_id
  subnet_id  = module.vpc.subnet_ids["zone-1"]
  zone       = "us-south-1"
  profile    = "bx2-2x8"
  ssh_key_ids = ["my-ssh-key"]
  tags       = ["production", "web"]
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
| name | VSI name | string | - | yes |
| vpc_id | VPC ID | string | - | yes |
| subnet_id | Subnet ID | string | - | yes |
| zone | Zone | string | - | yes |
| profile | Instance profile | string | bx2-2x8 | no |
| image_name | OS image name | string | ibm-ubuntu-22-04-1-amd64-1 | no |
| ssh_key_ids | SSH key names | list(string) | [] | no |
| security_group_ids | Security group IDs | list(string) | [] | no |
| boot_volume_size | Boot volume size (GB) | number | 100 | no |
| data_volume_ids | Data volume IDs | list(string) | [] | no |
| resource_group_id | Resource group ID | string | null | no |
| enable_floating_ip | Assign floating IP | bool | false | no |
| tags | Resource tags | list(string) | [] | no |

## Outputs

| Name | Description |
|------|-------------|
| instance_id | VSI ID |
| instance_crn | VSI CRN |
| instance_name | VSI name |
| primary_ip | Primary IP address |
| floating_ip | Floating IP address |
| floating_ip_id | Floating IP ID |
