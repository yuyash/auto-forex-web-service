"""Data models for Floor strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.trading.strategies.floor.calculators import ProgressionCalculator
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
    # --- Intra-layer retracement lot sizing ---
    # Controls how lot size changes on each retracement entry *within* a single layer.
    retracement_lot_mode: str
    retracement_lot_amount: Decimal
    # --- Cross-layer retracement trigger progression ---
    # Controls how the *starting* retracement trigger pips change when a new layer opens.
    # Layer 0 uses retracement_pips as-is; Layer N applies the progression formula.
    retracement_trigger_progression: str
    retracement_trigger_increment: Decimal
    # --- Cross-layer take-profit trigger progression ---
    # Controls how the *starting* take-profit pips change when a new layer opens.
    # Layer 0 uses take_profit_pips as-is; Layer N applies the progression formula.
    take_profit_trigger_progression: str
    take_profit_trigger_increment: Decimal
    # --- Intra-layer take-profit pips adjustment ---
    # Controls how take-profit pips change on each retracement entry *within* a layer.
    take_profit_pips_mode: str
    take_profit_pips_amount: Decimal
    max_layers: int
    max_retracements_per_layer: int
    candle_granularity_seconds: int
    candle_lookback_count: int
    hedging_enabled: bool
    allow_duplicate_units: bool
    margin_cut_start_ratio: Decimal
    margin_cut_target_ratio: Decimal
    margin_protection_enabled: bool
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
        # Migrate legacy "inverse" → "divisive"
        if retracement_lot_mode == "inverse":
            retracement_lot_mode = "divisive"
        if retracement_lot_mode not in {
            "constant",
            "additive",
            "subtractive",
            "multiplicative",
            "divisive",
        }:
            retracement_lot_mode = "additive"

        retracement_lot_amount = _to_decimal(
            raw.get(
                "retracement_lot_amount",
                raw.get("unit_increment", "1"),
            ),
            "1",
        )

        # Cross-layer retracement trigger progression
        retracement_trigger_progression = (
            str(raw.get("retracement_trigger_progression", "constant")).strip().lower()
        )
        if retracement_trigger_progression not in {
            "constant",
            "additive",
            "subtractive",
            "multiplicative",
            "divisive",
        }:
            retracement_trigger_progression = "constant"
        retracement_trigger_increment = _to_decimal(
            raw.get("retracement_trigger_increment", "5"), "5"
        )

        # Cross-layer take-profit trigger progression
        take_profit_trigger_progression = (
            str(raw.get("take_profit_trigger_progression", "constant")).strip().lower()
        )
        if take_profit_trigger_progression not in {
            "constant",
            "additive",
            "subtractive",
            "multiplicative",
            "divisive",
        }:
            take_profit_trigger_progression = "constant"
        take_profit_trigger_increment = _to_decimal(
            raw.get("take_profit_trigger_increment", "5"), "5"
        )

        # Intra-layer take-profit pips adjustment
        take_profit_pips_mode = str(raw.get("take_profit_pips_mode", "constant")).strip().lower()
        if take_profit_pips_mode not in {
            "constant",
            "additive",
            "subtractive",
            "multiplicative",
            "divisive",
        }:
            take_profit_pips_mode = "constant"
        take_profit_pips_amount = _to_decimal(raw.get("take_profit_pips_amount", "5"), "5")

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
            retracement_trigger_progression=retracement_trigger_progression,
            retracement_trigger_increment=retracement_trigger_increment,
            take_profit_trigger_progression=take_profit_trigger_progression,
            take_profit_trigger_increment=take_profit_trigger_increment,
            take_profit_pips_mode=take_profit_pips_mode,
            take_profit_pips_amount=take_profit_pips_amount,
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
            margin_cut_start_ratio=_to_decimal(raw.get("margin_cut_start_ratio", "0.6"), "0.6"),
            margin_cut_target_ratio=_to_decimal(raw.get("margin_cut_target_ratio", "0.5"), "0.5"),
            margin_protection_enabled=_to_bool(raw.get("margin_protection_enabled", True), True),
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
            "retracement_trigger_progression": self.retracement_trigger_progression,
            "retracement_trigger_increment": str(self.retracement_trigger_increment),
            "take_profit_trigger_progression": self.take_profit_trigger_progression,
            "take_profit_trigger_increment": str(self.take_profit_trigger_increment),
            "take_profit_pips_mode": self.take_profit_pips_mode,
            "take_profit_pips_amount": str(self.take_profit_pips_amount),
            "max_layers": self.max_layers,
            "max_retracements_per_layer": self.max_retracements_per_layer,
            "candle_granularity_seconds": self.candle_granularity_seconds,
            "candle_lookback_count": self.candle_lookback_count,
            "hedging_enabled": self.hedging_enabled,
            "allow_duplicate_units": self.allow_duplicate_units,
            "margin_cut_start_ratio": str(self.margin_cut_start_ratio),
            "margin_cut_target_ratio": str(self.margin_cut_target_ratio),
            "margin_protection_enabled": self.margin_protection_enabled,
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
        """Return the base take-profit pips for the given layer.

        If a floor_profile override exists for this index, use it.
        Otherwise apply cross-layer progression to the global take_profit_pips.
        """
        if 0 <= floor_index < len(self.floor_profiles):
            return self.floor_profiles[floor_index].get("take_profit_pips", self.take_profit_pips)
        from apps.trading.strategies.floor.enums import Progression

        mode = Progression(self.take_profit_trigger_progression)
        return ProgressionCalculator.calculate(
            base=self.take_profit_pips,
            index=floor_index,
            mode=mode,
            increment=self.take_profit_trigger_increment,
        )

    def floor_retracement_pips(self, floor_index: int) -> Decimal:
        """Return the base retracement trigger pips for the given layer.

        If a floor_profile override exists for this index, use it.
        Otherwise apply cross-layer progression to the global retracement_pips.
        """
        if 0 <= floor_index < len(self.floor_profiles):
            return self.floor_profiles[floor_index].get("retracement_pips", self.retracement_pips)
        from apps.trading.strategies.floor.enums import Progression

        mode = Progression(self.retracement_trigger_progression)
        return ProgressionCalculator.calculate(
            base=self.retracement_pips,
            index=floor_index,
            mode=mode,
            increment=self.retracement_trigger_increment,
        )

    def intra_layer_take_profit_pips(self, floor_index: int, retracement_index: int) -> Decimal:
        """Return take-profit pips adjusted for the Nth retracement within a layer.

        The base value comes from floor_take_profit_pips (cross-layer),
        then intra-layer progression is applied based on retracement_index.
        """
        base_tp = self.floor_take_profit_pips(floor_index)
        from apps.trading.strategies.floor.enums import Progression

        mode = Progression(self.take_profit_pips_mode)
        return ProgressionCalculator.calculate(
            base=base_tp,
            index=retracement_index,
            mode=mode,
            increment=self.take_profit_pips_amount,
        )


@dataclass
class CandleData:
    """Candle data for trend detection."""

    bucket_start_epoch: int
    close_price: Decimal
    high_price: Decimal | None = None
    low_price: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "bucket_start_epoch": self.bucket_start_epoch,
            "close_price": str(self.close_price),
        }
        if self.high_price is not None:
            result["high_price"] = str(self.high_price)
        if self.low_price is not None:
            result["low_price"] = str(self.low_price)
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CandleData:
        """Create from dictionary."""
        high_raw = data.get("high_price")
        low_raw = data.get("low_price")
        return CandleData(
            bucket_start_epoch=data["bucket_start_epoch"],
            close_price=Decimal(str(data["close_price"])),
            high_price=Decimal(str(high_raw)) if high_raw is not None else None,
            low_price=Decimal(str(low_raw)) if low_raw is not None else None,
        )


@dataclass
class FloorStrategyState:
    """State for Floor strategy."""

    status: StrategyStatus = StrategyStatus.RUNNING
    candles: list[CandleData] = field(default_factory=list)
    current_candle_close: Decimal | None = None
    current_candle_high: Decimal | None = None
    current_candle_low: Decimal | None = None
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
    hedge_neutralized: bool = False
    hedge_entry_ids: list[int] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "candles": [c.to_dict() for c in self.candles],
            "current_candle_close": str(self.current_candle_close)
            if self.current_candle_close
            else None,
            "current_candle_high": str(self.current_candle_high)
            if self.current_candle_high
            else None,
            "current_candle_low": str(self.current_candle_low) if self.current_candle_low else None,
            "last_mid": str(self.last_mid) if self.last_mid else None,
            "last_bid": str(self.last_bid) if self.last_bid else None,
            "last_ask": str(self.last_ask) if self.last_ask else None,
            "account_balance": str(self.account_balance),
            "account_nav": str(self.account_nav),
            "active_floor_index": self.active_floor_index,
            "home_floor_index": self.home_floor_index,
            "next_entry_id": self.next_entry_id,
            "floor_retracement_counts": {
                str(k): v for k, v in self.floor_retracement_counts.items()
            },
            "floor_directions": {str(k): v for k, v in self.floor_directions.items()},
            "return_stack": list(self.return_stack),
            "open_entries": list(self.open_entries),
            "volatility_locked": self.volatility_locked,
            "lock_reason": self.lock_reason,
            "hedge_neutralized": self.hedge_neutralized,
            "hedge_entry_ids": list(self.hedge_entry_ids),
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
            current_candle_high=_decimal_or_none(data.get("current_candle_high")),
            current_candle_low=_decimal_or_none(data.get("current_candle_low")),
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
                for item in (
                    data.get("return_stack", [])
                    if isinstance(data.get("return_stack"), list)
                    else []
                )
            ],
            open_entries=list(data.get("open_entries", []))
            if isinstance(data.get("open_entries"), list)
            else [],
            volatility_locked=_to_bool(data.get("volatility_locked", False), False),
            lock_reason=str(data.get("lock_reason", "")),
            hedge_neutralized=_to_bool(data.get("hedge_neutralized", False), False),
            hedge_entry_ids=[
                _to_int(item, 0)
                for item in (
                    data.get("hedge_entry_ids", [])
                    if isinstance(data.get("hedge_entry_ids"), list)
                    else []
                )
            ],
            metrics=dict(data.get("metrics", {})) if isinstance(data.get("metrics"), dict) else {},
        )

    @classmethod
    def from_strategy_state(cls, raw: Any) -> "FloorStrategyState":
        """Deserialize from persisted strategy_state payload."""
        if not isinstance(raw, dict):
            return cls()
        return cls.from_dict(raw)
