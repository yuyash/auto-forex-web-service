"""Integration tests for market admin."""

import pytest
from django.contrib.admin.sites import site

from apps.market.models import (
    CeleryTaskStatus,
    MarketEvent,
    OandaAccounts,
    OandaApiHealthStatus,
)


@pytest.mark.django_db
class TestMarketAdminIntegration:
    """Integration tests for market admin."""

    def test_all_models_registered(self) -> None:
        """Test that all models are registered with admin."""
        # Check that models are registered
        assert OandaAccounts in site._registry
        assert MarketEvent in site._registry
        assert CeleryTaskStatus in site._registry
        assert OandaApiHealthStatus in site._registry

    def test_oanda_account_admin_list_display(self) -> None:
        """Test OandaAccountAdmin list_display configuration."""
        admin_class = site._registry[OandaAccounts]

        assert "user" in admin_class.list_display
        assert "account_id" in admin_class.list_display
        assert "api_type" in admin_class.list_display
        assert "balance" in admin_class.list_display

    def test_oanda_account_admin_excludes_api_token(self) -> None:
        """Test that api_token is excluded from admin."""
        admin_class = site._registry[OandaAccounts]

        assert admin_class.exclude is not None
        assert "api_token" in admin_class.exclude

    def test_market_event_admin_list_display(self) -> None:
        """Test MarketEventAdmin list_display configuration."""
        admin_class = site._registry[MarketEvent]

        assert "event_type" in admin_class.list_display
        assert "category" in admin_class.list_display
        assert "severity" in admin_class.list_display

    def test_celery_task_status_admin_list_display(self) -> None:
        """Test CeleryTaskStatusAdmin list_display configuration."""
        admin_class = site._registry[CeleryTaskStatus]

        assert "task_name" in admin_class.list_display
        assert "instance_key" in admin_class.list_display
        assert "status" in admin_class.list_display

    def test_health_status_admin_readonly(self) -> None:
        """Test that health status admin is read-only."""
        from unittest.mock import MagicMock

        admin_class = site._registry[OandaApiHealthStatus]

        # Should not allow adding
        mock_request = MagicMock()
        assert admin_class.has_add_permission(mock_request) is False
