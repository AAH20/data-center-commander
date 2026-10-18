output "access_group_id" {
  description = "ID of the created access group"
  value       = ibm_iam_access_group.this.id
}

output "access_group_name" {
  description = "Name of the created access group"
  value       = ibm_iam_access_group.this.name
}

output "access_group_crn" {
  description = "CRN of the created access group"
  value       = ibm_iam_access_group.this.crn
}

output "policy_ids" {
  description = "Map of policy names to IDs"
  value       = { for k, v in ibm_iam_access_group_policy.this : k => v.id }
}

output "dynamic_rule_ids" {
  description = "Map of dynamic rule names to IDs"
  value       = { for k, v in ibm_iam_access_group_dynamic_rule.this : k => v.id }
}
