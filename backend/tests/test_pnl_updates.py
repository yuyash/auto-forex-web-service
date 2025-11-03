"""
Unit tests for P&L update functionality.

Tests cover:
- P&L calculation on tick updates
- WebSocket broadcast of P&L changes
- Batch position updates
- Handling of multiple instruments
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.market_data_streamer import MarketDataStreamer, TickData
from trading.models import Position, Strategy
from trading.position_pnl_updater import PositionPnLUpdater


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
    )
    return account


@pytest.fixture
def mock_strategy(db, mock_oanda_account):
    """Create a mock strategy for testing"""
    strategy = Strategy.objects.create(
        account=mock_oanda_account,
        strategy_type="test_strategy",
        is_active=True,
        config={"test": "config"},
        instruments=["EUR_USD", "GBP_USD"],
    )
    return strategy


@pytest.fixture
def mock_long_position(db, mock_oanda_account, mock_strategy):
    """Create a mock long position for testing"""
    position = Position.objects.create(
        account=mock_oanda_account,
        strategy=mock_strategy,
        position_id="test_position_long_001",
        instrument="EUR_USD",
        direction="long",
        units=Decimal("10000"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1000"),
        unrealized_pnl=Decimal("0"),
    )
    return position


@pytest.fixture
def mock_short_position(db, mock_oanda_account, mock_strategy):
    """Create a mock short position for testing"""
    position = Position.objects.create(
        account=mock_oanda_account,
        strategy=mock_strategy,
        position_id="test_position_short_001",
        instrument="GBP_USD",
        direction="short",
        units=Decimal("5000"),
        entry_price=Decimal("1.2500"),
        current_price=Decimal("1.2500"),
        unrealized_pnl=Decimal("0"),
    )
    return position


@pytest.mark.django_db
class TestPnLCalculationOnTickUpdates:
    """Test P&L calculation on tick updates"""

    @patch("trading.market_data_streamer.v20.Context")
    def test_pnl_update_on_tick_long_position_profit(
        self, mock_v20_context, mock_oanda_account, mock_long_position
    ):
        """Test P&L update for long position with profit"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick with higher price (profit for long)
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1050,  # 50 pips profit
            ask=1.1052,
        )

        # Update P&L
        streamer._update_positions_pnl(tick)

        # Refresh position from database
        mock_long_position.refresh_from_db()

        # Verify P&L calculation
        # Long position: (current_price - entry_price) * units
        # (1.1050 - 1.1000) * 10000 = 50
        assert mock_long_position.current_price == Decimal("1.1050")
        assert mock_long_position.unrealized_pnl == Decimal("50.00")

    @patch("trading.market_data_streamer.v20.Context")
    def test_pnl_update_on_tick_long_position_loss(
        self, mock_v20_context, mock_oanda_account, mock_long_position
    ):
        """Test P&L update for long position with loss"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick with lower price (loss for long)
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.0950,  # 50 pips loss
            ask=1.0952,
        )

        # Update P&L
        streamer._update_positions_pnl(tick)

        # Refresh position from database
        mock_long_position.refresh_from_db()

        # Verify P&L calculation
        # Long position: (current_price - entry_price) * units
        # (1.0950 - 1.1000) * 10000 = -50
        assert mock_long_position.current_price == Decimal("1.0950")
        assert mock_long_position.unrealized_pnl == Decimal("-50.00")

    @patch("trading.market_data_streamer.v20.Context")
    def test_pnl_update_on_tick_short_position_profit(
        self, mock_v20_context, mock_oanda_account, mock_short_position
    ):
        """Test P&L update for short position with profit"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick with lower price (profit for short)
        tick = TickData(
            instrument="GBP_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.2450,
            ask=1.2452,  # 48 pips profit
        )

        # Update P&L
        streamer._update_positions_pnl(tick)

        # Refresh position from database
        mock_short_position.refresh_from_db()

        # Verify P&L calculation
        # Short position: -(current_price - entry_price) * units
        # -(1.2452 - 1.2500) * 5000 = 24
        assert mock_short_position.current_price == Decimal("1.2452")
        assert mock_short_position.unrealized_pnl == Decimal("24.00")

    @patch("trading.market_data_streamer.v20.Context")
    def test_pnl_update_on_tick_short_position_loss(
        self, mock_v20_context, mock_oanda_account, mock_short_position
    ):
        """Test P&L update for short position with loss"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick with higher price (loss for short)
        tick = TickData(
            instrument="GBP_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.2550,
            ask=1.2552,  # 52 pips loss
        )

        # Update P&L
        streamer._update_positions_pnl(tick)

        # Refresh position from database
        mock_short_position.refresh_from_db()

        # Verify P&L calculation
        # Short position: -(current_price - entry_price) * units
        # -(1.2552 - 1.2500) * 5000 = -26
        assert mock_short_position.current_price == Decimal("1.2552")
        assert mock_short_position.unrealized_pnl == Decimal("-26.00")

    @patch("trading.market_data_streamer.v20.Context")
    def test_pnl_update_no_open_positions(self, mock_v20_context, mock_oanda_account):
        """Test P&L update when no open positions exist"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1050,
            ask=1.1052,
        )

        # Update P&L - should not raise exception
        streamer._update_positions_pnl(tick)

    @patch("trading.market_data_streamer.v20.Context")
    def test_pnl_update_closed_position_not_updated(
        self, mock_v20_context, mock_oanda_account, mock_long_position
    ):
        """Test that closed positions are not updated"""
        # Close the position
        mock_long_position.closed_at = timezone.now()
        mock_long_position.save()

        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1050,
            ask=1.1052,
        )

        # Update P&L
        streamer._update_positions_pnl(tick)

        # Refresh position from database
        mock_long_position.refresh_from_db()

        # Verify position was not updated (still at entry price)
        assert mock_long_position.current_price == Decimal("1.1000")
        assert mock_long_position.unrealized_pnl == Decimal("0")


