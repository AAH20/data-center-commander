output "database_cluster_id" {
  description = "ID of the created database cluster"
  value       = digitalocean_database_cluster.this.id
}

output "database_cluster_urn" {
  description = "URN of the created database cluster"
  value       = digitalocean_database_cluster.this.urn
}

output "database_cluster_name" {
  description = "Name of the database cluster"
  value       = digitalocean_database_cluster.this.name
}

output "database_cluster_engine" {
  description = "Engine of the database cluster"
  value       = digitalocean_database_cluster.this.engine
}

output "database_cluster_version" {
  description = "Version of the database cluster"
  value       = digitalocean_database_cluster.this.version
}

output "database_cluster_size" {
  description = "Size of the database cluster"
  value       = digitalocean_database_cluster.this.size
}

output "database_cluster_region" {
  description = "Region of the database cluster"
  value       = digitalocean_database_cluster.this.region
}

output "database_cluster_host" {
  description = "Host of the database cluster"
  value       = digitalocean_database_cluster.this.host
}

output "database_cluster_port" {
  description = "Port of the database cluster"
  value       = digitalocean_database_cluster.this.port
}

output "database_cluster_uri" {
  description = "URI of the database cluster"
  value       = digitalocean_database_cluster.this.uri
  sensitive   = true
}

output "database_cluster_private_uri" {
  description = "Private URI of the database cluster"
  value       = digitalocean_database_cluster.this.private_uri
  sensitive   = true
}

output "database_cluster_database" {
  description = "Default database name of the cluster"
  value       = digitalocean_database_cluster.this.database
}

output "database_cluster_user" {
  description = "Default user of the database cluster"
  value       = digitalocean_database_cluster.this.user
}

output "database_cluster_password" {
  description = "Password of the default user"
  value       = digitalocean_database_cluster.this.password
  sensitive   = true
}

output "database_cluster_status" {
  description = "Status of the database cluster"
  value       = digitalocean_database_cluster.this.status
}

output "database_cluster_maintenance_window" {
  description = "Maintenance window of the database cluster"
  value       = digitalocean_database_cluster.this.maintenance_window
}

output "database_cluster_node_count" {
  description = "Number of nodes in the database cluster"
  value       = digitalocean_database_cluster.this.node_count
}

output "database_db_ids" {
  description = "IDs of the created databases"
  value       = [for db in digitalocean_database_db.this : db.id]
}

output "database_user_ids" {
  description = "IDs of the created database users"
  value       = [for user in digitalocean_database_user.this : user.id]
}

output "database_firewall_id" {
  description = "ID of the database firewall"
  value       = length(var.allowed_droplet_ids) > 0 || length(var.allowed_cidrs) > 0 ? digitalocean_database_firewall.this[0].id : null
}
