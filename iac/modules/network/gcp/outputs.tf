output "network_id" {
  description = "ID of the VPC network"
  value       = one(google_compute_network.this[*].id)
}

output "network_name" {
  description = "Name of the VPC network"
  value       = one(google_compute_network.this[*].name)
}

output "network_self_link" {
  description = "Self-link of the VPC network"
  value       = one(google_compute_network.this[*].self_link)
}

output "subnet_id" {
  description = "ID of the subnet"
  value       = one(google_compute_subnetwork.this[*].id)
}

output "subnet_self_link" {
  description = "Self-link of the subnet"
  value       = one(google_compute_subnetwork.this[*].self_link)
}

output "router_id" {
  description = "ID of the Cloud Router"
  value       = var.enable_cloud_nat ? one(google_compute_router.this[*].id) : null
}

output "nat_id" {
  description = "ID of the Cloud NAT"
  value       = var.enable_cloud_nat ? one(google_compute_router_nat.this[*].id) : null
}
