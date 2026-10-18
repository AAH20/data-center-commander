output "instance_ids" {
  description = "List of instance IDs"
  value       = cloudstack_instance.this[*].id
}

output "instance_names" {
  description = "List of instance names"
  value       = cloudstack_instance.this[*].name
}

output "instance_ips" {
  description = "List of instance IPs"
  value       = cloudstack_instance.this[*].ip_address
}
