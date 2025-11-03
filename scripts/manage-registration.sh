#!/bin/bash
# Script to enable/disable user registration
# Usage: ./manage-registration.sh [enable|disable|status]

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

enable_registration() {
    log_info "Enabling user registration..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
settings.registration_enabled = True
settings.save()
print(f"✓ Registration enabled: {settings.registration_enabled}")
EOF
    log_info "User registration has been enabled"
}

disable_registration() {
    log_info "Disabling user registration..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
settings.registration_enabled = False
settings.save()
print(f"✓ Registration disabled: {settings.registration_enabled}")
EOF
    log_info "User registration has been disabled"
}

show_status() {
    log_info "Checking registration status..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
status = "ENABLED" if settings.registration_enabled else "DISABLED"
print(f"\nUser Registration: {status}")
print(f"Last Updated: {settings.updated_at}")
if settings.updated_by:
    print(f"Updated By: {settings.updated_by.email}")
EOF
}

show_usage() {
    echo "Usage: $0 [enable|disable|status]"
    echo ""
    echo "Commands:"
    echo "  enable   - Enable user registration"
    echo "  disable  - Disable user registration"
    echo "  status   - Show current registration status"
    exit 1
}

# Main
check_backend

case "${1:-}" in
    enable)
        enable_registration
        ;;
    disable)
        disable_registration
        ;;
    status)
        show_status
        ;;
    *)
        show_usage
        ;;
esac
