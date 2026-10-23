#!/usr/bin/env bash
# DCC Docker Swarm Rollback Script
# Usage: ./rollback.sh [stack-name] [service-name]

set -euo pipefail

STACK_NAME="${1:-dcc}"
SERVICE_NAME="${2:-app}"

echo "=== DCC Docker Swarm Rollback ==="
echo "Stack: ${STACK_NAME}"
echo "Service: ${SERVICE_NAME}"
echo ""

# ── Pre-flight checks ───────────────────────────────────────────────────────
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    echo "ERROR: This node is not part of an active Docker Swarm"
    exit 1
fi

if ! docker service ls --format '{{.Name}}' | grep -q "^${STACK_NAME}_${SERVICE_NAME}$"; then
    echo "ERROR: Service '${STACK_NAME}_${SERVICE_NAME}' does not exist"
    exit 1
fi

# ── Show current state ──────────────────────────────────────────────────────
echo "Current service state:"
docker service inspect "${STACK_NAME}_${SERVICE_NAME}" \
    --format '  Image: {{.Spec.TaskTemplate.ContainerSpec.Image}}
  Replicas: {{.Spec.Mode.Replicated.Replicas}}
  PreviousImage: {{.PreviousSpec.TaskTemplate.ContainerSpec.Image}}'
echo ""

# ── Confirm rollback ────────────────────────────────────────────────────────
read -p "Are you sure you want to rollback? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled"
    exit 0
fi

# ── Perform rollback ────────────────────────────────────────────────────────
echo "Performing rollback..."

docker service update \
    --rollback \
    --rollback-parallelism 0 \
    --rollback-delay 10s \
    --rollback-failure-action pause \
    --rollback-monitor 60s \
    --rollback-max-failure-ratio 0.3 \
    "${STACK_NAME}_${SERVICE_NAME}"

echo "  ✓ Rollback initiated"
echo ""

# ── Monitor rollback progress ───────────────────────────────────────────────
echo "Monitoring rollback progress..."
echo ""

MAX_WAIT=300
WAITED=0
LAST_STATE=""

while [ $WAITED -lt $MAX_WAIT ]; do
    STATE=$(docker service ps "${STACK_NAME}_${SERVICE_NAME}" --format '{{.CurrentState}}' | head -1)
    
    if [ "$STATE" != "$LAST_STATE" ]; then
        echo "  [${WAITED}s] State: ${STATE}"
        LAST_STATE="$STATE"
    fi
    
    RUNNING_COUNT=$(docker service ps "${STACK_NAME}_${SERVICE_NAME}" --filter "desired-state=running" --filter "current-state=running" --format '{{.Name}}' | wc -l)
    DESIRED_REPLICAS=$(docker service inspect "${STACK_NAME}_${SERVICE_NAME}" --format '{{.Spec.Mode.Replicated.Replicas}}')
    
    if [ "$RUNNING_COUNT" -eq "$DESIRED_REPLICAS" ]; then
        echo ""
        echo "  ✓ Rollback complete! All ${DESIRED_REPLICAS} replicas running."
        break
    fi
    
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo ""
    echo "  WARNING: Rollback did not complete within ${MAX_WAIT}s"
    exit 1
fi

echo ""
echo "=== Rollback Complete ==="
docker service inspect "${STACK_NAME}_${SERVICE_NAME}" \
    --format '  Image: {{.Spec.TaskTemplate.ContainerSpec.Image}}
  Replicas: {{.Spec.Mode.Replicated.Replicas}}'
