output "vpc_id" {
  description = "ID of the created VPC"
  value       = alicloud_vpc.this.id
}

output "vpc_name" {
  description = "Name of the created VPC"
  value       = alicloud_vpc.this.vpc_name
}

output "vswitch_ids" {
  description = "Map of vswitch names to IDs"
  value       = { for k, v in alicloud_vswitch.this : k => v.id }
}

output "security_group_id" {
  description = "ID of the security group (if created)"
  value       = var.create_security_group ? alicloud_security_group.this[0].id : null
}
