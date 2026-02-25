"""Unit tests for trading signals."""

from unittest.mock import MagicMock, patch

from apps.trading.signals import reset_orphaned_tasks


class TestResetOrphanedTasks:
    """Test legacy reset_orphaned_tasks no-op behavior."""

    def test_noop_for_non_trading_sender(self):
        sender = MagicMock()
        sender.name = "apps.accounts"
        with patch("apps.trading.signals.logger") as mock_logger:
            reset_orphaned_tasks(sender=sender)
            mock_logger.info.assert_called_once()

    def test_noop_for_trading_sender(self):
        sender = MagicMock()
        sender.name = "apps.trading"
        with patch("apps.trading.signals.logger") as mock_logger:
            reset_orphaned_tasks(sender=sender)
            mock_logger.info.assert_called_once()
