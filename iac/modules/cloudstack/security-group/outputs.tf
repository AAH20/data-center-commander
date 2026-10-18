output "security_group_id" {
  description = "ID of the security group"
  value       = cloudstack_security_group.this.id
}

output "security_group_name" {
  description = "Name of the security group"
  value       = cloudstack_security_group.this.name
}
