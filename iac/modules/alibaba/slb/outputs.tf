output "loadbalancer_id" {
  description = "ID of the load balancer"
  value       = alicloud_slb_load_balancer.this.id
}

output "loadbalancer_name" {
  description = "Name of the load balancer"
  value       = alicloud_slb_load_balancer.this.load_balancer_name
}

output "loadbalancer_address" {
  description = "IP address of the load balancer"
  value       = alicloud_slb_load_balancer.this.address
}

output "listener_ids" {
  description = "Map of listener names to IDs"
  value       = { for k, v in alicloud_slb_listener.this : k => v.id }
}
