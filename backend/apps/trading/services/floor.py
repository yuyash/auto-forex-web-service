from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from django.conf import settings

from apps.market.services.instruments import get_pip_size
from apps.trading.services.base import Strategy
from apps.trading.services.registry import register_strategy


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


@dataclass(frozen=True)
class FloorStrategyConfig:
    instrument: str

    base_lot_size: Decimal
    retracement_lot_mode: str
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
    status: StrategyStatus = StrategyStatus.RUNNING
    initialized: bool = False

    ticks_seen: int = 0
    price_history: list[Decimal] = field(default_factory=list)

    active_layers: list[LayerState] = field(default_factory=list)
    volatility_locked: bool = False

    # Derived mid (from bid/ask) for indicator history/plotting.
    last_mid: Decimal | None = None
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "initialized": bool(self.initialized),
            "ticks_seen": int(self.ticks_seen),
            "price_history": [str(x) for x in self.price_history],
            "active_layers": [
                {
                    "index": int(l.index),
                    "direction": str(l.direction),
                    "entry_price": str(l.entry_price),
                    "lot_size": str(l.lot_size),
                    "retracements": int(l.retracements),
                }
                for l in self.active_layers
            ],
            "volatility_locked": bool(self.volatility_locked),
            "last_mid": str(self.last_mid) if self.last_mid is not None else None,
            "last_bid": str(self.last_bid) if self.last_bid is not None else None,
            "last_ask": str(self.last_ask) if self.last_ask is not None else None,
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "FloorStrategyState":
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

        return FloorStrategyState(
            status=status,
            initialized=bool(raw.get("initialized") or False),
            ticks_seen=int(raw.get("ticks_seen") or 0),
            price_history=history,
            active_layers=layers,
            volatility_locked=bool(raw.get("volatility_locked") or False),
            last_mid=last_mid,
            last_bid=last_bid,
            last_ask=last_ask,
        )


@dataclass(frozen=True)
class StrategyEvent:
    type: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **({"details": self.details} if self.details else {})}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _pips_between(price_a: Decimal, price_b: Decimal, pip_size: Decimal) -> Decimal:
    return (price_b - price_a) / pip_size


def _sma(values: list[Decimal]) -> Decimal:
    return sum(values) / Decimal(len(values))


def _ema(values: list[Decimal], period: int) -> Decimal:
    if not values:
        return Decimal("0")
    k = Decimal("2") / (Decimal(period) + Decimal("1"))
    ema_val = values[0]
    for v in values[1:]:
        ema_val = (v * k) + (ema_val * (Decimal("1") - k))
    return ema_val


def _rsi(values: list[Decimal], period: int) -> Decimal:
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


