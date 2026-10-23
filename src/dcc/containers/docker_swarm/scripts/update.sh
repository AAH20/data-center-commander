#!/usr/bin/env bash
# DCC Docker Swarm Rolling Update Script
# Usage: ./update.sh [stack-name] [service-name] [new-image]

set -euo pipefail

STACK_NAME="${1:-dcc}"
SERVICE_NAME="${2:-app}"
NEW_IMAGE="${3:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo "=== DCC Docker Swarm Rolling Update ==="
echo "Stack: ${STACK_NAME}"
echo "Service: ${SERVICE_NAME}"
echo ""

# ── Pre-flight checks ───────────────────────────────────────────────────────
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    echo "ERROR: This node is not part of an active Docker Swarm"
    exit 1
fi

# Check if service exists
if ! docker service ls --format '{{.Name}}' | grep -q "^${STACK_NAME}_${SERVICE_NAME}$"; then
    echo "ERROR: Service '${STACK_NAME}_${SERVICE_NAME}' does not exist"
    exit 1
fi

# ── Build new image if needed ───────────────────────────────────────────────
if [ -z "${NEW_IMAGE}" ]; then
    echo "[1/4] Building new image..."
    cd "${PROJECT_ROOT}"
    docker build -t data-center-commander:latest .
    NEW_IMAGE="data-center-commander:latest"
    echo "  ✓ Image built: ${NEW_IMAGE}"
else
    echo "[1/4] Using specified image: ${NEW_IMAGE}"
fi
echo ""

# ── Get current service info ────────────────────────────────────────────────
echo "[2/4] Current service state:"
docker service inspect "${STACK_NAME}_${SERVICE_NAME}" \
    --format '  Image: {{.Spec.TaskTemplate.ContainerSpec.Image}}
  Replicas: {{.Spec.Mode.Replicated.Replicas}}
  UpdateConfig: {{.Spec.UpdateConfig}}
  RollbackConfig: {{.Spec.RollbackConfig}}'
echo ""

# ── Perform rolling update ──────────────────────────────────────────────────
echo "[3/4] Performing rolling update..."

UPDATE_ARGS=()
if [ -n "${NEW_IMAGE}" ]; then
    UPDATE_ARGS+=("--image" "${NEW_IMAGE}")
fi

# Add rollback config
UPDATE_ARGS+=(
    "--update-parallelism" "1"
    "--update-delay" "10s"
    "--update-failure-action" "rollback"
    "--update-monitor" "60s"
    "--update-max-failure-ratio" "0.3"
    "--update-order" "start-first"
    "--rollback-parallelism" "0"
    "--rollback-delay" "10s"
    "--rollback-failure-action" "pause"
    "--rollback-monitor" "60s"
    "--rollback-max-failure-ratio" "0.3"
)

docker service update "${UPDATE_ARGS[@]}" "${STACK_NAME}_${SERVICE_NAME}"

echo "  ✓ Rolling update initiated"
echo ""

# ── Monitor update progress ─────────────────────────────────────────────────
echo "[4/4] Monitoring update progress..."
echo ""

MAX_WAIT=300  # 5 minutes
WAITED=0
LAST_STATE=""

while [ $WAITED -lt $MAX_WAIT ]; do
    STATE=$(docker service ps "${STACK_NAME}_${SERVICE_NAME}" --format '{{.CurrentState}}' | head -1)
    
    if [ "$STATE" != "$LAST_STATE" ]; then
        echo "  [${WAITED}s] State: ${STATE}"
        LAST_STATE="$STATE"
    fi
    
    # Check if update is complete
    RUNNING_COUNT=$(docker service ps "${STACK_NAME}_${SERVICE_NAME}" --filter "desired-state=running" --format '{{.Name}}' | wc -l)
    DESIRED_REPLICAS=$(docker service inspect "${STACK_NAME}_${SERVICE_NAME}" --format '{{.Spec.Mode.Replicated.Replicas}}')
    
    if [ "$RUNNING_COUNT" -eq "$DESIRED_REPLICAS" ]; then
        # Check if all tasks are running (not just desired)
        TOTAL_RUNNING=$(docker service ps "${STACK_NAME}_${SERVICE_NAME}" --filter "desired-state=running" --filter "current-state=running" --format '{{.Name}}' | wc -l)
        if [ "$TOTAL_RUNNING" -eq "$DESIRED_REPLICAS" ]; then
            echo ""
            echo "  ✓ Rolling update complete! All ${DESIRED_REPLICAS} replicas running."
            break
        fi
    fi
    
    # Check for failed tasks
    FAILED_COUNT=$(docker service ps "${STACK_NAME}_${SERVICE_NAME}" --filter "desired-state=shutdown" --format '{{.Name}}' | wc -l)
    if [ "$FAILED_COUNT" -gt 0 ]; then
        echo ""
        echo "  WARNING: ${FAILED_COUNT} task(s) failed during update"
        docker service ps "${STACK_NAME}_${SERVICE_NAME}" --format "table {{.Name}}\t{{.CurrentState}}\t{{.Error}}"
        echo ""
        echo "  The update may have been rolled back. Check service status:"
        echo "    docker service inspect ${STACK_NAME}_${SERVICE_NAME}"
        exit 1
    fi
    
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo ""
    echo "  WARNING: Update did not complete within ${MAX_WAIT}s"
    echo "  Check status with: docker service ps ${STACK_NAME}_${SERVICE_NAME}"
    exit 1
fi

echo ""
echo "=== Rolling Update Complete ==="
echo ""
echo "Service status:"
docker service inspect "${STACK_NAME}_${SERVICE_NAME}" \
    --format '  Image: {{.Spec.TaskTemplate.ContainerSpec.Image}}
  Replicas: {{.Spec.Mode.Replicated.Replicas}}
  Running: {{.ServiceStatus.RunningTasks}}
  Desired: {{.ServiceStatus.DesiredTasks}}'
