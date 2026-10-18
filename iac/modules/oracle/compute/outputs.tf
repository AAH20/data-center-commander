output "instance_ids" {
  description = "List of compute instance IDs"
  value       = oci_core_instance.this[*].id
}

output "instance_names" {
  description = "List of compute instance display names"
  value       = oci_core_instance.this[*].display_name
}

output "instance_public_ips" {
  description = "List of public IPs (if assigned)"
  value       = oci_core_instance.this[*].public_ip
}

output "instance_private_ips" {
  description = "List of private IPs"
  value       = oci_core_instance.this[*].private_ip
}