@pytest.mark.django_db
class TestWebSocketPnLBroadcast:
    """Test WebSocket broadcast of P&L changes"""

    @patch("trading.market_data_streamer.v20.Context")
    @patch("trading.market_data_streamer.get_channel_layer")
    def test_pnl_broadcast_to_websocket(
        self, mock_get_channel_layer, mock_v20_context, mock_oanda_account, mock_long_position
    ):
        """Test P&L updates are broadcasted via WebSocket"""
        # Setup mock channel layer
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick with price change
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1050,
            ask=1.1052,
        )

        # Update P&L
        streamer._update_positions_pnl(tick)

        # Verify channel layer group_send was called
        assert mock_channel_layer.group_send.called
        call_args = mock_channel_layer.group_send.call_args

        # Verify group name
        group_name = call_args[0][0]
        assert group_name == f"market_data_{mock_oanda_account.id}"

        # Verify message structure
        message = call_args[0][1]
        assert message["type"] == "pnl_update"
        assert "data" in message
        assert "positions" in message["data"]
        assert "account_id" in message["data"]

    @patch("trading.market_data_streamer.v20.Context")
    @patch("trading.market_data_streamer.get_channel_layer")
    def test_pnl_broadcast_no_channel_layer(
        self, mock_get_channel_layer, mock_v20_context, mock_oanda_account, mock_long_position
    ):
        """Test P&L update handles missing channel layer gracefully"""
        # Setup mock channel layer to return None
        mock_get_channel_layer.return_value = None

        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create tick
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1050,
            ask=1.1052,
        )

        # Update P&L - should not raise exception
        streamer._update_positions_pnl(tick)

        # Verify position was still updated in database
        mock_long_position.refresh_from_db()
        assert mock_long_position.current_price == Decimal("1.1050")


