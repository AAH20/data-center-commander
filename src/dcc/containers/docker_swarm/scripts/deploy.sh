#!/usr/bin/env bash
# DCC Docker Swarm Stack Deployment Script
# Usage: ./deploy.sh [stack-name] [compose-file]

set -euo pipefail

STACK_NAME="${1:-dcc}"
COMPOSE_FILE="${2:-src/dcc/containers/docker_swarm/stack.yml}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo "=== DCC Docker Swarm Deployment ==="
echo "Stack: ${STACK_NAME}"
echo "Compose: ${COMPOSE_FILE}"
echo ""

# ── Pre-flight checks ───────────────────────────────────────────────────────
echo "[1/6] Running pre-flight checks..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running or user lacks permissions"
    exit 1
fi

if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    echo "ERROR: This node is not part of a Docker Swarm"
    echo "       Run 'docker swarm init' on the manager node first"
    exit 1
fi

if [ ! -f "${PROJECT_ROOT}/${COMPOSE_FILE}" ]; then
    echo "ERROR: Compose file not found: ${PROJECT_ROOT}/${COMPOSE_FILE}"
    exit 1
fi

echo "  ✓ Docker is available and node is in active swarm"
echo ""

# ── Create networks if they don't exist ─────────────────────────────────────
echo "[2/6] Ensuring overlay networks exist..."

if ! docker network ls --format '{{.Name}}' | grep -q "^dcc_backend$"; then
    echo "  Creating dcc_backend network..."
    docker network create --driver overlay --opt encrypted --subnet 10.0.1.0/24 dcc_backend
else
    echo "  ✓ dcc_backend network exists"
fi

if ! docker network ls --format '{{.Name}}' | grep -q "^dcc_frontend$"; then
    echo "  Creating dcc_frontend network..."
    docker network create --driver overlay --opt encrypted --subnet 10.0.2.0/24 dcc_frontend
else
    echo "  ✓ dcc_frontend network exists"
fi
echo ""

# ── Validate secrets exist ──────────────────────────────────────────────────
echo "[3/6] Validating secrets..."

REQUIRED_SECRETS=("db_password" "db_url" "grafana_admin_user" "grafana_admin_password")
MISSING_SECRETS=()

for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! docker secret ls --format '{{.Name}}' | grep -q "^${secret}$"; then
        MISSING_SECRETS+=("${secret}")
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo "  WARNING: Missing secrets: ${MISSING_SECRETS[*]}"
    echo "  Create them with:"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "    echo \"your-value\" | docker secret create ${secret} -"
    done
    echo ""
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "  ✓ All required secrets exist"
fi
echo ""

# ── Validate configs exist ──────────────────────────────────────────────────
echo "[4/6] Validating configs..."

REQUIRED_CONFIGS=(
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
MISSING_CONFIGS=()

for config in "${REQUIRED_CONFIGS[@]}"; do
    if ! docker config ls --format '{{.Name}}' | grep -q "^${config}$"; then
        MISSING_CONFIGS+=("${config}")
    fi
done

if [ ${#MISSING_CONFIGS[@]} -gt 0 ]; then
    echo "  WARNING: Missing configs: ${MISSING_CONFIGS[*]}"
    echo "  Create them with:"
    echo "    ./scripts/setup-configs.sh"
    echo ""
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "  ✓ All required configs exist"
fi
echo ""

# ── Deploy stack ────────────────────────────────────────────────────────────
echo "[5/6] Deploying stack '${STACK_NAME}'..."

cd "${PROJECT_ROOT}"
docker stack deploy -c "${COMPOSE_FILE}" "${STACK_NAME}" --with-registry-auth

echo "  ✓ Stack deployed"
echo ""

# ── Verify deployment ───────────────────────────────────────────────────────
echo "[6/6] Verifying deployment..."
echo ""

sleep 5

echo "Services:"
docker stack services "${STACK_NAME}" --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}"
echo ""

echo "Tasks:"
docker stack ps "${STACK_NAME}" --format "table {{.Name}}\t{{.CurrentState}}\t{{.Error}}"
echo ""

echo "=== Deployment Complete ==="
echo ""
echo "Useful commands:"
echo "  docker stack services ${STACK_NAME}"
echo "  docker service logs -f ${STACK_NAME}_app"
echo "  docker service scale ${STACK_NAME}_app=4"
echo "  ./scripts/health-check.sh ${STACK_NAME}"
echo "  ./scripts/rollback.sh ${STACK_NAME}"
