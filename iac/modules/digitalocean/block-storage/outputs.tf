output "volume_ids" {
  description = "IDs of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].id
}

output "volume_urns" {
  description = "URNs of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].urn
}

output "volume_names" {
  description = "Names of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].name
}

output "volume_regions" {
  description = "Regions of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].region
}

output "volume_sizes" {
  description = "Sizes of the created Block Storage volumes in GiB"
  value       = digitalocean_volume.this[*].size
}

output "volume_filesystem_types" {
  description = "Filesystem types of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].filesystem_type
}

output "volume_filesystem_labels" {
  description = "Filesystem labels of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].filesystem_label
}

output "volume_droplet_ids" {
  description = "Droplet IDs attached to the Block Storage volumes"
  value       = digitalocean_volume.this[*].droplet_ids
}

output "volume_descriptions" {
  description = "Descriptions of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].description
}

output "volume_tags" {
  description = "Tags of the created Block Storage volumes"
  value       = digitalocean_volume.this[*].tags
}

output "attachment_ids" {
  description = "IDs of the volume attachments"
  value       = var.attach_to_droplets ? digitalocean_volume_attachment.this[*].id : []
}
