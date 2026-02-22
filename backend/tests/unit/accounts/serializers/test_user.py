"""Unit tests for UserProfileSerializer (validation logic only)."""

import pytest

from apps.accounts.serializers.user import UserProfileSerializer


class TestUserProfileSerializerValidation:
    """Unit tests for UserProfileSerializer validation methods."""

    def test_validate_timezone_valid(self) -> None:
        """Test timezone validation with valid IANA timezone."""
        serializer = UserProfileSerializer()
        result = serializer.validate_timezone("America/New_York")
        assert result == "America/New_York"

    def test_validate_timezone_invalid(self) -> None:
        """Test timezone validation with invalid timezone."""
        from rest_framework.exceptions import ValidationError

        serializer = UserProfileSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_timezone("Invalid/Timezone")

    def test_validate_language_valid(self) -> None:
        """Test language validation with valid language."""
        serializer = UserProfileSerializer()
        result = serializer.validate_language("en")
        assert result == "en"

        result = serializer.validate_language("ja")
        assert result == "ja"

    def test_validate_language_invalid(self) -> None:
        """Test language validation with invalid language."""
        from rest_framework.exceptions import ValidationError

        serializer = UserProfileSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_language("fr")
