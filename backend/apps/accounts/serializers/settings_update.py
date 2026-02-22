"""Serializer for updating user settings."""

from rest_framework import serializers


class UserSettingsUpdateSerializer(serializers.Serializer):
    """Serializer for updating user settings."""

    # User profile fields
    timezone = serializers.CharField(required=False)
    language = serializers.ChoiceField(choices=["en", "ja"], required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False)

    # Notification settings
    notification_enabled = serializers.BooleanField(required=False)
    notification_email = serializers.BooleanField(required=False)
    notification_browser = serializers.BooleanField(required=False)

    # Additional settings JSON
    settings_json = serializers.JSONField(required=False)
