"""Unit tests for trading admin."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

from apps.trading.admin import (
    BacktestTasksAdmin,
    StrategyConfigurationsAdmin,
    TradingTasksAdmin,
)
from apps.trading.models import (
    BacktestTasks,
    StrategyConfigurations,
    TradingTasks,
)

User = get_user_model()


@pytest.mark.django_db
class TestBacktestTasksAdmin:
    """Test BacktestTasksAdmin."""

    def test_backtest_task_admin_registered(self):
        """Test BacktestTasks is registered in admin."""
        assert BacktestTasks in admin.site._registry
        assert isinstance(admin.site._registry[BacktestTasks], BacktestTasksAdmin)

    def test_backtest_task_admin_list_display(self):
        """Test list_display is configured."""
        admin_instance = BacktestTasksAdmin(BacktestTasks, admin.site)
        assert hasattr(admin_instance, "list_display")
        assert len(admin_instance.list_display) > 0

    def test_backtest_task_admin_search_fields(self):
        """Test search_fields is configured."""
        admin_instance = BacktestTasksAdmin(BacktestTasks, admin.site)
        assert hasattr(admin_instance, "search_fields")


@pytest.mark.django_db
class TestTradingTasksAdmin:
    """Test TradingTasksAdmin."""

    def test_trading_task_admin_registered(self):
        """Test TradingTasks is registered in admin."""
        assert TradingTasks in admin.site._registry
        assert isinstance(admin.site._registry[TradingTasks], TradingTasksAdmin)

    def test_trading_task_admin_list_display(self):
        """Test list_display is configured."""
        admin_instance = TradingTasksAdmin(TradingTasks, admin.site)
        assert hasattr(admin_instance, "list_display")
        assert len(admin_instance.list_display) > 0


@pytest.mark.django_db
class TestStrategyConfigurationsAdmin:
    """Test StrategyConfigurationsAdmin."""

    def test_strategy_config_admin_registered(self):
        """Test StrategyConfigurations is registered in admin."""
        assert StrategyConfigurations in admin.site._registry
        assert isinstance(admin.site._registry[StrategyConfigurations], StrategyConfigurationsAdmin)

    def test_strategy_config_admin_list_display(self):
        """Test list_display is configured."""
        admin_instance = StrategyConfigurationsAdmin(StrategyConfigurations, admin.site)
        assert hasattr(admin_instance, "list_display")
        assert len(admin_instance.list_display) > 0
