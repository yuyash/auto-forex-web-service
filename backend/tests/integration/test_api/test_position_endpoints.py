"""
Integration tests for position API endpoints.

Tests position creation, retrieval, update, closure, listing, and filtering.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.urls import reverse

from apps.market.services.oanda import OpenTrade, OrderDirection
from tests.integration.base import APIIntegrationTestCase
from tests.integration.factories import OandaAccountFactory


class PositionListCreateTests(APIIntegrationTestCase):
    """Tests for position list and create endpoints."""

    @patch("apps.market.views.OandaService")
    def test_list_positions_success(self, mock_service_class: MagicMock) -> None:
        """Test listing positions from OANDA API."""
        account = OandaAccountFactory(user=self.user)

        # Mock OANDA service to return open trades
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_trades = [
            OpenTrade(
                trade_id="1",
                instrument="EUR_USD",
                direction=OrderDirection.LONG,
                units=Decimal("1000"),
                entry_price=Decimal("1.08950"),
                unrealized_pnl=Decimal("25.50"),
                open_time=None,
                state="OPEN",
                account_id=account.account_id,  # ty:ignore[invalid-argument-type]
            ),
            OpenTrade(
                trade_id="2",
                instrument="GBP_USD",
                direction=OrderDirection.SHORT,
                units=Decimal("500"),
                entry_price=Decimal("1.25000"),
                unrealized_pnl=Decimal("-10.25"),
                open_time=None,
                state="OPEN",
                account_id=account.account_id,  # ty:ignore[invalid-argument-type]
            ),
        ]
        mock_service.get_open_trades.return_value = mock_trades

        url = reverse("market:position_list")
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("results", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["count"], 2)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["results"]), 2)  # ty:ignore[possibly-missing-attribute]

        # Verify position data structure
        position = response.data["results"][0]  # ty:ignore[possibly-missing-attribute]
        self.assertIn("id", position)
        self.assertIn("instrument", position)
        self.assertIn("direction", position)
        self.assertIn("units", position)
        self.assertIn("entry_price", position)
        self.assertIn("unrealized_pnl", position)
        self.assertIn("status", position)
        self.assertEqual(position["status"], "open")

    @patch("apps.market.views.OandaService")
    def test_list_positions_empty(self, mock_service_class: MagicMock) -> None:
        """Test listing positions when no positions exist."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_open_trades.return_value = []

        url = reverse("market:position_list")
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["results"]), 0)  # ty:ignore[possibly-missing-attribute]

    @patch("apps.market.views.OandaService")
    def test_list_positions_filter_by_instrument(self, mock_service_class: MagicMock) -> None:
        """Test filtering positions by instrument."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Mock returns only EUR_USD positions
        mock_trades = [
            OpenTrade(
                trade_id="1",
                instrument="EUR_USD",
                direction=OrderDirection.LONG,
                units=Decimal("1000"),
                entry_price=Decimal("1.08950"),
                unrealized_pnl=Decimal("25.50"),
                open_time=None,
                state="OPEN",
                account_id=account.account_id,  # ty:ignore[invalid-argument-type]
            ),
        ]
        mock_service.get_open_trades.return_value = mock_trades

        url = reverse("market:position_list")
        response = self.client.get(
            url,
            {
                "account_id": account.pk,  # type: ignore[attr-defined]
                "instrument": "EUR_USD",
            },
        )

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 1)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["results"][0]["instrument"], "EUR_USD")  # ty:ignore[possibly-missing-attribute]

    def test_list_positions_no_account_id(self) -> None:
        """Test listing positions without account_id uses all active accounts."""
        # Create multiple accounts
        OandaAccountFactory.create_batch(2, user=self.user, is_active=True)

        url = reverse("market:position_list")

        with patch("apps.market.views.OandaService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            mock_service.get_open_trades.return_value = []

            response = self.client.get(url)

            self.assert_response_success(response)  # type: ignore[arg-type]
            # Should have called OandaService twice (once per account)
            self.assertEqual(mock_service_class.call_count, 2)

    def test_list_positions_account_not_found(self) -> None:
        """Test listing positions with non-existent account returns 404."""
        url = reverse("market:position_list")
        response = self.client.get(url, {"account_id": 99999})

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_list_positions_account_belongs_to_other_user(self) -> None:
        """Test that users cannot list positions for accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)

        url = reverse("market:position_list")
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_list_positions_invalid_status(self) -> None:
        """Test listing positions with invalid status parameter."""
        account = OandaAccountFactory(user=self.user)

        url = reverse("market:position_list")
        response = self.client.get(
            url,
            {
                "account_id": account.pk,  # type: ignore[attr-defined]
                "status": "invalid",
            },
        )

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]

    def test_list_positions_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot list positions."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("market:position_list")

        response = self.client.get(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]

    @patch("apps.market.views.OandaService")
    def test_create_position_success(self, mock_service_class: MagicMock) -> None:
        """Test creating a new position via market order."""
        account = OandaAccountFactory(user=self.user)

        # Mock OANDA service
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_result = MagicMock()
        mock_result.order_id = "123"
        mock_result.instrument = "EUR_USD"
        mock_result.order_type.value = "MARKET"
        mock_result.units = Decimal("1000")
        mock_result.price = Decimal("1.08950")
        mock_result.state.value = "FILLED"
        mock_result.create_time = None
        mock_service.create_market_order.return_value = mock_result

        url = reverse("market:position_list")
        data = {
            "account_id": account.pk,  # type: ignore[attr-defined]
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response, status_code=201)  # ty:ignore[invalid-argument-type]
        self.assertIn("id", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["instrument"], "EUR_USD")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["type"], "MARKET")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["state"], "FILLED")  # ty:ignore[possibly-missing-attribute]

    @patch("apps.market.views.OandaService")
    def test_create_position_with_take_profit_stop_loss(
        self, mock_service_class: MagicMock
    ) -> None:
        """Test creating position with take profit and stop loss."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_result = MagicMock()
        mock_result.order_id = "123"
        mock_result.instrument = "EUR_USD"
        mock_result.order_type.value = "MARKET"
        mock_result.units = Decimal("1000")
        mock_result.price = Decimal("1.08950")
        mock_result.state.value = "FILLED"
        mock_result.create_time = None
        mock_service.create_market_order.return_value = mock_result

        url = reverse("market:position_list")
        data = {
            "account_id": account.pk,  # type: ignore[attr-defined]
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000",
            "take_profit": "1.09500",
            "stop_loss": "1.08500",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response, status_code=201)  # ty:ignore[invalid-argument-type]
        # Verify take_profit and stop_loss were passed to create_market_order
        call_args = mock_service.create_market_order.call_args
        self.assertIsNotNone(call_args)

    def test_create_position_missing_account_id(self) -> None:
        """Test creating position without account_id fails."""
        url = reverse("market:position_list")
        data = {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]

    def test_create_position_missing_required_fields(self) -> None:
        """Test creating position without required fields fails."""
        account = OandaAccountFactory(user=self.user)

        url = reverse("market:position_list")
        data = {
            "account_id": account.pk,  # type: ignore[attr-defined]
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]

    def test_create_position_account_not_found(self) -> None:
        """Test creating position with non-existent account returns 404."""
        url = reverse("market:position_list")
        data = {
            "account_id": 99999,
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_create_position_account_belongs_to_other_user(self) -> None:
        """Test that users cannot create positions for accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)

        url = reverse("market:position_list")
        data = {
            "account_id": account.pk,  # type: ignore[attr-defined]
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]


