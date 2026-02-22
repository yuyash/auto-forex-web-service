"""Unit tests for trading serializers backtest."""

from unittest.mock import MagicMock

from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)


class TestBacktestTaskSerializer:
    """Test BacktestTaskSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        assert "data_source" in fields
        assert "start_time" in fields
        assert "end_time" in fields
        assert "initial_balance" in fields
        assert "progress" in fields
        assert "current_tick" in fields

    def test_get_progress_non_running(self):
        serializer = BacktestTaskSerializer()
        obj = MagicMock()
        obj.status = "stopped"
        assert serializer.get_progress(obj) == 0

    def test_get_progress_no_celery_id(self):
        serializer = BacktestTaskSerializer()
        obj = MagicMock()
        obj.status = "running"
        obj.celery_task_id = None
        assert serializer.get_progress(obj) == 0


class TestBacktestTaskListSerializer:
    """Test BacktestTaskListSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskListSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        assert "data_source" in fields

    def test_get_progress_non_running(self):
        serializer = BacktestTaskListSerializer()
        obj = MagicMock()
        obj.status = "completed"
        assert serializer.get_progress(obj) == 0


class TestBacktestTaskCreateSerializer:
    """Test BacktestTaskCreateSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskCreateSerializer.Meta.fields
        assert "name" in fields
        assert "config" in fields
        assert "data_source" in fields
        assert "start_time" in fields
        assert "end_time" in fields
