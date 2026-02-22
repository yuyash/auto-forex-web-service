"""Serializers for user profile."""

from rest_framework import serializers

from apps.accounts.models import User


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile including timezone and language preferences."""

    def validate_timezone(self, value: str) -> str:
        """Validate timezone is a valid IANA timezone identifier."""
        import zoneinfo

        try:
            zoneinfo.ZoneInfo(value)
        except zoneinfo.ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                f"'{value}' is not a valid IANA timezone identifier."
            ) from exc
        return value

    def validate_language(self, value: str) -> str:
        """Validate language is supported."""
        valid_languages = ["en", "ja"]
        if value not in valid_languages:
            raise serializers.ValidationError(
                f"Language must be one of: {', '.join(valid_languages)}"
            )
        return value

    class Meta:
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
