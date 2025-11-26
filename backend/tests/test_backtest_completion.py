"""
Tests for backtest completion position closure functionality.

This module tests the finalize_backtest method and position closure
at backtest completion based on the sell_at_completion flag.

Requirements: 9.2, 9.3, 9.4
"""

from datetime import datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from trading.backtest_engine import BacktestConfig, BacktestEngine, BacktestPosition
from trading.historical_data_loader import TickDataPoint

# Test helpers


def create_base_config():
    """Create base backtest configuration."""
    return BacktestConfig(
        strategy_type="floor",
        strategy_config={
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "max_layers": 3,
        },
        instrument="USD_JPY",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
        initial_balance=Decimal("10000"),
        commission_per_trade=Decimal("0"),
    )


def create_sample_tick():
    """Create sample tick data."""
    return TickDataPoint(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        instrument="USD_JPY",
        bid=Decimal("149.50"),
        ask=Decimal("149.52"),
        mid=Decimal("149.51"),
        spread=Decimal("0.02"),
    )


class MockBacktest:
    """Mock backtest object for testing."""

    def __init__(self, sell_at_completion=False):
        self.sell_at_completion = sell_at_completion


def create_random_position(
    instrument="USD_JPY",
    direction="long",
    units=1.0,
    entry_price=149.50,
    entry_time=None,
):
    """Create a random backtest position for testing."""
    if entry_time is None:
        entry_time = datetime(2024, 1, 1, 10, 0, 0)

    return BacktestPosition(
        instrument=instrument,
        direction=direction,
        units=Decimal(str(units)),
        entry_price=Decimal(str(entry_price)),
        entry_time=entry_time,
        stop_loss=None,
        take_profit=None,
        layer_number=1,
        is_first_lot=True,
        position_id=f"test_{id(entry_time)}",
    )


# Property-based tests


@settings(max_examples=100, deadline=None)
@given(
    num_open_positions=st.integers(min_value=0, max_value=20),
    sell_at_completion=st.booleans(),
)
def test_property_11_backtest_completion_closes_positions_when_configured(
    num_open_positions, sell_at_completion
):
    """
    Property 11: Backtest completion closes positions when configured.

    For any backtest with sell_at_completion enabled, all open Floor Strategy
    positions should be closed at the final market price when the backtest finishes.

    Feature: floor-strategy-enhancements, Property 11
    Validates: Requirements 9.2, 9.4
    """
    # Create config and tick
    base_config = create_base_config()
    sample_tick = create_sample_tick()

    # Create engine
    engine = BacktestEngine(base_config)

    # Create mock backtest with sell_at_completion flag
    backtest = MockBacktest(sell_at_completion=sell_at_completion)

    # Create open positions
    for i in range(num_open_positions):
        position = create_random_position(
            direction="long" if i % 2 == 0 else "short",
            units=1.0 + (i * 0.1),
            entry_price=149.50 + (i * 0.01),
        )
        engine.positions.append(position)

    initial_position_count = len(engine.positions)
    initial_trade_count = len(engine.trade_log)

    # Finalize backtest
    engine.finalize_backtest(backtest, sample_tick)

    final_position_count = len(engine.positions)
    final_trade_count = len(engine.trade_log)

    # Verify behavior based on sell_at_completion flag
    if sell_at_completion:
        # All positions should be closed
        assert final_position_count == 0, (
            f"Expected all positions to be closed when sell_at_completion=True, "
            f"but {final_position_count} positions remain"
        )

        # Trade log should have entries for closed positions
        assert final_trade_count == initial_trade_count + initial_position_count, (
            f"Expected {initial_position_count} new trades in log, "
            f"but got {final_trade_count - initial_trade_count}"
        )

        # All new trades should have reason 'close'
        new_trades = engine.trade_log[initial_trade_count:]
        for trade in new_trades:
            assert (
                trade.reason == "close"
            ), f"Expected trade reason to be 'close', but got '{trade.reason}'"
    else:
        # Positions should remain unchanged
        assert final_position_count == initial_position_count, (
            f"Expected positions to remain unchanged when sell_at_completion=False, "
            f"but count changed from {initial_position_count} to {final_position_count}"
        )

        # No new trades should be created
        assert final_trade_count == initial_trade_count, (
            f"Expected no new trades when sell_at_completion=False, "
            f"but {final_trade_count - initial_trade_count} trades were created"
        )


