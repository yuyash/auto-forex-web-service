#!/bin/bash
# Script to enable/disable email whitelisting
# Usage: ./manage-email-whitelist.sh [enable|disable|status]

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

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

check_backend() {
    if ! docker compose -f "$COMPOSE_FILE" ps backend | grep -q "Up"; then
        log_error "Backend service is not running"
        exit 1
    fi
}

enable_whitelist() {
    log_info "Enabling email whitelist..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings, WhitelistedEmail
settings = SystemSettings.get_settings()
settings.email_whitelist_enabled = True
settings.save()
print(f"✓ Email whitelist enabled: {settings.email_whitelist_enabled}")

# Show count of active whitelist entries
active_count = WhitelistedEmail.objects.filter(is_active=True).count()
print(f"✓ Active whitelist entries: {active_count}")
if active_count == 0:
    print("\n⚠️  WARNING: No active whitelist entries found!")
    print("   Add emails using: ./scripts/whitelist-email.sh add <email>")
EOF
    log_info "Email whitelist has been enabled"
}

disable_whitelist() {
    log_info "Disabling email whitelist..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings
settings = SystemSettings.get_settings()
settings.email_whitelist_enabled = False
settings.save()
print(f"✓ Email whitelist disabled: {settings.email_whitelist_enabled}")
EOF
    log_info "Email whitelist has been disabled"
}

show_status() {
    log_info "Checking email whitelist status..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << 'EOF'
from accounts.models import SystemSettings, WhitelistedEmail
settings = SystemSettings.get_settings()
status = "ENABLED" if settings.email_whitelist_enabled else "DISABLED"
print(f"\nEmail Whitelist: {status}")
print(f"Last Updated: {settings.updated_at}")
if settings.updated_by:
    print(f"Updated By: {settings.updated_by.email}")

# Show whitelist entries
active_count = WhitelistedEmail.objects.filter(is_active=True).count()
inactive_count = WhitelistedEmail.objects.filter(is_active=False).count()
total_count = WhitelistedEmail.objects.count()

print(f"\nWhitelist Entries:")
print(f"  Active: {active_count}")
print(f"  Inactive: {inactive_count}")
print(f"  Total: {total_count}")

if active_count > 0:
    print(f"\nActive Entries:")
    for entry in WhitelistedEmail.objects.filter(is_active=True).order_by('email_pattern')[:10]:
        desc = f" - {entry.description}" if entry.description else ""
        print(f"  • {entry.email_pattern}{desc}")
    if active_count > 10:
        print(f"  ... and {active_count - 10} more")
EOF
}

show_usage() {
    echo "Usage: $0 [enable|disable|status]"
    echo ""
    echo "Commands:"
    echo "  enable   - Enable email whitelist enforcement"
    echo "  disable  - Disable email whitelist enforcement"
    echo "  status   - Show current whitelist status and entries"
    echo ""
    echo "Note: Use ./scripts/whitelist-email.sh to manage whitelist entries"
    exit 1
}

# Main
check_backend

case "${1:-}" in
    enable)
        enable_whitelist
        ;;
    disable)
        disable_whitelist
        ;;
    status)
        show_status
        ;;
    *)
        show_usage
        ;;
esac
