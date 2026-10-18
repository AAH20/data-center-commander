output "disk_ids" {
  description = "List of disk IDs"
  value       = alicloud_disk.this[*].id
}

output "disk_names" {
  description = "List of disk names"
  value       = alicloud_disk.this[*].disk_name
}

output "attachment_ids" {
  description = "List of disk attachment IDs (if attached)"
  value       = var.instance_id != null ? alicloud_disk_attachment.this[*].id : []
}
