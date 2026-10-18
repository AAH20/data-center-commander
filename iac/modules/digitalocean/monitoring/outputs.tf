output "alert_ids" {
  description = "IDs of the created monitoring alerts"
  value       = { for k, v in digitalocean_monitor_alert.this : k => v.id }
}

output "alert_types" {
  description = "Types of the created monitoring alerts"
  value       = { for k, v in digitalocean_monitor_alert.this : k => v.type }
}

output "alert_descriptions" {
  description = "Descriptions of the created monitoring alerts"
  value       = { for k, v in digitalocean_monitor_alert.this : k => v.description }
}

output "alert_enabled" {
  description = "Enabled status of the created monitoring alerts"
  value       = { for k, v in digitalocean_monitor_alert.this : k => v.enabled }
}

output "alert_entities" {
  description = "Entities of the created monitoring alerts"
  value       = { for k, v in digitalocean_monitor_alert.this : k => v.entities }
}
