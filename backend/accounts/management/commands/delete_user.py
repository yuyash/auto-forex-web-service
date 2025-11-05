"""
Management command to delete a user.

Usage:
    python manage.py delete_user --email user@example.com
    python manage.py delete_user --username john
    python manage.py delete_user --email user@example.com --force
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User


class Command(BaseCommand):
    help = "Delete a user by email or username"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--email",
            type=str,
            help="Email address of the user to delete",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="Username of the user to delete",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        email = options.get("email")
        username = options.get("username")
        force = options["force"]

        # Validate input
        if not email and not username:
            raise CommandError("Either --email or --username must be provided")

        # Find user
        try:
            if email:
                user = User.objects.get(email=str(email).strip().lower())
            else:
                user = User.objects.get(username=str(username).strip())
        except User.DoesNotExist as exc:
            identifier = email or username
            raise CommandError(f"User '{identifier}' does not exist") from exc

        # Display user information
        self.stdout.write(
            self.style.WARNING(
                f"User to delete:\n"
                f"  Email: {user.email}\n"
                f"  Username: {user.username}\n"
                f"  is_staff: {user.is_staff}\n"
                f"  is_superuser: {user.is_superuser}\n"
                f"  Created: {user.created_at}\n"
                f"  Last login: {user.last_login or 'Never'}"
            )
        )

        # Confirm deletion
        if not force:
            confirm = input("\nAre you sure you want to delete this user? [y/N]: ")
            if confirm.lower() != "y":
                self.stdout.write(self.style.WARNING("Deletion cancelled"))
                return

        # Delete user
        try:
            with transaction.atomic():
                user_email = user.email
                user_username = user.username
                user.delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully deleted user:\n"
                        f"  Email: {user_email}\n"
                        f"  Username: {user_username}"
                    )
                )

        except Exception as e:
            raise CommandError(f"Failed to delete user: {str(e)}") from e
