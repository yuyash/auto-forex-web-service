"""Unit tests for trading serializers."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import TradingTasks
from apps.trading.serializers.trading import TradingTaskSerializer

User = get_user_model()


@pytest.mark.django_db
class TestTradingTaskSerializer:
    """Test TradingTaskSerializer."""

    def test_serialize_trading_task(self):
        """Test serializing trading task."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        from apps.market.enums import ApiType
        from apps.market.models import OandaAccounts
        from apps.trading.models import StrategyConfigurations

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token",
            api_type=ApiType.PRACTICE,
        )

        task = TradingTasks.objects.create(
            user=user,
            name="Test Trading",
            config=config,
            oanda_account=account,
            instrument="EUR_USD",
        )

        serializer = TradingTaskSerializer(task)
        data = serializer.data

        assert data["name"] == "Test Trading"
        assert data["instrument"] == "EUR_USD"

    def test_trading_task_read_only_fields(self):
        """Test read-only fields are not writable."""
        serializer = TradingTaskSerializer()
        meta = serializer.Meta

        # Check that certain fields are read-only
        if hasattr(meta, "read_only_fields"):
            assert "id" in meta.read_only_fields or "created_at" in meta.read_only_fields