class PositionDetailTests(APIIntegrationTestCase):
    """Tests for position detail, update, and closure endpoints."""

    @patch("apps.market.views.OandaService")
    def test_retrieve_position_success(self, mock_service_class: MagicMock) -> None:
        """Test retrieving a specific position."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_trade = OpenTrade(
            trade_id="123",
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            entry_price=Decimal("1.08950"),
            unrealized_pnl=Decimal("25.50"),
            open_time=None,
            state="OPEN",
            account_id=account.account_id,  # ty:ignore[invalid-argument-type]
        )
        mock_service.get_open_trades.return_value = [mock_trade]

        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["id"], "123")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["instrument"], "EUR_USD")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["direction"], "long")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["units"], "1000")  # ty:ignore[possibly-missing-attribute]

    @patch("apps.market.views.OandaService")
    def test_retrieve_position_not_found(self, mock_service_class: MagicMock) -> None:
        """Test retrieving non-existent position returns 404."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_open_trades.return_value = []

        url = reverse("market:position_detail", kwargs={"position_id": "999"})
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_retrieve_position_missing_account_id(self) -> None:
        """Test retrieving position without account_id fails."""
        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        response = self.client.get(url)

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]

    def test_retrieve_position_account_not_found(self) -> None:
        """Test retrieving position with non-existent account returns 404."""
        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        response = self.client.get(url, {"account_id": 99999})

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_retrieve_position_account_belongs_to_other_user(self) -> None:
        """Test that users cannot retrieve positions for accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)

        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    @patch("apps.market.views.OandaService")
    def test_close_position_success(self, mock_service_class: MagicMock) -> None:
        """Test closing a position."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Mock get_open_trades to return the position
        mock_trade = OpenTrade(
            trade_id="123",
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            entry_price=Decimal("1.08950"),
            unrealized_pnl=Decimal("25.50"),
            open_time=None,
            state="OPEN",
            account_id=account.account_id,  # ty:ignore[invalid-argument-type]
        )
        mock_service.get_open_trades.return_value = [mock_trade]

        # Mock close_trade result
        mock_result = MagicMock()
        mock_result.order_id = "456"
        mock_result.instrument = "EUR_USD"
        mock_result.order_type.value = "MARKET"
        mock_result.direction.value = "long"
        mock_result.units = Decimal("1000")
        mock_result.price = Decimal("1.09000")
        mock_result.state.value = "FILLED"
        mock_result.fill_time = None
        mock_service.close_trade.return_value = mock_result

        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        data = {"account_id": account.pk}  # ty:ignore[unresolved-attribute]

        response = self.client.patch(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("message", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("details", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["details"]["id"], "456")  # ty:ignore[possibly-missing-attribute]

    @patch("apps.market.views.OandaService")
    def test_close_position_partial(self, mock_service_class: MagicMock) -> None:
        """Test partially closing a position."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_trade = OpenTrade(
            trade_id="123",
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            entry_price=Decimal("1.08950"),
            unrealized_pnl=Decimal("25.50"),
            open_time=None,
            state="OPEN",
            account_id=account.account_id,  # ty:ignore[invalid-argument-type]
        )
        mock_service.get_open_trades.return_value = [mock_trade]

        mock_result = MagicMock()
        mock_result.order_id = "456"
        mock_result.instrument = "EUR_USD"
        mock_result.order_type.value = "MARKET"
        mock_result.direction.value = "long"
        mock_result.units = Decimal("500")
        mock_result.price = Decimal("1.09000")
        mock_result.state.value = "FILLED"
        mock_result.fill_time = None
        mock_service.close_trade.return_value = mock_result

        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        data = {
            "account_id": account.pk,  # type: ignore[attr-defined]
            "units": "500",
        }

        response = self.client.patch(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]
        # Verify units parameter was passed to close_trade
        call_args = mock_service.close_trade.call_args
        self.assertIsNotNone(call_args)

    @patch("apps.market.views.OandaService")
    def test_close_position_not_found(self, mock_service_class: MagicMock) -> None:
        """Test closing non-existent position returns 404."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_open_trades.return_value = []

        url = reverse("market:position_detail", kwargs={"position_id": "999"})
        data = {"account_id": account.pk}  # ty:ignore[unresolved-attribute]

        response = self.client.patch(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_close_position_missing_account_id(self) -> None:
        """Test closing position without account_id fails."""
        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        data = {}

        response = self.client.patch(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]

    def test_close_position_account_not_found(self) -> None:
        """Test closing position with non-existent account returns 404."""
        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        data = {"account_id": 99999}

        response = self.client.patch(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_close_position_account_belongs_to_other_user(self) -> None:
        """Test that users cannot close positions for accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)

        url = reverse("market:position_detail", kwargs={"position_id": "123"})
        data = {"account_id": account.pk}  # ty:ignore[unresolved-attribute]

        response = self.client.patch(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]


class PositionFilteringTests(APIIntegrationTestCase):
    """Tests for filtering and querying positions."""

    @patch("apps.market.views.OandaService")
    def test_filter_positions_by_status_open(self, mock_service_class: MagicMock) -> None:
        """Test filtering positions by open status."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_trades = [
            OpenTrade(
                trade_id="1",
                instrument="EUR_USD",
                direction=OrderDirection.LONG,
                units=Decimal("1000"),
                entry_price=Decimal("1.08950"),
                unrealized_pnl=Decimal("25.50"),
                open_time=None,
                state="OPEN",
                account_id=account.account_id,  # ty:ignore[invalid-argument-type]
            ),
        ]
        mock_service.get_open_trades.return_value = mock_trades

        url = reverse("market:position_list")
        response = self.client.get(
            url,
            {
                "account_id": account.pk,  # type: ignore[attr-defined]
                "status": "open",
            },
        )

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 1)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["results"][0]["status"], "open")  # ty:ignore[possibly-missing-attribute]

    @patch("apps.market.views.OandaService")
    def test_filter_positions_by_multiple_accounts(self, mock_service_class: MagicMock) -> None:
        """Test listing positions across multiple accounts."""
        # Create multiple accounts
        account1 = OandaAccountFactory(user=self.user, is_active=True)
        OandaAccountFactory(user=self.user, is_active=True)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Return different positions for each account
        mock_trades = [
            OpenTrade(
                trade_id="1",
                instrument="EUR_USD",
                direction=OrderDirection.LONG,
                units=Decimal("1000"),
                entry_price=Decimal("1.08950"),
                unrealized_pnl=Decimal("25.50"),
                open_time=None,
                state="OPEN",
                account_id=account1.account_id,  # ty:ignore[invalid-argument-type]
            ),
        ]
        mock_service.get_open_trades.return_value = mock_trades

        url = reverse("market:position_list")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        # Should aggregate positions from both accounts
        self.assertEqual(response.data["count"], 2)  # ty:ignore[possibly-missing-attribute]

    @patch("apps.market.views.OandaService")
    def test_positions_include_account_info(self, mock_service_class: MagicMock) -> None:
        """Test that position responses include account information."""
        account = OandaAccountFactory(user=self.user)

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_trades = [
            OpenTrade(
                trade_id="1",
                instrument="EUR_USD",
                direction=OrderDirection.LONG,
                units=Decimal("1000"),
                entry_price=Decimal("1.08950"),
                unrealized_pnl=Decimal("25.50"),
                open_time=None,
                state="OPEN",
                account_id=account.account_id,  # ty:ignore[invalid-argument-type]
            ),
        ]
        mock_service.get_open_trades.return_value = mock_trades

        url = reverse("market:position_list")
        response = self.client.get(url, {"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        self.assert_response_success(response)  # type: ignore[arg-type]
        position = response.data["results"][0]  # ty:ignore[possibly-missing-attribute]
        self.assertIn("account_name", position)
        self.assertIn("account_db_id", position)
        self.assertEqual(position["account_db_id"], account.pk)  # type: ignore[attr-defined]