@settings(max_examples=100, deadline=None)
@given(
    num_open_positions=st.integers(min_value=1, max_value=20),
    bid_price=st.floats(min_value=140.0, max_value=160.0),
    ask_price=st.floats(min_value=140.0, max_value=160.0),
)
def test_property_12_backtest_completion_preserves_positions_when_not_configured(
    num_open_positions, bid_price, ask_price
):
    """
    Property 12: Backtest completion preserves positions when not configured.

    For any backtest with sell_at_completion disabled, all open Floor Strategy
    positions should remain open without closure when the backtest finishes.

    Feature: floor-strategy-enhancements, Property 12
    Validates: Requirements 9.3
    """
    # Ensure ask >= bid
    if ask_price < bid_price:
        bid_price, ask_price = ask_price, bid_price

    # Create config
    base_config = create_base_config()

    # Create engine
    engine = BacktestEngine(base_config)

    # Create mock backtest with sell_at_completion=False
    backtest = MockBacktest(sell_at_completion=False)

    # Create tick with random prices
    tick = TickDataPoint(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        instrument="USD_JPY",
        bid=Decimal(str(bid_price)),
        ask=Decimal(str(ask_price)),
        mid=Decimal(str((bid_price + ask_price) / 2)),
        spread=Decimal(str(ask_price - bid_price)),
    )

    # Create open positions
    positions_data = []
    for i in range(num_open_positions):
        position = create_random_position(
            direction="long" if i % 2 == 0 else "short",
            units=1.0 + (i * 0.1),
            entry_price=149.50 + (i * 0.01),
        )
        engine.positions.append(position)
        positions_data.append(
            {
                "instrument": position.instrument,
                "direction": position.direction,
                "units": position.units,
                "entry_price": position.entry_price,
            }
        )

    initial_position_count = len(engine.positions)

    # Finalize backtest
    engine.finalize_backtest(backtest, tick)

    final_position_count = len(engine.positions)

    # All positions should remain open
    assert final_position_count == initial_position_count, (
        f"Expected all {initial_position_count} positions to remain open, "
        f"but only {final_position_count} positions remain"
    )

    # Verify position data is unchanged
    for i, position in enumerate(engine.positions):
        original = positions_data[i]
        assert position.instrument == original["instrument"]
        assert position.direction == original["direction"]
        assert position.units == original["units"]
        assert position.entry_price == original["entry_price"]


# Unit tests


