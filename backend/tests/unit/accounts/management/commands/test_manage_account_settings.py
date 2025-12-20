from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import PublicAccountSettings


@pytest.mark.django_db
def test_manage_account_settings_updates_flags() -> None:
    settings = PublicAccountSettings.get_settings()
    assert settings.registration_enabled is True
    assert settings.login_enabled is True
    assert settings.email_whitelist_enabled is False

    call_command(
        "manage_account_settings",
        registration_enabled="false",
        login_enabled="false",
        email_whitelist_enabled="true",
    )

    settings.refresh_from_db()
    assert settings.registration_enabled is False
    assert settings.login_enabled is False
    assert settings.email_whitelist_enabled is True


@pytest.mark.django_db
def test_manage_account_settings_dry_run_does_not_persist() -> None:
    settings = PublicAccountSettings.get_settings()

    call_command(
        "manage_account_settings",
        dry_run=True,
        registration_enabled="false",
    )

    settings.refresh_from_db()
    assert settings.registration_enabled is True


@pytest.mark.django_db
def test_manage_account_settings_rejects_invalid_bool() -> None:
    with pytest.raises(CommandError):
        call_command(
            "manage_account_settings",
            registration_enabled="notabool",
        )
