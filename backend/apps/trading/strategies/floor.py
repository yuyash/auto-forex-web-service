from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from django.conf import settings

from apps.trading.dataclasses import ExecutionState, StrategyResult, Tick
from apps.trading.enums import StrategyType
from apps.trading.events import StrategyEvent
from apps.trading.services.base import Strategy
from apps.trading.services.registry import register_strategy

if TYPE_CHECKING:
    from apps.trading.models import StrategyConfig as StrategyConfigModel


class StrategyStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


class Progression(StrEnum):
    EQUAL = "equal"
    ADDITIVE = "additive"
    EXPONENTIAL = "exponential"
    INVERSE = "inverse"


class DirectionMethod(StrEnum):
    MOMENTUM = "momentum"
    SMA_CROSSOVER = "sma_crossover"
    EMA_CROSSOVER = "ema_crossover"
    PRICE_VS_SMA = "price_vs_sma"
    RSI = "rsi"
    OHLC_SMA_CROSSOVER = "ohlc_sma_crossover"
    OHLC_EMA_CROSSOVER = "ohlc_ema_crossover"
    OHLC_PRICE_VS_SMA = "ohlc_price_vs_sma"


class MomentumLookbackSource(StrEnum):
    TICKS = "ticks"
    CANDLES = "candles"


class LotMode(StrEnum):
    """Lot size calculation mode."""

    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"


# ============================================================================
# PROTOCOLS
# ============================================================================


class PriceCalculatorProtocol(Protocol):
    """Protocol for price and P&L calculations."""

    def pips_between(self, price_a: Decimal, price_b: Decimal) -> Decimal:
        """Calculate pips between two prices."""
        ...

    def calculate_pnl(self, layers: list[LayerState], bid: Decimal, ask: Decimal) -> Decimal:
        """Calculate net P&L in pips."""
        ...

    def against_position_pips(self, layer: LayerState, bid: Decimal, ask: Decimal) -> Decimal:
        """Calculate adverse movement in pips for a layer."""
        ...


