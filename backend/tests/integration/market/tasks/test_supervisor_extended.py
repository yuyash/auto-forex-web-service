"""Extended integration tests for supervisor task."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.tasks.supervisor import TickSupervisorRunner
from apps.trading.enums import TaskStatus
from apps.trading.models import StrategyConfiguration, TradingTask


@pytest.mark.django_db
class TestTickSupervisorRunnerExtendedIntegration:
    """Extended integration tests for TickSupervisorRunner."""

    def test_target_account_pks_returns_only_active_trading_accounts(self, user: Any) -> None:
        practice = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            api_token="token-1",
        )
        live = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
            api_token="token-2",
        )
        unused = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
            api_token="token-3",
        )
        config = StrategyConfiguration.objects.create(
            user=user,
            name="Config",
            strategy_type="snowball",
            parameters={"instrument": "USD_JPY"},
        )
        TradingTask.objects.create(
            user=user,
            config=config,
            oanda_account=practice,
            name="Practice task",
            instrument="USD_JPY",
            status=TaskStatus.RUNNING,
        )
        TradingTask.objects.create(
            user=user,
            config=config,
            oanda_account=live,
            name="Live task",
            instrument="USD_JPY",
            status=TaskStatus.STARTING,
        )
        TradingTask.objects.create(
            user=user,
            config=config,
            oanda_account=unused,
            name="Stopped task",
            instrument="USD_JPY",
            status=TaskStatus.STOPPED,
        )

        runner = TickSupervisorRunner()

        assert runner._target_account_pks() == [practice.pk, live.pk]

    @patch("apps.market.tasks.publish_oanda_ticks.delay")
    def test_ensure_publishers_running(
        self,
        mock_pub_delay: Any,
    ) -> None:
        mock_client = MagicMock()
        mock_client.exists.side_effect = [False, True]

        runner = TickSupervisorRunner()
        runner._ensure_publishers_running(client=mock_client, account_pks=[1, 2])

        mock_pub_delay.assert_called_once_with(account_id=1)

    @patch("apps.market.tasks.subscribe_ticks_to_db.delay")
    def test_ensure_subscriber_running(self, mock_sub_delay: Any) -> None:
        mock_client = MagicMock()
        mock_client.exists.return_value = False

        runner = TickSupervisorRunner()
        runner._ensure_subscriber_running(mock_client)

        mock_sub_delay.assert_called_once()
