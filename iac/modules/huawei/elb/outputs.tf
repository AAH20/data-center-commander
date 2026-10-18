output "loadbalancer_id" {
  description = "ID of the load balancer"
  value       = huaweicloud_lb_loadbalancer_v3.this.id
}

output "loadbalancer_name" {
  description = "Name of the load balancer"
  value       = huaweicloud_lb_loadbalancer_v3.this.name
}

output "loadbalancer_vip" {
  description = "VIP address of the load balancer"
  value       = huaweicloud_lb_loadbalancer_v3.this.ipv4_address
}

output "listener_ids" {
  description = "Map of listener names to IDs"
  value       = { for k, v in huaweicloud_lb_listener_v3.this : k => v.id }
}

output "pool_ids" {
  description = "Map of pool names to IDs"
  value       = { for k, v in huaweicloud_lb_pool_v3.this : k => v.id }
}
