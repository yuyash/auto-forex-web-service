"""History management for Floor strategy."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.trading.strategies.floor.enums import DirectionMethod, MomentumLookbackSource
from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState

if TYPE_CHECKING:
    from apps.trading.dataclasses import Tick


def _tick_bucket_start_epoch_seconds(*, tick_dt: datetime, granularity_seconds: int) -> int | None:
    """Calculate candle bucket start epoch from datetime."""
    if granularity_seconds <= 0:
        return None
    epoch = int(tick_dt.timestamp())
    return epoch - (epoch % int(granularity_seconds))


class PriceHistoryManager:
    """Manages price history and candle building."""

    def __init__(self, config: FloorStrategyConfig) -> None:
        self.config = config

    def update_from_tick(self, state: FloorStrategyState, tick: "Tick") -> None:
        """Update state with tick data and price history.

        Args:
            state: Strategy state to update
            tick: Tick data
        """

        # Update market data
        state.last_bid = tick.bid
        state.last_ask = tick.ask
        state.last_mid = tick.mid
        state.ticks_seen += 1

        # Update price history and candles
        state.price_history.append(tick.mid)
        self._update_candles(state, tick.timestamp)
        self._trim_history(state)

    def update(self, state: FloorStrategyState, mid_price: Decimal, tick_dt: datetime) -> None:
        """Update price history and candle data (legacy method).

        Deprecated: Use update_from_tick() instead.
        """
        state.price_history.append(mid_price)
        self._update_candles(state, tick_dt)
        self._trim_history(state)

    def _update_candles(self, state: FloorStrategyState, tick_dt: datetime) -> None:
        """Update candle history if configured."""
        if self.config.direction_method != DirectionMethod.MOMENTUM:
            return
        if self.config.momentum_lookback_source != MomentumLookbackSource.CANDLES:
            return

        bucket_start = _tick_bucket_start_epoch_seconds(
            tick_dt=tick_dt,
            granularity_seconds=int(self.config.entry_signal_candle_granularity_seconds),
        )
        if bucket_start is None:
            return

        if state.current_candle_bucket_start_epoch is None:
            state.current_candle_bucket_start_epoch = bucket_start
            state.current_candle_close = state.last_mid
            return

        # Same candle -> update close
        if int(state.current_candle_bucket_start_epoch) == int(bucket_start):
            state.current_candle_close = state.last_mid
            return

        # New candle -> finalize previous close
        if state.current_candle_close is not None:
            state.candle_closes.append(state.current_candle_close)

        # Trim to bounded size
        max_needed = max(1, int(self.config.entry_signal_lookback_candles) + 5)
        if len(state.candle_closes) > max_needed:
            state.candle_closes = state.candle_closes[-max_needed:]

        state.current_candle_bucket_start_epoch = bucket_start
        state.current_candle_close = state.last_mid

    def _trim_history(self, state: FloorStrategyState) -> None:
        """Trim price history to required size."""
        max_needed = max(
            self.config.entry_signal_lookback_ticks,
            self.config.sma_slow_period,
            self.config.ema_slow_period,
            self.config.rsi_period + 1,
        )
        if len(state.price_history) > max_needed:
            state.price_history = state.price_history[-max_needed:]

    def get_momentum_history(self, state: FloorStrategyState) -> list[Decimal]:
        """Get history for momentum calculation."""
        if self.config.momentum_lookback_source == MomentumLookbackSource.CANDLES:
            # If we can't build candles, fall back to ticks
            if state.current_candle_bucket_start_epoch is None:
                return state.price_history
            # Include current candle close for live reaction
            out = list(state.candle_closes)
            if state.current_candle_close is not None:
                out.append(state.current_candle_close)
            return out
        return state.price_history

    def has_enough_history_for_entry(self, state: FloorStrategyState) -> bool:
        """Check if enough history exists for initial entry."""
        if self.config.direction_method == DirectionMethod.MOMENTUM:
            if self.config.momentum_lookback_source == MomentumLookbackSource.CANDLES:
                # If candle bucketing isn't possible, fall back to ticks
                if state.current_candle_bucket_start_epoch is None:
                    return int(state.ticks_seen) >= int(self.config.entry_signal_lookback_ticks)
                return len(self.get_momentum_history(state)) >= int(
                    self.config.entry_signal_lookback_candles
                )
            return int(state.ticks_seen) >= int(self.config.entry_signal_lookback_ticks)
        # For non-momentum methods
        return int(state.ticks_seen) >= int(self.config.entry_signal_lookback_ticks)
