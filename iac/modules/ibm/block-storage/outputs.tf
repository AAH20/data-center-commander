output "volume_id" {
  description = "ID of the created block storage volume"
  value       = ibm_is_volume.this.id
}

output "volume_crn" {
  description = "CRN of the created block storage volume"
  value       = ibm_is_volume.this.crn
}

output "volume_name" {
  description = "Name of the created block storage volume"
  value       = ibm_is_volume.this.name
}

output "volume_capacity" {
  description = "Capacity of the volume in GB"
  value       = ibm_is_volume.this.capacity
}

output "attachment_id" {
  description = "ID of the volume attachment (if attached)"
  value       = var.instance_id != null ? ibm_is_instance_volume_attachment.this[0].id : null
}
