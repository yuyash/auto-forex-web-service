from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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


class MomentumLookbackSource(StrEnum):
    TICKS = "ticks"
    CANDLES = "candles"


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
                    "index": int(l.index),
                    "direction": str(l.direction),
                    "entry_price": str(l.entry_price),
                    "lot_size": str(l.lot_size),
                    "retracements": int(l.retracements),
                }
                for l in self.active_layers
            ],
            "volatility_locked": bool(self.volatility_locked),
            "margin_protection": bool(self.margin_protection),
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
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _tick_bucket_start_epoch_seconds(*, tick_ts: str, granularity_seconds: int) -> int | None:
    if granularity_seconds <= 0:
        return None
    dt = _parse_iso_datetime_best_effort(tick_ts)
    if dt is None:
        return None
    epoch = int(dt.timestamp())
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
            "dependsOn": {
                "field": "direction_method",
                "values": ["momentum"],
                "and": [{"field": "momentum_lookback_source", "values": ["ticks"]}],
            },
        },
        "momentum_lookback_source": {
            "type": "string",
            "title": "Momentum Lookback Source",
            "description": "Use raw ticks or candle closes to decide momentum direction.",
            "enum": ["ticks", "candles"],
            "default": "candles",
            "dependsOn": {"field": "direction_method", "values": ["momentum"]},
        },
        "entry_signal_lookback_candles": {
            "type": "integer",
            "title": "Momentum Lookback Candles",
            "description": "Number of candles to analyze when using candle-based momentum.",
            "default": 50,
            "dependsOn": {
                "field": "direction_method",
                "values": ["momentum"],
                "and": [{"field": "momentum_lookback_source", "values": ["candles"]}],
            },
        },
        "entry_signal_candle_granularity_seconds": {
            "type": "integer",
            "title": "Momentum Candle Granularity (seconds)",
            "description": "Candle size in seconds used for momentum lookback (e.g., 60 for 1m).",
            "default": 60,
            "dependsOn": {
                "field": "direction_method",
                "values": ["momentum"],
                "and": [{"field": "momentum_lookback_source", "values": ["candles"]}],
            },
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


def _parse_momentum_lookback_source(value: Any) -> MomentumLookbackSource:
    v = str(value or MomentumLookbackSource.CANDLES).strip()
    try:
        return MomentumLookbackSource(v)
    except Exception:
        return MomentumLookbackSource.CANDLES


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

    def _update_candle_history(self, *, s: FloorStrategyState, tick: dict[str, Any]) -> None:
        if self.config.direction_method != DirectionMethod.MOMENTUM:
            return
        if self.config.momentum_lookback_source != MomentumLookbackSource.CANDLES:
            return

        tick_ts = str(tick.get("timestamp") or "")
        bucket_start = _tick_bucket_start_epoch_seconds(
            tick_ts=tick_ts,
            granularity_seconds=int(self.config.entry_signal_candle_granularity_seconds),
        )
        if bucket_start is None:
            # Can't build candles without timestamps; fall back to tick history.
            return

        if s.current_candle_bucket_start_epoch is None:
            s.current_candle_bucket_start_epoch = bucket_start
            s.current_candle_close = s.last_mid
            return

        # Same candle -> update close.
        if int(s.current_candle_bucket_start_epoch) == int(bucket_start):
            s.current_candle_close = s.last_mid
            return

        # New candle -> finalize previous close.
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

    def _atr_and_current_range_pips(
        self, s: FloorStrategyState
    ) -> tuple[Decimal | None, Decimal | None]:
        series = self._volatility_series(s)
        if len(series) < 3:
            return None, None

        diffs_pips: list[Decimal] = []
        for i in range(1, len(series)):
            diffs_pips.append(abs(series[i] - series[i - 1]) / self.pip_size)

        if len(diffs_pips) < 2:
            return None, None

        current_range_pips = diffs_pips[-1]
        prior = diffs_pips[:-1]
        lookback = prior[-min(14, len(prior)) :]
        if not lookback:
            return None, None
        atr_pips = sum(lookback) / Decimal(len(lookback))
        return atr_pips, current_range_pips

    def _maybe_emit_volatility_lock(
        self,
        *,
        s: FloorStrategyState,
        tick: dict[str, Any],
        bid: Decimal,
        ask: Decimal,
        price: Decimal,
    ) -> dict[str, Any] | None:
        atr_pips, current_range_pips = self._atr_and_current_range_pips(s)
        if atr_pips is None or current_range_pips is None:
            return None
        if atr_pips <= 0:
            return None

        should_lock = current_range_pips > (atr_pips * self.config.volatility_lock_multiplier)
        if should_lock and not s.volatility_locked:
            s.volatility_locked = True
            tick_ts = str(tick.get("timestamp") or "")
            return _canonical_event(
                "volatility_lock",
                timestamp=tick_ts or None,
                instrument=self.config.instrument,
                layer_number=(len(s.active_layers) if s.active_layers else None),
                bid=str(bid),
                ask=str(ask),
                price=str(price),
                atr_pips=str(atr_pips),
                current_range_pips=str(current_range_pips),
                volatility_lock_multiplier=str(self.config.volatility_lock_multiplier),
            )

        if (not should_lock) and s.volatility_locked:
            # Unlock silently; we only emit when entering the locked state.
            s.volatility_locked = False
        return None

    def _maybe_emit_margin_protection(
        self,
        *,
        s: FloorStrategyState,
        tick: dict[str, Any],
        bid: Decimal,
        ask: Decimal,
        price: Decimal,
    ) -> dict[str, Any] | None:
        if len(s.active_layers) < int(self.config.max_layers):
            s.margin_protection = False
            return None
        if s.margin_protection:
            return None

        s.margin_protection = True
        tick_ts = str(tick.get("timestamp") or "")
        return _canonical_event(
            "margin_protection",
            timestamp=tick_ts or None,
            instrument=self.config.instrument,
            layer_number=(len(s.active_layers) if s.active_layers else None),
            bid=str(bid),
            ask=str(ask),
            price=str(price),
            current_layers=int(len(s.active_layers)),
            max_layers=int(self.config.max_layers),
        )

    def on_start(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.RUNNING:
            s.status = StrategyStatus.RUNNING
        return s.to_dict(), []

    def on_pause(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.PAUSED:
            s.status = StrategyStatus.PAUSED
        return s.to_dict(), []

    def on_resume(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.RUNNING:
            s.status = StrategyStatus.RUNNING
        return s.to_dict(), []

    def on_stop(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        s = FloorStrategyState.from_dict(state)
        if s.status != StrategyStatus.STOPPED:
            s.status = StrategyStatus.STOPPED
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

        # Candle builder for candle-based momentum.
        self._update_candle_history(s=s, tick=tick)

        # Keep enough history for indicators
        max_needed = max(
            self.config.entry_signal_lookback_ticks,
            self.config.sma_slow_period,
            self.config.ema_slow_period,
            self.config.rsi_period + 1,
        )
        if len(s.price_history) > max_needed:
            s.price_history = s.price_history[-max_needed:]

        events: list[dict[str, Any]] = []

        # Volatility lock (transition-based event).
        vol_event = self._maybe_emit_volatility_lock(
            s=s, tick=tick, bid=bid, ask=ask, price=derived_mid
        )
        if vol_event is not None:
            events.append(vol_event)

        # If paused/stopped, still track ticks but never trade
        if s.status != StrategyStatus.RUNNING:
            return s.to_dict(), list(events)

        # Initial entry
        if not s.initialized and self._has_enough_history_for_initial_entry(s):
            tick_ts = str(tick.get("timestamp") or "")
            history = (
                self._momentum_history(s)
                if self.config.direction_method == DirectionMethod.MOMENTUM
                else s.price_history
            )
            direction = self._decide_direction(history)
            entry_price = ask if direction == Direction.LONG else bid
            layer = LayerState(
                index=0,
                direction=direction,
                entry_price=entry_price,
                lot_size=self._lot_size_for_layer(0),
            )
            s.active_layers = [layer]
            s.initialized = True
            if tick_ts:
                s.cycle_entry_time = tick_ts
            events.append(
                _canonical_event(
                    "add_layer",
                    timestamp=tick_ts or None,
                    instrument=self.config.instrument,
                    layer_number=1,
                    direction=str(direction),
                    bid=str(bid),
                    ask=str(ask),
                    price=str(derived_mid),
                )
            )
            events.append(
                _canonical_event(
                    "initial_entry",
                    timestamp=tick_ts or None,
                    instrument=self.config.instrument,
                    layer_number=1,
                    retracement_count=0,
                    direction=str(direction),
                    units=str(layer.lot_size),
                    bid=str(bid),
                    ask=str(ask),
                    price=str(entry_price),
                    entry_price=str(entry_price),
                    max_retracements_per_layer=int(self.config.max_retracements_per_layer),
                )
            )

            # Margin protection becomes active when reaching max layers.
            mp_event = self._maybe_emit_margin_protection(
                s=s, tick=tick, bid=bid, ask=ask, price=derived_mid
            )
            if mp_event is not None:
                events.append(mp_event)

        if not s.active_layers:
            return s.to_dict(), list(events)

        # Take profit check (close all)
        total_pips = self._net_pips(s.active_layers, bid=bid, ask=ask)
        if total_pips >= self.config.take_profit_pips:
            # Compute realized P&L in quote currency using current bid/ask.
            # Assumption: lot_size is treated as units.
            exit_ts = str(tick.get("timestamp") or "")
            cycle_entry_time = s.cycle_entry_time

            total_units = sum((l.lot_size for l in s.active_layers), Decimal("0"))
            weighted_entry = Decimal("0")
            if total_units > 0:
                weighted_entry = (
                    sum(
                        (l.entry_price * l.lot_size for l in s.active_layers if l.lot_size > 0),
                        Decimal("0"),
                    )
                    / total_units
                )

            # Historically this strategy assumed a single direction per cycle.
            # If layers contain mixed directions (possible when direction is re-evaluated
            # on new layer creation), report a neutral/mixed direction and use mid for
            # display-only exit_price.
            directions = {l.direction for l in s.active_layers}
            if len(directions) == 1:
                overall_direction = next(iter(directions))
                exit_price = bid if overall_direction == Direction.LONG else ask
                direction_out: str | None = str(overall_direction)
            else:
                exit_price = derived_mid
                direction_out = "mixed"

            total_pnl = Decimal("0")
            for l in s.active_layers:
                if l.lot_size <= 0:
                    continue
                if l.direction == Direction.LONG:
                    total_pnl += (bid - l.entry_price) * l.lot_size
                else:
                    total_pnl += (l.entry_price - ask) * l.lot_size

            max_layer_number = max((int(l.index) + 1 for l in s.active_layers), default=1)
            events.append(
                _canonical_event(
                    "take_profit",
                    timestamp=exit_ts or None,
                    instrument=self.config.instrument,
                    layer_number=max_layer_number,
                    retracement_count=0,
                    direction=direction_out,
                    units=str(total_units) if total_units > 0 else None,
                    bid=str(bid),
                    ask=str(ask),
                    price=str(exit_price),
                    entry_price=str(weighted_entry) if total_units > 0 else None,
                    exit_price=str(exit_price),
                    pips=str(total_pips),
                    pnl=str(total_pnl),
                    entry_time=cycle_entry_time,
                    exit_time=exit_ts or None,
                )
            )
            events.append(
                _canonical_event(
                    "remove_layer",
                    timestamp=exit_ts or None,
                    instrument=self.config.instrument,
                    layer_number=1,
                    bid=str(bid),
                    ask=str(ask),
                    price=str(exit_price),
                )
            )
            s.active_layers = []
            s.initialized = False
            s.cycle_entry_time = None
            s.volatility_locked = False
            s.margin_protection = False
            return s.to_dict(), list(events)

        # Retracement logic per layer
        for layer in list(s.active_layers):
            if layer.retracements >= self.config.max_retracements_per_layer:
                continue

            against_pips = self._against_position_pips(layer, bid=bid, ask=ask)
            trigger_pips = self._retracement_trigger_for_layer(layer.index)
            if (
                against_pips >= trigger_pips
                and len(s.active_layers) <= self.config.max_layers
                and not s.volatility_locked
            ):
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
                tick_ts = str(tick.get("timestamp") or "")
                events.append(
                    _canonical_event(
                        "retracement",
                        timestamp=tick_ts or None,
                        instrument=self.config.instrument,
                        layer_number=int(layer.index) + 1,
                        retracement_count=int(layer.retracements),
                        direction=str(layer.direction),
                        units=str(lot_size),
                        bid=str(bid),
                        ask=str(ask),
                        price=str(fill_price),
                        entry_price=str(fill_price),
                        max_retracements_per_layer=int(self.config.max_retracements_per_layer),
                    )
                )

                # unlock next layer when max retracements reached
                if (
                    layer.retracements >= self.config.max_retracements_per_layer
                    and len(s.active_layers) < self.config.max_layers
                    and not s.volatility_locked
                ):
                    next_idx = len(s.active_layers)

                    # Re-evaluate direction when creating a new layer (instead of inheriting).
                    # This matches the expectation that each layer's direction is decided at
                    # creation time from the latest indicator history.
                    history = (
                        self._momentum_history(s)
                        if self.config.direction_method == DirectionMethod.MOMENTUM
                        else s.price_history
                    )
                    new_direction = self._decide_direction(history)
                    new_fill_price = ask if new_direction == Direction.LONG else bid

                    new_layer = LayerState(
                        index=next_idx,
                        direction=new_direction,
                        entry_price=new_fill_price,
                        lot_size=self._lot_size_for_layer(next_idx),
                    )
                    s.active_layers.append(new_layer)
                    tick_ts = str(tick.get("timestamp") or "")
                    events.append(
                        _canonical_event(
                            "add_layer",
                            timestamp=tick_ts or None,
                            instrument=self.config.instrument,
                            layer_number=int(next_idx) + 1,
                            direction=str(new_layer.direction),
                            bid=str(bid),
                            ask=str(ask),
                            price=str(derived_mid),
                        )
                    )
                    events.append(
                        _canonical_event(
                            "initial_entry",
                            timestamp=tick_ts or None,
                            instrument=self.config.instrument,
                            layer_number=int(next_idx) + 1,
                            retracement_count=0,
                            direction=str(new_layer.direction),
                            units=str(new_layer.lot_size),
                            bid=str(bid),
                            ask=str(ask),
                            price=str(new_fill_price),
                            entry_price=str(new_fill_price),
                            max_retracements_per_layer=int(self.config.max_retracements_per_layer),
                        )
                    )

                    # Margin protection becomes active when reaching max layers.
                    mp_event = self._maybe_emit_margin_protection(
                        s=s, tick=tick, bid=bid, ask=ask, price=derived_mid
                    )
                    if mp_event is not None:
                        events.append(mp_event)

        return s.to_dict(), list(events)

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
