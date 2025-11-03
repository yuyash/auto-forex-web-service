#!/bin/bash
# Django management command wrapper
# Usage: ./manage.sh [command] [args...]

set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_backend() {
    if ! docker compose -f "$COMPOSE_FILE" ps backend | grep -q "Up"; then
        log_error "Backend service is not running"
        exit 1
    fi
}

show_usage() {
    echo "Usage: $0 [command] [args...]"
    echo ""
    echo "Common commands:"
    echo "  migrate              - Run database migrations"
    echo "  makemigrations       - Create new migrations"
    echo "  createsuperuser      - Create a superuser account"
    echo "  shell                - Open Django shell"
    echo "  dbshell              - Open database shell"
    echo "  collectstatic        - Collect static files"
    echo "  init_system_settings - Initialize system settings"
    echo ""
    echo "Examples:"
    echo "  $0 migrate"
    echo "  $0 createsuperuser"
    echo "  $0 shell"
    exit 1
}

# Main
if [ -z "${1:-}" ]; then
    show_usage
fi

check_backend

log_info "Running: python manage.py $*"
docker compose -f "$COMPOSE_FILE" exec backend python manage.py "$@"
