output "config_file_path" {
  description = "Path to the generated data center config"
  value       = local_file.dc_config.filename
}

output "capacity_plan_path" {
  description = "Path to the generated capacity plan"
  value       = local_file.capacity_plan.filename
}

output "alert_rules_path" {
  description = "Path to the generated alert rules"
  value       = var.prometheus_enabled ? local_file.alert_rules[0].filename : null
}

output "backup_script_path" {
  description = "Path to the generated backup script"
  value       = var.backup_enabled ? local_file.backup_script[0].filename : null
}

output "runbook_path" {
  description = "Path to the generated runbook"
  value       = local_file.runbook.filename
}

output "datacenter_name" {
  description = "Name of the data center"
  value       = var.datacenter_name
}

output "environment" {
  description = "Environment label"
  value       = var.environment
}

output "tier" {
  description = "Data center tier"
  value       = var.tier
}

output "total_capacity" {
  description = "Total capacity summary"
  value = {
    racks         = var.total_racks
    rack_units    = var.total_racks * var.rack_units
    power_kw      = var.total_power_kw
    cooling_tons  = var.total_cooling_tons
    network_gbps  = var.total_network_gbps
    floor_sqm     = var.usable_floor_sqm
  }
}

output "utilization" {
  description = "Current utilization percentages"
  value = {
    rack_units = var.total_racks * var.rack_units > 0 ? var.allocated_rack_units / (var.total_racks * var.rack_units) * 100 : 0
    power      = var.total_power_kw > 0 ? var.allocated_power_kw / var.total_power_kw * 100 : 0
    cooling    = var.total_cooling_tons > 0 ? var.allocated_cooling_tons / var.total_cooling_tons * 100 : 0
    network    = var.total_network_gbps > 0 ? var.allocated_network_gbps / var.total_network_gbps * 100 : 0
  }
}
