output "vpc_id" {
  description = "ID of the created VPC"
  value       = digitalocean_vpc.this.id
}

output "vpc_urn" {
  description = "URN of the created VPC"
  value       = digitalocean_vpc.this.urn
}

output "vpc_ip_range" {
  description = "IP range of the VPC"
  value       = digitalocean_vpc.this.ip_range
}

output "vpc_default" {
  description = "Whether this is the default VPC for the region"
  value       = digitalocean_vpc.this.default
}
