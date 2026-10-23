#!/usr/bin/env bash
# DCC Docker Swarm Health Check Script
# Usage: ./health-check.sh [stack-name]

set -euo pipefail

STACK_NAME="${1:-dcc}"

echo "=== DCC Docker Swarm Health Check ==="
echo "Stack: ${STACK_NAME}"
echo ""

# ── Pre-flight checks ───────────────────────────────────────────────────────
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    echo "ERROR: This node is not part of an active Docker Swarm"
    exit 1
fi

# ── Service status ──────────────────────────────────────────────────────────
echo "[1/5] Service Status:"
echo ""

docker stack services "${STACK_NAME}" --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}" 2>/dev/null || {
    echo "  WARNING: Stack '${STACK_NAME}' not found or no services"
    exit 1
}
echo ""

# ── Task status ─────────────────────────────────────────────────────────────
echo "[2/5] Task Status:"
echo ""

docker stack ps "${STACK_NAME}" --format "table {{.Name}}\t{{.CurrentState}}\t{{.Error}}" 2>/dev/null || echo "  No tasks found"
echo ""

# ── Service health checks ───────────────────────────────────────────────────
echo "[3/5] Service Health Checks:"
echo ""

SERVICES=("db" "app" "nginx" "otel-collector" "prometheus" "grafana")
ALL_HEALTHY=true

for service in "${SERVICES[@]}"; do
    FULL_NAME="${STACK_NAME}_${service}"
    
    if ! docker service ls --format '{{.Name}}' | grep -q "^${FULL_NAME}$"; then
        echo "  ⚠ ${service}: not deployed"
        continue
    fi
    
    # Check if service has healthcheck
    HAS_HEALTHCHECK=$(docker service inspect "${FULL_NAME}" --format '{{if .Spec.TaskTemplate.ContainerSpec.Healthcheck}}true{{else}}false{{end}}')
    
    if [ "$HAS_HEALTHCHECK" = "false" ]; then
        echo "  ⚠ ${service}: no healthcheck defined"
        continue
    fi
    
    # Get health status from tasks
    HEALTHY_TASKS=$(docker service ps "${FULL_NAME}" --filter "desired-state=running" --format '{{.Name}}' | while read -r task; do
        docker inspect "${task}" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' 2>/dev/null
    done | grep -c "healthy" || true)
    
    TOTAL_TASKS=$(docker service ps "${FULL_NAME}" --filter "desired-state=running" --format '{{.Name}}' | wc -l)
    
    if [ "$HEALTHY_TASKS" -eq "$TOTAL_TASKS" ] && [ "$TOTAL_TASKS" -gt 0 ]; then
        echo "  ✓ ${service}: ${HEALTHY_TASKS}/${TOTAL_TASKS} healthy"
    else
        echo "  ✗ ${service}: ${HEALTHY_TASKS}/${TOTAL_TASKS} healthy"
        ALL_HEALTHY=false
    fi
done
echo ""

# ── Endpoint checks ─────────────────────────────────────────────────────────
echo "[4/5] Endpoint Checks:"
echo ""

# Check API health
if curl -sf http://localhost:8790/healthz &>/dev/null; then
    echo "  ✓ API health endpoint: http://localhost:8790/healthz"
else
    echo "  ✗ API health endpoint: http://localhost:8790/healthz"
    ALL_HEALTHY=false
fi

# Check Nginx
if curl -sf http://localhost:80/healthz &>/dev/null; then
    echo "  ✓ Nginx proxy: http://localhost:80/healthz"
else
    echo "  ✗ Nginx proxy: http://localhost:80/healthz"
    ALL_HEALTHY=false
fi

# Check Prometheus
if curl -sf http://localhost:9090/-/healthy &>/dev/null; then
    echo "  ✓ Prometheus: http://localhost:9090/-/healthy"
else
    echo "  ⚠ Prometheus: not responding (optional)"
fi

# Check Grafana
if curl -sf http://localhost:3000/api/health &>/dev/null; then
    echo "  ✓ Grafana: http://localhost:3000/api/health"
else
    echo "  ⚠ Grafana: not responding (optional)"
fi
echo ""

# ── Resource usage ──────────────────────────────────────────────────────────
echo "[5/5] Resource Usage:"
echo ""

docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" 2>/dev/null | grep -E "dcc|NAME" || echo "  No container stats available"
echo ""

# ── Summary ─────────────────────────────────────────────────────────────────
echo "=== Health Check Summary ==="
if [ "$ALL_HEALTHY" = true ]; then
    echo "  ✓ All services are healthy"
    exit 0
else
    echo "  ✗ Some services are unhealthy"
    echo ""
    echo "Troubleshooting:"
    echo "  docker service logs ${STACK_NAME}_app"
    echo "  docker service ps ${STACK_NAME}_app --no-trunc"
    exit 1
fi
