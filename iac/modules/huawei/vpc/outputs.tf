output "vpc_id" {
  description = "ID of the created VPC"
  value       = huaweicloud_vpc_v1.this.id
}

output "vpc_name" {
  description = "Name of the created VPC"
  value       = huaweicloud_vpc_v1.this.name
}

output "subnet_ids" {
  description = "Map of subnet names to IDs"
  value       = { for k, v in huaweicloud_vpc_subnet_v1.this : k => v.id }
}

output "security_group_id" {
  description = "ID of the security group (if created)"
  value       = var.create_security_group ? huaweicloud_networking_secgroup_v2.this[0].id : null
}
