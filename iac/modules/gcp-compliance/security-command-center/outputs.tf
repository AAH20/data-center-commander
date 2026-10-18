output "source_id" {
  description = "ID of the SCC source"
  value       = google_scc_source.this.id
}

output "source_name" {
  description = "Resource name of the SCC source"
  value       = google_scc_source.this.name
}

output "notification_config_id" {
  description = "ID of the notification config"
  value       = var.enable_notification_config ? google_scc_notification_config.this[0].id : null
}

output "pubsub_topic_id" {
  description = "ID of the Pub/Sub topic for SCC notifications"
  value       = var.enable_notification_config ? google_pubsub_topic.scc_notifications[0].id : null
}

output "mute_config_ids" {
  description = "IDs of the mute configs"
  value       = { for k, v in google_scc_mute_config.mute_rules : k => v.id }
}
