"""
Django management command for managing email whitelist.

Usage:
    python manage.py manage_whitelist --list
    python manage.py manage_whitelist --add user@example.com --description "User"
    python manage.py manage_whitelist --add "*@company.com" --description "All employees"
    python manage.py manage_whitelist --remove 1
    python manage.py manage_whitelist --enable
    python manage.py manage_whitelist --disable
    python manage.py manage_whitelist --check user@example.com
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import SystemSettings, WhitelistedEmail


class Command(BaseCommand):
    """Management command for email whitelist operations."""

    help = "Manage email whitelist for registration and login"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        """Add command arguments."""
        parser.add_argument(
            "--list",
            action="store_true",
            help="List all whitelisted emails",
        )
        parser.add_argument(
            "--add",
            type=str,
            help="Add email pattern to whitelist (e.g., user@example.com or *@example.com)",
        )
        parser.add_argument(
            "--description",
            type=str,
            help="Description for the whitelist entry",
        )
        parser.add_argument(
            "--remove",
            type=int,
            help="Remove whitelist entry by ID",
        )
        parser.add_argument(
            "--enable",
            action="store_true",
            help="Enable email whitelist enforcement",
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help="Disable email whitelist enforcement",
        )
        parser.add_argument(
            "--check",
            type=str,
            help="Check if an email is whitelisted",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Show whitelist status",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        """Handle the command."""
        if options["list"]:
            self.list_whitelist()
        elif options["add"]:
            self.add_to_whitelist(options["add"], options.get("description", ""))
        elif options["remove"]:
            self.remove_from_whitelist(options["remove"])
        elif options["enable"]:
            self.enable_whitelist()
        elif options["disable"]:
            self.disable_whitelist()
        elif options["check"]:
            self.check_email(options["check"])
        elif options["status"]:
            self.show_status()
        else:
            self.stdout.write(
                self.style.WARNING("No action specified. Use --help to see available options.")
            )

    def list_whitelist(self) -> None:
        """List all whitelisted emails."""
        entries = WhitelistedEmail.objects.all().order_by("email_pattern")

        if not entries.exists():
            self.stdout.write(self.style.WARNING("No whitelisted emails found."))
            return

        self.stdout.write(self.style.SUCCESS("\nWhitelisted Emails:"))
        self.stdout.write("-" * 80)

        for entry in entries:
            status = "✓ Active" if entry.is_active else "✗ Inactive"
            self.stdout.write(
                f"ID: {entry.id:3d} | {entry.email_pattern:40s} | "
                f"{status:12s} | {entry.description}"
            )

        self.stdout.write("-" * 80)
        self.stdout.write(f"Total: {entries.count()} entries\n")

    def add_to_whitelist(self, email_pattern: str, description: str) -> None:
        """Add email pattern to whitelist."""
        try:
            entry = WhitelistedEmail.objects.create(
                email_pattern=email_pattern.lower().strip(),
                description=description,
                is_active=True,
            )
            self.stdout.write(
                self.style.SUCCESS(f"✓ Added '{entry.email_pattern}' to whitelist (ID: {entry.id})")
            )
        except Exception as e:
            raise CommandError(f"Failed to add to whitelist: {e}") from e

    def remove_from_whitelist(self, entry_id: int) -> None:
        """Remove email pattern from whitelist."""
        try:
            entry = WhitelistedEmail.objects.get(id=entry_id)
            email_pattern = entry.email_pattern
            entry.delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Removed '{email_pattern}' from whitelist"))
        except WhitelistedEmail.DoesNotExist as exc:
            raise CommandError(f"Whitelist entry with ID {entry_id} not found") from exc

    def enable_whitelist(self) -> None:
        """Enable email whitelist enforcement."""
        settings = SystemSettings.get_settings()
        settings.email_whitelist_enabled = True
        settings.save()
        self.stdout.write(self.style.SUCCESS("✓ Email whitelist enforcement enabled"))

    def disable_whitelist(self) -> None:
        """Disable email whitelist enforcement."""
        settings = SystemSettings.get_settings()
        settings.email_whitelist_enabled = False
        settings.save()
        self.stdout.write(self.style.SUCCESS("✓ Email whitelist enforcement disabled"))

    def check_email(self, email: str) -> None:
        """Check if an email is whitelisted."""
        is_whitelisted = WhitelistedEmail.is_email_whitelisted(email)

        if is_whitelisted:
            self.stdout.write(self.style.SUCCESS(f"✓ '{email}' is whitelisted"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ '{email}' is NOT whitelisted"))

    def show_status(self) -> None:
        """Show whitelist status."""
        settings = SystemSettings.get_settings()
        active_count = WhitelistedEmail.objects.filter(is_active=True).count()
        total_count = WhitelistedEmail.objects.count()

        self.stdout.write(self.style.SUCCESS("\nEmail Whitelist Status:"))
        self.stdout.write("-" * 50)

        status = "ENABLED" if settings.email_whitelist_enabled else "DISABLED"
        style = self.style.SUCCESS if settings.email_whitelist_enabled else self.style.WARNING

        self.stdout.write(f"Enforcement: {style(status)}")
        self.stdout.write(f"Active entries: {active_count}")
        self.stdout.write(f"Total entries: {total_count}")
        self.stdout.write("-" * 50 + "\n")
