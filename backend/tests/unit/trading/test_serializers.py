from __future__ import annotations

import pytest
from rest_framework.test import APIRequestFactory

from apps.market.models import OandaAccount
from apps.trading.models import StrategyConfig
from apps.trading.serializers import TradingTaskCreateSerializer


@pytest.mark.django_db
class TestTradingTaskCreateSerializer:
    def test_validate_config_must_belong_to_user(self, test_user):
        other_user = type(test_user).objects.create_user(
            username="other",
            email="other@example.com",
            password="Pass123!",
        )
        other_user.email_verified = True
        other_user.save(update_fields=["email_verified"])

        config = StrategyConfig.objects.create(
            user=other_user,
            name="cfg",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )

        factory = APIRequestFactory()
        request = factory.post("/api/trading/trading-tasks/", {})
        request.user = test_user

        serializer = TradingTaskCreateSerializer(context={"request": request})
        with pytest.raises(Exception):
            serializer.validate_config(config)

    def test_validate_oanda_account_requires_active(self, test_user):
        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-002",
            api_token="",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=False,
            is_default=False,
        )
        account.set_api_token("token")
        account.save(update_fields=["api_token"])

        factory = APIRequestFactory()
        request = factory.post("/api/trading/trading-tasks/", {})
        request.user = test_user

        serializer = TradingTaskCreateSerializer(context={"request": request})
        with pytest.raises(Exception):
            serializer.validate_oanda_account(account)
