#!/bin/bash
# Production deployment script
# This script handles the deployment of the Forex Trading System

set -e  # Exit on error

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root (parent of scripts directory)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"
PROJECT_NAME="${PROJECT_NAME:-forex-trading}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env() {
    if [ ! -f .env ]; then
        log_error ".env file not found!"
        log_info "Please create .env file from .env.example"
        exit 1
    fi
}

pull_images() {
    log_info "Pulling latest Docker images..."
    docker compose -f "$COMPOSE_FILE" pull
}

start_services() {
    log_info "Starting services..."
    docker compose -f "$COMPOSE_FILE" up -d
    log_info "Services started successfully"
}

stop_services() {
    log_info "Stopping services..."
    docker compose -f "$COMPOSE_FILE" down
    log_info "Services stopped successfully"
}

restart_services() {
    log_info "Restarting services..."
    docker compose -f "$COMPOSE_FILE" restart
    log_info "Services restarted successfully"
}

wait_for_db() {
    log_info "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker exec forex_postgres pg_isready -U postgres > /dev/null 2>&1; then
            log_info "PostgreSQL is ready"
            return 0
        fi
        log_warn "Waiting for PostgreSQL... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL failed to become ready"
    return 1
}

run_migrations() {
    log_info "Running database migrations..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py migrate
    log_info "Migrations completed successfully"
}

collect_static() {
    log_info "Collecting static files..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py collectstatic --noinput
    log_info "Static files collected successfully"
}

init_system_settings() {
    log_info "Initializing system settings..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py init_system_settings
    log_info "System settings initialized successfully"
}

show_status() {
    log_info "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
}

cleanup_images() {
    log_info "Cleaning up old Docker images..."
    docker image prune -af
    log_info "Cleanup completed"
}

# Main deployment flow
main() {
    log_info "Starting deployment..."

    check_env
    pull_images
    stop_services
    start_services
    wait_for_db
    run_migrations
    collect_static
    init_system_settings
    show_status

    log_info "Deployment completed successfully!"
    log_info "Access the application at: http://localhost"
}

# Run main function
main
