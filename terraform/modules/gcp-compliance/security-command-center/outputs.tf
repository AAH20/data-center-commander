output "scc_source_id" {
  description = "ID of the SCC source"
  value       = google_scc_source.this.id
}

output "scc_notification_config_id" {
  description = "ID of the SCC notification config"
  value       = var.enable_notification_config ? google_scc_notification_config.this[0].id : null
}

output "scc_mute_rules" {
  description = "List of SCC mute rules"
  value       = [for rule in google_scc_mute_config.mute_rules : rule.mute_config_id]
}