@pytest.mark.django_db
class TestBatchPositionUpdates:
    """Test batch position updates"""

    def test_batch_update_multiple_positions(self, mock_oanda_account, mock_strategy):
        """Test batch updating multiple positions"""
        # Create multiple positions
        positions = []
        for i in range(5):
            position = Position.objects.create(
                account=mock_oanda_account,
                strategy=mock_strategy,
                position_id=f"test_position_{i}",
                instrument="EUR_USD",
                direction="long",
                units=Decimal("10000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
                unrealized_pnl=Decimal("0"),
            )
            positions.append(position)

        # Create updater
        updater = PositionPnLUpdater(account=mock_oanda_account)

        # Update all positions
        price_data = {
            "EUR_USD": {
                "bid": Decimal("1.1050"),
                "ask": Decimal("1.1052"),
            }
        }

        result = updater.update_all_positions(price_data)

        # Verify all positions were updated
        assert result["success"] is True
        assert result["updated_count"] == 5
        assert result["error_count"] == 0
        assert len(result["positions"]) == 5

        # Verify each position
        for position in positions:
            position.refresh_from_db()
            assert position.current_price == Decimal("1.1050")
            assert position.unrealized_pnl == Decimal("50.00")

    def test_batch_update_no_positions(self, mock_oanda_account):
        """Test batch update when no positions exist"""
        updater = PositionPnLUpdater(account=mock_oanda_account)

        price_data = {
            "EUR_USD": {
                "bid": Decimal("1.1050"),
                "ask": Decimal("1.1052"),
            }
        }

        result = updater.update_all_positions(price_data)

        assert result["success"] is True
        assert result["updated_count"] == 0
        assert result["error_count"] == 0

    def test_batch_update_missing_price_data(self, mock_oanda_account, mock_long_position):
        """Test batch update with missing price data for instrument"""
        updater = PositionPnLUpdater(account=mock_oanda_account)

        # Price data for different instrument
        price_data = {
            "GBP_USD": {
                "bid": Decimal("1.2500"),
                "ask": Decimal("1.2502"),
            }
        }

        result = updater.update_all_positions(price_data)

        # Position should not be updated
        assert result["success"] is True
        assert result["updated_count"] == 0

        # Verify position unchanged
        mock_long_position.refresh_from_db()
        assert mock_long_position.current_price == Decimal("1.1000")
        assert mock_long_position.unrealized_pnl == Decimal("0")

    def test_batch_update_statistics(self, mock_oanda_account, mock_strategy):
        """Test batch update statistics tracking"""
        # Create positions
        for i in range(3):
            Position.objects.create(
                account=mock_oanda_account,
                strategy=mock_strategy,
                position_id=f"test_position_{i}",
                instrument="EUR_USD",
                direction="long",
                units=Decimal("10000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
                unrealized_pnl=Decimal("0"),
            )

        updater = PositionPnLUpdater(account=mock_oanda_account)

        price_data = {
            "EUR_USD": {
                "bid": Decimal("1.1050"),
                "ask": Decimal("1.1052"),
            }
        }

        updater.update_all_positions(price_data)

        # Check statistics
        stats = updater.get_statistics()
        assert stats["updated_count"] == 3
        assert stats["error_count"] == 0

        # Reset statistics
        updater.reset_statistics()
        stats = updater.get_statistics()
        assert stats["updated_count"] == 0
        assert stats["error_count"] == 0


@pytest.mark.django_db
class TestMultipleInstruments:
    """Test handling of multiple instruments"""

    def test_update_multiple_instruments(self, mock_oanda_account, mock_strategy):
        """Test updating positions for multiple instruments"""
        # Create positions for different instruments
        eur_position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="test_position_eur",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
        )

        gbp_position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="test_position_gbp",
            instrument="GBP_USD",
            direction="short",
            units=Decimal("5000"),
            entry_price=Decimal("1.2500"),
            current_price=Decimal("1.2500"),
            unrealized_pnl=Decimal("0"),
        )

        # Create updater
        updater = PositionPnLUpdater(account=mock_oanda_account)

        # Update with price data for both instruments
        price_data = {
            "EUR_USD": {
                "bid": Decimal("1.1050"),
                "ask": Decimal("1.1052"),
            },
            "GBP_USD": {
                "bid": Decimal("1.2450"),
                "ask": Decimal("1.2452"),
            },
        }

        result = updater.update_all_positions(price_data)

        # Verify both positions were updated
        assert result["success"] is True
        assert result["updated_count"] == 2
        assert len(result["positions"]) == 2

        # Verify EUR position
        eur_position.refresh_from_db()
        assert eur_position.current_price == Decimal("1.1050")
        assert eur_position.unrealized_pnl == Decimal("50.00")

        # Verify GBP position
        gbp_position.refresh_from_db()
        assert gbp_position.current_price == Decimal("1.2452")
        assert gbp_position.unrealized_pnl == Decimal("24.00")

    def test_update_single_instrument(self, mock_oanda_account, mock_strategy):
        """Test updating positions for a single instrument"""
        # Create positions for different instruments
        eur_position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="test_position_eur",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
        )

        Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="test_position_gbp",
            instrument="GBP_USD",
            direction="short",
            units=Decimal("5000"),
            entry_price=Decimal("1.2500"),
            current_price=Decimal("1.2500"),
            unrealized_pnl=Decimal("0"),
        )

        # Create updater
        updater = PositionPnLUpdater(account=mock_oanda_account)

        # Update only EUR_USD
        updated_positions = updater.update_positions_for_instrument(
            instrument="EUR_USD",
            bid=Decimal("1.1050"),
            ask=Decimal("1.1052"),
        )

        # Verify only EUR position was updated
        assert len(updated_positions) == 1
        assert updated_positions[0]["instrument"] == "EUR_USD"

        # Verify EUR position
        eur_position.refresh_from_db()
        assert eur_position.current_price == Decimal("1.1050")
        assert eur_position.unrealized_pnl == Decimal("50.00")

    def test_efficient_instrument_grouping(self, mock_oanda_account, mock_strategy):
        """Test efficient grouping of positions by instrument"""
        # Create multiple positions for same instrument
        for i in range(3):
            Position.objects.create(
                account=mock_oanda_account,
                strategy=mock_strategy,
                position_id=f"test_position_eur_{i}",
                instrument="EUR_USD",
                direction="long",
                units=Decimal("10000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
                unrealized_pnl=Decimal("0"),
            )

        for i in range(2):
            Position.objects.create(
                account=mock_oanda_account,
                strategy=mock_strategy,
                position_id=f"test_position_gbp_{i}",
                instrument="GBP_USD",
                direction="short",
                units=Decimal("5000"),
                entry_price=Decimal("1.2500"),
                current_price=Decimal("1.2500"),
                unrealized_pnl=Decimal("0"),
            )

        # Create updater
        updater = PositionPnLUpdater(account=mock_oanda_account)

        # Update all positions
        price_data = {
            "EUR_USD": {
                "bid": Decimal("1.1050"),
                "ask": Decimal("1.1052"),
            },
            "GBP_USD": {
                "bid": Decimal("1.2450"),
                "ask": Decimal("1.2452"),
            },
        }

        result = updater.update_all_positions(price_data)

        # Verify all positions were updated
        assert result["success"] is True
        assert result["updated_count"] == 5
        assert len(result["positions"]) == 5
