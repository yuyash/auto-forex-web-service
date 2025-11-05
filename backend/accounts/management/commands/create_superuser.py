"""
Management command to create a superuser with is_superuser=True and is_staff=True.

Usage:
    python manage.py create_superuser --email admin@example.com
    python manage.py create_superuser --email admin@example.com --password pass
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User


class Command(BaseCommand):
    help = "Create a superuser with is_superuser=True and is_staff=True"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Email address for the superuser",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="Username for the superuser (defaults to email prefix)",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password for the superuser (will prompt if not provided)",
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

    def handle(self, *args: Any, **options: Any) -> None:
        email = options["email"].strip().lower()
        username = options.get("username") or email.split("@")[0]
        password = options.get("password")
        timezone = options["timezone"]
        language = options["language"]

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

        # Create superuser
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    username=username,
                    password=password,
                    timezone=timezone,
                    language=language,
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                    email_verified=True,  # Auto-verify superuser email
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created superuser:\n"
                        f"  Email: {user.email}\n"
                        f"  Username: {user.username}\n"
                        f"  is_staff: {user.is_staff}\n"
                        f"  is_superuser: {user.is_superuser}\n"
                        f"  Timezone: {user.timezone}\n"
                        f"  Language: {user.language}"
                    )
                )

        except Exception as e:
            raise CommandError(f"Failed to create superuser: {str(e)}") from e
