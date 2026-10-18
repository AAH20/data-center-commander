# EC2 Module

Creates EC2 instances with configurable storage, networking, and monitoring.

## Usage

```hcl
module "app_servers" {
  source = "./modules/aws/ec2"

  name           = "app-server"
  instance_count = 2
  instance_type  = "t3.large"
  subnet_ids     = module.subnets.private_subnet_ids
  security_group_ids = [module.app_sg.security_group_id]
  key_name       = "my-key"
  root_volume_size = 50

  tags = {
    Environment = "production"
    Role        = "application"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Name prefix | string | - | yes |
| instance_count | Number of instances | number | 1 | no |
| instance_type | EC2 type | string | t3.medium | no |
| ami_id | AMI ID (auto if null) | string | null | no |
| ami_name_filter | AMI name filter | string | amzn2-ami-hvm-*-x86_64-gp2 | no |
| ami_owners | AMI owners | list(string) | ["amazon"] | no |
| subnet_ids | Subnet IDs | list(string) | - | yes |
| security_group_ids | Security group IDs | list(string) | [] | no |
| key_name | SSH key name | string | null | no |
| iam_instance_profile | Instance profile | string | null | no |
| user_data | User data script | string | null | no |
| detailed_monitoring | Detailed monitoring | bool | false | no |
| root_volume_size | Root volume GB | number | 20 | no |
| root_volume_type | Root volume type | string | gp3 | no |
| root_volume_encrypted | Encrypt root | bool | true | no |
| additional_volumes | Extra EBS volumes | list(object) | [] | no |
| assign_elastic_ip | Assign EIPs | bool | false | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| instance_ids | Instance IDs |
| instance_public_ips | Public IPs |
| instance_private_ips | Private IPs |
| elastic_ips | Elastic IPs |
