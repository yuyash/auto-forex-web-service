"""Pure unit tests for OandaApiHealthStatusSerializer (no DB)."""

from unittest.mock import MagicMock

from apps.market.enums import ApiType
from apps.market.serializers import OandaApiHealthStatusSerializer


class TestOandaApiHealthStatusSerializerUnit:
    """Pure unit tests for OandaApiHealthStatusSerializer."""

    def test_serialize_health_status(self) -> None:
        """Test serializing health status without DB."""
        # Create mock account
        mock_account = MagicMock()
        mock_account.account_id = "101-001-1234567-001"
        mock_account.api_type = ApiType.PRACTICE

        # Create mock health status
        mock_health = MagicMock()
        mock_health.id = 1
        mock_health.account = mock_account
        mock_health.is_available = True
        mock_health.checked_at = "2024-01-01T00:00:00Z"
        mock_health.latency_ms = 150
        mock_health.http_status = 200
        mock_health.error_message = ""

        serializer = OandaApiHealthStatusSerializer(mock_health)
        data = serializer.data

        assert data["oanda_account_id"] == "101-001-1234567-001"
        assert data["api_type"] == ApiType.PRACTICE
        assert data["is_available"] is True
        assert data["latency_ms"] == 150
        assert data["http_status"] == 200

    def test_all_fields_read_only(self) -> None:
        """Test that all fields are read-only."""
        serializer = OandaApiHealthStatusSerializer()

        # All fields should be in read_only_fields
        assert len(serializer.Meta.read_only_fields) == len(serializer.Meta.fields)

    def test_nested_account_fields(self) -> None:
        """Test that account fields are properly nested."""
        serializer = OandaApiHealthStatusSerializer()

        # Check that oanda_account_id and api_type are defined
        assert "oanda_account_id" in serializer.fields
        assert "api_type" in serializer.fields

        # Both should be read-only
        assert serializer.fields["oanda_account_id"].read_only is True
        assert serializer.fields["api_type"].read_only is True
