output "volume_ids" {
  description = "List of volume IDs"
  value       = oci_core_volume.this[*].id
}

output "volume_names" {
  description = "List of volume display names"
  value       = oci_core_volume.this[*].display_name
}

output "attachment_ids" {
  description = "List of volume attachment IDs (if attached)"
  value       = var.instance_id != null ? oci_core_volume_attachment.this[*].id : []
}

output "backup_policy_id" {
  description = "ID of the backup policy (if created)"
  value       = var.create_backup_policy ? oci_core_volume_backup_policy.this[0].id : null
}
