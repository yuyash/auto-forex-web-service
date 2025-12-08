"""
Management command to reset a user's password.

Usage:
    python manage.py reset_password --email user@example.com
    python manage.py reset_password --username john --password newpass123
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Reset password for a specific user"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--email",
            type=str,
            help="Email address of the user",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="Username of the user",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="New password (will prompt if not provided)",
        )
        parser.add_argument(
            "--unlock",
            action="store_true",
            help="Unlock the account if it's locked",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        email = options.get("email")
        username = options.get("username")
        password = options.get("password")
        unlock = options["unlock"]

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
            f"User found:\n"
            f"  Email: {user.email}\n"
            f"  Username: {user.username}\n"
            f"  is_locked: {user.is_locked}\n"
            f"  failed_login_attempts: {user.failed_login_attempts}"
        )

        # Prompt for password if not provided
        if not password:
            from getpass import getpass

            password = getpass("New password: ")
            password_confirm = getpass("New password (again): ")

            if password != password_confirm:
                raise CommandError("Passwords do not match")

        if not password:
            raise CommandError("Password cannot be empty")

        # Reset password
        try:
            with transaction.atomic():
                user.set_password(password)
                user.reset_failed_login()

                if unlock and user.is_locked:
                    user.unlock_account()
                    self.stdout.write(self.style.SUCCESS("Account unlocked"))

                user.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully reset password for user:\n"
                        f"  Email: {user.email}\n"
                        f"  Username: {user.username}\n"
                        f"  is_locked: {user.is_locked}\n"
                        f"  failed_login_attempts: {user.failed_login_attempts}"
                    )
                )

        except Exception as e:
            raise CommandError(f"Failed to reset password: {str(e)}") from e
