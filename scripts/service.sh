#!/bin/bash
# Service management script
# Usage: ./service.sh [command]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

start() {
    log_info "Starting services..."
    docker compose -f "$COMPOSE_FILE" up -d
    log_info "Services started"
    docker compose -f "$COMPOSE_FILE" ps
}

stop() {
    log_info "Stopping services..."
    docker compose -f "$COMPOSE_FILE" down
    log_info "Services stopped"
}

restart() {
    log_info "Restarting services..."
    docker compose -f "$COMPOSE_FILE" restart
    log_info "Services restarted"
    docker compose -f "$COMPOSE_FILE" ps
}

status() {
    log_info "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
}

pull() {
    log_info "Pulling latest images..."
    docker compose -f "$COMPOSE_FILE" pull
    log_info "Images updated"
}

clean() {
    log_info "Cleaning up..."
    docker compose -f "$COMPOSE_FILE" down -v
    docker image prune -af
    log_info "Cleanup completed"
}

show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start all services"
    echo "  stop     - Stop all services"
    echo "  restart  - Restart all services"
    echo "  status   - Show service status"
    echo "  pull     - Pull latest Docker images"
    echo "  clean    - Stop services and remove volumes/images"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 restart"
    exit 1
}

# Main
case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    pull)
        pull
        ;;
    clean)
        clean
        ;;
    *)
        show_usage
        ;;
esac
