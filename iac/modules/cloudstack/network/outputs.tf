output "network_id" {
  description = "ID of the network"
  value       = cloudstack_network.this.id
}

output "network_name" {
  description = "Name of the network"
  value       = cloudstack_network.this.name
}

output "ip_address_id" {
  description = "ID of the acquired IP address (if acquired)"
  value       = var.acquire_ip ? cloudstack_ipaddress.this[0].id : null
}