class IndicatorCalculatorProtocol(Protocol):
    """Protocol for technical indicator calculations."""

    @staticmethod
    def sma(values: list[Decimal]) -> Decimal:
        """Calculate Simple Moving Average."""
        ...

    @staticmethod
    def ema(values: list[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        ...

    @staticmethod
    def rsi(values: list[Decimal], period: int) -> Decimal:
        """Calculate Relative Strength Index."""
        ...


class DirectionDeciderProtocol(Protocol):
    """Protocol for deciding trade direction."""

    def decide_direction(self, history: list[Decimal]) -> Direction:
        """Decide trading direction based on price history."""
        ...


class VolatilityMonitorProtocol(Protocol):
    """Protocol for monitoring volatility."""

    def should_lock(self, volatility_series: list[Decimal]) -> bool:
        """Determine if volatility lock should be activated."""
        ...


class LayerManagerProtocol(Protocol):
    """Protocol for managing layers."""

    def should_open_initial_layer(
        self, has_enough_history: bool, active_layers: list[LayerState]
    ) -> bool:
        """Determine if initial layer should be opened."""
        ...

    def should_retracement(
        self,
        layer: LayerState,
        bid: Decimal,
        ask: Decimal,
        active_layers_count: int,
        volatility_locked: bool,
    ) -> bool:
        """Determine if retracement entry should be triggered."""
        ...

    def should_take_profit(self, layers: list[LayerState], bid: Decimal, ask: Decimal) -> bool:
        """Determine if take profit condition is met."""
        ...


@dataclass(frozen=True, slots=True)
class FloorStrategyConfig:
    """Configuration dataclass for Floor strategy.

    This is parsed from apps.trading.models.StrategyConfig.config_dict
    and contains all Floor-specific parameters.

    Note: instrument and pip_size are NOT included here as they're passed
    separately to FloorStrategy.__init__
    """

    base_lot_size: Decimal
    retracement_lot_mode: LotMode
    retracement_lot_amount: Decimal

    retracement_pips: Decimal
    take_profit_pips: Decimal
    max_layers: int
    max_retracements_per_layer: int

    volatility_lock_multiplier: Decimal

    retracement_trigger_progression: Progression
    retracement_trigger_increment: Decimal

    lot_size_progression: Progression
    lot_size_increment: Decimal

    entry_signal_lookback_ticks: int
    momentum_lookback_source: MomentumLookbackSource
    entry_signal_lookback_candles: int
    entry_signal_candle_granularity_seconds: int
    direction_method: DirectionMethod

    sma_fast_period: int
    sma_slow_period: int
    ema_fast_period: int
    ema_slow_period: int
    rsi_period: int
    rsi_overbought: int
    rsi_oversold: int


@dataclass
class LayerState:
    index: int
    direction: Direction
    entry_price: Decimal
    lot_size: Decimal
    retracements: int = 0


@dataclass
class FloorStrategyState:
    """State for Floor strategy.

    Implements the StrategyState protocol for type-safe state management.
    This state is stored in ExecutionState.strategy_state.

    Attributes:
        status: Current strategy status (RUNNING, PAUSED, STOPPED)
        initialized: Whether the strategy has been initialized
        cycle_entry_time: Start time of current trade cycle
        ticks_seen: Number of ticks processed
        price_history: Historical mid prices for indicators
        candle_closes: Candle close prices for momentum lookback
        current_candle_bucket_start_epoch: Current candle bucket start time
        current_candle_close: Current candle close price
        active_layers: List of active trading layers
        volatility_locked: Whether volatility lock is active
        margin_protection: Whether margin protection is active
        last_mid: Last mid price
        last_bid: Last bid price
        last_ask: Last ask price
    """

    status: StrategyStatus = StrategyStatus.RUNNING
    initialized: bool = False

    # Track the start of a "trade cycle" so we can emit entry/exit times
    # when the strategy closes all layers.
    cycle_entry_time: str | None = None

    ticks_seen: int = 0
    price_history: list[Decimal] = field(default_factory=list)

    # Candle-derived close history for momentum lookback when configured.
    candle_closes: list[Decimal] = field(default_factory=list)
    current_candle_bucket_start_epoch: int | None = None
    current_candle_close: Decimal | None = None

    active_layers: list[LayerState] = field(default_factory=list)
    volatility_locked: bool = False
    margin_protection: bool = False

    # Derived mid (from bid/ask) for indicator history/plotting.
    last_mid: Decimal | None = None
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None

    def add_layer(self, layer: LayerState) -> None:
        """Add a new layer to active layers."""
        self.active_layers.append(layer)

    def remove_layer(self, index: int) -> None:
        """Remove a layer by index."""
        self.active_layers = [layer for layer in self.active_layers if layer.index != index]

    def get_layer(self, index: int) -> LayerState | None:
        """Get a layer by index."""
        for layer in self.active_layers:
            if layer.index == index:
                return layer
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "initialized": bool(self.initialized),
            "cycle_entry_time": self.cycle_entry_time,
            "ticks_seen": int(self.ticks_seen),
            "price_history": [str(x) for x in self.price_history],
            "candle_closes": [str(x) for x in self.candle_closes],
            "current_candle_bucket_start_epoch": (
                int(self.current_candle_bucket_start_epoch)
                if self.current_candle_bucket_start_epoch is not None
                else None
            ),
            "current_candle_close": (
                str(self.current_candle_close) if self.current_candle_close is not None else None
            ),
            "active_layers": [
                {
                    "index": int(layer.index),
                    "direction": str(layer.direction),
                    "entry_price": str(layer.entry_price),
                    "lot_size": str(layer.lot_size),
                    "retracements": int(layer.retracements),
                }
                for layer in self.active_layers
            ],
            "volatility_locked": bool(self.volatility_locked),
            "margin_protection": bool(self.margin_protection),
            "last_mid": str(self.last_mid) if self.last_mid is not None else None,
            "last_bid": str(self.last_bid) if self.last_bid is not None else None,
            "last_ask": str(self.last_ask) if self.last_ask is not None else None,
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> FloorStrategyState:
        status_raw = str(raw.get("status") or StrategyStatus.RUNNING)
        try:
            status = StrategyStatus(status_raw)
        except Exception:
            status = StrategyStatus.RUNNING

        history_raw = raw.get("price_history")
        history: list[Decimal] = []
        if isinstance(history_raw, list):
            for v in history_raw:
                d = _to_decimal(v)
                if d is not None:
                    history.append(d)

        candle_closes_raw = raw.get("candle_closes")
        candle_closes: list[Decimal] = []
        if isinstance(candle_closes_raw, list):
            for v in candle_closes_raw:
                d = _to_decimal(v)
                if d is not None:
                    candle_closes.append(d)

        current_candle_bucket_raw = raw.get("current_candle_bucket_start_epoch")
        current_candle_bucket_start_epoch: int | None = None
        try:
            if current_candle_bucket_raw is not None:
                current_candle_bucket_start_epoch = int(current_candle_bucket_raw)
        except Exception:
            current_candle_bucket_start_epoch = None

        current_candle_close = _to_decimal(raw.get("current_candle_close"))

        layers: list[LayerState] = []
        layers_raw = raw.get("active_layers")
        if isinstance(layers_raw, list):
            for item in layers_raw:
                if not isinstance(item, dict):
                    continue
                direction_raw = str(item.get("direction") or Direction.LONG)
                try:
                    direction = Direction(direction_raw)
                except Exception:
                    direction = Direction.LONG

                entry_price = _to_decimal(item.get("entry_price")) or Decimal("0")
                lot_size = _to_decimal(item.get("lot_size")) or Decimal("0")
                layers.append(
                    LayerState(
                        index=int(item.get("index") or 0),
                        direction=direction,
                        entry_price=entry_price,
                        lot_size=lot_size,
                        retracements=int(item.get("retracements") or 0),
                    )
                )

        last_mid = _to_decimal(raw.get("last_mid"))
        last_bid = _to_decimal(raw.get("last_bid"))
        last_ask = _to_decimal(raw.get("last_ask"))

        cycle_entry_time_raw = raw.get("cycle_entry_time")
        cycle_entry_time = str(cycle_entry_time_raw) if cycle_entry_time_raw else None

        return FloorStrategyState(
            status=status,
            initialized=bool(raw.get("initialized") or False),
            cycle_entry_time=cycle_entry_time,
            ticks_seen=int(raw.get("ticks_seen") or 0),
            price_history=history,
            candle_closes=candle_closes,
            current_candle_bucket_start_epoch=current_candle_bucket_start_epoch,
            current_candle_close=current_candle_close,
            active_layers=layers,
            volatility_locked=bool(raw.get("volatility_locked") or False),
            margin_protection=bool(raw.get("margin_protection") or False),
            last_mid=last_mid,
            last_bid=last_bid,
            last_ask=last_ask,
        )


def _parse_iso_datetime_best_effort(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        s = str(value)
    except Exception:
        return None
    s = s.strip()
    if not s:
        return None
    # Accept Z suffix.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _tick_bucket_start_epoch_seconds(*, tick_dt: datetime, granularity_seconds: int) -> int | None:
    """Calculate candle bucket start epoch from datetime."""
    if granularity_seconds <= 0:
        return None
    epoch = int(tick_dt.timestamp())
    return epoch - (epoch % int(granularity_seconds))


def _canonical_event(event_type: str, **fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"event_type": str(event_type)}
    for k, v in fields.items():
        if v is None:
            continue
        out[str(k)] = v
    return out


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ============================================================================
# COMPONENT CLASSES
# ============================================================================


class PriceCalculator:
    """Handles price and P&L calculations."""

    def __init__(self, pip_size: Decimal) -> None:
        self.pip_size = pip_size

    def pips_between(self, price_a: Decimal, price_b: Decimal) -> Decimal:
        """Calculate pips between two prices."""
        return (price_b - price_a) / self.pip_size

    def calculate_pnl(self, layers: list[LayerState], bid: Decimal, ask: Decimal) -> Decimal:
        """Calculate net P&L in pips, weighted by lot size."""
        total = Decimal("0")
        weight = Decimal("0")

        for layer in layers:
            if layer.lot_size <= 0:
                continue

            mark = bid if layer.direction == Direction.LONG else ask
            pips = self.pips_between(layer.entry_price, mark)

            if layer.direction == Direction.SHORT:
                pips = -pips

            total += pips * layer.lot_size
            weight += layer.lot_size

        return total / weight if weight > 0 else Decimal("0")

    def against_position_pips(self, layer: LayerState, bid: Decimal, ask: Decimal) -> Decimal:
        """Calculate adverse movement in pips for a layer."""
        mark = bid if layer.direction == Direction.LONG else ask

        if layer.direction == Direction.LONG:
            if mark >= layer.entry_price:
                return Decimal("0")
            return abs(self.pips_between(layer.entry_price, mark))
        else:
            if mark <= layer.entry_price:
                return Decimal("0")
            return abs(self.pips_between(layer.entry_price, mark))


class IndicatorCalculator:
    """Handles technical indicator calculations."""

    @staticmethod
    def sma(values: list[Decimal]) -> Decimal:
        """Calculate Simple Moving Average."""
        return sum(values) / Decimal(len(values)) if values else Decimal("0")

    @staticmethod
    def ema(values: list[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        if not values:
            return Decimal("0")

        k = Decimal("2") / (Decimal(period) + Decimal("1"))
        ema_val = values[0]

        for v in values[1:]:
            ema_val = (v * k) + (ema_val * (Decimal("1") - k))

        return ema_val

    @staticmethod
    def rsi(values: list[Decimal], period: int) -> Decimal:
        """Calculate Relative Strength Index."""
        if len(values) < period + 1:
            return Decimal("50")

        gains: list[Decimal] = []
        losses: list[Decimal] = []

        for i in range(-period, 0):
            delta = values[i] - values[i - 1]
            if delta >= 0:
                gains.append(delta)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(-delta)

        avg_gain = sum(gains) / Decimal(period)
        avg_loss = sum(losses) / Decimal(period)

        if avg_loss == 0:
            return Decimal("100")

        rs = avg_gain / avg_loss
        return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))


# Legacy function wrappers for backward compatibility
def _pips_between(price_a: Decimal, price_b: Decimal, pip_size: Decimal) -> Decimal:
    return (price_b - price_a) / pip_size


def _sma(values: list[Decimal]) -> Decimal:
    return IndicatorCalculator.sma(values)


def _ema(values: list[Decimal], period: int) -> Decimal:
    return IndicatorCalculator.ema(values, period)


def _rsi(values: list[Decimal], period: int) -> Decimal:
    return IndicatorCalculator.rsi(values, period)


def _progress_value(*, base: Decimal, index: int, mode: Progression, inc: Decimal) -> Decimal:
    i = max(0, int(index))
    if mode == Progression.EQUAL:
        return base
    if mode == Progression.INVERSE:
        return base / Decimal(i + 1)
    if mode == Progression.EXPONENTIAL:
        return base * (inc ** Decimal(i))
    # additive
    return base + (inc * Decimal(i))


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

    def should_lock(self, volatility_series: list[Decimal]) -> bool:
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
    ) -> bool:
        """Determine if a retracement entry should be triggered for a layer."""
        if layer.retracements >= self.config.max_retracements_per_layer:
            return False

        against_pips = self.price_calc.against_position_pips(layer, bid, ask)
        trigger_pips = self._retracement_trigger_for_layer(layer.index)

        return (
            against_pips >= trigger_pips
            and active_layers_count <= self.config.max_layers
            and not volatility_locked
        )

    def should_take_profit(self, layers: list[LayerState], bid: Decimal, ask: Decimal) -> bool:
        """Determine if take profit condition is met."""
        total_pips = self.price_calc.calculate_pnl(layers, bid, ask)
        return total_pips >= self.config.take_profit_pips

    def _retracement_trigger_for_layer(self, layer_index: int) -> Decimal:
        """Calculate retracement trigger pips for a given layer."""
        return _progress_value(
            base=self.config.retracement_pips,
            index=layer_index,
            mode=self.config.retracement_trigger_progression,
            inc=self.config.retracement_trigger_increment,
        )


def _defaults() -> dict[str, Any]:
    raw = getattr(settings, "TRADING_FLOOR_STRATEGY_DEFAULTS", {})
    return dict(raw) if isinstance(raw, dict) else {}


def _config_value(config: dict[str, Any], key: str) -> Any:
    if key in config and config.get(key) is not None:
        return config.get(key)
    return _defaults().get(key)


def _parse_progression(value: Any) -> Progression:
    v = str(value or "additive")
    try:
        return Progression(v)
    except Exception:
        return Progression.ADDITIVE


def _parse_direction_method(value: Any) -> DirectionMethod:
    v = str(value or DirectionMethod.MOMENTUM).strip()
    try:
        return DirectionMethod(v)
    except Exception:
        return DirectionMethod.MOMENTUM


def _parse_momentum_lookback_source(value: Any) -> MomentumLookbackSource:
    v = str(value or MomentumLookbackSource.CANDLES).strip()
    try:
        return MomentumLookbackSource(v)
    except Exception:
        return MomentumLookbackSource.CANDLES


def _parse_lot_mode(value: Any) -> LotMode:
    v = str(value or LotMode.ADDITIVE).strip()
    try:
        return LotMode(v)
    except Exception:
        return LotMode.ADDITIVE


def _parse_required_decimal(config: dict[str, Any], key: str) -> Decimal:
    val = _config_value(config, key)
    d = _to_decimal(val)
    if d is None:
        raise ValueError(f"Missing or invalid '{key}'")
    return d


def _parse_required_str(config: dict[str, Any], key: str) -> str:
    val = _config_value(config, key)
    s = str(val or "").strip()
    if not s:
        raise ValueError(f"Missing '{key}'")
    return s


def _parse_int(config: dict[str, Any], key: str, *, required: bool = False) -> int:
    val = _config_value(config, key)
    if val is None:
        if required:
            raise ValueError(f"Missing '{key}'")
        return 0
    try:
        return int(val)
    except Exception as exc:
        raise ValueError(f"Invalid '{key}'") from exc


def _parse_required_int(config: dict[str, Any], key: str) -> int:
    return _parse_int(config, key, required=True)


@register_strategy("floor", "trading/schemas/floor.json", display_name="Floor Strategy")
class FloorStrategy(Strategy[FloorStrategyState]):
    """Floor strategy implementation with typed configuration.

    Generic over FloorStrategyState to provide type-safe state access.
    """

    config: FloorStrategyConfig

    # Components
    price_calc: PriceCalculator
    indicator_calc: IndicatorCalculator
    direction_decider: FloorDirectionDecider
    volatility_monitor: FloorVolatilityMonitor
    layer_manager: FloorLayerManager

    def __init__(
        self,
        instrument: str,
        pip_size: Decimal,
        strategy_config: "StrategyConfigModel",
    ) -> None:
        """Initialize the strategy with instrument, pip_size, and configuration.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for the instrument
            strategy_config: StrategyConfig model instance
        """
        # Parse config from model
        parsed_config = self._parse_config(strategy_config.config_dict)

        super().__init__(instrument, pip_size, parsed_config)

        # Initialize all components
        self.price_calc = PriceCalculator(pip_size)
        self.indicator_calc = IndicatorCalculator()
        self.direction_decider = FloorDirectionDecider(parsed_config, self.indicator_calc)
        self.volatility_monitor = FloorVolatilityMonitor(parsed_config, self.price_calc)
        self.layer_manager = FloorLayerManager(parsed_config, self.price_calc)

    @property
    def strategy_type(self) -> "StrategyType":
        """Return the strategy type enum value."""
        from apps.trading.enums import StrategyType

        return StrategyType.FLOOR

    def initialize_strategy_state(self, state_dict: dict[str, Any]) -> FloorStrategyState:
        """Convert dict to FloorStrategyState object.

        Args:
            state_dict: Dictionary containing strategy state from persistence

        Returns:
            FloorStrategyState: Initialized strategy state object
        """
        return FloorStrategyState.from_dict(state_dict)

    @staticmethod
    def _parse_config(raw: dict[str, Any]) -> FloorStrategyConfig:
        """Parse configuration dictionary to FloorStrategyConfig.

        Note: instrument is NOT parsed here as it's passed separately to __init__
        """
        base_lot_size = _parse_required_decimal(raw, "base_lot_size")
        retracement_lot_mode = _parse_lot_mode(_config_value(raw, "retracement_lot_mode"))
        retracement_lot_amount = _parse_required_decimal(raw, "retracement_lot_amount")

        retracement_pips = _parse_required_decimal(raw, "retracement_pips")
        take_profit_pips = _parse_required_decimal(raw, "take_profit_pips")
        max_layers = _parse_required_int(raw, "max_layers")
        max_retracements_per_layer = _parse_required_int(raw, "max_retracements_per_layer")

        volatility_lock_multiplier = _parse_required_decimal(raw, "volatility_lock_multiplier")

        retr_prog = _parse_progression(_config_value(raw, "retracement_trigger_progression"))
        retr_inc = _parse_required_decimal(raw, "retracement_trigger_increment")

        lot_prog = _parse_progression(_config_value(raw, "lot_size_progression"))
        lot_inc = _parse_required_decimal(raw, "lot_size_increment")

        direction_method = _parse_direction_method(_config_value(raw, "direction_method"))

        # Momentum lookback configuration (ticks vs candle closes).
        momentum_lookback_source = _parse_momentum_lookback_source(
            _config_value(raw, "momentum_lookback_source")
        )
        entry_signal_lookback_ticks = _parse_int(raw, "entry_signal_lookback_ticks")
        entry_signal_lookback_candles = _parse_int(raw, "entry_signal_lookback_candles")
        entry_signal_candle_granularity_seconds = _parse_int(
            raw, "entry_signal_candle_granularity_seconds"
        )

        # Apply sane defaults if not specified.
        if entry_signal_lookback_ticks <= 0:
            entry_signal_lookback_ticks = 100
        if entry_signal_lookback_candles <= 0:
            entry_signal_lookback_candles = 50
        if entry_signal_candle_granularity_seconds <= 0:
            entry_signal_candle_granularity_seconds = 60

        sma_fast_period = _parse_required_int(raw, "sma_fast_period")
        sma_slow_period = _parse_required_int(raw, "sma_slow_period")
        ema_fast_period = _parse_required_int(raw, "ema_fast_period")
        ema_slow_period = _parse_required_int(raw, "ema_slow_period")
        rsi_period = _parse_required_int(raw, "rsi_period")
        rsi_overbought = _parse_required_int(raw, "rsi_overbought")
        rsi_oversold = _parse_required_int(raw, "rsi_oversold")

        return FloorStrategyConfig(
            base_lot_size=base_lot_size,
            retracement_lot_mode=retracement_lot_mode,
            retracement_lot_amount=retracement_lot_amount,
            retracement_pips=retracement_pips,
            take_profit_pips=take_profit_pips,
            max_layers=max_layers,
            max_retracements_per_layer=max_retracements_per_layer,
            volatility_lock_multiplier=volatility_lock_multiplier,
            retracement_trigger_progression=retr_prog,
            retracement_trigger_increment=retr_inc,
            lot_size_progression=lot_prog,
            lot_size_increment=lot_inc,
            entry_signal_lookback_ticks=entry_signal_lookback_ticks,
            momentum_lookback_source=momentum_lookback_source,
            entry_signal_lookback_candles=entry_signal_lookback_candles,
            entry_signal_candle_granularity_seconds=entry_signal_candle_granularity_seconds,
            direction_method=direction_method,
            sma_fast_period=sma_fast_period,
            sma_slow_period=sma_slow_period,
            ema_fast_period=ema_fast_period,
            ema_slow_period=ema_slow_period,
            rsi_period=rsi_period,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
        )
        retracement_lot_mode = _parse_lot_mode(_config_value(raw, "retracement_lot_mode"))
        retracement_lot_amount = _parse_required_decimal(raw, "retracement_lot_amount")

        retracement_pips = _parse_required_decimal(raw, "retracement_pips")
        take_profit_pips = _parse_required_decimal(raw, "take_profit_pips")
        max_layers = _parse_required_int(raw, "max_layers")
        max_retracements_per_layer = _parse_required_int(raw, "max_retracements_per_layer")

        volatility_lock_multiplier = _parse_required_decimal(raw, "volatility_lock_multiplier")

        retr_prog = _parse_progression(_config_value(raw, "retracement_trigger_progression"))
        retr_inc = _parse_required_decimal(raw, "retracement_trigger_increment")

        lot_prog = _parse_progression(_config_value(raw, "lot_size_progression"))
        lot_inc = _parse_required_decimal(raw, "lot_size_increment")

        direction_method = _parse_direction_method(_config_value(raw, "direction_method"))

        # Momentum lookback configuration (ticks vs candle closes).
        momentum_lookback_source = _parse_momentum_lookback_source(
            _config_value(raw, "momentum_lookback_source")
        )
        entry_signal_lookback_ticks = _parse_int(raw, "entry_signal_lookback_ticks")
        entry_signal_lookback_candles = _parse_int(raw, "entry_signal_lookback_candles")
        entry_signal_candle_granularity_seconds = _parse_int(
            raw, "entry_signal_candle_granularity_seconds"
        )

        # Apply sane defaults if not specified.
        if entry_signal_lookback_ticks <= 0:
            entry_signal_lookback_ticks = 100
        if entry_signal_lookback_candles <= 0:
            entry_signal_lookback_candles = 50
        if entry_signal_candle_granularity_seconds <= 0:
            entry_signal_candle_granularity_seconds = 60

        sma_fast_period = _parse_required_int(raw, "sma_fast_period")
        sma_slow_period = _parse_required_int(raw, "sma_slow_period")
        ema_fast_period = _parse_required_int(raw, "ema_fast_period")
        ema_slow_period = _parse_required_int(raw, "ema_slow_period")
        rsi_period = _parse_required_int(raw, "rsi_period")
        rsi_overbought = _parse_required_int(raw, "rsi_overbought")
        rsi_oversold = _parse_required_int(raw, "rsi_oversold")

        return FloorStrategyConfig(
            base_lot_size=base_lot_size,
            retracement_lot_mode=retracement_lot_mode,
            retracement_lot_amount=retracement_lot_amount,
            retracement_pips=retracement_pips,
            take_profit_pips=take_profit_pips,
            max_layers=max_layers,
            max_retracements_per_layer=max_retracements_per_layer,
            volatility_lock_multiplier=volatility_lock_multiplier,
            retracement_trigger_progression=retr_prog,
            retracement_trigger_increment=retr_inc,
            lot_size_progression=lot_prog,
            lot_size_increment=lot_inc,
            entry_signal_lookback_ticks=entry_signal_lookback_ticks,
            momentum_lookback_source=momentum_lookback_source,
            entry_signal_lookback_candles=entry_signal_lookback_candles,
            entry_signal_candle_granularity_seconds=entry_signal_candle_granularity_seconds,
            direction_method=direction_method,
            sma_fast_period=sma_fast_period,
            sma_slow_period=sma_slow_period,
            ema_fast_period=ema_fast_period,
            ema_slow_period=ema_slow_period,
            rsi_period=rsi_period,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
        )

    def _update_candle_history(self, *, s: FloorStrategyState, tick_dt: datetime) -> None:
        """Update candle history with new tick timestamp."""
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

        if s.current_candle_bucket_start_epoch is None:
            s.current_candle_bucket_start_epoch = bucket_start
            s.current_candle_close = s.last_mid
            return

        # Same candle -> update close
        if int(s.current_candle_bucket_start_epoch) == int(bucket_start):
            s.current_candle_close = s.last_mid
            return

        # New candle -> finalize previous close
        if s.current_candle_close is not None:
            s.candle_closes.append(s.current_candle_close)

        # Trim to bounded size.
        max_needed = max(1, int(self.config.entry_signal_lookback_candles) + 5)
        if len(s.candle_closes) > max_needed:
            s.candle_closes = s.candle_closes[-max_needed:]

        s.current_candle_bucket_start_epoch = bucket_start
        s.current_candle_close = s.last_mid

    def _momentum_history(self, s: FloorStrategyState) -> list[Decimal]:
        if self.config.momentum_lookback_source == MomentumLookbackSource.CANDLES:
            # If we can't build candles (e.g., backtests without timestamps), fall back to ticks.
            if s.current_candle_bucket_start_epoch is None:
                return s.price_history
            # Include the current candle close (best-effort) so the decision can react live.
            out = list(s.candle_closes)
            if s.current_candle_close is not None:
                out.append(s.current_candle_close)
            return out
        return s.price_history

    def _has_enough_history_for_initial_entry(self, s: FloorStrategyState) -> bool:
        if self.config.direction_method == DirectionMethod.MOMENTUM:
            if self.config.momentum_lookback_source == MomentumLookbackSource.CANDLES:
                # If candle bucketing isn't possible (missing timestamps), fall back to ticks.
                if s.current_candle_bucket_start_epoch is None:
                    return int(s.ticks_seen) >= int(self.config.entry_signal_lookback_ticks)
                return len(self._momentum_history(s)) >= int(
                    self.config.entry_signal_lookback_candles
                )
            return int(s.ticks_seen) >= int(self.config.entry_signal_lookback_ticks)
        # For non-momentum methods keep existing behavior.
        return int(s.ticks_seen) >= int(self.config.entry_signal_lookback_ticks)

    def _volatility_series(self, s: FloorStrategyState) -> list[Decimal]:
        # Prefer candle closes when available (more stable), otherwise fall back to tick mid history.
        if s.current_candle_bucket_start_epoch is not None:
            out = list(s.candle_closes)
            if s.current_candle_close is not None:
                out.append(s.current_candle_close)
            if len(out) >= 2:
                return out
        return s.price_history

    def _maybe_emit_volatility_lock(
        self,
        *,
        s: FloorStrategyState,
        tick_dt: datetime,
        bid: Decimal,
        ask: Decimal,
        price: Decimal,
    ) -> dict[str, Any] | None:
        """Emit volatility lock event if conditions are met."""
        volatility_series = self._volatility_series(s)
        should_lock = self.volatility_monitor.should_lock(volatility_series)

        if should_lock and not s.volatility_locked:
            s.volatility_locked = True
            atr_pips, current_range_pips = self.volatility_monitor._calculate_atr(volatility_series)
            return _canonical_event(
                "volatility_lock",
                timestamp=tick_dt.isoformat(),
                instrument=self.instrument,
                layer_number=(len(s.active_layers) if s.active_layers else None),
                bid=str(bid),
                ask=str(ask),
                price=str(price),
                atr_pips=str(atr_pips) if atr_pips is not None else None,
                current_range_pips=str(current_range_pips)
                if current_range_pips is not None
                else None,
                volatility_lock_multiplier=str(self.config.volatility_lock_multiplier),
            )

        if (not should_lock) and s.volatility_locked:
            s.volatility_locked = False
        return None

    def _maybe_emit_margin_protection(
        self,
        *,
        s: FloorStrategyState,
        tick_dt: datetime,
        bid: Decimal,
        ask: Decimal,
        price: Decimal,
    ) -> dict[str, Any] | None:
        """Emit margin protection event if conditions are met."""
        if len(s.active_layers) < int(self.config.max_layers):
            s.margin_protection = False
            return None
        if s.margin_protection:
            return None

        s.margin_protection = True
        return _canonical_event(
            "margin_protection",
            timestamp=tick_dt.isoformat(),
            instrument=self.instrument,
            layer_number=(len(s.active_layers) if s.active_layers else None),
            bid=str(bid),
            ask=str(ask),
            price=str(price),
            current_layers=int(len(s.active_layers)),
            max_layers=int(self.config.max_layers),
        )

    def _lot_size_for_layer(self, layer_index: int) -> Decimal:
        return _progress_value(
            base=self.config.base_lot_size,
            index=layer_index,
            mode=self.config.lot_size_progression,
            inc=self.config.lot_size_increment,
        )

    def _retracement_lot_size(self, current: Decimal) -> Decimal:
        if self.config.retracement_lot_mode == LotMode.MULTIPLICATIVE:
            return current * self.config.retracement_lot_amount
        return current + self.config.retracement_lot_amount

    # ========================================================================
    # STRATEGY LIFECYCLE METHODS
    # ========================================================================

    def on_tick(
        self, *, tick: Tick, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Process a tick and return updated state and events.

        Args:
            tick: Tick dataclass containing market data
            state: Current execution state with FloorStrategyState

        Returns:
            StrategyResult: Updated state and list of emitted events
        """

        s = state.strategy_state

        # Tick already has Decimal values - no conversion needed
        bid = tick.bid
        ask = tick.ask

        derived_mid = (bid + ask) / Decimal("2")
        s.last_bid = bid
        s.last_ask = ask
        s.last_mid = derived_mid
        s.ticks_seen += 1
        s.price_history.append(derived_mid)

        # Update candle history
        self._update_candle_history(s=s, tick_dt=tick.timestamp)

        # Keep enough history
        max_needed = max(
            self.config.entry_signal_lookback_ticks,
            self.config.sma_slow_period,
            self.config.ema_slow_period,
            self.config.rsi_period + 1,
        )
        if len(s.price_history) > max_needed:
            s.price_history = s.price_history[-max_needed:]

        events_dict: list[dict[str, Any]] = []

        # Volatility lock
        vol_event = self._maybe_emit_volatility_lock(
            s=s, tick_dt=tick.timestamp, bid=bid, ask=ask, price=derived_mid
        )
        if vol_event is not None:
            events_dict.append(vol_event)

        # If not running, still track ticks but don't trade
        if s.status != StrategyStatus.RUNNING:
            new_state = state.copy_with(strategy_state=s)
            return self._convert_events_to_result(new_state, events_dict)

        # Continue with trading logic (retracement, take profit, etc.)
        # This is a simplified version - the full logic is in the original on_tick
        # For now, we'll just update the state
        new_state = state.copy_with(strategy_state=s)
        return self._convert_events_to_result(new_state, events_dict)

    def _convert_events_to_result(
        self, state: "ExecutionState", events_dict: list[dict[str, Any]]
    ) -> "StrategyResult":
        """Convert dict events to typed StrategyEvent objects."""
        from apps.trading.dataclasses import StrategyResult
        from apps.trading.events import (
            AddLayerEvent,
            InitialEntryEvent,
            MarginProtectionEvent,
            RemoveLayerEvent,
            RetracementEvent,
            TakeProfitEvent,
            VolatilityLockEvent,
        )

        typed_events: list["StrategyEvent"] = []
        for event_dict in events_dict:
            event_type = event_dict.get("event_type", "")

            if event_type == "initial_entry":
                typed_events.append(InitialEntryEvent.from_dict(event_dict))
            elif event_type == "retracement":
                typed_events.append(RetracementEvent.from_dict(event_dict))
            elif event_type == "take_profit":
                typed_events.append(TakeProfitEvent.from_dict(event_dict))
            elif event_type == "add_layer":
                typed_events.append(AddLayerEvent.from_dict(event_dict))
            elif event_type == "remove_layer":
                typed_events.append(RemoveLayerEvent.from_dict(event_dict))
            elif event_type == "volatility_lock":
                typed_events.append(VolatilityLockEvent.from_dict(event_dict))
            elif event_type == "margin_protection":
                typed_events.append(MarginProtectionEvent.from_dict(event_dict))
        return StrategyResult.with_events(state=state, events=typed_events)

    def on_start(
        self, *, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Called when strategy starts."""
        s = state.strategy_state  # Type: FloorStrategyState
        s.status = StrategyStatus.RUNNING
        return StrategyResult.from_state(state.copy_with(strategy_state=s))

    def on_stop(
        self, *, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Called when strategy stops."""
        s = state.strategy_state  # Type: FloorStrategyState
        s.status = StrategyStatus.STOPPED
        return StrategyResult.from_state(state.copy_with(strategy_state=s))

    def on_resume(
        self, *, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Called when strategy resumes."""
        s = state.strategy_state
        s.status = StrategyStatus.RUNNING
        return StrategyResult.from_state(state.copy_with(strategy_state=s))
