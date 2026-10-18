output "instance_ids" {
  description = "IDs of compute instances"
  value       = google_compute_instance.this[*].id
}

output "instance_names" {
  description = "Names of compute instances"
  value       = google_compute_instance.this[*].name
}

output "instance_public_ips" {
  description = "Public IPs of compute instances"
  value = [
    for instance in google_compute_instance.this :
    instance.network_interface[0].access_config[0].nat_ip if length(instance.network_interface[0].access_config) > 0
  ]
}

output "instance_private_ips" {
  description = "Private IPs of compute instances"
  value       = google_compute_instance.this[*].network_interface[0].network_ip
}

output "instance_zones" {
  description = "Zones of compute instances"
  value       = google_compute_instance.this[*].zone
}
