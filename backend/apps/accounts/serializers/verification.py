"""Serializers for email verification."""

from rest_framework import serializers


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification request."""

    token = serializers.CharField(required=True, help_text="Email verification token")


class ResendVerificationSerializer(serializers.Serializer):
    """Serializer for resend verification email request."""

    email = serializers.EmailField(
        required=True, help_text="Email address to resend verification to"
    )
