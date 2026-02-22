"""Unit tests for WhitelistedEmailSerializer (validation logic only)."""

import pytest

from apps.accounts.serializers.whitelist import WhitelistedEmailSerializer


class TestWhitelistedEmailSerializerValidation:
    """Unit tests for WhitelistedEmailSerializer validation methods."""

    def test_validate_email_pattern_valid_email(self) -> None:
        """Test email pattern validation with valid email."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("test@example.com")
        assert result == "test@example.com"

    def test_validate_email_pattern_domain_wildcard(self) -> None:
        """Test email pattern validation with domain wildcard."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("*@example.com")
        assert result == "*@example.com"

    def test_validate_email_pattern_at_domain(self) -> None:
        """Test email pattern validation with @domain format."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("@example.com")
        assert result == "@example.com"

    def test_validate_email_pattern_invalid_email(self) -> None:
        """Test email pattern validation with invalid email."""
        from rest_framework.exceptions import ValidationError

        serializer = WhitelistedEmailSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_email_pattern("invalid_email")

    def test_validate_email_pattern_invalid_domain(self) -> None:
        """Test email pattern validation with invalid domain."""
        from rest_framework.exceptions import ValidationError

        serializer = WhitelistedEmailSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_email_pattern("*@invalid")

    def test_validate_email_pattern_normalizes_case(self) -> None:
        """Test email pattern validation normalizes to lowercase."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("Test@Example.COM")
        assert result == "test@example.com"