class TestBacktestCompletion:
    """Unit tests for backtest completion functionality."""

    def test_positions_closed_when_sell_at_completion_true(self):
        """
        Test positions are closed when sell_at_completion=True.

        Requirements: 9.2, 9.4
        """
        # Create config and engine
        config = create_base_config()
        engine = BacktestEngine(config)

        # Create mock backtest with sell_at_completion=True
        backtest = MockBacktest(sell_at_completion=True)

        # Create sample tick
        tick = create_sample_tick()

        # Add some open positions
        for i in range(3):
            position = create_random_position(
                direction="long" if i % 2 == 0 else "short",
                units=1.0 + i,
            )
            engine.positions.append(position)

        # Verify positions exist
        assert len(engine.positions) == 3

        # Finalize backtest
        engine.finalize_backtest(backtest, tick)

        # All positions should be closed
        assert len(engine.positions) == 0
        assert len(engine.trade_log) == 3

        # All trades should have reason 'close'
        for trade in engine.trade_log:
            assert trade.reason == "close"

    def test_positions_preserved_when_sell_at_completion_false(self):
        """
        Test positions are preserved when sell_at_completion=False.

        Requirements: 9.3
        """
        # Create config and engine
        config = create_base_config()
        engine = BacktestEngine(config)

        # Create mock backtest with sell_at_completion=False
        backtest = MockBacktest(sell_at_completion=False)

        # Create sample tick
        tick = create_sample_tick()

        # Add some open positions
        for i in range(3):
            position = create_random_position(
                direction="long" if i % 2 == 0 else "short",
                units=1.0 + i,
            )
            engine.positions.append(position)

        # Verify positions exist
        assert len(engine.positions) == 3

        # Finalize backtest
        engine.finalize_backtest(backtest, tick)

        # All positions should remain open
        assert len(engine.positions) == 3
        assert len(engine.trade_log) == 0

    def test_close_events_are_logged(self):
        """
        Test close events are logged when positions are closed.

        Requirements: 9.4
        """
        # Create config and engine with strategy
        config = create_base_config()
        engine = BacktestEngine(config)

        # Initialize a mock strategy to capture events
        from trading.base_strategy import BaseStrategy

        class MockStrategy(BaseStrategy):
            def __init__(self, config):
                super().__init__(config)
                self._backtest_events = []
                self._is_backtest = True  # Mark as backtest mode

            def on_tick(self, tick_data):
                return []

            def on_position_update(self, position):
                pass

            def validate_config(self, config):
                return True

        engine.strategy = MockStrategy(config.strategy_config)

        # Create mock backtest with sell_at_completion=True
        backtest = MockBacktest(sell_at_completion=True)

        # Create sample tick
        tick = create_sample_tick()

        # Add some open positions
        for idx in range(2):
            position = create_random_position(
                direction="long",
                units=1.0 + idx,
            )
            engine.positions.append(position)

        # Finalize backtest
        engine.finalize_backtest(backtest, tick)

        # Verify close events were logged
        assert len(engine.strategy._backtest_events) == 2
        for event in engine.strategy._backtest_events:
            assert event["details"]["event_type"] == "close"
            assert event["details"]["reason"] == "backtest_completion"

    def test_final_metrics_include_closed_positions(self):
        """
        Test final metrics include closed positions.

        Requirements: 9.4
        """
        # Create config and engine
        config = create_base_config()
        engine = BacktestEngine(config)

        # Create mock backtest with sell_at_completion=True
        backtest = MockBacktest(sell_at_completion=True)

        # Create sample tick
        tick = create_sample_tick()

        # Add some open positions
        for _ in range(3):
            position = create_random_position(
                direction="long",
                units=1.0,
                entry_price=149.00,  # Entry below current price for profit
            )
            engine.positions.append(position)

        # Finalize backtest
        engine.finalize_backtest(backtest, tick)

        # Calculate metrics
        metrics = engine.calculate_performance_metrics()

        # Metrics should include the closed positions
        assert metrics["total_trades"] == 3
        assert metrics["final_balance"] != float(config.initial_balance)

    def test_no_positions_to_close(self):
        """
        Test finalize_backtest handles case with no open positions.

        Requirements: 9.2
        """
        # Create config and engine
        config = create_base_config()
        engine = BacktestEngine(config)

        # Create mock backtest with sell_at_completion=True
        backtest = MockBacktest(sell_at_completion=True)

        # Create sample tick
        tick = create_sample_tick()

        # No positions added

        # Finalize backtest - should not raise error
        engine.finalize_backtest(backtest, tick)

        # No positions, no trades
        assert len(engine.positions) == 0
        assert len(engine.trade_log) == 0

    def test_mixed_long_and_short_positions(self):
        """
        Test closing mixed long and short positions.

        Requirements: 9.2, 9.4
        """
        # Create config and engine
        config = create_base_config()
        engine = BacktestEngine(config)

        # Create mock backtest with sell_at_completion=True
        backtest = MockBacktest(sell_at_completion=True)

        # Create sample tick
        tick = create_sample_tick()

        # Add mixed positions
        long_position = create_random_position(direction="long", units=1.0)
        short_position = create_random_position(direction="short", units=2.0)
        engine.positions.extend([long_position, short_position])

        # Finalize backtest
        engine.finalize_backtest(backtest, tick)

        # All positions should be closed
        assert len(engine.positions) == 0
        assert len(engine.trade_log) == 2

        # Verify correct exit prices were used
        # Long positions exit at bid, short positions exit at ask
        long_trade = [t for t in engine.trade_log if t.direction == "long"][0]
        short_trade = [t for t in engine.trade_log if t.direction == "short"][0]

        assert long_trade.exit_price == float(tick.bid)
        assert short_trade.exit_price == float(tick.ask)
