output "instance_name" {
  description = "Name of the Cloud SQL instance"
  value       = google_sql_database_instance.this.name
}

output "instance_connection_name" {
  description = "Connection name of the Cloud SQL instance"
  value       = google_sql_database_instance.this.connection_name
}

output "instance_self_link" {
  description = "Self link of the Cloud SQL instance"
  value       = google_sql_database_instance.this.self_link
}

output "instance_ip_address" {
  description = "IP address of the Cloud SQL instance"
  value       = google_sql_database_instance.this.ip_address
}

output "instance_private_ip_address" {
  description = "Private IP address of the Cloud SQL instance"
  value       = google_sql_database_instance.this.private_ip_address
}

output "kms_key_id" {
  description = "KMS key ID used for encryption"
  value       = var.kms_key_id
}

output "backup_enabled" {
  description = "Whether automated backups are enabled"
  value       = var.backup_enabled
}

output "backup_start_time" {
  description = "Start time for automated backups"
  value       = var.backup_start_time
}

output "point_in_time_recovery_enabled" {
  description = "Whether point-in-time recovery is enabled"
  value       = var.point_in_time_recovery_enabled
}

output "database_name" {
  description = "Name of the created database"
  value       = var.create_database ? google_sql_database.this[0].name : null
}

output "master_password" {
  description = "Master password (sensitive)"
  value       = var.password != null ? var.password : random_password.master_password[0].result
  sensitive   = true
}
