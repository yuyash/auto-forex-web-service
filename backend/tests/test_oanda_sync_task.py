"""
Unit tests for OANDA Synchronization Task.

Tests cover:
- Order reconciliation with mocked OANDA API
- Position reconciliation with mocked OANDA API
- Handling of discrepancies (missed fills, cancellations)
- Celery task scheduling and execution

Requirements: 8.3, 9.1
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from accounts.models import OandaAccount
from trading.models import Order, Position, Strategy
from trading.oanda_sync_task import OrderReconciler, PositionReconciler, oanda_sync_task


@pytest.fixture
def mock_oanda_account(db):
    """Create a mock OANDA account for testing"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )

    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token_12345",
        api_type="practice",
        balance=10000.00,
        is_active=True,
    )
    return account


@pytest.fixture
def mock_strategy(db, mock_oanda_account):
    """Create a mock strategy for testing"""
    strategy = Strategy.objects.create(
        account=mock_oanda_account,
        strategy_type="test_strategy",
        is_active=True,
        config={"lot_size": 1000},
        instrument="EUR_USD",
    )
    return strategy


@pytest.mark.django_db
class TestOrderReconciler:
    """Test OrderReconciler class"""

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_order_reconciliation_with_cancelled_order(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account, mock_strategy
    ):
        """Test order reconciliation when order is cancelled in OANDA"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Create a pending order in database
        order = Order.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            order_id="12345",
            instrument="EUR_USD",
            order_type="limit",
            direction="long",
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            status="pending",
        )

        # Mock OANDA API to return empty list (order no longer exists)
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.orders = []
        mock_api.order.list_pending.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = OrderReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        assert result["discrepancies_found"] == 1
        assert result["orders_updated"] == 1

        # Verify order was marked as cancelled
        order.refresh_from_db()
        assert order.status == "cancelled"

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_order_reconciliation_with_missing_order(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account
    ):
        """Test order reconciliation when order exists in OANDA but not in database"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Mock OANDA API to return an order
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200

        mock_order = MagicMock()
        mock_order.dict.return_value = {
            "id": "67890",
            "type": "LIMIT",
            "instrument": "GBP_USD",
            "units": "2000",
            "price": "1.2500",
        }
        mock_response.orders = [mock_order]
        mock_api.order.list_pending.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = OrderReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        assert result["discrepancies_found"] == 1
        assert result["orders_updated"] == 1

        # Verify order was created in database
        created_order = Order.objects.get(order_id="67890")
        assert created_order.instrument == "GBP_USD"
        assert created_order.order_type == "limit"
        assert created_order.units == Decimal("2000")
        assert created_order.price == Decimal("1.2500")
        assert created_order.status == "pending"

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_order_reconciliation_with_no_discrepancies(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account, mock_strategy
    ):
        """Test order reconciliation when orders match"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Create a pending order in database
        Order.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            order_id="12345",
            instrument="EUR_USD",
            order_type="limit",
            direction="long",
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            status="pending",
        )

        # Mock OANDA API to return the same order
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200

        mock_order = MagicMock()
        mock_order.dict.return_value = {
            "id": "12345",
            "type": "LIMIT",
            "instrument": "EUR_USD",
            "units": "1000",
            "price": "1.1000",
        }
        mock_response.orders = [mock_order]
        mock_api.order.list_pending.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = OrderReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        assert result["discrepancies_found"] == 0
        assert result["orders_updated"] == 0

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_order_reconciliation_handles_api_error(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account
    ):
        """Test order reconciliation handles OANDA API errors gracefully"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Mock OANDA API to raise an exception
        mock_api = MagicMock()
        mock_api.order.list_pending.side_effect = Exception("API connection failed")
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = OrderReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify error is handled gracefully - the reconciler catches exceptions
        # and returns empty list, so reconciliation still succeeds but with no updates
        assert result["success"] is True
        assert result["discrepancies_found"] == 0
        assert result["orders_updated"] == 0


