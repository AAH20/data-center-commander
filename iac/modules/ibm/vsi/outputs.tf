output "instance_id" {
  description = "ID of the created VSI"
  value       = ibm_is_instance.this.id
}

output "instance_crn" {
  description = "CRN of the created VSI"
  value       = ibm_is_instance.this.crn
}

output "instance_name" {
  description = "Name of the created VSI"
  value       = ibm_is_instance.this.name
}

output "primary_ip" {
  description = "Primary IP address of the VSI"
  value       = ibm_is_instance.this.primary_network_interface[0].primary_ip[0].address
}

output "floating_ip" {
  description = "Floating IP address (if enabled)"
  value       = var.enable_floating_ip ? ibm_is_floating_ip.this[0].address : null
}

output "floating_ip_id" {
  description = "Floating IP ID (if enabled)"
  value       = var.enable_floating_ip ? ibm_is_floating_ip.this[0].id : null
}
