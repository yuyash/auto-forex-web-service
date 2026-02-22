"""Serializer for user login."""

from typing import Any

from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.accounts.models import PublicAccountSettings, WhitelistedEmail


class UserLoginSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for user login."""

    email = serializers.EmailField(required=True, help_text="User's email address")
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="User's password",
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate login credentials and whitelist."""
        email: str = attrs.get("email", "").lower()
        password: str = attrs.get("password", "")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        system_settings: PublicAccountSettings = PublicAccountSettings.get_settings()
        if system_settings.email_whitelist_enabled and not WhitelistedEmail.is_email_whitelisted(
            email
        ):
            raise serializers.ValidationError(
                "This email address is not authorized to login. Please contact the administrator."
            )

        user = authenticate(username=email, password=password)

        if user is None:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        if user.is_locked:  # type: ignore[attr-defined]
            raise serializers.ValidationError(
                "Account is locked due to excessive failed login attempts. Please contact support."
            )

        attrs["user"] = user
        return attrs
