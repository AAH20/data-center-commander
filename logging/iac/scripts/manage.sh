#!/bin/bash
# =============================================================================
# Data Center Commander — IaC Logging Stack
# =============================================================================
# Helper script to manage the IaC logging stack.
#
# Usage:
#   ./scripts/start.sh          Start all services
#   ./scripts/stop.sh           Stop all services
#   ./scripts/restart.sh        Restart all services
#   ./scripts/status.sh         Check service health
#   ./scripts/logs.sh           Tail logs from all services
#   ./scripts/test.sh           Send test logs
#   ./scripts/cleanup.sh        Remove all data and containers
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

start() {
    log_info "Starting IaC logging stack..."
    cd "$PROJECT_DIR"
    docker compose up -d
    log_ok "Services started"
    echo ""
    echo "Access points:"
    echo "  Kibana:    http://localhost:5601"
    echo "  Grafana:   http://localhost:3000 (admin/admin)"
    echo "  ES API:    http://localhost:9200"
    echo "  Loki API:  http://localhost:3100"
}

stop() {
    log_info "Stopping IaC logging stack..."
    cd "$PROJECT_DIR"
    docker compose stop
    log_ok "Services stopped"
}

restart() {
    log_info "Restarting IaC logging stack..."
    cd "$PROJECT_DIR"
    docker compose restart
    log_ok "Services restarted"
}

status() {
    log_info "Checking service health..."
    echo ""

    # Elasticsearch
    if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        health=$(curl -sf http://localhost:9200/_cluster/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
        log_ok "Elasticsearch: $health"
    else
        log_error "Elasticsearch: unreachable"
    fi

    # Kibana
    if curl -sf http://localhost:5601/api/status > /dev/null 2>&1; then
        log_ok "Kibana: running"
    else
        log_error "Kibana: unreachable"
    fi

    # Loki
    if curl -sf http://localhost:3100/ready > /dev/null 2>&1; then
        log_ok "Loki: ready"
    else
        log_error "Loki: not ready"
    fi

    # Grafana
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        log_ok "Grafana: running"
    else
        log_error "Grafana: unreachable"
    fi

    # Logstash
    if curl -sf http://localhost:9600 > /dev/null 2>&1; then
        log_ok "Logstash: running"
    else
        log_error "Logstash: unreachable"
    fi

    echo ""
    docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
}

logs() {
    log_info "Tailing logs (Ctrl+C to exit)..."
    cd "$PROJECT_DIR"
    docker compose logs -f --tail=100
}

test_logs() {
    log_info "Sending test logs..."

    # Test log to Filebeat (via TCP to Logstash)
    echo '{"message":"Test log from IaC stack","level":"INFO","service":"test","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' | nc -q1 localhost 5000

    # Test log to Fluentd
    echo '{"message":"Test log to Fluentd","level":"INFO","service":"test","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' | nc -u -w1 localhost 24224

    # Test log to Loki (via HTTP)
    curl -s -X POST http://localhost:3100/loki/api/v1/push \
        -H "Content-Type: application/json" \
        -d '{
            "streams": [{
                "stream": {"job": "test", "level": "info"},
                "values": [["'$(date +%s%N)'", "Test log to Loki via HTTP"]]
            }]
        }'

    log_ok "Test logs sent. Check Kibana and Grafana."
}

cleanup() {
    log_warn "This will remove all containers, volumes, and data!"
    read -p "Are you sure? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$PROJECT_DIR"
        docker compose down -v --remove-orphans
        log_ok "Cleanup complete"
    else
        log_info "Cancelled"
    fi
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    logs)    logs ;;
    test)    test_logs ;;
    cleanup) cleanup ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|test|cleanup}"
        exit 1
        ;;
esac
