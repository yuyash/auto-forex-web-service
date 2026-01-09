"""
Serializers for user authentication and management.

This module contains serializers for:
- User registration
- User login
- User profile
"""

import re
from typing import Any

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Password must be at least 8 characters long",
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Confirm password",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "username",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_username(self, value: str) -> str:
        """
        Validate username contains only allowed characters.

        Allowed characters: alphanumeric, underscore, period, dash.

        Args:
            value: Username to validate

        Returns:
            Validated username

        Raises:
            serializers.ValidationError: If username contains invalid characters
        """
        if not value:
            return value

        # Only allow alphanumeric characters, underscore, period, and dash
        username_regex = r"^[a-zA-Z0-9._-]+$"
        if not re.match(username_regex, value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, underscores, periods, and dashes."
            )

        # Check length constraints
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if len(value) > 150:
            raise serializers.ValidationError("Username must not exceed 150 characters.")

        return value

    def validate_email(self, value: str) -> str:
        """
        Validate email format, uniqueness, and whitelist.

        Args:
            value: Email address to validate

        Returns:
            Validated email address

        Raises:
            serializers.ValidationError: If email is invalid or already exists
        """
        # pylint: disable=import-outside-toplevel
        from apps.accounts.models import PublicAccountSettings, WhitelistedEmail

        # Validate email format
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Enter a valid email address.")

        # Normalize email to lowercase for case-insensitive comparison
        normalized_email = value.lower()

        # Check email uniqueness (case-insensitive)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")

        # Check email whitelist if enabled
        system_settings = PublicAccountSettings.get_settings()
        if system_settings.email_whitelist_enabled and not WhitelistedEmail.is_email_whitelisted(
            normalized_email
        ):
            raise serializers.ValidationError(
                "This email address is not authorized to register. "
                "Please contact the administrator."
            )

        return normalized_email

    def validate_password(self, value: str) -> str:
        """
        Validate password strength using Django's password validators.

        Args:
            value: Password to validate

        Returns:
            Validated password

        Raises:
            serializers.ValidationError: If password doesn't meet requirements
        """
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validate that passwords match.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes

        Raises:
            serializers.ValidationError: If passwords don't match
        """
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> "User":
        """
        Create a new user with hashed password.

        Args:
            validated_data: Validated user data

        Returns:
            Created user instance
        """
        # Remove password_confirm as it's not needed for user creation
        validated_data.pop("password_confirm")

        # Generate username from email if not provided
        if "username" not in validated_data or not validated_data["username"]:
            email = validated_data["email"]
            # Extract local part and filter to only allowed characters
            local_part = email.split("@")[0]
            # Keep only alphanumeric, underscore, period, dash
            base_username = re.sub(r"[^a-zA-Z0-9._-]", "", local_part)
            # Ensure minimum length
            if len(base_username) < 3:
                base_username = f"user_{base_username}" if base_username else "user"
            username = base_username

            # Ensure username is unique
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            validated_data["username"] = username

        # Create user with hashed password
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

        return user


class UserLoginSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for user login.

    Note: This is a read-only serializer used only for validation.
    It does not implement create() or update() methods as it never persists data.
    """

    email = serializers.EmailField(required=True, help_text="User's email address")
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="User's password",
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validate login credentials and whitelist.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes with user instance

        Raises:
            serializers.ValidationError: If credentials are invalid
        """
        # pylint: disable=import-outside-toplevel
        from apps.accounts.models import PublicAccountSettings, WhitelistedEmail

        email = attrs.get("email", "").lower()
        password = attrs.get("password", "")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        # Check email whitelist if enabled (before authentication)
        system_settings = PublicAccountSettings.get_settings()
        if system_settings.email_whitelist_enabled and not WhitelistedEmail.is_email_whitelisted(
            email
        ):
            raise serializers.ValidationError(
                "This email address is not authorized to login. Please contact the administrator."
            )

        # Authenticate user
        user = authenticate(username=email, password=password)

        if user is None:
            # Don't reveal whether email or password is incorrect
            raise serializers.ValidationError("Invalid credentials.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        if user.is_locked:  # type: ignore[attr-defined]
            raise serializers.ValidationError(
                "Account is locked due to excessive failed login attempts. Please contact support."
            )

        attrs["user"] = user
        return attrs


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for user settings.
    """

    class Meta:
        """Serializer metadata."""

        from apps.accounts.models import UserSettings  # pylint: disable=import-outside-toplevel

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


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile including timezone and language preferences.
    """

    def validate_timezone(self, value: str) -> str:
        """
        Validate timezone is a valid IANA timezone identifier.

        Args:
            value: Timezone to validate

        Returns:
            Validated timezone

        Raises:
            serializers.ValidationError: If timezone is invalid
        """
        import zoneinfo  # pylint: disable=import-outside-toplevel

        try:
            zoneinfo.ZoneInfo(value)
        except zoneinfo.ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                f"'{value}' is not a valid IANA timezone identifier."
            ) from exc
        return value

    def validate_language(self, value: str) -> str:
        """
        Validate language is supported.

        Args:
            value: Language code to validate

        Returns:
            Validated language code

        Raises:
            serializers.ValidationError: If language is not supported
        """
        valid_languages = ["en", "ja"]
        if value not in valid_languages:
            raise serializers.ValidationError(
                f"Language must be one of: {', '.join(valid_languages)}"
            )
        return value

    class Meta:
        """Serializer metadata."""

        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "timezone",
            "language",
            "email_verified",
        ]
        read_only_fields = ["id", "email", "email_verified"]


class WhitelistedEmailSerializer(serializers.ModelSerializer):
    """
    Serializer for whitelisted email management.
    """

    class Meta:
        from apps.accounts.models import WhitelistedEmail  # pylint: disable=import-outside-toplevel

        model = WhitelistedEmail
        fields = [
            "id",
            "email_pattern",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_email_pattern(self, value: str) -> str:
        """
        Validate email pattern format.

        Args:
            value: Email pattern to validate

        Returns:
            Validated email pattern

        Raises:
            serializers.ValidationError: If pattern is invalid
        """
        value = value.lower().strip()

        # Check if it's a domain wildcard pattern
        if value.startswith("*@") or value.startswith("@"):
            # Extract domain part
            domain = value.lstrip("*@")
            if not domain or "." not in domain:
                raise serializers.ValidationError(
                    "Invalid domain pattern. Use format: *@example.com or @example.com"
                )
            # Validate domain format
            domain_regex = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(domain_regex, domain):
                raise serializers.ValidationError("Invalid domain format.")
        else:
            # Validate as full email address
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, value):
                raise serializers.ValidationError(
                    "Invalid email format. Use format: user@example.com, "
                    "*@example.com, or @example.com"
                )

        return value


class PublicAccountSettingsSerializer(serializers.ModelSerializer):
    """Serializer for public account settings (no authentication required)."""

    class Meta:
        from apps.accounts.models import (  # pylint: disable=import-outside-toplevel
            PublicAccountSettings,
        )

        model = PublicAccountSettings
        fields = ["registration_enabled", "login_enabled", "email_whitelist_enabled"]
