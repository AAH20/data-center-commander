terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ─── SCC Source ───────────────────────────────────────────────────────────────

resource "google_scc_source" "this" {
  display_name = var.source_display_name
  organization = var.organization_id
  description  = var.source_description
}

# ─── SCC Notification Config ─────────────────────────────────────────────────

resource "google_scc_notification_config" "this" {
  count        = var.enable_notification_config ? 1 : 0
  config_id    = var.notification_config_id
  organization = var.organization_id
  description  = var.notification_description

  pubsub_topic = google_pubsub_topic.scc_notifications[0].id

  streaming_config {
    filter = var.notification_filter
  }
}

resource "google_pubsub_topic" "scc_notifications" {
  count = var.enable_notification_config ? 1 : 0
  name  = "${var.notification_config_id}-topic"
}

# ─── SCC Mute Rules ──────────────────────────────────────────────────────────

resource "google_scc_mute_config" "mute_rules" {
  for_each = var.mute_rules

  mute_config_id = each.key
  organization   = var.organization_id
  filter         = each.value.filter
  description    = each.value.description
}

# ─── SCC Custom Config (optional) ────────────────────────────────────────────

resource "google_scc_custom_config" "this" {
  count        = var.enable_custom_config ? 1 : 0
  organization = var.organization_id

  custom_config {
    display_name = var.custom_config_display_name
    description  = var.custom_config_description

    custom_output {
      properties {
        name = "severity"
        value_expression {
          expression = "severity"
        }
      }
    }
  }
}
