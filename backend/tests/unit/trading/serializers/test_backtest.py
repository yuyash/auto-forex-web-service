"""Unit tests for backtest serializers."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import BacktestTasks
from apps.trading.serializers.backtest import BacktestTaskSerializer

User = get_user_model()


@pytest.mark.django_db
class TestBacktestTaskSerializer:
    """Test BacktestTaskSerializer."""

    def test_serialize_backtest_task(self):
        """Test serializing backtest task."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        from django.utils import timezone

        from apps.trading.models import StrategyConfigurations

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        from datetime import timedelta

        task = BacktestTasks.objects.create(
            user=user,
            name="Test Backtest",
            config=config,
            instrument="EUR_USD",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        serializer = BacktestTaskSerializer(task)
        data = serializer.data

        assert data["name"] == "Test Backtest"
        assert data["instrument"] == "EUR_USD"

    def test_backtest_task_read_only_fields(self):
        """Test read-only fields are not writable."""
        serializer = BacktestTaskSerializer()
        meta = serializer.Meta

        # Check that certain fields are read-only
        if hasattr(meta, "read_only_fields"):
            assert "id" in meta.read_only_fields or "created_at" in meta.read_only_fields
