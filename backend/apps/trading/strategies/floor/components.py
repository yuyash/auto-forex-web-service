"""Component classes for Floor strategy."""

from decimal import Decimal

from apps.trading.strategies.floor.calculators import IndicatorCalculator, PriceCalculator
from apps.trading.strategies.floor.enums import Direction, DirectionMethod
from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState, LayerState


class FloorDirectionDecider:
    """Component responsible for deciding trading direction based on technical indicators."""

    def __init__(self, config: FloorStrategyConfig, indicator_calc: IndicatorCalculator) -> None:
        self.config = config
        self.indicator_calc = indicator_calc

    def decide_direction(self, history: list[Decimal]) -> Direction:
        """Decide trading direction based on configured method and price history."""
        method = self.config.direction_method
        if method in {
            DirectionMethod.OHLC_SMA_CROSSOVER,
            DirectionMethod.OHLC_EMA_CROSSOVER,
            DirectionMethod.OHLC_PRICE_VS_SMA,
        }:
            # Fallback to tick-based momentum if OHLC not provided
            method = DirectionMethod.MOMENTUM

        if method == DirectionMethod.SMA_CROSSOVER:
            return self._sma_crossover_direction(history)

        if method == DirectionMethod.EMA_CROSSOVER:
            return self._ema_crossover_direction(history)

        if method == DirectionMethod.PRICE_VS_SMA:
            if len(history) < self.config.sma_slow_period:
                return Direction.LONG
            slow = history[-self.config.sma_slow_period :]
            return (
                Direction.LONG if history[-1] >= self.indicator_calc.sma(slow) else Direction.SHORT
            )

        if method == DirectionMethod.RSI:
            return self._rsi_direction(history)

        # momentum (default)
        return self._momentum_direction(history)

    def _momentum_direction(self, history: list[Decimal]) -> Direction:
        """Decide direction based on momentum (first vs last price)."""
        if len(history) < 2:
            return Direction.LONG
        return Direction.LONG if history[-1] >= history[0] else Direction.SHORT

    def _sma_crossover_direction(self, history: list[Decimal]) -> Direction:
        """Decide direction based on SMA crossover (fast vs slow)."""
        if len(history) < self.config.sma_slow_period:
            return Direction.LONG
        slow = history[-self.config.sma_slow_period :]
        fast = history[-self.config.sma_fast_period :]
        return (
            Direction.LONG
            if self.indicator_calc.sma(fast) >= self.indicator_calc.sma(slow)
            else Direction.SHORT
        )

    def _ema_crossover_direction(self, history: list[Decimal]) -> Direction:
        """Decide direction based on EMA crossover (fast vs slow)."""
        if len(history) < self.config.ema_slow_period:
            return Direction.LONG
        slow = history[-self.config.ema_slow_period :]
        fast = history[-self.config.ema_fast_period :]
        return (
            Direction.LONG
            if self.indicator_calc.ema(fast, self.config.ema_fast_period)
            >= self.indicator_calc.ema(slow, self.config.ema_slow_period)
            else Direction.SHORT
        )

    def _rsi_direction(self, history: list[Decimal]) -> Direction:
        """Decide direction based on RSI (overbought/oversold levels)."""
        rsi = self.indicator_calc.rsi(history, self.config.rsi_period)
        if rsi <= Decimal(self.config.rsi_oversold):
            return Direction.LONG
        if rsi >= Decimal(self.config.rsi_overbought):
            return Direction.SHORT
        # Neutral -> momentum fallback
        return self._momentum_direction(history)


class FloorVolatilityMonitor:
    """Component responsible for monitoring volatility and determining lock conditions."""

    def __init__(self, config: FloorStrategyConfig, price_calc: PriceCalculator) -> None:
        self.config = config
        self.price_calc = price_calc

    def check_and_update(
        self, state: FloorStrategyState, volatility_series: list[Decimal]
    ) -> tuple[bool, Decimal | None, Decimal | None]:
        """Check volatility and update lock state.

        Returns:
            tuple: (lock_changed, atr_pips, current_range_pips)
        """

        should_lock = self._should_lock(volatility_series)
        lock_changed = False

        if should_lock and not state.volatility_locked:
            state.volatility_locked = True
            lock_changed = True
        elif not should_lock and state.volatility_locked:
            state.volatility_locked = False

        atr_pips, current_range_pips = self._calculate_atr(volatility_series)
        return lock_changed, atr_pips, current_range_pips

    def _should_lock(self, volatility_series: list[Decimal]) -> bool:
        """Determine if volatility lock should be activated based on ATR."""
        atr_pips, current_range_pips = self._calculate_atr(volatility_series)
        if atr_pips is None or current_range_pips is None:
            return False
        if atr_pips <= 0:
            return False

        return current_range_pips > (atr_pips * self.config.volatility_lock_multiplier)

    def _calculate_atr(self, series: list[Decimal]) -> tuple[Decimal | None, Decimal | None]:
        """Calculate Average True Range and current range in pips."""
        if len(series) < 3:
            return None, None

        diffs_pips: list[Decimal] = []
        for i in range(1, len(series)):
            diffs_pips.append(abs(self.price_calc.pips_between(series[i - 1], series[i])))

        if len(diffs_pips) < 2:
            return None, None

        current_range_pips = diffs_pips[-1]
        prior = diffs_pips[:-1]
        lookback = prior[-min(14, len(prior)) :]
        if not lookback:
            return None, None
        atr_pips = sum(lookback) / Decimal(len(lookback))
        return atr_pips, current_range_pips

    def get_volatility_series(self, state: FloorStrategyState) -> list[Decimal]:
        """Get appropriate price series for volatility calculation."""

        # Prefer candle closes when available (more stable)
        if state.current_candle_bucket_start_epoch is not None:
            out = list(state.candle_closes)
            if state.current_candle_close is not None:
                out.append(state.current_candle_close)
            if len(out) >= 2:
                return out
        return state.price_history


class FloorLayerManager:
    """Component responsible for managing layers and determining entry/exit conditions."""

    def __init__(self, config: FloorStrategyConfig, price_calc: PriceCalculator) -> None:
        self.config = config
        self.price_calc = price_calc

    def should_open_initial_layer(
        self, has_enough_history: bool, active_layers: list[LayerState]
    ) -> bool:
        """Determine if initial layer should be opened."""
        return has_enough_history and len(active_layers) == 0

    def should_retracement(
        self,
        layer: LayerState,
        bid: Decimal,
        ask: Decimal,
        active_layers_count: int,
        volatility_locked: bool,
        trigger_pips: Decimal,
    ) -> bool:
        """Determine if a retracement entry should be triggered for a layer."""
        if layer.retracements >= self.config.max_retracements_per_layer:
            return False

        against_pips = self.price_calc.against_position_pips(layer, bid, ask)

        return (
            against_pips >= trigger_pips
            and active_layers_count <= self.config.max_layers
            and not volatility_locked
        )

    def should_take_profit(self, layers: list[LayerState], bid: Decimal, ask: Decimal) -> bool:
        """Determine if take profit condition is met."""
        total_pips = self.price_calc.calculate_pnl(layers, bid, ask)
        return total_pips >= self.config.take_profit_pips
