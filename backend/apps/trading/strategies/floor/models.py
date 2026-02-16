"""Data models for Floor strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.trading.strategies.floor.enums import Direction, StrategyStatus


def _to_decimal(value: Any, default: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


@dataclass(frozen=True, slots=True)
class FloorStrategyConfig:
    """Normalized Floor strategy configuration."""

    lot_unit_size: Decimal
    base_lot_size: Decimal
    take_profit_pips: Decimal
    retracement_pips: Decimal
    retracement_lot_mode: str
    retracement_lot_amount: Decimal
    max_layers: int
    max_retracements_per_layer: int
    candle_granularity_seconds: int
    candle_lookback_count: int
    hedging_enabled: bool
    allow_duplicate_units: bool
    margin_closeout_threshold: Decimal
    margin_cut_start_ratio: Decimal
    margin_cut_target_ratio: Decimal
    margin_protection_enabled: bool
    leverage: Decimal
    margin_rate: Decimal
    volatility_check_enabled: bool
    volatility_lock_multiplier: Decimal
    volatility_unlock_multiplier: Decimal
    atr_period: int
    atr_baseline_period: int
    market_condition_spread_limit_pips: Decimal
    market_condition_override_enabled: bool
    dynamic_parameter_adjustment_enabled: bool
    floor_profiles: list[dict[str, Decimal]]

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "FloorStrategyConfig":
        """Create normalized config from raw/legacy parameters."""
        lot_unit_size = _to_decimal(raw.get("lot_unit_size", "1000"), "1000")
        legacy_initial_units = raw.get("initial_units")
        if legacy_initial_units is not None:
            base_lot_size = _to_decimal(legacy_initial_units, "1000") / lot_unit_size
        else:
            base_lot_size = _to_decimal(raw.get("base_lot_size", "1"), "1")

        take_profit_pips = _to_decimal(
            raw.get("take_profit_pips", raw.get("profit_pips", "25")), "25"
        )
        retracement_pips = _to_decimal(
            raw.get("retracement_pips", raw.get("initial_retracement_pips", "30")), "30"
        )
        retracement_lot_mode = str(raw.get("retracement_lot_mode", "additive")).strip().lower()
        if retracement_lot_mode not in {"additive", "multiplicative"}:
            retracement_lot_mode = "additive"

        retracement_lot_amount = _to_decimal(
            raw.get(
                "retracement_lot_amount",
                raw.get("unit_increment", "1"),
            ),
            "1",
        )

        max_retracements_per_layer = _to_int(
            raw.get("max_retracements_per_layer", raw.get("max_additional_entries", 10)), 10
        )

        floor_profiles: list[dict[str, Decimal]] = []
        raw_profiles = raw.get("floor_profiles")
        if isinstance(raw_profiles, list):
            for profile in raw_profiles:
                if not isinstance(profile, dict):
                    continue
                floor_profiles.append(
                    {
                        "take_profit_pips": _to_decimal(
                            profile.get("take_profit_pips", take_profit_pips), str(take_profit_pips)
                        ),
                        "retracement_pips": _to_decimal(
                            profile.get("retracement_pips", retracement_pips), str(retracement_pips)
                        ),
                    }
                )
        else:
            # Backward compatibility with array-based per-floor keys.
            tp_values = raw.get("floor_take_profit_pips")
            rt_values = raw.get("floor_retracement_pips")
            if isinstance(tp_values, list) or isinstance(rt_values, list):
                max_len = max(
                    len(tp_values) if isinstance(tp_values, list) else 0,
                    len(rt_values) if isinstance(rt_values, list) else 0,
                )
                for idx in range(max_len):
                    tp_val = (
                        tp_values[idx]
                        if isinstance(tp_values, list) and idx < len(tp_values)
                        else take_profit_pips
                    )
                    rt_val = (
                        rt_values[idx]
                        if isinstance(rt_values, list) and idx < len(rt_values)
                        else retracement_pips
                    )
                    floor_profiles.append(
                        {
                            "take_profit_pips": _to_decimal(tp_val, str(take_profit_pips)),
                            "retracement_pips": _to_decimal(rt_val, str(retracement_pips)),
                        }
                    )

        return FloorStrategyConfig(
            lot_unit_size=lot_unit_size,
            base_lot_size=base_lot_size,
            take_profit_pips=take_profit_pips,
            retracement_pips=retracement_pips,
            retracement_lot_mode=retracement_lot_mode,
            retracement_lot_amount=retracement_lot_amount,
            max_layers=_to_int(raw.get("max_layers", "3"), 3),
            max_retracements_per_layer=max_retracements_per_layer,
            candle_granularity_seconds=_to_int(
                raw.get(
                    "candle_granularity_seconds",
                    raw.get("entry_signal_candle_granularity_seconds", "60"),
                ),
                60,
            ),
            candle_lookback_count=_to_int(
                raw.get(
                    "candle_lookback_count",
                    raw.get("entry_signal_lookback_candles", "20"),
                ),
                20,
            ),
            hedging_enabled=_to_bool(raw.get("hedging_enabled", False), False),
            allow_duplicate_units=_to_bool(raw.get("allow_duplicate_units", False), False),
            margin_closeout_threshold=_to_decimal(raw.get("margin_closeout_threshold", "0.8"), "0.8"),
            margin_cut_start_ratio=_to_decimal(raw.get("margin_cut_start_ratio", "0.6"), "0.6"),
            margin_cut_target_ratio=_to_decimal(raw.get("margin_cut_target_ratio", "0.5"), "0.5"),
            margin_protection_enabled=_to_bool(raw.get("margin_protection_enabled", True), True),
            leverage=_to_decimal(raw.get("leverage", "25"), "25"),
            margin_rate=_to_decimal(raw.get("margin_rate", "0.04"), "0.04"),
            volatility_check_enabled=_to_bool(raw.get("volatility_check_enabled", True), True),
            volatility_lock_multiplier=_to_decimal(
                raw.get("volatility_lock_multiplier", "5.0"), "5.0"
            ),
            volatility_unlock_multiplier=_to_decimal(
                raw.get("volatility_unlock_multiplier", "1.5"), "1.5"
            ),
            atr_period=_to_int(raw.get("atr_period", "14"), 14),
            atr_baseline_period=_to_int(raw.get("atr_baseline_period", "50"), 50),
            market_condition_spread_limit_pips=_to_decimal(
                raw.get("market_condition_spread_limit_pips", "3.0"), "3.0"
            ),
            market_condition_override_enabled=_to_bool(
                raw.get("market_condition_override_enabled", True), True
            ),
            dynamic_parameter_adjustment_enabled=_to_bool(
                raw.get("dynamic_parameter_adjustment_enabled", False), False
            ),
            floor_profiles=floor_profiles,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to normalized parameters for JSON column storage."""
        return {
            "lot_unit_size": str(self.lot_unit_size),
            "base_lot_size": str(self.base_lot_size),
            "take_profit_pips": str(self.take_profit_pips),
            "retracement_pips": str(self.retracement_pips),
            "retracement_lot_mode": self.retracement_lot_mode,
            "retracement_lot_amount": str(self.retracement_lot_amount),
            "max_layers": self.max_layers,
            "max_retracements_per_layer": self.max_retracements_per_layer,
            "candle_granularity_seconds": self.candle_granularity_seconds,
            "candle_lookback_count": self.candle_lookback_count,
            "hedging_enabled": self.hedging_enabled,
            "allow_duplicate_units": self.allow_duplicate_units,
            "margin_closeout_threshold": str(self.margin_closeout_threshold),
            "margin_cut_start_ratio": str(self.margin_cut_start_ratio),
            "margin_cut_target_ratio": str(self.margin_cut_target_ratio),
            "margin_protection_enabled": self.margin_protection_enabled,
            "leverage": str(self.leverage),
            "margin_rate": str(self.margin_rate),
            "volatility_check_enabled": self.volatility_check_enabled,
            "volatility_lock_multiplier": str(self.volatility_lock_multiplier),
            "volatility_unlock_multiplier": str(self.volatility_unlock_multiplier),
            "atr_period": self.atr_period,
            "atr_baseline_period": self.atr_baseline_period,
            "market_condition_spread_limit_pips": str(self.market_condition_spread_limit_pips),
            "market_condition_override_enabled": self.market_condition_override_enabled,
            "dynamic_parameter_adjustment_enabled": self.dynamic_parameter_adjustment_enabled,
            "floor_profiles": [
                {
                    "take_profit_pips": str(profile.get("take_profit_pips", self.take_profit_pips)),
                    "retracement_pips": str(profile.get("retracement_pips", self.retracement_pips)),
                }
                for profile in self.floor_profiles
            ],
        }

    def floor_take_profit_pips(self, floor_index: int) -> Decimal:
        if 0 <= floor_index < len(self.floor_profiles):
            return self.floor_profiles[floor_index].get("take_profit_pips", self.take_profit_pips)
        return self.take_profit_pips

    def floor_retracement_pips(self, floor_index: int) -> Decimal:
        if 0 <= floor_index < len(self.floor_profiles):
            return self.floor_profiles[floor_index].get("retracement_pips", self.retracement_pips)
        return self.retracement_pips


