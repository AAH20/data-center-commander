#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Data Center Commander - IaC Monitoring Stack${NC}"
echo "=============================================="

# Check dependencies
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Parse command
COMMAND="${1:-up}"

case "$COMMAND" in
    up)
        echo -e "${GREEN}Starting monitoring stack...${NC}"
        if [ -f .env ]; then
            docker compose --env-file .env up -d
        else
            echo -e "${YELLOW}Warning: .env not found, using defaults${NC}"
            docker compose up -d
        fi
        echo ""
        echo "Services:"
        echo "  Prometheus:    http://localhost:9090"
        echo "  Grafana:       http://localhost:3000"
        echo "  Alertmanager:  http://localhost:9093"
        echo "  IaC Exporter:  http://localhost:9091/metrics"
        echo ""
        echo "Run './run.sh logs' to view logs"
        echo "Run './run.sh down' to stop"
        ;;
    down)
        echo -e "${YELLOW}Stopping monitoring stack...${NC}"
        docker compose down
        ;;
    restart)
        echo -e "${GREEN}Restarting monitoring stack...${NC}"
        docker compose restart
        ;;
    logs)
        docker compose logs -f
        ;;
    status)
        docker compose ps
        ;;
    clean)
        echo -e "${RED}Removing all data volumes...${NC}"
        docker compose down -v
        ;;
    *)
        echo "Usage: $0 {up|down|restart|logs|status|clean}"
        exit 1
        ;;
esac