FLOOR_STRATEGY_CONFIG_SCHEMA: dict[str, Any] = {
    "display_name": "Floor Strategy",
    "type": "object",
    "properties": {
        "instrument": {
            "type": "string",
            "title": "Instrument",
            "description": "Trading instrument (currency pair) to trade.",
        },
        "base_lot_size": {
            "type": "number",
            "title": "Base Lot Size",
            "description": "Initial lot size for the first entry.",
        },
        "retracement_lot_mode": {
            "type": "string",
            "title": "Retracement Lot Mode",
            "enum": ["additive", "multiplicative"],
            "description": "How lot size changes on each retracement entry.",
        },
        "retracement_lot_amount": {
            "type": "number",
            "title": "Retracement Lot Amount",
            "description": "Amount to add/multiply by on each retracement entry.",
        },
        "retracement_pips": {
            "type": "number",
            "title": "Retracement Pips",
            "description": "Adverse movement in pips required to trigger a retracement entry.",
        },
        "take_profit_pips": {
            "type": "number",
            "title": "Take Profit Pips",
            "description": "Profit in pips required to close the position.",
        },
        "max_layers": {
            "type": "integer",
            "title": "Maximum Layers",
            "description": "Maximum number of layers that can be opened.",
        },
        "max_retracements_per_layer": {
            "type": "integer",
            "title": "Max Retracements Per Layer",
            "description": "Max number of retracement entries allowed per layer before opening the next one.",
        },
        "volatility_lock_multiplier": {
            "type": "number",
            "title": "Volatility Lock Multiplier",
            "description": "ATR multiplier threshold to trigger volatility lock.",
        },
        "retracement_trigger_progression": {
            "type": "string",
            "title": "Retracement Trigger Progression",
            "enum": ["equal", "additive", "exponential", "inverse"],
            "description": "How retracement triggers progress across layers.",
        },
        "retracement_trigger_increment": {
            "type": "number",
            "title": "Retracement Trigger Increment",
            "description": "Used for additive/exponential progression (ignored for equal/inverse).",
            "dependsOn": {
                "field": "retracement_trigger_progression",
                "values": ["additive", "exponential"],
            },
        },
        "lot_size_progression": {
            "type": "string",
            "title": "Lot Size Progression",
            "enum": ["equal", "additive", "exponential", "inverse"],
            "description": "How base lot size changes across layers.",
        },
        "lot_size_increment": {
            "type": "number",
            "title": "Lot Size Increment",
            "description": "Used for additive/exponential progression (ignored for equal/inverse).",
            "dependsOn": {"field": "lot_size_progression", "values": ["additive", "exponential"]},
        },
        "entry_signal_lookback_ticks": {
            "type": "integer",
            "title": "Momentum Lookback Ticks",
            "description": "Number of ticks to analyze when using momentum direction.",
            "dependsOn": {"field": "direction_method", "values": ["momentum"]},
        },
        "direction_method": {
            "type": "string",
            "title": "Direction Decision Method",
            "description": "Technical method used to decide long vs short.",
            "enum": [
                "momentum",
                "sma_crossover",
                "ema_crossover",
                "price_vs_sma",
                "rsi",
            ],
        },
        "sma_fast_period": {
            "type": "integer",
            "title": "SMA Fast Period",
            "description": "Fast SMA window size (in ticks).",
            "dependsOn": {"field": "direction_method", "values": ["sma_crossover"]},
        },
        "sma_slow_period": {
            "type": "integer",
            "title": "SMA Slow Period",
            "description": "Slow SMA window size (in ticks).",
            "dependsOn": {"field": "direction_method", "values": ["sma_crossover", "price_vs_sma"]},
        },
        "ema_fast_period": {
            "type": "integer",
            "title": "EMA Fast Period",
            "description": "Fast EMA window size (in ticks).",
            "dependsOn": {"field": "direction_method", "values": ["ema_crossover"]},
        },
        "ema_slow_period": {
            "type": "integer",
            "title": "EMA Slow Period",
            "description": "Slow EMA window size (in ticks).",
            "dependsOn": {"field": "direction_method", "values": ["ema_crossover"]},
        },
        "rsi_period": {
            "type": "integer",
            "title": "RSI Period",
            "description": "RSI window size (in ticks).",
            "dependsOn": {"field": "direction_method", "values": ["rsi"]},
        },
        "rsi_overbought": {
            "type": "integer",
            "title": "RSI Overbought",
            "description": "RSI threshold above which to short.",
            "dependsOn": {"field": "direction_method", "values": ["rsi"]},
        },
        "rsi_oversold": {
            "type": "integer",
            "title": "RSI Oversold",
            "description": "RSI threshold below which to long.",
            "dependsOn": {"field": "direction_method", "values": ["rsi"]},
        },
    },
    "required": [
        "instrument",
        "base_lot_size",
        "retracement_lot_mode",
        "retracement_lot_amount",
        "retracement_pips",
        "take_profit_pips",
    ],
}


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