@dataclass
class CandleData:
    """Candle data for trend detection."""

    bucket_start_epoch: int
    close_price: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bucket_start_epoch": self.bucket_start_epoch,
            "close_price": str(self.close_price),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CandleData:
        """Create from dictionary."""
        return CandleData(
            bucket_start_epoch=data["bucket_start_epoch"],
            close_price=Decimal(str(data["close_price"])),
        )


@dataclass
class FloorStrategyState:
    """State for Floor strategy."""

    status: StrategyStatus = StrategyStatus.RUNNING
    candles: list[CandleData] = field(default_factory=list)
    current_candle_close: Decimal | None = None
    last_mid: Decimal | None = None
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None
    account_balance: Decimal = Decimal("0")
    account_nav: Decimal = Decimal("0")
    active_floor_index: int = 0
    home_floor_index: int = 0
    next_entry_id: int = 1
    floor_retracement_counts: dict[int, int] = field(default_factory=dict)
    floor_directions: dict[int, str] = field(default_factory=dict)
    return_stack: list[int] = field(default_factory=list)
    open_entries: list[dict[str, Any]] = field(default_factory=list)
    volatility_locked: bool = False
    lock_reason: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "candles": [c.to_dict() for c in self.candles],
            "current_candle_close": str(self.current_candle_close)
            if self.current_candle_close
            else None,
            "last_mid": str(self.last_mid) if self.last_mid else None,
            "last_bid": str(self.last_bid) if self.last_bid else None,
            "last_ask": str(self.last_ask) if self.last_ask else None,
            "account_balance": str(self.account_balance),
            "account_nav": str(self.account_nav),
            "active_floor_index": self.active_floor_index,
            "home_floor_index": self.home_floor_index,
            "next_entry_id": self.next_entry_id,
            "floor_retracement_counts": {str(k): v for k, v in self.floor_retracement_counts.items()},
            "floor_directions": {str(k): v for k, v in self.floor_directions.items()},
            "return_stack": list(self.return_stack),
            "open_entries": list(self.open_entries),
            "volatility_locked": self.volatility_locked,
            "lock_reason": self.lock_reason,
            "metrics": dict(self.metrics),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FloorStrategyState:
        """Create from dictionary."""
        def _decimal_or_none(val: Any) -> Decimal | None:
            if val is None:
                return None
            return _to_decimal(val, "0")

        floor_retracement_counts: dict[int, int] = {}
        raw_floor_counts = data.get("floor_retracement_counts", {})
        if isinstance(raw_floor_counts, dict):
            for key, value in raw_floor_counts.items():
                floor_retracement_counts[_to_int(key, 0)] = _to_int(value, 0)

        floor_directions: dict[int, str] = {}
        raw_floor_directions = data.get("floor_directions", {})
        if isinstance(raw_floor_directions, dict):
            for key, value in raw_floor_directions.items():
                val = str(value).strip().lower()
                if val in {Direction.LONG.value, Direction.SHORT.value}:
                    floor_directions[_to_int(key, 0)] = val

        return FloorStrategyState(
            status=StrategyStatus(data.get("status", StrategyStatus.RUNNING.value)),
            candles=[CandleData.from_dict(c) for c in data.get("candles", [])],
            current_candle_close=_decimal_or_none(data.get("current_candle_close")),
            last_mid=_decimal_or_none(data.get("last_mid")),
            last_bid=_decimal_or_none(data.get("last_bid")),
            last_ask=_decimal_or_none(data.get("last_ask")),
            account_balance=_to_decimal(data.get("account_balance", "0"), "0"),
            account_nav=_to_decimal(data.get("account_nav", "0"), "0"),
            active_floor_index=_to_int(data.get("active_floor_index", 0), 0),
            home_floor_index=_to_int(data.get("home_floor_index", 0), 0),
            next_entry_id=max(1, _to_int(data.get("next_entry_id", 1), 1)),
            floor_retracement_counts=floor_retracement_counts,
            floor_directions=floor_directions,
            return_stack=[
                _to_int(item, 0)
                for item in (data.get("return_stack", []) if isinstance(data.get("return_stack"), list) else [])
            ],
            open_entries=list(data.get("open_entries", []))
            if isinstance(data.get("open_entries"), list)
            else [],
            volatility_locked=_to_bool(data.get("volatility_locked", False), False),
            lock_reason=str(data.get("lock_reason", "")),
            metrics=dict(data.get("metrics", {})) if isinstance(data.get("metrics"), dict) else {},
        )

    @classmethod
    def from_strategy_state(cls, raw: Any) -> "FloorStrategyState":
        """Deserialize from persisted strategy_state payload."""
        if not isinstance(raw, dict):
            return cls()
        return cls.from_dict(raw)
