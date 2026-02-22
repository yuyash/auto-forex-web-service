"""Unit tests for trading serializers task."""

from datetime import timedelta
from unittest.mock import MagicMock

from apps.trading.serializers.task import (
    TaskLogSerializer,
    TaskSerializer,
)


class TestTaskSerializer:
    """Test TaskSerializer base class."""

    def test_meta_fields(self):
        fields = TaskSerializer.Meta.fields
        assert "id" in fields
        assert "name" in fields
        assert "status" in fields
        assert "duration" in fields
        assert "task_type" in fields

    def test_get_duration_with_value(self):
        serializer = TaskSerializer()
        obj = MagicMock()
        obj.duration = timedelta(seconds=120)
        assert serializer.get_duration(obj) == 120.0

    def test_get_duration_none(self):
        serializer = TaskSerializer()
        obj = MagicMock()
        obj.duration = None
        assert serializer.get_duration(obj) is None

    def test_get_task_type_backtest(self):
        from apps.trading.models import BacktestTask

        serializer = TaskSerializer()
        obj = MagicMock(spec=BacktestTask)
        result = serializer.get_task_type(obj)
        assert result == "backtest"

    def test_get_task_type_trading(self):
        from apps.trading.models import TradingTask

        serializer = TaskSerializer()
        obj = MagicMock(spec=TradingTask)
        result = serializer.get_task_type(obj)
        assert result == "trading"


class TestTaskLogSerializer:
    """Test TaskLogSerializer."""

    def test_meta_fields(self):
        fields = TaskLogSerializer.Meta.fields
        assert "id" in fields
        assert "task_type" in fields
        assert "level" in fields
        assert "message" in fields
        assert "details" in fields

    def test_read_only_fields(self):
        assert "id" in TaskLogSerializer.Meta.read_only_fields
        assert "timestamp" in TaskLogSerializer.Meta.read_only_fields