@register_strategy("floor", FLOOR_STRATEGY_CONFIG_SCHEMA, display_name="Floor Strategy")
class FloorStrategyService(Strategy):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.config = self._parse_config(config)
        self.pip_size = get_pip_size(instrument=self.config.instrument)

    @staticmethod
    def _parse_config(raw: dict[str, Any]) -> FloorStrategyConfig:
        instrument = _parse_required_str(raw, "instrument")

        base_lot_size = _parse_required_decimal(raw, "base_lot_size")
        retracement_lot_mode = _parse_required_str(raw, "retracement_lot_mode")
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

        entry_signal_lookback_ticks = _parse_required_int(raw, "entry_signal_lookback_ticks")
        direction_method = _parse_direction_method(_config_value(raw, "direction_method"))

        sma_fast_period = _parse_required_int(raw, "sma_fast_period")
        sma_slow_period = _parse_required_int(raw, "sma_slow_period")
        ema_fast_period = _parse_required_int(raw, "ema_fast_period")
        ema_slow_period = _parse_required_int(raw, "ema_slow_period")
        rsi_period = _parse_required_int(raw, "rsi_period")
        rsi_overbought = _parse_required_int(raw, "rsi_overbought")
        rsi_oversold = _parse_required_int(raw, "rsi_oversold")

        return FloorStrategyConfig(
            instrument=instrument,
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
            direction_method=direction_method,
            sma_fast_period=sma_fast_period,
            sma_slow_period=sma_slow_period,
            ema_fast_period=ema_fast_period,
            ema_slow_period=ema_slow_period,
            rsi_period=rsi_period,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
        )

    def on_start(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.RUNNING:
            s.status = StrategyStatus.RUNNING
            return s.to_dict(), [StrategyEvent(type="strategy_started").to_dict()]
        return s.to_dict(), []

    def on_pause(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.PAUSED:
            s.status = StrategyStatus.PAUSED
            return s.to_dict(), [StrategyEvent(type="strategy_paused").to_dict()]
        return s.to_dict(), []

    def on_resume(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.RUNNING:
            s.status = StrategyStatus.RUNNING
            return s.to_dict(), [StrategyEvent(type="strategy_resumed").to_dict()]
        return s.to_dict(), []

    def on_stop(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.STOPPED:
            s.status = StrategyStatus.STOPPED
            return s.to_dict(), [StrategyEvent(type="strategy_stopped").to_dict()]
        return s.to_dict(), []

    def on_tick(
        self, *, tick: dict[str, Any], state: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)

        bid = _to_decimal(tick.get("bid"))
        ask = _to_decimal(tick.get("ask"))
        mid = _to_decimal(tick.get("mid"))

        # Prefer bid/ask for trade decisions.
        # If only mid is available (older backtests), treat it as both bid and ask.
        if bid is None or ask is None:
            if mid is None:
                return s.to_dict(), []
            bid = mid
            ask = mid

        derived_mid = (bid + ask) / Decimal("2")
        s.last_bid = bid
        s.last_ask = ask
        s.last_mid = derived_mid
        s.ticks_seen += 1
        s.price_history.append(derived_mid)

        # Keep enough history for indicators
        max_needed = max(
            self.config.entry_signal_lookback_ticks,
            self.config.sma_slow_period,
            self.config.ema_slow_period,
            self.config.rsi_period + 1,
        )
        if len(s.price_history) > max_needed:
            s.price_history = s.price_history[-max_needed:]

        events: list[StrategyEvent] = []

        # If paused/stopped, still track ticks but never trade
        if s.status != StrategyStatus.RUNNING:
            return s.to_dict(), [e.to_dict() for e in events]

        # Initial entry
        if not s.initialized and s.ticks_seen >= self.config.entry_signal_lookback_ticks:
            direction = self._decide_direction(s.price_history)
            entry_price = ask if direction == Direction.LONG else bid
            layer = LayerState(
                index=0,
                direction=direction,
                entry_price=entry_price,
                lot_size=self._lot_size_for_layer(0),
            )
            s.active_layers = [layer]
            s.initialized = True
            events.append(
                StrategyEvent(
                    type="open",
                    details={
                        "layer": 0,
                        "direction": str(direction),
                        "entry_price": str(entry_price),
                        "lot_size": str(layer.lot_size),
                        "instrument": self.config.instrument,
                    },
                )
            )
            events.append(StrategyEvent(type="layer_opened", details={"layer": 0}))

        if not s.active_layers:
            return s.to_dict(), [e.to_dict() for e in events]

        # Take profit check (close all)
        total_pips = self._net_pips(s.active_layers, bid=bid, ask=ask)
        if total_pips >= self.config.take_profit_pips:
            events.append(
                StrategyEvent(
                    type="close",
                    details={
                        "reason": "take_profit",
                        "pips": str(total_pips),
                        "instrument": self.config.instrument,
                    },
                )
            )
            events.append(StrategyEvent(type="take_profit_hit", details={"pips": str(total_pips)}))
            s.active_layers = []
            s.initialized = False
            return s.to_dict(), [e.to_dict() for e in events]

        # Retracement logic per layer
        for layer in list(s.active_layers):
            if layer.retracements >= self.config.max_retracements_per_layer:
                continue

            against_pips = self._against_position_pips(layer, bid=bid, ask=ask)
            trigger_pips = self._retracement_trigger_for_layer(layer.index)
            if against_pips >= trigger_pips and len(s.active_layers) <= self.config.max_layers:
                # retracement entry (as another open event)
                layer.retracements += 1
                prev_lot_size = layer.lot_size
                lot_size = self._retracement_lot_size(prev_lot_size)
                added_lot = lot_size - prev_lot_size

                fill_price = ask if layer.direction == Direction.LONG else bid

                # This strategy models each layer as an aggregated position.
                # When adding a retracement entry, update the layer entry price to the weighted
                # average, so further retracement entries require additional adverse movement.
                if lot_size > 0 and added_lot > 0 and prev_lot_size > 0:
                    layer.entry_price = (
                        (layer.entry_price * prev_lot_size) + (fill_price * added_lot)
                    ) / lot_size
                layer.lot_size = lot_size
                events.append(
                    StrategyEvent(
                        type="open",
                        details={
                            "layer": int(layer.index),
                            "direction": str(layer.direction),
                            "entry_price": str(fill_price),
                            "lot_size": str(lot_size),
                            "instrument": self.config.instrument,
                            "retracement_open": True,
                            "retracement": int(layer.retracements),
                            "against_pips": str(against_pips),
                            "trigger_pips": str(trigger_pips),
                        },
                    )
                )
                events.append(
                    StrategyEvent(
                        type="layer_retracement_opened",
                        details={"layer": int(layer.index), "retracement": int(layer.retracements)},
                    )
                )

                # unlock next layer when max retracements reached
                if (
                    layer.retracements >= self.config.max_retracements_per_layer
                    and len(s.active_layers) < self.config.max_layers
                ):
                    next_idx = len(s.active_layers)
                    new_layer = LayerState(
                        index=next_idx,
                        direction=layer.direction,
                        entry_price=fill_price,
                        lot_size=self._lot_size_for_layer(next_idx),
                    )
                    s.active_layers.append(new_layer)
                    events.append(
                        StrategyEvent(
                            type="open",
                            details={
                                "layer": int(next_idx),
                                "direction": str(new_layer.direction),
                                "entry_price": str(fill_price),
                                "lot_size": str(new_layer.lot_size),
                                "instrument": self.config.instrument,
                            },
                        )
                    )
                    events.append(
                        StrategyEvent(type="layer_opened", details={"layer": int(next_idx)})
                    )

        return s.to_dict(), [e.to_dict() for e in events]

    def _decide_direction(self, history: list[Decimal]) -> Direction:
        method = self.config.direction_method
        if method in {
            DirectionMethod.OHLC_SMA_CROSSOVER,
            DirectionMethod.OHLC_EMA_CROSSOVER,
            DirectionMethod.OHLC_PRICE_VS_SMA,
        }:
            # Fallback to tick-based momentum if OHLC not provided
            method = DirectionMethod.MOMENTUM

        if method == DirectionMethod.SMA_CROSSOVER:
            if len(history) < self.config.sma_slow_period:
                return Direction.LONG
            slow = history[-self.config.sma_slow_period :]
            fast = history[-self.config.sma_fast_period :]
            return Direction.LONG if _sma(fast) >= _sma(slow) else Direction.SHORT

        if method == DirectionMethod.EMA_CROSSOVER:
            if len(history) < self.config.ema_slow_period:
                return Direction.LONG
            slow = history[-self.config.ema_slow_period :]
            fast = history[-self.config.ema_fast_period :]
            return (
                Direction.LONG
                if _ema(fast, self.config.ema_fast_period)
                >= _ema(slow, self.config.ema_slow_period)
                else Direction.SHORT
            )

        if method == DirectionMethod.PRICE_VS_SMA:
            if len(history) < self.config.sma_slow_period:
                return Direction.LONG
            slow = history[-self.config.sma_slow_period :]
            return Direction.LONG if history[-1] >= _sma(slow) else Direction.SHORT

        if method == DirectionMethod.RSI:
            rsi = _rsi(history, self.config.rsi_period)
            if rsi <= Decimal(self.config.rsi_oversold):
                return Direction.LONG
            if rsi >= Decimal(self.config.rsi_overbought):
                return Direction.SHORT
            # Neutral -> momentum

        # momentum (default)
        if len(history) < 2:
            return Direction.LONG
        return Direction.LONG if history[-1] >= history[0] else Direction.SHORT

    def _lot_size_for_layer(self, layer_index: int) -> Decimal:
        return _progress_value(
            base=self.config.base_lot_size,
            index=layer_index,
            mode=self.config.lot_size_progression,
            inc=self.config.lot_size_increment,
        )

    def _retracement_trigger_for_layer(self, layer_index: int) -> Decimal:
        return _progress_value(
            base=self.config.retracement_pips,
            index=layer_index,
            mode=self.config.retracement_trigger_progression,
            inc=self.config.retracement_trigger_increment,
        )

    def _retracement_lot_size(self, current: Decimal) -> Decimal:
        if str(self.config.retracement_lot_mode) == "multiplicative":
            return current * self.config.retracement_lot_amount
        return current + self.config.retracement_lot_amount

    def _against_position_pips(self, layer: LayerState, *, bid: Decimal, ask: Decimal) -> Decimal:
        mark = bid if layer.direction == Direction.LONG else ask
        if layer.direction == Direction.LONG:
            # losing if price < entry
            if mark >= layer.entry_price:
                return Decimal("0")
            return abs(_pips_between(layer.entry_price, mark, self.pip_size))

        # short
        if mark <= layer.entry_price:
            return Decimal("0")
        return abs(_pips_between(layer.entry_price, mark, self.pip_size))

    def _net_pips(self, layers: list[LayerState], *, bid: Decimal, ask: Decimal) -> Decimal:
        # Weighted by lot size (proxy). Positive means profit.
        total = Decimal("0")
        weight = Decimal("0")
        for l in layers:
            if l.lot_size <= 0:
                continue
            if l.direction == Direction.LONG:
                p = _pips_between(l.entry_price, bid, self.pip_size)
            else:
                p = _pips_between(ask, l.entry_price, self.pip_size)
            total += p * l.lot_size
            weight += l.lot_size
        if weight == 0:
            return Decimal("0")
        return total / weight
