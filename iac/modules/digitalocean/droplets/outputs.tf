output "droplet_ids" {
  description = "IDs of the created Droplets"
  value       = digitalocean_droplet.this[*].id
}

output "droplet_urns" {
  description = "URNs of the created Droplets"
  value       = digitalocean_droplet.this[*].urn
}

output "droplet_names" {
  description = "Names of the created Droplets"
  value       = digitalocean_droplet.this[*].name
}

output "droplet_ipv4_addresses" {
  description = "Public IPv4 addresses of the created Droplets"
  value       = digitalocean_droplet.this[*].ipv4_address
}

output "droplet_ipv4_addresses_private" {
  description = "Private IPv4 addresses of the created Droplets"
  value       = digitalocean_droplet.this[*].ipv4_address_private
}

output "droplet_ipv6_addresses" {
  description = "IPv6 addresses of the created Droplets"
  value       = digitalocean_droplet.this[*].ipv6_address
}

output "droplet_regions" {
  description = "Regions of the created Droplets"
  value       = digitalocean_droplet.this[*].region
}

output "droplet_sizes" {
  description = "Sizes of the created Droplets"
  value       = digitalocean_droplet.this[*].size
}

output "droplet_tags" {
  description = "Tags of the created Droplets"
  value       = digitalocean_droplet.this[*].tags
}
