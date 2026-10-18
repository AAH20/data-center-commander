output "loadbalancer_id" {
  description = "ID of the created Load Balancer"
  value       = digitalocean_loadbalancer.this.id
}

output "loadbalancer_urn" {
  description = "URN of the created Load Balancer"
  value       = digitalocean_loadbalancer.this.urn
}

output "loadbalancer_ip" {
  description = "Public IP address of the Load Balancer"
  value       = digitalocean_loadbalancer.this.ip
}

output "loadbalancer_name" {
  description = "Name of the Load Balancer"
  value       = digitalocean_loadbalancer.this.name
}

output "loadbalancer_region" {
  description = "Region of the Load Balancer"
  value       = digitalocean_loadbalancer.this.region
}

output "loadbalancer_size" {
  description = "Size of the Load Balancer"
  value       = digitalocean_loadbalancer.this.size
}

output "loadbalancer_algorithm" {
  description = "Algorithm of the Load Balancer"
  value       = digitalocean_loadbalancer.this.algorithm
}

output "loadbalancer_status" {
  description = "Status of the Load Balancer"
  value       = digitalocean_loadbalancer.this.status
}

output "loadbalancer_forwarding_rules" {
  description = "Forwarding rules of the Load Balancer"
  value       = digitalocean_loadbalancer.this.forwarding_rule
}

output "loadbalancer_healthcheck" {
  description = "Health check configuration of the Load Balancer"
  value       = digitalocean_loadbalancer.this.healthcheck
}

output "loadbalancer_sticky_sessions" {
  description = "Sticky sessions configuration of the Load Balancer"
  value       = digitalocean_loadbalancer.this.sticky_sessions
}

output "loadbalancer_droplet_ids" {
  description = "Droplet IDs attached to the Load Balancer"
  value       = digitalocean_loadbalancer.this.droplet_ids
}
