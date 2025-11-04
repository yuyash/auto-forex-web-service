#!/bin/bash
# Script to add/remove/list emails in the whitelist
# Usage: ./whitelist-email.sh [add|remove|list|check] [email] [description]

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
BLUE='\033[0;34m'
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

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

check_backend() {
    if ! docker compose -f "$COMPOSE_FILE" ps backend | grep -q "Up"; then
        log_error "Backend service is not running"
        exit 1
    fi
}

add_email() {
    local email="$1"
    local description="${2:-}"

    if [ -z "$email" ]; then
        log_error "Email address is required"
        show_usage
    fi

    log_info "Adding email to whitelist: $email"
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << EOF
from accounts.models import WhitelistedEmail
from django.db import IntegrityError

email = "$email"
description = "$description"

try:
    entry, created = WhitelistedEmail.objects.get_or_create(
        email_pattern=email.lower().strip(),
        defaults={
            'description': description,
            'is_active': True
        }
    )

    if created:
        print(f"✓ Added to whitelist: {entry.email_pattern}")
        if description:
            print(f"  Description: {description}")
    else:
        if not entry.is_active:
            entry.is_active = True
            entry.save()
            print(f"✓ Reactivated existing entry: {entry.email_pattern}")
        else:
            print(f"⚠️  Email already in whitelist: {entry.email_pattern}")
        if description and description != entry.description:
            entry.description = description
            entry.save()
            print(f"  Updated description: {description}")
except IntegrityError as e:
    print(f"✗ Error adding email: {e}")
    exit(1)
EOF

    if [ $? -eq 0 ]; then
        log_success "Email whitelist updated"
    else
        log_error "Failed to add email to whitelist"
        exit 1
    fi
}

remove_email() {
    local email="$1"

    if [ -z "$email" ]; then
        log_error "Email address is required"
        show_usage
    fi

    log_info "Removing email from whitelist: $email"
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << EOF
from accounts.models import WhitelistedEmail

email = "$email"

try:
    entry = WhitelistedEmail.objects.get(email_pattern=email.lower().strip())
    entry.delete()
    print(f"✓ Removed from whitelist: {entry.email_pattern}")
except WhitelistedEmail.DoesNotExist:
    print(f"⚠️  Email not found in whitelist: {email}")
    exit(1)
EOF

    if [ $? -eq 0 ]; then
        log_success "Email removed from whitelist"
    else
        log_error "Failed to remove email from whitelist"
        exit 1
    fi
}

list_emails() {
    local show_inactive="${1:-false}"

    log_info "Listing whitelisted emails..."
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << EOF
from accounts.models import WhitelistedEmail

show_inactive = "$show_inactive" == "true"

if show_inactive:
    entries = WhitelistedEmail.objects.all().order_by('email_pattern')
    print("\nAll Whitelisted Emails:")
else:
    entries = WhitelistedEmail.objects.filter(is_active=True).order_by('email_pattern')
    print("\nActive Whitelisted Emails:")

if not entries.exists():
    print("  (none)")
else:
    for entry in entries:
        status = "✓" if entry.is_active else "✗"
        desc = f" - {entry.description}" if entry.description else ""
        print(f"  {status} {entry.email_pattern}{desc}")
        print(f"     Created: {entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\nTotal: {entries.count()} entries")
EOF
}

check_email() {
    local email="$1"

    if [ -z "$email" ]; then
        log_error "Email address is required"
        show_usage
    fi

    log_info "Checking if email is whitelisted: $email"
    docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py shell << EOF
from accounts.models import WhitelistedEmail

email = "$email"

is_whitelisted = WhitelistedEmail.is_email_whitelisted(email)

if is_whitelisted:
    print(f"\n✓ Email IS whitelisted: {email}")

    # Find matching entry
    email_lower = email.lower().strip()

    # Check exact match
    exact = WhitelistedEmail.objects.filter(
        email_pattern__iexact=email_lower,
        is_active=True
    ).first()

    if exact:
        print(f"  Matched by: Exact match")
        print(f"  Pattern: {exact.email_pattern}")
        if exact.description:
            print(f"  Description: {exact.description}")
    else:
        # Check domain match
        if "@" in email_lower:
            domain = email_lower.split("@")[1]
            domain_patterns = [f"*@{domain}", f"@{domain}"]
            domain_match = WhitelistedEmail.objects.filter(
                email_pattern__in=domain_patterns,
                is_active=True
            ).first()

            if domain_match:
                print(f"  Matched by: Domain wildcard")
                print(f"  Pattern: {domain_match.email_pattern}")
                if domain_match.description:
                    print(f"  Description: {domain_match.description}")
else:
    print(f"\n✗ Email is NOT whitelisted: {email}")
    print(f"  Add it using: ./scripts/whitelist-email.sh add {email}")
EOF
}

show_usage() {
    echo "Usage: $0 [add|remove|list|check] [email] [description]"
    echo ""
    echo "Commands:"
    echo "  add <email> [description]  - Add email to whitelist"
    echo "                               Supports wildcards: *@example.com or @example.com"
    echo "  remove <email>             - Remove email from whitelist"
    echo "  list [--all]               - List whitelisted emails (use --all to include inactive)"
    echo "  check <email>              - Check if an email is whitelisted"
    echo ""
    echo "Examples:"
    echo "  $0 add user@example.com \"John Doe\""
    echo "  $0 add *@company.com \"All company emails\""
    echo "  $0 add @trusted.org \"Trusted organization\""
    echo "  $0 remove user@example.com"
    echo "  $0 list"
    echo "  $0 list --all"
    echo "  $0 check user@example.com"
    exit 1
}

# Main
check_backend

case "${1:-}" in
    add)
        add_email "$2" "$3"
        ;;
    remove)
        remove_email "$2"
        ;;
    list)
        if [ "$2" = "--all" ]; then
            list_emails "true"
        else
            list_emails "false"
        fi
        ;;
    check)
        check_email "$2"
        ;;
    *)
        show_usage
        ;;
esac
