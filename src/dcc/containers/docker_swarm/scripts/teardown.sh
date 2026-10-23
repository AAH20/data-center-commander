#!/usr/bin/env bash
# DCC Docker Swarm Teardown Script
# Usage: ./teardown.sh [stack-name] [--remove-volumes] [--remove-secrets] [--remove-configs]

set -euo pipefail

STACK_NAME="${1:-dcc}"
REMOVE_VOLUMES=false
REMOVE_SECRETS=false
REMOVE_CONFIGS=false

# Parse flags
for arg in "$@"; do
    case "$arg" in
        --remove-volumes) REMOVE_VOLUMES=true ;;
        --remove-secrets) REMOVE_SECRETS=true ;;
        --remove-configs) REMOVE_CONFIGS=true ;;
    esac
done

echo "=== DCC Docker Swarm Teardown ==="
echo "Stack: ${STACK_NAME}"
echo "Remove volumes: ${REMOVE_VOLUMES}"
echo "Remove secrets: ${REMOVE_SECRETS}"
echo "Remove configs: ${REMOVE_CONFIGS}"
echo ""

# ── Pre-flight checks ───────────────────────────────────────────────────────
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    echo "ERROR: This node is not part of an active Docker Swarm"
    exit 1
fi

# ── Confirm teardown ────────────────────────────────────────────────────────
read -p "Are you sure you want to remove stack '${STACK_NAME}'? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Teardown cancelled"
    exit 0
fi

# ── Remove stack ────────────────────────────────────────────────────────────
echo "[1/4] Removing stack '${STACK_NAME}'..."

if docker stack ls --format '{{.Name}}' | grep -q "^${STACK_NAME}$"; then
    docker stack rm "${STACK_NAME}"
    echo "  ✓ Stack removed"
else
    echo "  ⚠ Stack '${STACK_NAME}' not found"
fi
echo ""

# ── Remove volumes ──────────────────────────────────────────────────────────
if [ "$REMOVE_VOLUMES" = true ]; then
    echo "[2/4] Removing volumes..."
    
    VOLUMES=("${STACK_NAME}_db_data" "${STACK_NAME}_prometheus_data" "${STACK_NAME}_grafana_data")
    
    for vol in "${VOLUMES[@]}"; do
        if docker volume ls --format '{{.Name}}' | grep -q "^${vol}$"; then
            docker volume rm "${vol}" 2>/dev/null && echo "  ✓ Removed volume: ${vol}" || echo "  ⚠ Could not remove volume: ${vol} (may be in use)"
        else
            echo "  ⚠ Volume not found: ${vol}"
        fi
    done
else
    echo "[2/4] Skipping volume removal (use --remove-volumes to remove)"
fi
echo ""

# ── Remove secrets ──────────────────────────────────────────────────────────
if [ "$REMOVE_SECRETS" = true ]; then
    echo "[3/4] Removing secrets..."
    
    SECRETS=("db_password" "db_url" "grafana_admin_user" "grafana_admin_password")
    
    for secret in "${SECRETS[@]}"; do
        if docker secret ls --format '{{.Name}}' | grep -q "^${secret}$"; then
            docker secret rm "${secret}" && echo "  ✓ Removed secret: ${secret}" || echo "  ⚠ Could not remove secret: ${secret}"
        else
            echo "  ⚠ Secret not found: ${secret}"
        fi
    done
else
    echo "[3/4] Skipping secret removal (use --remove-secrets to remove)"
fi
echo ""

# ── Remove configs ──────────────────────────────────────────────────────────
if [ "$REMOVE_CONFIGS" = true ]; then
    echo "[4/4] Removing configs..."
    
    CONFIGS=(
        "db_init_schema"
        "db_init_migration_001"
        "db_init_migration_002"
        "db_init_migration_003"
        "db_init_migration_004"
        "app_config"
        "nginx_conf"
        "nginx_dcc_conf"
        "otel_config"
        "prometheus_config"
        "grafana_datasources"
        "grafana_dashboards"
    )
    
    for config in "${CONFIGS[@]}"; do
        if docker config ls --format '{{.Name}}' | grep -q "^${config}$"; then
            docker config rm "${config}" && echo "  ✓ Removed config: ${config}" || echo "  ⚠ Could not remove config: ${config}"
        else
            echo "  ⚠ Config not found: ${config}"
        fi
    done
else
    echo "[4/4] Skipping config removal (use --remove-configs to remove)"
fi
echo ""

echo "=== Teardown Complete ==="
echo ""
echo "Remaining resources:"
echo "  Networks:"
docker network ls --filter name=dcc --format "    {{.Name}}" 2>/dev/null || echo "    None"
echo ""
echo "  Volumes:"
docker volume ls --filter name=dcc --format "    {{.Name}}" 2>/dev/null || echo "    None"
