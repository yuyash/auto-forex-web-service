"""Unit tests for trading urls."""

from django.urls import reverse


class TestTradingUrls:
    """Test trading URL configuration."""

    def test_app_name(self):
        from apps.trading.urls import app_name

        assert app_name == "trading"

    def test_strategy_list_url(self):
        url = reverse("trading:strategy_list")
        assert url == "/api/trading/strategies/"

    def test_strategy_defaults_url(self):
        url = reverse("trading:strategy_defaults", args=["floor"])
        assert url == "/api/trading/strategies/floor/defaults/"

    def test_strategy_config_list_create_url(self):
        url = reverse("trading:strategy_config_list_create")
        assert url == "/api/trading/strategy-configs/"

    def test_backtest_task_list_url(self):
        url = reverse("trading:backtest-task-list")
        assert "/api/trading/tasks/backtest/" in url

    def test_trading_task_list_url(self):
        url = reverse("trading:trading-task-list")
        assert "/api/trading/tasks/trading/" in url
