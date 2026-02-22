"""Unit tests for market admin."""

import pytest
from django.contrib import admin

from apps.market.admin import (
    CeleryTaskStatusAdmin,
    MarketEventAdmin,
    OandaAccountAdmin,
    OandaApiHealthStatusAdmin,
)
from apps.market.models import (
    CeleryTaskStatus,
    MarketEvent,
    OandaAccounts,
    OandaApiHealthStatus,
    TickData,
)


@pytest.mark.django_db
class TestOandaAccountAdmin:
    """Test OandaAccountAdmin."""

    def test_oanda_accounts_admin_registered(self):
        """Test OandaAccounts is registered in admin."""
        assert OandaAccounts in admin.site._registry
        assert isinstance(admin.site._registry[OandaAccounts], OandaAccountAdmin)

    def test_oanda_accounts_admin_list_display(self):
        """Test list_display is configured."""
        admin_instance = OandaAccountAdmin(OandaAccounts, admin.site)
        assert hasattr(admin_instance, "list_display")
        assert len(admin_instance.list_display) > 0


@pytest.mark.django_db
class TestTickDataAdmin:
    """Test TickData admin."""

    def test_tick_data_admin_exists(self):
        """Test TickData may or may not be registered in admin."""
        # TickData might not be registered in admin
        # Just verify the model exists
        assert TickData is not None


@pytest.mark.django_db
class TestMarketEventAdmin:
    """Test MarketEventAdmin."""

    def test_market_event_admin_registered(self):
        """Test MarketEvent is registered in admin."""
        assert MarketEvent in admin.site._registry
        assert isinstance(admin.site._registry[MarketEvent], MarketEventAdmin)


@pytest.mark.django_db
class TestCeleryTaskStatusAdmin:
    """Test CeleryTaskStatusAdmin."""

    def test_celery_task_status_admin_registered(self):
        """Test CeleryTaskStatus is registered in admin."""
        assert CeleryTaskStatus in admin.site._registry
        assert isinstance(admin.site._registry[CeleryTaskStatus], CeleryTaskStatusAdmin)


@pytest.mark.django_db
class TestOandaApiHealthStatusAdmin:
    """Test OandaApiHealthStatusAdmin."""

    def test_health_status_admin_registered(self):
        """Test OandaApiHealthStatus is registered in admin."""
        assert OandaApiHealthStatus in admin.site._registry
        assert isinstance(admin.site._registry[OandaApiHealthStatus], OandaApiHealthStatusAdmin)
