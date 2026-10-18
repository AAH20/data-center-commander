# IAM Module

Creates IAM roles, policies, instance profiles, groups, and users.

## Usage

```hcl
module "iam" {
  source = "./modules/aws/iam"

  roles = {
    "ec2-cloudwatch-role" = {
      description = "Role for EC2 instances to publish CloudWatch metrics"
      assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Action    = "sts:AssumeRole"
          Effect    = "Allow"
          Principal = { Service = "ec2.amazonaws.com" }
        }]
      })
      managed_policy_arns = [
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
    }
  }

  instance_profiles = {
    "ec2-cloudwatch-profile" = {
      role_name = "ec2-cloudwatch-role"
    }
  }

  tags = {
    Environment = "production"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| roles | IAM roles map | map(object) | {} | no |
| policies | IAM policies map | map(object) | {} | no |
| instance_profiles | Instance profiles map | map(object) | {} | no |
| groups | IAM groups map | map(object) | {} | no |
| group_policy_attachments | Group policy attachments | map(object) | {} | no |
| users | IAM users map | map(object) | {} | no |
| user_policy_attachments | User policy attachments | map(object) | {} | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| role_arns | Role name to ARN map |
| role_names | Role name map |
| policy_arns | Policy name to ARN map |
| instance_profile_names | Instance profile names |
| instance_profile_arns | Instance profile ARNs |
| user_names | User names |
| access_key_ids | Access key IDs (sensitive) |
| secret_access_keys | Secret access keys (sensitive) |
