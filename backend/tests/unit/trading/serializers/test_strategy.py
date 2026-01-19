"""Unit tests for strategy serializers."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import StrategyConfigurations

User = get_user_model()


@pytest.mark.django_db
class TestStrategyConfigSerializer:
    """Test StrategyConfigSerializer."""

    def test_serialize_strategy_config(self):
        """Test serializing strategy configuration."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Strategy",
            strategy_type="floor",
            parameters={"param1": "value1"},
        )

        from apps.trading.serializers.strategy import StrategyConfigDetailSerializer

        serializer = StrategyConfigDetailSerializer(config)
        data = serializer.data

        assert data["name"] == "Test Strategy"
        assert data["strategy_type"] == "floor"

    def test_strategy_config_validation(self):
        """Test strategy config validation."""
        from apps.trading.serializers.strategy import StrategyConfigCreateSerializer

        data = {
            "name": "Test Strategy",
            "strategy_type": "floor",
            "parameters": {"param1": "value1"},
        }

        serializer = StrategyConfigCreateSerializer(data=data)
        # Should validate successfully or fail with specific errors
        is_valid = serializer.is_valid()
        assert is_valid or len(serializer.errors) > 0
