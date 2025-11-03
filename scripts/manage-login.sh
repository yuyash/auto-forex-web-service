#!/bin/bash
# Script to enable/disable user login
# Usage: ./manage-login.sh [enable|disable|status]

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

check_backend() {
    if ! docker compose -f "$COMPOSE_FILE" ps backend | grep -q "Up"; then
        log_error "Backend service is not running"
        exit 1
    fi
}

enable_login() {
    log_info "Enabling user login..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
settings.login_enabled = True
settings.save()
print(f"✓ Login enabled: {settings.login_enabled}")
EOF
    log_info "User login has been enabled"
}

disable_login() {
    log_info "Disabling user login..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
settings.login_enabled = False
settings.save()
print(f"✓ Login disabled: {settings.login_enabled}")
EOF
    log_info "User login has been disabled"
}

show_status() {
    log_info "Checking login status..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
status = "ENABLED" if settings.login_enabled else "DISABLED"
print(f"\nUser Login: {status}")
print(f"Last Updated: {settings.updated_at}")
if settings.updated_by:
    print(f"Updated By: {settings.updated_by.email}")
EOF
}

show_usage() {
    echo "Usage: $0 [enable|disable|status]"
    echo ""
    echo "Commands:"
    echo "  enable   - Enable user login"
    echo "  disable  - Disable user login"
    echo "  status   - Show current login status"
    exit 1
}

# Main
check_backend

case "${1:-}" in
    enable)
        enable_login
        ;;
    disable)
        disable_login
        ;;
    status)
        show_status
        ;;
    *)
        show_usage
        ;;
esac
