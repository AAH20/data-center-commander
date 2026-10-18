output "droplet_ids" {
  description = "IDs of droplets"
  value       = digitalocean_droplet.this[*].id
}

output "droplet_names" {
  description = "Names of droplets"
  value       = digitalocean_droplet.this[*].name
}

output "droplet_public_ips" {
  description = "Public IPs of droplets"
  value       = digitalocean_droplet.this[*].ipv4_address
}

output "droplet_private_ips" {
  description = "Private IPs of droplets"
  value       = digitalocean_droplet.this[*].ipv4_address_private
}

output "droplet_urns" {
  description = "URNs of droplets"
  value       = digitalocean_droplet.this[*].urn
}

output "firewall_id" {
  description = "ID of the firewall"
  value       = var.enable_firewall ? digitalocean_firewall.this[0].id : null
}
