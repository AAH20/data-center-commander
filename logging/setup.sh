#!/bin/bash
# Setup script for Data Center Commander centralized logging stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Data Center Commander Logging Stack Setup ==="

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not installed"
    exit 1
fi

# Create log directories
echo "Creating log directories..."
mkdir -p "$PROJECT_ROOT"/logs/{app,api,errors,audit}

# Copy environment file if it doesn't exist
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Creating .env file..."
    cat > "$SCRIPT_DIR/.env" << 'EOF'
DCC_ENV=development
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
DCC_LOG_LEVEL=INFO
DCC_STRUCTURED_LOGGING=true
DCC_LOG_DIR=logs
EOF
fi

# Pull images
echo "Pulling Docker images..."
cd "$SCRIPT_DIR"
if command -v docker-compose &> /dev/null; then
    docker-compose pull
else
    docker compose pull
fi

# Start the stack
echo "Starting logging stack..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "=== Service Status ==="
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi

echo ""
echo "=== Logging Stack Ready ==="
echo "  Grafana:    http://localhost:3000 (admin/admin)"
echo "  Loki:       http://localhost:3100"
echo "  Promtail:   http://localhost:9080/metrics"
echo ""
echo "  Log files:  $PROJECT_ROOT/logs/"
echo "  App logs:   $PROJECT_ROOT/logs/app/"
echo "  API logs:   $PROJECT_ROOT/logs/api/"
echo "  Error logs: $PROJECT_ROOT/logs/errors/"
echo "  Audit logs: $PROJECT_ROOT/logs/audit/"
echo ""
echo "To view logs in Grafana:"
echo "  1. Open http://localhost:3000"
echo "  2. Go to Explore > Loki"
echo "  3. Query: {job=\"dcc-application\"}"
echo ""
echo "To stop the stack:"
if command -v docker-compose &> /dev/null; then
    echo "  cd $SCRIPT_DIR && docker-compose down"
else
    echo "  cd $SCRIPT_DIR && docker compose down"
fi
