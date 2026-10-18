output "instance_ids" {
  description = "List of ECS instance IDs"
  value       = alicloud_instance.this[*].id
}

output "instance_names" {
  description = "List of ECS instance names"
  value       = alicloud_instance.this[*].instance_name
}

output "instance_ips" {
  description = "List of ECS instance private IPs"
  value       = alicloud_instance.this[*].private_ip
}

output "eip_address" {
  description = "Elastic IP address (if enabled)"
  value       = var.enable_eip ? alicloud_eip_address.this[0].ip_address : null
}
