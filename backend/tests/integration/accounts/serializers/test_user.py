"""Integration tests for UserProfileSerializer (with database)."""

import pytest

from apps.accounts.models import User
from apps.accounts.serializers.user import UserProfileSerializer


@pytest.mark.django_db
class TestUserProfileSerializerIntegration:
    """Integration tests for UserProfileSerializer."""

    def test_serialize_user(self) -> None:
        """Test serializing a user."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
            first_name="Test",
            last_name="User",
            timezone="America/New_York",
            language="en",
        )

        serializer = UserProfileSerializer(user)
        data = serializer.data

        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert data["timezone"] == "America/New_York"
        assert data["language"] == "en"

    def test_update_user_profile(self) -> None:
        """Test updating user profile."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        data = {
            "first_name": "Updated",
            "last_name": "Name",
            "timezone": "Asia/Tokyo",
            "language": "ja",
        }
        serializer = UserProfileSerializer(user, data=data, partial=True)
        assert serializer.is_valid()

        updated_user = serializer.save()
        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "Name"
        assert updated_user.timezone == "Asia/Tokyo"
        assert updated_user.language == "ja"

    def test_read_only_fields(self) -> None:
        """Test that read-only fields cannot be updated."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        data = {
            "email": "newemail@example.com",
            "email_verified": True,
        }
        serializer = UserProfileSerializer(user, data=data, partial=True)
        assert serializer.is_valid()

        updated_user = serializer.save()
        # Email should not change (read-only)
        assert updated_user.email == "test@example.com"
