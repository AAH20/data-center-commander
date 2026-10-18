terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

# ─── Data Center Configuration ───────────────────────────────────────────────

resource "local_file" "dc_config" {
  filename = "${var.config_output_path}/${var.datacenter_name}-config.json"
  content = jsonencode({
    datacenter = {
      name        = var.datacenter_name
      environment = var.environment
      location    = var.location
      tier        = var.tier
    }
    capacity = {
      total_racks        = var.total_racks
      total_power_kw     = var.total_power_kw
      total_cooling_tons = var.total_cooling_tons
      total_network_gbps = var.total_network_gbps
      usable_floor_sqm   = var.usable_floor_sqm
    }
    thresholds = {
      pue_warning           = var.pue_warning_threshold
      pue_critical          = var.pue_critical_threshold
      temp_warning_c        = var.temp_warning_c
      temp_critical_c       = var.temp_critical_c
      humidity_warning_pct  = var.humidity_warning_pct
      humidity_critical_pct = var.humidity_critical_pct
    }
    monitoring = {
      prometheus_enabled   = var.prometheus_enabled
      grafana_enabled      = var.grafana_enabled
      alertmanager_enabled = var.alertmanager_enabled
      scrape_interval      = var.scrape_interval
      retention_days       = var.retention_days
    }
    backup = {
      enabled             = var.backup_enabled
      schedule            = var.backup_schedule
      retention_count     = var.backup_retention_count
      offsite_replication = var.offsite_replication
    }
    security = {
      tls_enabled          = var.tls_enabled
      cert_manager_enabled = var.cert_manager_enabled
      network_policies     = var.network_policies_enabled
      audit_logging        = var.audit_logging_enabled
    }
    tags = var.tags
  })
}

# ─── Capacity Planning ───────────────────────────────────────────────────────

resource "local_file" "capacity_plan" {
  filename = "${var.config_output_path}/${var.datacenter_name}-capacity.json"
  content = jsonencode({
    datacenter = var.datacenter_name
    computed = {
      max_rack_units        = var.total_racks * var.rack_units
      power_per_rack_kw     = var.total_power_kw / var.total_racks
      cooling_per_rack_tons = var.total_cooling_tons / var.total_racks
      network_per_rack_gbps = var.total_network_gbps / var.total_racks
      floor_per_rack_sqm    = var.usable_floor_sqm / var.total_racks
    }
    headroom = {
      rack_units_available  = var.total_racks * var.rack_units - var.allocated_rack_units
      power_headroom_kw     = var.total_power_kw - var.allocated_power_kw
      cooling_headroom_tons = var.total_cooling_tons - var.allocated_cooling_tons
      network_headroom_gbps = var.total_network_gbps - var.allocated_network_gbps
    }
    utilization = {
      rack_unit_utilization = var.allocated_rack_units / (var.total_racks * var.rack_units) * 100
      power_utilization     = var.allocated_power_kw / var.total_power_kw * 100
      cooling_utilization   = var.allocated_cooling_tons / var.total_cooling_tons * 100
      network_utilization   = var.allocated_network_gbps / var.total_network_gbps * 100
    }
  })
}

# ─── Alert Rules ─────────────────────────────────────────────────────────────

resource "local_file" "alert_rules" {
  count = var.prometheus_enabled ? 1 : 0

  filename = "${var.config_output_path}/${var.datacenter_name}-alerts.yml"
  content = yamlencode({
    groups = [
      {
        name = "datacenter.environment"
        rules = [
          {
            alert = "HighPUE"
            expr  = "datacenter_pue > ${var.pue_warning_threshold}"
            for   = "5m"
            labels = {
              severity = "warning"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "PUE above warning threshold"
              description = "PUE is {{ $value }} (threshold: ${var.pue_warning_threshold})"
            }
          },
          {
            alert = "CriticalPUE"
            expr  = "datacenter_pue > ${var.pue_critical_threshold}"
            for   = "5m"
            labels = {
              severity = "critical"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "PUE above critical threshold"
              description = "PUE is {{ $value }} (threshold: ${var.pue_critical_threshold})"
            }
          },
          {
            alert = "HighTemperature"
            expr  = "datacenter_temperature_c > ${var.temp_warning_c}"
            for   = "2m"
            labels = {
              severity = "warning"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Temperature above warning threshold"
              description = "Temperature is {{ $value }}°C (threshold: ${var.temp_warning_c}°C)"
            }
          },
          {
            alert = "CriticalTemperature"
            expr  = "datacenter_temperature_c > ${var.temp_critical_c}"
            for   = "1m"
            labels = {
              severity = "critical"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Temperature above critical threshold"
              description = "Temperature is {{ $value }}°C (threshold: ${var.temp_critical_c}°C)"
            }
          },
          {
            alert = "HighHumidity"
            expr  = "datacenter_humidity_pct > ${var.humidity_warning_pct}"
            for   = "5m"
            labels = {
              severity = "warning"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Humidity above warning threshold"
              description = "Humidity is {{ $value }}% (threshold: ${var.humidity_warning_pct}%)"
            }
          },
          {
            alert = "LowHumidity"
            expr  = "datacenter_humidity_pct < ${var.humidity_critical_pct}"
            for   = "5m"
            labels = {
              severity = "critical"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Humidity below critical threshold"
              description = "Humidity is {{ $value }}% (threshold: ${var.humidity_critical_pct}%)"
            }
          }
        ]
      },
      {
        name = "datacenter.capacity"
        rules = [
          {
            alert = "RackCapacityWarning"
            expr  = "datacenter_rack_utilization > 80"
            for   = "10m"
            labels = {
              severity = "warning"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Rack utilization above 80%"
              description = "Rack utilization is {{ $value }}%"
            }
          },
          {
            alert = "PowerCapacityWarning"
            expr  = "datacenter_power_utilization > 85"
            for   = "5m"
            labels = {
              severity = "warning"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Power utilization above 85%"
              description = "Power utilization is {{ $value }}%"
            }
          },
          {
            alert = "CoolingCapacityWarning"
            expr  = "datacenter_cooling_utilization > 90"
            for   = "5m"
            labels = {
              severity = "warning"
              dc       = var.datacenter_name
            }
            annotations = {
              summary     = "Cooling utilization above 90%"
              description = "Cooling utilization is {{ $value }}%"
            }
          }
        ]
      }
    ]
  })
}

