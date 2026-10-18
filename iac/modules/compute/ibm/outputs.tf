output "instance_ids" {
  description = "IDs of VPC instances"
  value       = ibm_is_instance.this[*].id
}

output "instance_names" {
  description = "Names of VPC instances"
  value       = ibm_is_instance.this[*].name
}

output "instance_public_ips" {
  description = "Public IPs of instances"
  value       = var.enable_floating_ip ? ibm_is_floating_ip.this[*].address : []
}

output "instance_private_ips" {
  description = "Private IPs of instances"
  value       = ibm_is_instance.this[*].primary_network_interface[0].primary_ipv4_address
}

output "floating_ip_ids" {
  description = "Floating IP IDs"
  value       = var.enable_floating_ip ? ibm_is_floating_ip.this[*].id : []
}
