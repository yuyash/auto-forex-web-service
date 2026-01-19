"""Extended integration tests for supervisor task."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.tasks.supervisor import TickSupervisorRunner


@pytest.mark.django_db
class TestTickSupervisorRunnerExtendedIntegration:
    """Extended integration tests for TickSupervisorRunner."""

    @patch("apps.market.tasks.supervisor.redis_client")
    def test_get_or_initialize_account_no_accounts(self, mock_redis: Any) -> None:
        """Test getting account when none exist."""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis.return_value = mock_client

        runner = TickSupervisorRunner()

        account = runner._get_or_initialize_account(mock_client)

        assert account is None

    @patch("apps.market.tasks.supervisor.redis_client")
    def test_get_or_initialize_account_with_live_account(self, mock_redis: Any, user: Any) -> None:
        """Test getting account when LIVE account exists."""
        # Create LIVE account
        live_account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
        )

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis.return_value = mock_client

        runner = TickSupervisorRunner()

        account = runner._get_or_initialize_account(mock_client)

        assert account is not None
        assert account.pk == live_account.pk
        assert account.api_type == ApiType.LIVE

    @patch("apps.market.tasks.supervisor.redis_client")
    def test_get_or_initialize_account_with_cached_id(self, mock_redis: Any, user: Any) -> None:
        """Test getting account from cached ID."""
        # Create LIVE account
        live_account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type=ApiType.LIVE,
        )

        mock_client = MagicMock()
        mock_client.get.return_value = str(live_account.pk)
        mock_redis.return_value = mock_client

        runner = TickSupervisorRunner()

        account = runner._get_or_initialize_account(mock_client)

        assert account is not None
        assert account.pk == live_account.pk

    @patch("apps.market.tasks.supervisor.redis_client")
    def test_ensure_tasks_running(self, mock_redis: Any) -> None:
        """Test ensuring tasks are running."""
        mock_client = MagicMock()
        mock_client.exists.return_value = False
        mock_redis.return_value = mock_client

        runner = TickSupervisorRunner()

        # Should not raise exception
        runner._ensure_tasks_running(
            client=mock_client,
            account_pk=1,
        )
