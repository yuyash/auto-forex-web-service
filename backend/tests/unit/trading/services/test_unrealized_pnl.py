"""Unit tests for trading.services.unrealized_pnl module."""

from decimal import Decimal
from unittest.mock import patch

from apps.trading.services.unrealized_pnl import update_unrealized_pnl


class TestUpdateUnrealizedPnl:
    @patch("apps.trading.services.unrealized_pnl.Position")
    def test_basic_call(self, mock_pos):
        mock_qs = mock_pos.objects.filter.return_value
        mock_qs.update.return_value = 3

        result = update_unrealized_pnl(
            task_type="trading",
            task_id="abc-123",
            current_price=Decimal("1.12345"),
        )

        assert result == 3
        mock_pos.objects.filter.assert_called_once()
        mock_qs.update.assert_called_once()

    @patch("apps.trading.services.unrealized_pnl.Position")
    def test_filters_include_celery_task_id(self, mock_pos):
        mock_qs = mock_pos.objects.filter.return_value
        mock_qs.update.return_value = 0

        update_unrealized_pnl(
            task_type="backtest",
            task_id="def-456",
            current_price=Decimal("1.00"),
            execution_id="celery-xyz",
        )

        filter_kwargs = mock_pos.objects.filter.call_args[1]
        assert filter_kwargs["execution_id"] == "celery-xyz"

    @patch("apps.trading.services.unrealized_pnl.Position")
    def test_filters_include_execution_run_id(self, mock_pos):
        mock_qs = mock_pos.objects.filter.return_value
        mock_qs.update.return_value = 0

        update_unrealized_pnl(
            task_type="trading",
            task_id="ghi-789",
            current_price=Decimal("1.00"),
            execution_id=5,
        )

        filter_kwargs = mock_pos.objects.filter.call_args[1]
        assert filter_kwargs["execution_id"] == 5

    @patch("apps.trading.services.unrealized_pnl.Position")
    def test_no_optional_filters(self, mock_pos):
        mock_qs = mock_pos.objects.filter.return_value
        mock_qs.update.return_value = 0

        update_unrealized_pnl(
            task_type="trading",
            task_id="jkl-000",
            current_price=Decimal("1.50"),
        )

        filter_kwargs = mock_pos.objects.filter.call_args[1]
        assert "execution_id" not in filter_kwargs
