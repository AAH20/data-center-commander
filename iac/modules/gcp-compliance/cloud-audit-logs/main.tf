terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ─── Audit Log Config ─────────────────────────────────────────────────────────

resource "google_project_iam_audit_config" "project" {
  count   = var.target_type == "project" ? 1 : 0
  project = var.target_id
  service = "allServices"

  audit_log_config {
    log_type         = "ADMIN_READ"
    exempted_members = var.exempted_members
  }

  audit_log_config {
    log_type         = "DATA_READ"
    exempted_members = var.exempted_members
  }

  audit_log_config {
    log_type         = "DATA_WRITE"
    exempted_members = var.exempted_members
  }
}

resource "google_folder_iam_audit_config" "folder" {
  count   = var.target_type == "folder" ? 1 : 0
  folder  = var.target_id
  service = "allServices"

  audit_log_config {
    log_type         = "ADMIN_READ"
    exempted_members = var.exempted_members
  }

  audit_log_config {
    log_type         = "DATA_READ"
    exempted_members = var.exempted_members
  }

  audit_log_config {
    log_type         = "DATA_WRITE"
    exempted_members = var.exempted_members
  }
}

resource "google_organization_iam_audit_config" "organization" {
  count   = var.target_type == "organization" ? 1 : 0
  org_id  = var.target_id
  service = "allServices"

  audit_log_config {
    log_type         = "ADMIN_READ"
    exempted_members = var.exempted_members
  }

  audit_log_config {
    log_type         = "DATA_READ"
    exempted_members = var.exempted_members
  }

  audit_log_config {
    log_type         = "DATA_WRITE"
    exempted_members = var.exempted_members
  }
}

# ─── Log Sink ─────────────────────────────────────────────────────────────────

resource "google_logging_project_sink" "project_sink" {
  count                  = var.target_type == "project" && var.enable_log_sink ? 1 : 0
  name                   = var.sink_name
  destination            = var.sink_destination
  filter                 = var.sink_filter
  project                = var.target_id
  unique_writer_identity = true

  dynamic "exclusions" {
    for_each = var.sink_exclusions
    content {
      name        = exclusions.value.name
      description = exclusions.value.description
      filter      = exclusions.value.filter
      disabled    = exclusions.value.disabled
    }
  }
}

resource "google_logging_folder_sink" "folder_sink" {
  count                  = var.target_type == "folder" && var.enable_log_sink ? 1 : 0
  name                   = var.sink_name
  destination            = var.sink_destination
  filter                 = var.sink_filter
  folder                 = var.target_id
  include_children       = var.sink_include_children
  unique_writer_identity = true

  dynamic "exclusions" {
    for_each = var.sink_exclusions
    content {
      name        = exclusions.value.name
      description = exclusions.value.description
      filter      = exclusions.value.filter
      disabled    = exclusions.value.disabled
    }
  }
}

resource "google_logging_organization_sink" "org_sink" {
  count                  = var.target_type == "organization" && var.enable_log_sink ? 1 : 0
  name                   = var.sink_name
  destination            = var.sink_destination
  filter                 = var.sink_filter
  org_id                 = var.target_id
  include_children       = var.sink_include_children
  unique_writer_identity = true

  dynamic "exclusions" {
    for_each = var.sink_exclusions
    content {
      name        = exclusions.value.name
      description = exclusions.value.description
      filter      = exclusions.value.filter
      disabled    = exclusions.value.disabled
    }
  }
}

# ─── Log Bucket (optional) ────────────────────────────────────────────────────

resource "google_logging_project_bucket_config" "bucket" {
  count          = var.target_type == "project" && var.enable_log_bucket ? 1 : 0
  project        = var.target_id
  location       = var.log_bucket_location
  bucket_id      = var.log_bucket_id
  description    = var.log_bucket_description
  retention_days = var.log_bucket_retention_days
}

resource "google_logging_folder_bucket_config" "folder_bucket" {
  count          = var.target_type == "folder" && var.enable_log_bucket ? 1 : 0
  folder         = var.target_id
  location       = var.log_bucket_location
  bucket_id      = var.log_bucket_id
  description    = var.log_bucket_description
  retention_days = var.log_bucket_retention_days
}

resource "google_logging_organization_bucket_config" "org_bucket" {
  count          = var.target_type == "organization" && var.enable_log_bucket ? 1 : 0
  org_id         = var.target_id
  location       = var.log_bucket_location
  bucket_id      = var.log_bucket_id
  description    = var.log_bucket_description
  retention_days = var.log_bucket_retention_days
}

# ─── Log View (optional) ──────────────────────────────────────────────────────

resource "google_logging_log_view" "view" {
  for_each = var.log_views

  name        = each.key
  bucket      = each.value.bucket
  description = each.value.description
  filter      = each.value.filter
  location    = var.log_bucket_location
  project     = var.target_type == "project" ? var.target_id : null
}