@pytest.mark.django_db
class TestPositionReconciler:
    """Test PositionReconciler class"""

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_position_reconciliation_with_closed_position(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account, mock_strategy
    ):
        """Test position reconciliation when position is closed in OANDA"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Create an open position in database
        position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="pos_12345",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("50.00"),
        )

        # Mock OANDA API to return empty list (position no longer exists)
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.positions = []
        mock_api.position.list_open.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = PositionReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        assert result["discrepancies_found"] == 1
        assert result["positions_updated"] == 1

        # Verify position was marked as closed
        position.refresh_from_db()
        assert position.closed_at is not None
        assert position.realized_pnl == Decimal("50.00")

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_position_reconciliation_with_missing_position(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account
    ):
        """Test position reconciliation when position exists in OANDA but not in database"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Mock OANDA API to return a position
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200

        mock_position = MagicMock()
        mock_position.dict.return_value = {
            "instrument": "GBP_USD",
            "long": {
                "units": "2000",
                "averagePrice": "1.2500",
                "unrealizedPL": "100.00",
            },
            "short": {
                "units": "0",
                "averagePrice": "0",
                "unrealizedPL": "0",
            },
        }
        mock_response.positions = [mock_position]
        mock_api.position.list_open.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = PositionReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        assert result["discrepancies_found"] == 1
        assert result["positions_updated"] == 1

        # Verify position was created in database
        created_positions = Position.objects.filter(
            account=mock_oanda_account, instrument="GBP_USD"
        )
        assert created_positions.count() == 1
        created_position = created_positions.first()
        assert created_position is not None
        assert created_position.direction == "long"
        assert created_position.units == Decimal("2000")
        assert created_position.entry_price == Decimal("1.2500")
        assert created_position.unrealized_pnl == Decimal("100.00")

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_position_reconciliation_updates_details(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account, mock_strategy
    ):
        """Test position reconciliation updates position details when they differ"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Create an open position in database with outdated values
        position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="pos_12345",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("50.00"),
        )

        # Mock OANDA API to return position with updated values
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200

        mock_position = MagicMock()
        mock_position.dict.return_value = {
            "instrument": "EUR_USD",
            "long": {
                "units": "1500",  # Units increased
                "averagePrice": "1.1025",  # Average price changed
                "unrealizedPL": "75.00",  # P&L changed
            },
            "short": {
                "units": "0",
                "averagePrice": "0",
                "unrealizedPL": "0",
            },
        }
        mock_response.positions = [mock_position]
        mock_api.position.list_open.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = PositionReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        # The reconciler counts multiple field changes as separate discrepancies
        assert result["discrepancies_found"] >= 1
        assert result["positions_updated"] == 1

        # Verify position was updated
        position.refresh_from_db()
        assert position.units == Decimal("1500")
        assert position.current_price == Decimal("1.1025")
        assert position.unrealized_pnl == Decimal("75.00")

    @patch("accounts.models.OandaAccount.get_api_token")
    @patch("trading.oanda_sync_task.v20.Context")
    def test_position_reconciliation_with_no_discrepancies(
        self, mock_v20_context, mock_get_api_token, mock_oanda_account, mock_strategy
    ):
        """Test position reconciliation when positions match"""
        # Mock get_api_token to return plain token
        mock_get_api_token.return_value = "test_token_12345"

        # Create an open position in database
        Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="pos_12345",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("50.00"),
        )

        # Mock OANDA API to return the same position
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200

        mock_position = MagicMock()
        mock_position.dict.return_value = {
            "instrument": "EUR_USD",
            "long": {
                "units": "1000",
                "averagePrice": "1.1050",
                "unrealizedPL": "50.00",
            },
            "short": {
                "units": "0",
                "averagePrice": "0",
                "unrealizedPL": "0",
            },
        }
        mock_response.positions = [mock_position]
        mock_api.position.list_open.return_value = mock_response
        mock_v20_context.return_value = mock_api

        # Run reconciliation
        reconciler = PositionReconciler(mock_oanda_account)
        result = reconciler.reconcile()

        # Verify results
        assert result["success"] is True
        assert result["discrepancies_found"] == 0
        assert result["positions_updated"] == 0


@pytest.mark.django_db
class TestOandaSyncTask:
    """Test oanda_sync_task Celery task"""

    @patch("trading.oanda_sync_task.sync_account_task")
    def test_sync_task_processes_all_active_accounts(
        self, mock_sync_account_task, mock_oanda_account
    ):
        """Test sync task processes all active accounts"""
        # Create another active account
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )
        account2 = OandaAccount.objects.create(
            user=user2,
            account_id="001-001-7654321-001",
            api_type="practice",
            balance=20000.00,
            is_active=True,
        )
        account2.set_api_token("test_token_67890")
        account2.save()

        # Mock the async task result (fire-and-forget, no .get() call)
        mock_result = Mock()
        mock_result.id = "task-id-123"
        mock_sync_account_task.apply_async.return_value = mock_result

        # Run sync task
        result = oanda_sync_task()

        # Verify results (fire-and-forget pattern)
        assert result["success"] is True
        assert result["accounts_synced"] == 2
        assert result["tasks_triggered"] == 2
        assert len(result["task_ids"]) == 2
        assert len(result["errors"]) == 0

        # Verify sync_account_task was called for each account
        assert mock_sync_account_task.apply_async.call_count == 2

    @patch("trading.oanda_sync_task.sync_account_task")
    def test_sync_task_handles_reconciliation_errors(
        self, mock_sync_account_task, mock_oanda_account
    ):
        """Test sync task handles reconciliation errors gracefully"""
        # Mock the async task to raise an exception during apply_async
        mock_sync_account_task.apply_async.side_effect = Exception("Task queue error")

        # Run sync task
        result = oanda_sync_task()

        # Verify results (fire-and-forget pattern - errors during task triggering)
        assert result["success"] is False  # Task fails when triggering fails
        assert result["accounts_synced"] == 0  # No tasks successfully triggered
        assert len(result["errors"]) >= 1
        assert "Task queue error" in result["errors"][0]

    @patch("trading.oanda_sync_task.PositionReconciler")
    @patch("trading.oanda_sync_task.OrderReconciler")
    def test_sync_task_skips_inactive_accounts(
        self, mock_order_reconciler_class, mock_position_reconciler_class, mock_oanda_account
    ):
        """Test sync task skips inactive accounts"""
        # Mark account as inactive
        mock_oanda_account.is_active = False
        mock_oanda_account.save()

        # Run sync task
        result = oanda_sync_task()

        # Verify no accounts were synced
        assert result["accounts_synced"] == 0
        assert mock_order_reconciler_class.call_count == 0
        assert mock_position_reconciler_class.call_count == 0

    @patch("trading.oanda_sync_task.OandaAccount.objects.filter")
    def test_sync_task_handles_database_errors(self, mock_filter):
        """Test sync task handles database errors gracefully"""
        # Mock database to raise an exception
        mock_filter.side_effect = Exception("Database connection failed")

        # Run sync task
        result = oanda_sync_task()

        # Verify error is handled
        assert result["success"] is False
        assert len(result["errors"]) == 1
        assert "Database connection failed" in result["errors"][0]
