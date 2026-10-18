terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Generate a random password if none is provided
resource "random_password" "master_password" {
  count   = var.password == null ? 1 : 0
  length  = 32
  special = true
}

# Cloud SQL instance with encryption and backup configuration
resource "google_sql_database_instance" "this" {
  name             = var.name
  database_version = var.database_version
  region           = var.region
  project          = var.project_id

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    disk_size         = var.disk_size
    disk_type         = var.disk_type

    # Encryption configuration (CMEK)
    disk_encryption_configuration {
      kms_key_name = var.kms_key_id
    }

    # Backup configuration
    backup_configuration {
      enabled                        = var.backup_enabled
      start_time                     = var.backup_start_time
      location                       = var.backup_location
      point_in_time_recovery_enabled = var.point_in_time_recovery_enabled
      transaction_log_retention_days = var.transaction_log_retention_days

      backup_retention_settings {
        retained_backups = var.retained_backups
        retention_unit   = "COUNT"
      }
    }

    # Maintenance configuration
    maintenance_window {
      day          = var.maintenance_day
      hour         = var.maintenance_hour
      update_track = var.maintenance_update_track
    }

    # IP configuration
    ip_configuration {
      ipv4_enabled    = var.publicly_accessible
      private_network = var.private_network
      require_ssl     = var.require_ssl

      dynamic "authorized_networks" {
        for_each = var.authorized_networks
        content {
          name  = authorized_networks.value.name
          value = authorized_networks.value.value
        }
      }
    }

    # Database flags
    dynamic "database_flags" {
      for_each = var.database_flags
      content {
        name  = database_flags.key
        value = database_flags.value
      }
    }

    # User labels
    user_labels = var.labels
  }

  deletion_protection = var.deletion_protection

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

# Create a database within the instance
resource "google_sql_database" "this" {
  count     = var.create_database ? 1 : 0
  name      = var.database_name
  instance  = google_sql_database_instance.this.name
  project   = var.project_id
  charset   = var.database_charset
  collation = var.database_collation
}
