"""Settings models for user preferences and public account settings."""

from typing import Any

from django.db import models


class UserSettings(models.Model):
    """User preferences and notification settings."""

    user = models.OneToOneField(
        "User",
        on_delete=models.CASCADE,
        related_name="settings",
        help_text="User associated with these settings",
    )
    notification_enabled = models.BooleanField(
        default=True,
        help_text="Whether notifications are enabled",
    )
    notification_email = models.BooleanField(
        default=True,
        help_text="Whether to send email notifications",
    )
    notification_browser = models.BooleanField(
        default=True,
        help_text="Whether to send browser notifications",
    )
    settings_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional settings stored as JSON",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when settings were created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when settings were last updated",
    )

    class Meta:
        db_table = "user_settings"
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self) -> str:
        return f"Settings for {self.user.email}"


class PublicAccountSettings(models.Model):
    """Public account settings for the application (singleton model)."""

    registration_enabled = models.BooleanField(
        default=True,
        help_text="Whether new user registration is enabled",
    )
    login_enabled = models.BooleanField(
        default=True,
        help_text="Whether user login is enabled",
    )
    email_whitelist_enabled = models.BooleanField(
        default=False,
        help_text="Whether email whitelist is enforced for registration/login",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when settings were last updated",
    )

    class Meta:
        db_table = "public_account_settings"
        verbose_name = "Public Account Settings"
        verbose_name_plural = "Public Account Settings"

    def __str__(self) -> str:
        return (
            f"Public Account Settings (Registration: {self.registration_enabled}, "
            f"Login: {self.login_enabled}, "
            f"Email Whitelist: {self.email_whitelist_enabled})"
        )

    @classmethod
    def get_settings(cls) -> "PublicAccountSettings":
        """Get or create the singleton PublicAccountSettings instance."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to ensure only one instance exists."""
        self.pk = 1
        super().save(*args, **kwargs)
