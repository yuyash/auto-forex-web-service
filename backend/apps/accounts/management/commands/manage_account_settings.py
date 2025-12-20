"""Django management command for managing public account settings.

These settings control whether users can register/login and whether email
whitelist enforcement is enabled.

Usage:
    python manage.py manage_account_settings --show
    python manage.py manage_account_settings --registration-enabled false
    python manage.py manage_account_settings --login-enabled false
    python manage.py manage_account_settings --email-whitelist-enabled true
    python manage.py manage_account_settings --registration-enabled true --login-enabled true

Boolean values accepted: true/false, 1/0, yes/no, on/off.
"""

from __future__ import annotations

import argparse

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import PublicAccountSettings


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disable", "disabled"}:
        return False
    raise argparse.ArgumentTypeError(
        "Invalid boolean value. Use one of: true/false, 1/0, yes/no, on/off."
    )


def _coerce_optional_bool(*, name: str, value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return _parse_bool(value)
        except argparse.ArgumentTypeError as exc:
            raise CommandError(f"{name}: {exc}") from exc
    raise CommandError(f"{name}: expected a boolean or boolean-like string")


class Command(BaseCommand):
    help = "Manage public account settings (registration/login/email whitelist)."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--show",
            action="store_true",
            help="Show current settings.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show changes without saving.",
        )

        parser.add_argument(
            "--registration-enabled",
            type=_parse_bool,
            default=None,
            help="Enable/disable new user registration.",
        )
        parser.add_argument(
            "--login-enabled",
            type=_parse_bool,
            default=None,
            help="Enable/disable user login.",
        )
        parser.add_argument(
            "--email-whitelist-enabled",
            type=_parse_bool,
            default=None,
            help="Enable/disable email whitelist enforcement.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        settings = PublicAccountSettings.get_settings()

        if options["show"]:
            self._print_settings(settings)

        requested_updates = {
            "registration_enabled": _coerce_optional_bool(
                name="registration_enabled", value=options.get("registration_enabled")
            ),
            "login_enabled": _coerce_optional_bool(
                name="login_enabled", value=options.get("login_enabled")
            ),
            "email_whitelist_enabled": _coerce_optional_bool(
                name="email_whitelist_enabled", value=options.get("email_whitelist_enabled")
            ),
        }

        updates = {k: v for k, v in requested_updates.items() if v is not None}

        if not updates:
            if not options["show"]:
                self.stdout.write(
                    self.style.WARNING(
                        "No changes specified. Use --show or pass one or more flags."
                    )
                )
            return

        before = {
            "registration_enabled": settings.registration_enabled,
            "login_enabled": settings.login_enabled,
            "email_whitelist_enabled": settings.email_whitelist_enabled,
        }

        for field, value in updates.items():
            setattr(settings, field, value)

        after = {
            "registration_enabled": settings.registration_enabled,
            "login_enabled": settings.login_enabled,
            "email_whitelist_enabled": settings.email_whitelist_enabled,
        }

        self.stdout.write(self.style.SUCCESS("\nPublic account settings update:"))
        for key in ["registration_enabled", "login_enabled", "email_whitelist_enabled"]:
            old = before[key]
            new = after[key]
            if old == new:
                continue
            self.stdout.write(f"- {key}: {old} -> {new}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDry run: no changes saved."))
            return

        # Save (include updated_at so auto_now updates even with update_fields).
        settings.save(update_fields=[*updates.keys(), "updated_at"])
        self.stdout.write(self.style.SUCCESS("\n✓ Settings saved."))

    def _print_settings(self, settings: PublicAccountSettings) -> None:
        self.stdout.write(self.style.SUCCESS("\nPublic Account Settings:"))
        self.stdout.write("-" * 40)
        self.stdout.write(f"registration_enabled: {settings.registration_enabled}")
        self.stdout.write(f"login_enabled:        {settings.login_enabled}")
        self.stdout.write(f"email_whitelist:      {settings.email_whitelist_enabled}")
        self.stdout.write("-" * 40)
