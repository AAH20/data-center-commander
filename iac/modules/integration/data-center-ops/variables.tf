variable "datacenter_name" {
  description = "Name of the data center"
  type        = string
}

variable "environment" {
  description = "Environment label"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "location" {
  description = "Physical location of the data center"
  type        = string
  default     = "us-east-1"
}

variable "tier" {
  description = "Data center tier (I, II, III, IV)"
  type        = string
  default     = "III"

  validation {
    condition     = contains(["I", "II", "III", "IV"], var.tier)
    error_message = "Tier must be I, II, III, or IV."
  }
}

variable "config_output_path" {
  description = "Local path to write generated config files"
  type        = string
  default     = "./generated"
}

# ─── Capacity ────────────────────────────────────────────────────────────────

variable "total_racks" {
  description = "Total number of racks"
  type        = number
  default     = 10
}

variable "rack_units" {
  description = "Rack units per rack"
  type        = number
  default     = 42
}

variable "total_power_kw" {
  description = "Total power capacity in kW"
  type        = number
  default     = 500
}

variable "total_cooling_tons" {
  description = "Total cooling capacity in tons"
  type        = number
  default     = 150
}

variable "total_network_gbps" {
  description = "Total network capacity in Gbps"
  type        = number
  default     = 100
}

variable "usable_floor_sqm" {
  description = "Usable floor area in square meters"
  type        = number
  default     = 500
}

variable "allocated_rack_units" {
  description = "Currently allocated rack units"
  type        = number
  default     = 0
}

variable "allocated_power_kw" {
  description = "Currently allocated power in kW"
  type        = number
  default     = 0
}

variable "allocated_cooling_tons" {
  description = "Currently allocated cooling in tons"
  type        = number
  default     = 0
}

variable "allocated_network_gbps" {
  description = "Currently allocated network in Gbps"
  type        = number
  default     = 0
}

# ─── Thresholds ──────────────────────────────────────────────────────────────

variable "pue_warning_threshold" {
  description = "PUE warning threshold"
  type        = number
  default     = 1.5
}

variable "pue_critical_threshold" {
  description = "PUE critical threshold"
  type        = number
  default     = 1.8
}

variable "temp_warning_c" {
  description = "Temperature warning threshold in Celsius"
  type        = number
  default     = 27
}

variable "temp_critical_c" {
  description = "Temperature critical threshold in Celsius"
  type        = number
  default     = 32
}

variable "humidity_warning_pct" {
  description = "Humidity warning threshold in percent"
  type        = number
  default     = 60
}

variable "humidity_critical_pct" {
  description = "Humidity critical threshold in percent"
  type        = number
  default     = 20
}

# ─── Monitoring ──────────────────────────────────────────────────────────────

variable "prometheus_enabled" {
  description = "Enable Prometheus"
  type        = bool
  default     = true
}

variable "grafana_enabled" {
  description = "Enable Grafana"
  type        = bool
  default     = true
}

variable "alertmanager_enabled" {
  description = "Enable Alertmanager"
  type        = bool
  default     = true
}

variable "scrape_interval" {
  description = "Prometheus scrape interval"
  type        = string
  default     = "15s"
}

variable "retention_days" {
  description = "Metrics retention in days"
  type        = number
  default     = 15
}

# ─── Backup ──────────────────────────────────────────────────────────────────

variable "backup_enabled" {
  description = "Enable automated backups"
  type        = bool
  default     = true
}

variable "backup_schedule" {
  description = "Backup cron schedule"
  type        = string
  default     = "0 2 * * *"
}

variable "backup_retention_count" {
  description = "Number of backup copies to retain"
  type        = number
  default     = 7
}

variable "offsite_replication" {
  description = "Enable offsite backup replication"
  type        = bool
  default     = false
}

# ─── Security ────────────────────────────────────────────────────────────────

variable "tls_enabled" {
  description = "Enable TLS"
  type        = bool
  default     = true
}

variable "cert_manager_enabled" {
  description = "Enable cert-manager"
  type        = bool
  default     = true
}

variable "network_policies_enabled" {
  description = "Enable Kubernetes network policies"
  type        = bool
  default     = true
}

variable "audit_logging_enabled" {
  description = "Enable audit logging"
  type        = bool
  default     = true
}

# ─── Contacts ────────────────────────────────────────────────────────────────

variable "facilities_contact" {
  description = "Facilities team contact"
  type        = string
  default     = "facilities@datacenter.local"
}

variable "noc_contact" {
  description = "NOC contact"
  type        = string
  default     = "noc@datacenter.local"
}

variable "security_contact" {
  description = "Security team contact"
  type        = string
  default     = "security@datacenter.local"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