# ─── Backup Scripts ──────────────────────────────────────────────────────────

resource "local_file" "backup_script" {
  count = var.backup_enabled ? 1 : 0

  filename = "${var.config_output_path}/${var.datacenter_name}-backup.sh"
  content  = <<-EOT
    #!/usr/bin/env bash
    # Data Center Commander - Backup Script
    # Datacenter: ${var.datacenter_name}
    # Schedule: ${var.backup_schedule}
    # Retention: ${var.backup_retention_count} copies

    set -euo pipefail

    BACKUP_DIR="/var/backups/datacenter-commander"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$${BACKUP_DIR}/$${TIMESTAMP}"
    RETENTION=${var.backup_retention_count}

    mkdir -p "$${BACKUP_PATH}"

    # Database backup
    echo "Backing up database..."
    pg_dump "$${DATABASE_URL:-postgresql://localhost/datacenter}" \
      > "$${BACKUP_PATH}/database.sql"

    # Configuration backup
    echo "Backing up configuration..."
    tar czf "$${BACKUP_PATH}/config.tar.gz" \
      -C "${var.config_output_path}" .

    # Secrets backup (encrypted)
    echo "Backing up secrets..."
    tar czf - -C /etc/datacenter-commander . \
      | gpg --symmetric --cipher-algo AES256 \
      > "$${BACKUP_PATH}/secrets.tar.gz.gpg"

    # Cleanup old backups
    echo "Cleaning up old backups..."
    ls -1t "$${BACKUP_DIR}" | tail -n +$((RETENTION + 1)) | while read -r old; do
      rm -rf "$${BACKUP_DIR}/$${old}"
    done

    # Offsite replication
    ${var.offsite_replication ? "echo \"Replicating to offsite...\"\n    rclone sync \"$${BACKUP_PATH}\" remote:${var.datacenter_name}-backups/" : "# Offsite replication disabled"}

    echo "Backup complete: $${BACKUP_PATH}"
  EOT

  file_permission = "0755"
}

# ─── Runbook Documents ───────────────────────────────────────────────────────

resource "local_file" "runbook" {
  filename = "${var.config_output_path}/${var.datacenter_name}-runbook.md"
  content  = <<-EOT
    # ${var.datacenter_name} — Operations Runbook

    ## Datacenter Profile

    | Property | Value |
    |----------|-------|
    | Name | ${var.datacenter_name} |
    | Environment | ${var.environment} |
    | Location | ${var.location} |
    | Tier | ${var.tier} |
    | Total Racks | ${var.total_racks} |
    | Total Power | ${var.total_power_kw} kW |
    | Total Cooling | ${var.total_cooling_tons} tons |
    | Total Network | ${var.total_network_gbps} Gbps |

    ## Thresholds

    | Metric | Warning | Critical |
    |--------|---------|----------|
    | PUE | ${var.pue_warning_threshold} | ${var.pue_critical_threshold} |
    | Temperature | ${var.temp_warning_c}°C | ${var.temp_critical_c}°C |
    | Humidity | ${var.humidity_warning_pct}% | ${var.humidity_critical_pct}% |

    ## Emergency Contacts

    - Facilities: ${var.facilities_contact}
    - Network Operations: ${var.noc_contact}
    - Security: ${var.security_contact}

    ## Backup Schedule

    - Schedule: ${var.backup_schedule}
    - Retention: ${var.backup_retention_count} copies
    - Offsite Replication: ${var.offsite_replication ? "Enabled" : "Disabled"}

    ## Monitoring Endpoints

    - Prometheus: ${var.prometheus_enabled ? "http://prometheus:9090" : "Disabled"}
    - Grafana: ${var.grafana_enabled ? "http://grafana:3000" : "Disabled"}
    - Alertmanager: ${var.alertmanager_enabled ? "http://alertmanager:9093" : "Disabled"}
  EOT
}
