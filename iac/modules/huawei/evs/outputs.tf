output "volume_ids" {
  description = "List of EVS volume IDs"
  value       = huaweicloud_evs_volume_v3.this[*].id
}

output "volume_names" {
  description = "List of EVS volume names"
  value       = huaweicloud_evs_volume_v3.this[*].name
}

output "attachment_ids" {
  description = "List of volume attachment IDs (if attached)"
  value       = var.instance_id != null ? huaweicloud_compute_volume_attach_v2.this[*].id : []
}
