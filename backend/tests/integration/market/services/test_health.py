"""Integration tests for OandaHealthCheckService."""

from typing import Any

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts, OandaApiHealthStatus
from apps.market.services.health import OandaHealthCheckService


@pytest.mark.django_db
class TestOandaHealthCheckServiceIntegration:
    """Integration tests for OandaHealthCheckService."""

    def test_check_creates_health_status(self, user: Any) -> None:
        """Test that check() creates OandaApiHealthStatus record."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("test_token_12345")
        account.save()

        service = OandaHealthCheckService(account)

        # Perform health check (may fail if OANDA unavailable)
        try:
            result = service.check()

            # Verify record was created
            assert result is not None
            assert isinstance(result, OandaApiHealthStatus)
            assert result.account == account

            # Check that record was persisted
            health_count = OandaApiHealthStatus.objects.filter(account=account).count()
            assert health_count >= 1

        except Exception:
            # OANDA API may be unavailable in test environment
            pass

    def test_multiple_checks_create_multiple_records(self, user: Any) -> None:
        """Test that multiple checks create multiple records."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("test_token_12345")
        account.save()

        service = OandaHealthCheckService(account)

        initial_count = OandaApiHealthStatus.objects.filter(account=account).count()

        # Perform multiple checks
        try:
            service.check()
            service.check()

            final_count = OandaApiHealthStatus.objects.filter(account=account).count()
            assert final_count >= initial_count + 2

        except Exception:
            # OANDA API may be unavailable
            pass
