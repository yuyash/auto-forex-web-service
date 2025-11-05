"""
Management command to create a normal user.

Usage:
    python manage.py create_user --email user@example.com
    python manage.py create_user --email user@example.com --password pass123
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User


class Command(BaseCommand):
    help = "Create a normal user"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Email address for the user",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="Username for the user (defaults to email prefix)",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password for the user (will prompt if not provided)",
        )
        parser.add_argument(
            "--timezone",
            type=str,
            default="UTC",
            help="Timezone for the user (default: UTC)",
        )
        parser.add_argument(
            "--language",
            type=str,
            default="en",
            choices=["en", "ja"],
            help="Language preference (default: en)",
        )
        parser.add_argument(
            "--verify-email",
            action="store_true",
            help="Mark email as verified (default: False)",
        )
        parser.add_argument(
            "--staff",
            action="store_true",
            help="Grant staff privileges (default: False)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        email = options["email"].strip().lower()
        username = options.get("username") or email.split("@")[0]
        password = options.get("password")
        timezone = options["timezone"]
        language = options["language"]
        verify_email = options["verify_email"]
        is_staff = options["staff"]

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            raise CommandError(f"User with email '{email}' already exists")

        if User.objects.filter(username=username).exists():
            raise CommandError(f"User with username '{username}' already exists")

        # Prompt for password if not provided
        if not password:
            from getpass import getpass

            password = getpass("Password: ")
            password_confirm = getpass("Password (again): ")

            if password != password_confirm:
                raise CommandError("Passwords do not match")

        if not password:
            raise CommandError("Password cannot be empty")

        # Create user
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    username=username,
                    password=password,
                    timezone=timezone,
                    language=language,
                    is_staff=is_staff,
                    is_superuser=False,
                    is_active=True,
                    email_verified=verify_email,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created user:\n"
                        f"  Email: {user.email}\n"
                        f"  Username: {user.username}\n"
                        f"  is_staff: {user.is_staff}\n"
                        f"  is_superuser: {user.is_superuser}\n"
                        f"  email_verified: {user.email_verified}\n"
                        f"  Timezone: {user.timezone}\n"
                        f"  Language: {user.language}"
                    )
                )

        except Exception as e:
            raise CommandError(f"Failed to create user: {str(e)}") from e
