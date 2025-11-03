#!/bin/bash
# Database restore script
# Usage: ./restore.sh [backup_file]

set -e

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
NC='\033[0m'

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_postgres() {
    if ! docker compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
        log_error "PostgreSQL service is not running"
        exit 1
    fi
}

list_backups() {
    log_info "Available backups:"
    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.sql.gz 2>/dev/null)" ]; then
        ls -lh "$BACKUP_DIR"/*.sql.gz | awk '{print $9, "(" $5 ")"}'
    else
        log_warn "No backups found in $BACKUP_DIR"
        exit 1
    fi
}

restore_backup() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_warn "This will replace the current database with the backup!"
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi

    log_info "Restoring database from: $backup_file"

    # Stop backend services to prevent connections
    log_info "Stopping backend services..."
    docker compose -f "$COMPOSE_FILE" stop backend celery celery-beat

    # Restore database
    gunzip -c "$backup_file" | docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres forex_trading

    # Restart backend services
    log_info "Restarting backend services..."
    docker compose -f "$COMPOSE_FILE" start backend celery celery-beat

    log_info "Database restored successfully"
}

show_usage() {
    echo "Usage: $0 [backup_file]"
    echo ""
    echo "If no backup file is specified, available backups will be listed."
    echo ""
    echo "Example:"
    echo "  $0 ./backups/backup_20250103_120000.sql.gz"
    exit 1
}

# Main
check_postgres

if [ -z "${1:-}" ]; then
    list_backups
    echo ""
    echo "To restore a backup, run:"
    echo "  $0 <backup_file>"
else
    restore_backup "$1"
fi
