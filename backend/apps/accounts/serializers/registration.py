"""Serializer for user registration."""

import re
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import PublicAccountSettings, User, WhitelistedEmail


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

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
        """Validate username contains only allowed characters."""
        if not value:
            return value

        username_regex = r"^[a-zA-Z0-9._-]+$"
        if not re.match(username_regex, value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, underscores, periods, and dashes."
            )

        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if len(value) > 150:
            raise serializers.ValidationError("Username must not exceed 150 characters.")

        return value

    def validate_email(self, value: str) -> str:
        """Validate email format, uniqueness, and whitelist."""
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Enter a valid email address.")

        normalized_email = value.lower()

        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")

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
        """Validate password strength using Django's password validators."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate that passwords match."""
        password_mismatch_msg = "Passwords do not match."  # nosec B105
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": password_mismatch_msg})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> "User":
        """Create a new user with hashed password."""
        validated_data.pop("password_confirm")

        if "username" not in validated_data or not validated_data["username"]:
            email = validated_data["email"]
            local_part = email.split("@")[0]
            base_username = re.sub(r"[^a-zA-Z0-9._-]", "", local_part)
            if len(base_username) < 3:
                base_username = f"user_{base_username}" if base_username else "user"
            username = base_username

            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            validated_data["username"] = username

        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

        return user
