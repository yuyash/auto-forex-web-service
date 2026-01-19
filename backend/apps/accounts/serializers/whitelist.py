"""Serializer for whitelisted email management."""

import re

from rest_framework import serializers

from apps.accounts.models import WhitelistedEmail


class WhitelistedEmailSerializer(serializers.ModelSerializer):
    """Serializer for whitelisted email management."""

    class Meta:
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
        """Validate email pattern format."""
        value = value.lower().strip()

        if value.startswith("*@") or value.startswith("@"):
            domain = value.lstrip("*@")
            if not domain or "." not in domain:
                raise serializers.ValidationError(
                    "Invalid domain pattern. Use format: *@example.com or @example.com"
                )
            domain_regex = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(domain_regex, domain):
                raise serializers.ValidationError("Invalid domain format.")
        else:
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, value):
                raise serializers.ValidationError(
                    "Invalid email format. Use format: user@example.com, "
                    "*@example.com, or @example.com"
                )

        return value
