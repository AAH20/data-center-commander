output "disk_ids" {
  description = "List of disk IDs"
  value       = cloudstack_disk.this[*].id
}

output "disk_names" {
  description = "List of disk names"
  value       = cloudstack_disk.this[*].name
}

output "volume_id" {
  description = "ID of the standalone volume (if created)"
  value       = var.create_volume ? cloudstack_volume.this[0].id : null
}
