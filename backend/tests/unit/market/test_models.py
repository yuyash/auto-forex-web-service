from __future__ import annotations

from decimal import Decimal

import pytest

from apps.market.models import CeleryTaskStatus, OandaAccount, TickData


@pytest.mark.django_db
class TestMarketModels:
    def test_celery_task_status_str(self) -> None:
        row = CeleryTaskStatus.objects.create(task_name="t", instance_key="k")
        assert "t" in str(row)
        assert "k" in str(row)

    def test_tickdata_spread_property(self) -> None:
        tick = TickData(
            instrument="EUR_USD",
            timestamp="2025-01-01T00:00:00Z",
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
            mid=Decimal("1.10005"),
        )
        assert tick.spread == Decimal("0.00010")

    def test_oanda_account_token_strips_whitespace(self, test_user) -> None:
        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-123",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
        )
        account.set_api_token(" token-with-newline\n")
        account.save(update_fields=["api_token"])

        assert account.get_api_token() == "token-with-newline"
