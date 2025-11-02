"""
Serializers for user authentication and management.

This module contains serializers for:
- User registration
- User login
- User profile
"""

import re
from typing import TYPE_CHECKING, Any, Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

if TYPE_CHECKING:
    from accounts.models import User as UserType
else:
    UserType = get_user_model()

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    Requirements: 1.1, 1.2, 1.3, 1.5
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
        fields = ["email", "username", "password", "password_confirm"]
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": False},
        }

    def validate_email(self, value: str) -> str:
        """
        Validate email format and uniqueness.

        Args:
            value: Email address to validate

        Returns:
            Validated email address

        Raises:
            serializers.ValidationError: If email is invalid or already exists
        """
        # Validate email format
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Enter a valid email address.")

        # Normalize email to lowercase for case-insensitive comparison
        normalized_email = value.lower()

        # Check email uniqueness (case-insensitive)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")

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
            raise serializers.ValidationError(list(e.messages))

        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
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

    def create(self, validated_data: Dict[str, Any]) -> "UserType":
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
            base_username = email.split("@")[0]
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
        )

        return user
