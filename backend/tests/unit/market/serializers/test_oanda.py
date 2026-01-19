"""Pure unit tests for OandaAccountsSerializer (no DB)."""

from unittest.mock import MagicMock

from apps.market.enums import ApiType, Jurisdiction
from apps.market.serializers import OandaAccountsSerializer


class TestOandaAccountsSerializerUnit:
    """Pure unit tests for OandaAccountsSerializer."""

    def test_serialize_account_data(self) -> None:
        """Test serializing account data without DB."""
        # Create mock account instance
        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.account_id = "101-001-1234567-001"
        mock_account.api_type = ApiType.PRACTICE
        mock_account.jurisdiction = Jurisdiction.OTHER
        mock_account.currency = "USD"
        mock_account.balance = 10000.00
        mock_account.margin_used = 1000.00
        mock_account.margin_available = 9000.00
        mock_account.unrealized_pnl = 100.00
        mock_account.is_active = True
        mock_account.is_default = False
        mock_account.created_at = "2024-01-01T00:00:00Z"
        mock_account.updated_at = "2024-01-01T00:00:00Z"

        serializer = OandaAccountsSerializer(mock_account)
        data = serializer.data

        assert data["account_id"] == "101-001-1234567-001"
        assert data["api_type"] == ApiType.PRACTICE

    def test_validate_api_type_valid(self) -> None:
        """Test API type validation with valid value."""
        serializer = OandaAccountsSerializer()
        result = serializer.validate_api_type(ApiType.PRACTICE)

        assert result == ApiType.PRACTICE

    def test_validate_api_type_invalid(self) -> None:
        """Test API type validation with invalid value."""
        from rest_framework.exceptions import ValidationError

        serializer = OandaAccountsSerializer()

        try:
            serializer.validate_api_type("invalid_type")
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            assert "API type must be one of" in str(e)

    def test_validate_jurisdiction_valid(self) -> None:
        """Test jurisdiction validation with valid value."""
        serializer = OandaAccountsSerializer()
        result = serializer.validate_jurisdiction(Jurisdiction.OTHER)

        assert result == Jurisdiction.OTHER

    def test_validate_jurisdiction_invalid(self) -> None:
        """Test jurisdiction validation with invalid value."""
        from rest_framework.exceptions import ValidationError

        serializer = OandaAccountsSerializer()

        try:
            serializer.validate_jurisdiction("invalid_jurisdiction")
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            assert "Jurisdiction must be one of" in str(e)

    def test_read_only_fields(self) -> None:
        """Test that certain fields are read-only."""
        serializer = OandaAccountsSerializer()

        read_only_fields = serializer.Meta.read_only_fields

        assert "id" in read_only_fields
        assert "balance" in read_only_fields
        assert "margin_used" in read_only_fields
        assert "margin_available" in read_only_fields
        assert "unrealized_pnl" in read_only_fields
        assert "created_at" in read_only_fields
        assert "updated_at" in read_only_fields

    def test_api_token_write_only(self) -> None:
        """Test that api_token is write-only."""
        serializer = OandaAccountsSerializer()

        # api_token should be in fields
        assert "api_token" in serializer.fields

        # api_token should be write_only
        assert serializer.fields["api_token"].write_only is True
