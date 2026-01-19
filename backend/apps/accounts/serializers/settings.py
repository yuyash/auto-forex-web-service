"""Serializers for user settings and public account settings."""

from rest_framework import serializers

from apps.accounts.models import PublicAccountSettings, UserSettings


class UserSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user settings."""

    class Meta:
        model = UserSettings
        fields = [
            "id",
            "notification_enabled",
            "notification_email",
            "notification_browser",
            "settings_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PublicAccountSettingsSerializer(serializers.ModelSerializer):
    """Serializer for public account settings (no authentication required)."""

    class Meta:
        model = PublicAccountSettings
        fields = ["registration_enabled", "login_enabled", "email_whitelist_enabled"]
