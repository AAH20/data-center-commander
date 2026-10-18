output "instance_ids" {
  description = "List of ECS instance IDs"
  value       = huaweicloud_compute_instance_v2.this[*].id
}

output "instance_names" {
  description = "List of ECS instance names"
  value       = huaweicloud_compute_instance_v2.this[*].name
}

output "instance_ips" {
  description = "List of ECS instance private IPs"
  value       = huaweicloud_compute_instance_v2.this[*].access_ip_v4
}

output "eip_address" {
  description = "Elastic IP address (if enabled)"
  value       = var.enable_eip ? huaweicloud_compute_eip_associate.this[0].public_ip : null
}
