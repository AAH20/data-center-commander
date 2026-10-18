output "role_arns" {
  description = "Map of role names to ARNs"
  value       = { for k, v in aws_iam_role.this : k => v.arn }
}

output "role_names" {
  description = "Map of role names to names"
  value       = { for k, v in aws_iam_role.this : k => v.name }
}

output "policy_arns" {
  description = "Map of policy names to ARNs"
  value       = { for k, v in aws_iam_policy.this : k => v.arn }
}

output "instance_profile_names" {
  description = "Map of instance profile names"
  value       = { for k, v in aws_iam_instance_profile.this : k => v.name }
}

output "instance_profile_arns" {
  description = "Map of instance profile ARNs"
  value       = { for k, v in aws_iam_instance_profile.this : k => v.arn }
}

output "user_names" {
  description = "Map of user names"
  value       = { for k, v in aws_iam_user.this : k => v.name }
}

output "access_key_ids" {
  description = "Map of access key IDs (sensitive)"
  value       = { for k, v in aws_iam_access_key.this : k => v.id }
  sensitive   = true
}

output "secret_access_keys" {
  description = "Map of secret access keys (sensitive)"
  value       = { for k, v in aws_iam_access_key.this : k => v.secret }
  sensitive   = true
}
