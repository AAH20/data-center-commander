#!/bin/bash
# =============================================================================
# Data Center Commander — SOC Stack Deployment Script
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    log_info "Prerequisites OK"
}

# Deploy SOC stack
deploy() {
    log_info "Deploying SOC + AutoScaling stack..."

    cd "${PROJECT_ROOT}"

    # Copy environment file if it doesn't exist
    if [ ! -f "docker/soc/.env" ]; then
        log_warn "No .env file found, using .env.example"
        cp docker/soc/.env.example docker/soc/.env
    fi

    # Build and start services
    docker compose -f docker/soc/docker-compose.yml --env-file docker/soc/.env up -d --build

    log_info "SOC stack deployed successfully"
    log_info "Grafana: http://localhost:3000"
    log_info "Prometheus: http://localhost:9090"
    log_info "Alertmanager: http://localhost:9093"
}

# Run security scan
scan() {
    log_info "Running security scan..."

    cd "${PROJECT_ROOT}"
    docker compose -f docker/soc/docker-compose.yml --env-file docker/soc/.env run --rm soc-scanner

    log_info "Security scan completed"
}

# View logs
logs() {
    cd "${PROJECT_ROOT}"
    docker compose -f docker/soc/docker-compose.yml --env-file docker/soc/.env logs -f
}

# Stop stack
stop() {
    log_info "Stopping SOC stack..."
    cd "${PROJECT_ROOT}"
    docker compose -f docker/soc/docker-compose.yml --env-file docker/soc/.env down
    log_info "SOC stack stopped"
}

# Main
case "${1:-deploy}" in
    deploy)
        check_prerequisites
        deploy
        ;;
    scan)
        check_prerequisites
        scan
        ;;
    logs)
        logs
        ;;
    stop)
        stop
        ;;
    *)
        echo "Usage: $0 {deploy|scan|logs|stop}"
        exit 1
        ;;
esac
