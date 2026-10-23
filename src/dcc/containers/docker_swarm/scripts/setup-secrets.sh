#!/usr/bin/env bash
# DCC Docker Swarm Secrets Setup Script
# Creates all required secrets for the DCC stack

set -euo pipefail

echo "=== DCC Docker Swarm Secrets Setup ==="
echo ""

# ── Helper function ─────────────────────────────────────────────────────────
create_secret() {
    local name="$1"
    local description="$2"
    local default_value="${3:-}"
    
    if docker secret ls --format '{{.Name}}' | grep -q "^${name}$"; then
        echo "  ✓ Secret '${name}' already exists"
        return 0
    fi
    
    echo "  Creating secret: ${name}"
    echo "    ${description}"
    
    if [ -n "$default_value" ]; then
        read -s -p "    Enter value (default: ${default_value}): " value
        echo ""
        value="${value:-$default_value}"
    else
        read -s -p "    Enter value: " value
        echo ""
    fi
    
    if [ -z "$value" ]; then
        echo "    ERROR: Value cannot be empty"
        return 1
    fi
    
    echo "$value" | docker secret create "${name}" -
    echo "    ✓ Secret '${name}' created"
}

# ── Create secrets ──────────────────────────────────────────────────────────
echo "Creating required secrets..."
echo ""

create_secret "db_password" "PostgreSQL password for DCC user" "dcc_dev_password"
echo ""

create_secret "db_url" "Full PostgreSQL connection URL" "postgresql://dcc:dcc_dev_password@db:5432/data_center_commander"
echo ""

create_secret "grafana_admin_user" "Grafana admin username" "admin"
echo ""

create_secret "grafana_admin_password" "Grafana admin password" "admin"
echo ""

echo "=== Secrets Setup Complete ==="
echo ""
echo "Secrets created:"
docker secret ls --filter name=dcc --format "table {{.Name}}\t{{.CreatedAt}}"
echo ""
echo "NOTE: These secrets are stored encrypted in the Swarm Raft log."
echo "      They are only accessible to services that explicitly reference them."
