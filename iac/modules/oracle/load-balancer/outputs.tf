output "loadbalancer_id" {
  description = "ID of the load balancer"
  value       = oci_load_balancer_load_balancer.this.id
}

output "loadbalancer_name" {
  description = "Display name of the load balancer"
  value       = oci_load_balancer_load_balancer.this.display_name
}

output "loadbalancer_ip" {
  description = "IP address of the load balancer"
  value       = oci_load_balancer_load_balancer.this.ip_addresses[0].ip_address
}

output "backend_set_ids" {
  description = "Map of backend set names to IDs"
  value       = { for k, v in oci_load_balancer_backend_set.this : k => v.id }
}

output "listener_ids" {
  description = "Map of listener names to IDs"
  value       = { for k, v in oci_load_balancer_listener.this : k => v.id }
}
