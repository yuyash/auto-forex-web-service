"""Unit tests for trading config models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import StrategyConfigurations

User = get_user_model()


@pytest.mark.django_db
class TestStrategyConfigurationsModel:
    """Test StrategyConfigurations model - additional tests."""

    def test_config_dict_returns_parsed_json(self):
        """Test config_dict property returns parsed JSON."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1", "param2": 123},
        )

        config_dict = config.config_dict
        assert isinstance(config_dict, dict)
        assert config_dict["param1"] == "value1"
        assert config_dict["param2"] == 123

    def test_str_representation(self):
        """Test string representation."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        str_repr = str(config)
        assert "Test Config" in str_repr or "testuser" in str_repr
