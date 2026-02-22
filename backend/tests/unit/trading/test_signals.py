"""Unit tests for trading signals."""

from unittest.mock import MagicMock, patch

from apps.trading.enums import TaskStatus
from apps.trading.signals import reset_orphaned_tasks


class TestResetOrphanedTasks:
    """Test reset_orphaned_tasks signal handler."""

    def test_skips_non_trading_app(self):
        """Signal should skip if sender is not the trading app."""
        sender = MagicMock()
        sender.name = "apps.accounts"
        with patch("apps.trading.models.BacktestTask") as mock_bt:
            reset_orphaned_tasks(sender=sender)
            mock_bt.objects.filter.assert_not_called()

    @patch("apps.trading.models.TradingTask")
    @patch("apps.trading.models.BacktestTask")
    def test_resets_orphaned_backtest_tasks(self, mock_bt, mock_tt):
        """Orphaned backtest tasks should be reset to STOPPED."""
        sender = MagicMock()
        sender.name = "apps.trading"

        mock_bt.objects.filter.return_value.count.return_value = 2
        mock_bt.objects.filter.return_value.update.return_value = 2
        mock_tt.objects.filter.return_value.count.return_value = 0

        reset_orphaned_tasks(sender=sender)

        mock_bt.objects.filter.assert_called()
        mock_bt.objects.filter.return_value.update.assert_called_once_with(
            status=TaskStatus.STOPPED,
            celery_task_id=None,
            error_message="Task was interrupted by server restart",
        )

    @patch("apps.trading.models.TradingTask")
    @patch("apps.trading.models.BacktestTask")
    def test_resets_orphaned_trading_tasks(self, mock_bt, mock_tt):
        """Orphaned trading tasks should be reset to STOPPED."""
        sender = MagicMock()
        sender.name = "apps.trading"

        mock_bt.objects.filter.return_value.count.return_value = 0
        mock_tt.objects.filter.return_value.count.return_value = 3
        mock_tt.objects.filter.return_value.update.return_value = 3

        reset_orphaned_tasks(sender=sender)

        mock_tt.objects.filter.return_value.update.assert_called_once_with(
            status=TaskStatus.STOPPED,
            celery_task_id=None,
            error_message="Task was interrupted by server restart",
        )

    @patch("apps.trading.models.TradingTask")
    @patch("apps.trading.models.BacktestTask")
    def test_logs_info_when_no_orphaned_tasks(self, mock_bt, mock_tt):
        """Should log info when no orphaned tasks found."""
        sender = MagicMock()
        sender.name = "apps.trading"

        mock_bt.objects.filter.return_value.count.return_value = 0
        mock_tt.objects.filter.return_value.count.return_value = 0

        with patch("apps.trading.signals.logger") as mock_logger:
            reset_orphaned_tasks(sender=sender)
            mock_logger.info.assert_called_once_with("No orphaned tasks found on startup")
