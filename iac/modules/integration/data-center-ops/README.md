# Data Center Operations Integration Module

Data center operations configuration and tooling for Data Center Commander.

## Overview

This module generates operational artifacts for data center management:

- **DC Configuration**: JSON config with capacity, thresholds, monitoring, backup, and security settings
- **Capacity Plan**: Computed capacity metrics and utilization percentages
- **Alert Rules**: Prometheus alerting rules for environmental and capacity thresholds
- **Backup Script**: Automated backup script with retention and optional offsite replication
- **Runbook**: Markdown operations runbook with contacts, thresholds, and endpoints

## Usage

```hcl
module "data_center_ops" {
  source = "../integration/data-center-ops"

  datacenter_name = "dc-us-east-1"
  environment      = "prod"
  location         = "Ashburn, VA"
  tier             = "III"

  total_racks        = 20
  total_power_kw     = 1000
  total_cooling_tons = 300
  total_network_gbps = 400

  allocated_rack_units  = 400
  allocated_power_kw    = 600
  allocated_cooling_tons = 180
  allocated_network_gbps = 200

  backup_enabled      = true
  offsite_replication = true
}
```

## Requirements

- Terraform >= 1.5.0
- `local` provider for file generation
- `null` provider for resource triggers

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| datacenter_name | Data center name | string | required |
| environment | Environment label | string | dev |
| location | Physical location | string | us-east-1 |
| tier | DC tier (I-IV) | string | III |
| config_output_path | Output path for configs | string | ./generated |
| total_racks | Total racks | number | 10 |
| rack_units | Units per rack | number | 42 |
| total_power_kw | Power capacity (kW) | number | 500 |
| total_cooling_tons | Cooling capacity | number | 150 |
| total_network_gbps | Network capacity | number | 100 |
| usable_floor_sqm | Floor area (sqm) | number | 500 |
| allocated_rack_units | Allocated rack units | number | 0 |
| allocated_power_kw | Allocated power | number | 0 |
| allocated_cooling_tons | Allocated cooling | number | 0 |
| allocated_network_gbps | Allocated network | number | 0 |
| pue_warning_threshold | PUE warning | number | 1.5 |
| pue_critical_threshold | PUE critical | number | 1.8 |
| temp_warning_c | Temp warning (°C) | number | 27 |
| temp_critical_c | Temp critical (°C) | number | 32 |
| humidity_warning_pct | Humidity warning | number | 60 |
| humidity_critical_pct | Humidity critical | number | 20 |
| prometheus_enabled | Enable Prometheus | bool | true |
| grafana_enabled | Enable Grafana | bool | true |
| alertmanager_enabled | Enable Alertmanager | bool | true |
| scrape_interval | Scrape interval | string | 15s |
| retention_days | Metrics retention | number | 15 |
| backup_enabled | Enable backups | bool | true |
| backup_schedule | Backup cron | string | 0 2 * * * |
| backup_retention_count | Backup copies | number | 7 |
| offsite_replication | Offsite replication | bool | false |
| tls_enabled | Enable TLS | bool | true |
| cert_manager_enabled | Enable cert-manager | bool | true |
| network_policies_enabled | Enable netpol | bool | true |
| audit_logging_enabled | Enable audit logs | bool | true |
| facilities_contact | Facilities contact | string | facilities@datacenter.local |
| noc_contact | NOC contact | string | noc@datacenter.local |
| security_contact | Security contact | string | security@datacenter.local |
| tags | Resource tags | map | {} |

## Outputs

| Name | Description |
|------|-------------|
| config_file_path | DC config file path |
| capacity_plan_path | Capacity plan file path |
| alert_rules_path | Alert rules file path |
| backup_script_path | Backup script file path |
| runbook_path | Runbook file path |
| datacenter_name | DC name |
| environment | Environment |
| tier | DC tier |
| total_capacity | Capacity summary map |
| utilization | Utilization percentages map |
