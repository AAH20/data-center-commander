#!/usr/bin/env bash
# DCC Docker Swarm Configs Setup Script
# Creates all required configs for the DCC stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo "=== DCC Docker Swarm Configs Setup ==="
echo ""

# ── Helper function ─────────────────────────────────────────────────────────
create_config() {
    local name="$1"
    local file_path="$2"
    local description="$3"
    
    if docker config ls --format '{{.Name}}' | grep -q "^${name}$"; then
        echo "  ✓ Config '${name}' already exists"
        return 0
    fi
    
    if [ ! -f "${PROJECT_ROOT}/${file_path}" ]; then
        echo "  ✗ File not found: ${PROJECT_ROOT}/${file_path}"
        return 1
    fi
    
    echo "  Creating config: ${name}"
    echo "    Source: ${file_path}"
    echo "    ${description}"
    
    docker config create "${name}" "${PROJECT_ROOT}/${file_path}"
    echo "    ✓ Config '${name}' created"
}

# ── Create configs ──────────────────────────────────────────────────────────
echo "Creating database initialization configs..."
echo ""

create_config "db_init_schema" "database/schema.sql" "Database schema"
echo ""

create_config "db_init_migration_001" "database/migrations/001_cost_intelligence.sql" "Migration: cost intelligence"
echo ""

create_config "db_init_migration_002" "database/migrations/002_lifecycle_rollup_fix.sql" "Migration: lifecycle rollup fix"
echo ""

create_config "db_init_migration_003" "database/migrations/003_estimate_price_link_validation.sql" "Migration: estimate price link validation"
echo ""

create_config "db_init_migration_004" "database/migrations/004_placement_comparison_snapshots.sql" "Migration: placement comparison snapshots"
echo ""

echo "Creating application configs..."
echo ""

create_config "app_config" "src/dcc/containers/docker_swarm/configs/app.env" "Application environment"
echo ""

create_config "nginx_conf" "src/dcc/containers/docker_swarm/configs/nginx.conf" "Nginx main configuration"
echo ""

create_config "nginx_dcc_conf" "src/dcc/containers/docker_swarm/configs/dcc.conf" "Nginx DCC virtual host"
echo ""

create_config "otel_config" "src/dcc/containers/docker_swarm/configs/otel-collector.yaml" "OpenTelemetry Collector configuration"
echo ""

create_config "prometheus_config" "src/dcc/containers/docker_swarm/configs/prometheus.yml" "Prometheus configuration"
echo ""

create_config "grafana_datasources" "src/dcc/containers/docker_swarm/configs/grafana-datasources.yml" "Grafana datasources"
echo ""

create_config "grafana_dashboards" "src/dcc/containers/docker_swarm/configs/grafana-dashboards.yml" "Grafana dashboards"
echo ""

echo "=== Configs Setup Complete ==="
echo ""
echo "Configs created:"
docker config ls --format "table {{.Name}}\t{{.CreatedAt}}"
echo ""
echo "NOTE: Configs are stored encrypted in the Swarm Raft log."
echo "      They are mounted as files into containers at the specified target path."
