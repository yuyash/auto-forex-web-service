"""Integration tests for WhitelistedEmailSerializer (with database)."""

import pytest

from apps.accounts.models import User, WhitelistedEmail
from apps.accounts.serializers.whitelist import WhitelistedEmailSerializer


@pytest.mark.django_db
class TestWhitelistedEmailSerializerIntegration:
    """Integration tests for WhitelistedEmailSerializer."""

    def test_serialize_whitelisted_email(self) -> None:
        """Test serializing a whitelisted email."""
        admin = User.objects.create_user(
            email="admin@example.com",
            username="admin",
            password="TestPass123!",
        )
        whitelist = WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            description="Test entry",
            is_active=True,
            created_by=admin,
        )

        serializer = WhitelistedEmailSerializer(whitelist)
        data = serializer.data

        assert data["email_pattern"] == "test@example.com"
        assert data["description"] == "Test entry"
        assert data["is_active"] is True

    def test_create_whitelisted_email(self) -> None:
        """Test creating a whitelisted email."""
        data = {
            "email_pattern": "new@example.com",
            "description": "New entry",
            "is_active": True,
        }
        serializer = WhitelistedEmailSerializer(data=data)
        assert serializer.is_valid()

        whitelist = serializer.save()
        assert whitelist.email_pattern == "new@example.com"
        assert whitelist.description == "New entry"

    def test_update_whitelisted_email(self) -> None:
        """Test updating a whitelisted email."""
        whitelist = WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            is_active=True,
        )

        data = {"is_active": False, "description": "Updated"}
        serializer = WhitelistedEmailSerializer(whitelist, data=data, partial=True)
        assert serializer.is_valid()

        updated = serializer.save()
        assert updated.is_active is False
        assert updated.description == "Updated"
