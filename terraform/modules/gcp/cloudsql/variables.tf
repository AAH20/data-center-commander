variable "name" {
  description = "Name of the Cloud SQL instance"
  type        = string
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the Cloud SQL instance"
  type        = string
  default     = "us-central1"
}

variable "database_version" {
  description = "Database engine version (e.g., POSTGRES_15, MYSQL_8_0)"
  type        = string
  default     = "POSTGRES_15"
}

variable "tier" {
  description = "Machine tier for the Cloud SQL instance"
  type        = string
  default     = "db-f1-micro"
}

variable "availability_type" {
  description = "Availability type (REGIONAL or ZONAL)"
  type        = string
  default     = "REGIONAL"
}

variable "disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 10
}

variable "disk_type" {
  description = "Disk type (PD_SSD or PD_HDD)"
  type        = string
  default     = "PD_SSD"
}

# Encryption configuration
variable "kms_key_id" {
  description = "KMS key ID for Cloud SQL encryption (CMEK). If null, Google-managed encryption is used."
  type        = string
  default     = null
}

# Backup configuration
variable "backup_enabled" {
  description = "Enable automated backups"
  type        = bool
  default     = true
}

variable "backup_start_time" {
  description = "Start time for automated backups (HH:MM format)"
  type        = string
  default     = "03:00"
}

variable "backup_location" {
  description = "Location for automated backups"
  type        = string
  default     = "us"
}

variable "point_in_time_recovery_enabled" {
  description = "Enable point-in-time recovery"
  type        = bool
  default     = true
}

variable "transaction_log_retention_days" {
  description = "Transaction log retention in days"
  type        = number
  default     = 7
}

variable "retained_backups" {
  description = "Number of automated backups to retain"
  type        = number
  default     = 7
}

# Maintenance configuration
variable "maintenance_day" {
  description = "Day of maintenance window (1-7, Monday=1)"
  type        = number
  default     = 7
}

variable "maintenance_hour" {
  description = "Hour of maintenance window (0-23)"
  type        = number
  default     = 4
}

variable "maintenance_update_track" {
  description = "Update track (stable or canary)"
  type        = string
  default     = "stable"
}

# Network configuration
variable "publicly_accessible" {
  description = "Make instance publicly accessible"
  type        = bool
  default     = false
}

variable "private_network" {
  description = "VPC network for private IP"
  type        = string
  default     = null
}

variable "require_ssl" {
  description = "Require SSL connections"
  type        = bool
  default     = true
}

variable "authorized_networks" {
  description = "List of authorized networks for public access"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

# Database configuration
variable "create_database" {
  description = "Create a database within the instance"
  type        = bool
  default     = true
}

variable "database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "datacenter"
}

variable "database_charset" {
  description = "Database charset"
  type        = string
  default     = "UTF8"
}

variable "database_collation" {
  description = "Database collation"
  type        = string
  default     = "en_US.UTF8"
}

# Credentials
variable "password" {
  description = "Master password (auto-generated if null)"
  type        = string
  default     = null
  sensitive   = true
}

# Database flags
variable "database_flags" {
  description = "Map of database flags"
  type        = map(string)
  default     = {}
}

# Labels
variable "labels" {
  description = "User labels for the instance"
  type        = map(string)
  default     = {}
}

# Protection
variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = true
}

variable "prevent_destroy" {
  description = "Prevent Terraform from destroying the instance"
  type        = bool
  default     = false
}
