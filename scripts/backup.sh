#!/bin/bash
# Database backup script
# Usage: ./backup.sh

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
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
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

create_backup() {
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"

    log_info "Creating database backup..."
    log_info "Backup file: $BACKUP_FILE"

    # Create backup
    docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U postgres forex_trading | gzip > "$BACKUP_FILE"

    # Check if backup was created successfully
    if [ -f "$BACKUP_FILE" ]; then
        local size=$(du -h "$BACKUP_FILE" | cut -f1)
        log_info "Backup created successfully (Size: $size)"
        log_info "Location: $BACKUP_FILE"
    else
        log_error "Backup failed"
        exit 1
    fi
}

cleanup_old_backups() {
    local keep_days=${BACKUP_RETENTION_DAYS:-30}
    log_info "Cleaning up backups older than $keep_days days..."

    find "$BACKUP_DIR" -name "backup_*.sql.gz" -type f -mtime +$keep_days -delete

    log_info "Cleanup completed"
}

# Main
check_postgres
create_backup
cleanup_old_backups

log_info "Backup process completed successfully"
