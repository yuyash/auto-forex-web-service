"""Data models for Floor strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.trading.strategies.floor.enums import (
    Direction,
    DirectionMethod,
    LotMode,
    MomentumLookbackSource,
    Progression,
    StrategyStatus,
)


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

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "FloorStrategyConfig":
        """Create FloorStrategyConfig from raw configuration dictionary.

        Args:
            raw: Raw configuration dictionary from StrategyConfig.config_dict

        Returns:
            FloorStrategyConfig: Validated and typed configuration

        Raises:
            ValueError: If required fields are missing or invalid
        """
        from django.conf import settings

        def _defaults() -> dict[str, Any]:
            defaults = getattr(settings, "TRADING_FLOOR_STRATEGY_DEFAULTS", {})
            return dict(defaults) if isinstance(defaults, dict) else {}

        def _get_value(key: str) -> Any:
            if key in raw and raw.get(key) is not None:
                return raw.get(key)
            return _defaults().get(key)

        def _to_decimal(value: Any) -> Decimal | None:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError):
                return None

        def _parse_decimal(key: str) -> Decimal:
            val = _get_value(key)
            d = _to_decimal(val)
            if d is None:
                raise ValueError(f"Missing or invalid '{key}'")
            return d

        def _parse_int(key: str, required: bool = False) -> int:
            val = _get_value(key)
            if val is None:
                if required:
                    raise ValueError(f"Missing '{key}'")
                return 0
            try:
                return int(val)
            except Exception as exc:
                raise ValueError(f"Invalid '{key}'") from exc

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

        def _parse_momentum_source(value: Any) -> MomentumLookbackSource:
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

        # Parse all fields
        base_lot_size = _parse_decimal("base_lot_size")
        retracement_lot_mode = _parse_lot_mode(_get_value("retracement_lot_mode"))
        retracement_lot_amount = _parse_decimal("retracement_lot_amount")

        retracement_pips = _parse_decimal("retracement_pips")
        take_profit_pips = _parse_decimal("take_profit_pips")
        max_layers = _parse_int("max_layers", required=True)
        max_retracements_per_layer = _parse_int("max_retracements_per_layer", required=True)

        volatility_lock_multiplier = _parse_decimal("volatility_lock_multiplier")

        retr_prog = _parse_progression(_get_value("retracement_trigger_progression"))
        retr_inc = _parse_decimal("retracement_trigger_increment")

        lot_prog = _parse_progression(_get_value("lot_size_progression"))
        lot_inc = _parse_decimal("lot_size_increment")

        direction_method = _parse_direction_method(_get_value("direction_method"))

        momentum_lookback_source = _parse_momentum_source(_get_value("momentum_lookback_source"))
        entry_signal_lookback_ticks = _parse_int("entry_signal_lookback_ticks")
        entry_signal_lookback_candles = _parse_int("entry_signal_lookback_candles")
        entry_signal_candle_granularity_seconds = _parse_int(
            "entry_signal_candle_granularity_seconds"
        )

        # Apply defaults
        if entry_signal_lookback_ticks <= 0:
            entry_signal_lookback_ticks = 100
        if entry_signal_lookback_candles <= 0:
            entry_signal_lookback_candles = 50
        if entry_signal_candle_granularity_seconds <= 0:
            entry_signal_candle_granularity_seconds = 60

        sma_fast_period = _parse_int("sma_fast_period", required=True)
        sma_slow_period = _parse_int("sma_slow_period", required=True)
        ema_fast_period = _parse_int("ema_fast_period", required=True)
        ema_slow_period = _parse_int("ema_slow_period", required=True)
        rsi_period = _parse_int("rsi_period", required=True)
        rsi_overbought = _parse_int("rsi_overbought", required=True)
        rsi_oversold = _parse_int("rsi_oversold", required=True)

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


@dataclass
class Position:
    """Individual position entry (used in Hedging Mode)."""

    entry_price: Decimal
    lot_size: Decimal
    entry_time: datetime
    exit_price: Decimal | None = None
    exit_time: datetime | None = None


@dataclass
class LayerState:
    index: int
    direction: Direction
    entry_price: Decimal  # Weighted average in Netting Mode, first entry in Hedging Mode
    lot_size: Decimal  # Total lot size
    retracements: int = 0
    positions: list[Position] = field(default_factory=list)  # Individual positions for Hedging Mode


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
                    "positions": [
                        {
                            "entry_price": str(pos.entry_price),
                            "lot_size": str(pos.lot_size),
                            "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
                            "exit_price": str(pos.exit_price)
                            if pos.exit_price is not None
                            else None,
                            "exit_time": pos.exit_time.isoformat() if pos.exit_time else None,
                        }
                        for pos in layer.positions
                    ],
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

                # Parse positions for Hedging Mode
                positions: list[Position] = []
                positions_raw = item.get("positions", [])
                if isinstance(positions_raw, list):
                    for pos_item in positions_raw:
                        if not isinstance(pos_item, dict):
                            continue
                        pos_entry_price = _to_decimal(pos_item.get("entry_price")) or Decimal("0")
                        pos_lot_size = _to_decimal(pos_item.get("lot_size")) or Decimal("0")

                        # Parse entry_time
                        pos_entry_time_raw = pos_item.get("entry_time")
                        pos_entry_time: datetime | None = None
                        if pos_entry_time_raw:
                            try:
                                if isinstance(pos_entry_time_raw, datetime):
                                    pos_entry_time = pos_entry_time_raw
                                else:
                                    pos_entry_time = datetime.fromisoformat(str(pos_entry_time_raw))
                            except (ValueError, TypeError):
                                pass

                        # Parse exit_price
                        pos_exit_price = _to_decimal(pos_item.get("exit_price"))

                        # Parse exit_time
                        pos_exit_time_raw = pos_item.get("exit_time")
                        pos_exit_time: datetime | None = None
                        if pos_exit_time_raw:
                            try:
                                if isinstance(pos_exit_time_raw, datetime):
                                    pos_exit_time = pos_exit_time_raw
                                else:
                                    pos_exit_time = datetime.fromisoformat(str(pos_exit_time_raw))
                            except (ValueError, TypeError):
                                pass

                        if pos_entry_time:  # Only add position if entry_time is valid
                            positions.append(
                                Position(
                                    entry_price=pos_entry_price,
                                    lot_size=pos_lot_size,
                                    entry_time=pos_entry_time,
                                    exit_price=pos_exit_price,
                                    exit_time=pos_exit_time,
                                )
                            )

                layers.append(
                    LayerState(
                        index=int(item.get("index") or 0),
                        direction=direction,
                        entry_price=entry_price,
                        lot_size=lot_size,
                        retracements=int(item.get("retracements") or 0),
                        positions=positions,
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


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
