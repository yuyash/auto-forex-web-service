"""Unit tests for accounts serializers verification."""

from apps.accounts.serializers.verification import (
    EmailVerificationSerializer,
    ResendVerificationSerializer,
)


class TestEmailVerificationSerializer:
    """Test EmailVerificationSerializer."""

    def test_valid_data(self):
        serializer = EmailVerificationSerializer(data={"token": "abc123"})
        assert serializer.is_valid()

    def test_missing_token(self):
        serializer = EmailVerificationSerializer(data={})
        assert not serializer.is_valid()
        assert "token" in serializer.errors

    def test_fields(self):
        serializer = EmailVerificationSerializer()
        assert "token" in serializer.fields


class TestResendVerificationSerializer:
    """Test ResendVerificationSerializer."""

    def test_valid_data(self):
        data = {"email": "user@example.com"}
        serializer = ResendVerificationSerializer(data=data)
        assert serializer.is_valid()

    def test_missing_email(self):
        serializer = ResendVerificationSerializer(data={})
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_invalid_email(self):
        serializer = ResendVerificationSerializer(data={"email": "not-an-email"})
        assert not serializer.is_valid()
