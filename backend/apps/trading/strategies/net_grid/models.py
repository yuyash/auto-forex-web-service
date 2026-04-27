from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


DEFAULTS = {
    "direction_mode": "long_only",
    "auto_fast_ema_ticks": 5,
    "auto_slow_ema_ticks": 20,
    "auto_min_trend_pips": "1",
    "base_units": 1000,
    "max_net_units": 10000,
    "min_order_units": 1,
    "max_steps": 5,
    "grid_interval_pips": "30",
    "grid_spacing_mode": "fixed",
    "grid_atr_multiplier": "1.5",
    "grid_min_interval_pips": "5",
    "grid_max_interval_pips": "100",
    "take_profit_pips": "10",
    "take_profit_mode": "fixed",
    "take_profit_atr_multiplier": "0.5",
    "take_profit_min_pips": "2",
    "take_profit_max_pips": "50",
    "atr_period_ticks": 20,
    "sizing_mode": "fixed",
    "linear_increment_units": 1000,
    "multiplier": "2",
    "volatility_size_mode": "fixed",
    "volatility_size_atr_threshold_pips": "20",
    "volatility_size_min_multiplier": "0.5",
    "max_spread_pips": "3",
    "max_adverse_pips": "200",
    "max_loss": "0",
    "cooldown_ticks": 1,
    "cooldown_seconds": 0,
    "regime_filter_enabled": False,
    "regime_max_atr_pips": "0",
    "regime_trend_guard_pips": "0",
    "max_full_grid_ticks": 0,
    "max_adverse_after_full_grid_pips": "0",
}

VALID_DIRECTION_MODES = frozenset({"long_only", "short_only", "auto"})
VALID_ADAPTIVE_MODES = frozenset({"fixed", "atr"})


def decimal_from(value: Any, default: Any) -> Decimal:
    if value is None or value == "":
        return Decimal(str(default))
    return Decimal(str(value))


def int_from(value: Any, default: Any) -> int:
    if value is None or value == "":
        return int(default)
    return int(value)


def bool_from(value: Any, default: Any) -> bool:
    if value is None or value == "":
        return bool(default)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True, slots=True)
class NetGridConfig:
    direction_mode: str = "long_only"
    auto_fast_ema_ticks: int = 5
    auto_slow_ema_ticks: int = 20
    auto_min_trend_pips: Decimal = Decimal("1")
    base_units: int = 1000
    max_net_units: int = 10000
    min_order_units: int = 1
    max_steps: int = 5
    grid_interval_pips: Decimal = Decimal("30")
    grid_spacing_mode: str = "fixed"
    grid_atr_multiplier: Decimal = Decimal("1.5")
    grid_min_interval_pips: Decimal = Decimal("5")
    grid_max_interval_pips: Decimal = Decimal("100")
    take_profit_pips: Decimal = Decimal("10")
    take_profit_mode: str = "fixed"
    take_profit_atr_multiplier: Decimal = Decimal("0.5")
    take_profit_min_pips: Decimal = Decimal("2")
    take_profit_max_pips: Decimal = Decimal("50")
    atr_period_ticks: int = 20
    sizing_mode: str = "fixed"
    linear_increment_units: int = 1000
    multiplier: Decimal = Decimal("2")
    volatility_size_mode: str = "fixed"
    volatility_size_atr_threshold_pips: Decimal = Decimal("20")
    volatility_size_min_multiplier: Decimal = Decimal("0.5")
    max_spread_pips: Decimal = Decimal("3")
    max_adverse_pips: Decimal = Decimal("200")
    max_loss: Decimal = Decimal("0")
    cooldown_ticks: int = 1
    cooldown_seconds: int = 0
    regime_filter_enabled: bool = False
    regime_max_atr_pips: Decimal = Decimal("0")
    regime_trend_guard_pips: Decimal = Decimal("0")
    max_full_grid_ticks: int = 0
    max_adverse_after_full_grid_pips: Decimal = Decimal("0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetGridConfig":
        direction_mode = str(data.get("direction_mode", DEFAULTS["direction_mode"]))
        if direction_mode not in VALID_DIRECTION_MODES:
            direction_mode = str(DEFAULTS["direction_mode"])
        grid_spacing_mode = str(data.get("grid_spacing_mode", DEFAULTS["grid_spacing_mode"]))
        if grid_spacing_mode not in VALID_ADAPTIVE_MODES:
            grid_spacing_mode = str(DEFAULTS["grid_spacing_mode"])
        take_profit_mode = str(data.get("take_profit_mode", DEFAULTS["take_profit_mode"]))
        if take_profit_mode not in VALID_ADAPTIVE_MODES:
            take_profit_mode = str(DEFAULTS["take_profit_mode"])
        volatility_size_mode = str(
            data.get("volatility_size_mode", DEFAULTS["volatility_size_mode"])
        )
        if volatility_size_mode not in VALID_ADAPTIVE_MODES:
            volatility_size_mode = str(DEFAULTS["volatility_size_mode"])
        return cls(
            direction_mode=direction_mode,
            auto_fast_ema_ticks=int_from(
                data.get("auto_fast_ema_ticks"), DEFAULTS["auto_fast_ema_ticks"]
            ),
            auto_slow_ema_ticks=int_from(
                data.get("auto_slow_ema_ticks"), DEFAULTS["auto_slow_ema_ticks"]
            ),
            auto_min_trend_pips=decimal_from(
                data.get("auto_min_trend_pips"), DEFAULTS["auto_min_trend_pips"]
            ),
            base_units=int_from(data.get("base_units"), DEFAULTS["base_units"]),
            max_net_units=int_from(data.get("max_net_units"), DEFAULTS["max_net_units"]),
            min_order_units=int_from(data.get("min_order_units"), DEFAULTS["min_order_units"]),
            max_steps=int_from(data.get("max_steps"), DEFAULTS["max_steps"]),
            grid_interval_pips=decimal_from(
                data.get("grid_interval_pips"), DEFAULTS["grid_interval_pips"]
            ),
            grid_spacing_mode=grid_spacing_mode,
            grid_atr_multiplier=decimal_from(
                data.get("grid_atr_multiplier"), DEFAULTS["grid_atr_multiplier"]
            ),
            grid_min_interval_pips=decimal_from(
                data.get("grid_min_interval_pips"), DEFAULTS["grid_min_interval_pips"]
            ),
            grid_max_interval_pips=decimal_from(
                data.get("grid_max_interval_pips"), DEFAULTS["grid_max_interval_pips"]
            ),
            take_profit_pips=decimal_from(
                data.get("take_profit_pips"), DEFAULTS["take_profit_pips"]
            ),
            take_profit_mode=take_profit_mode,
            take_profit_atr_multiplier=decimal_from(
                data.get("take_profit_atr_multiplier"),
                DEFAULTS["take_profit_atr_multiplier"],
            ),
            take_profit_min_pips=decimal_from(
                data.get("take_profit_min_pips"), DEFAULTS["take_profit_min_pips"]
            ),
            take_profit_max_pips=decimal_from(
                data.get("take_profit_max_pips"), DEFAULTS["take_profit_max_pips"]
            ),
            atr_period_ticks=int_from(data.get("atr_period_ticks"), DEFAULTS["atr_period_ticks"]),
            sizing_mode=str(data.get("sizing_mode", DEFAULTS["sizing_mode"])),
            linear_increment_units=int_from(
                data.get("linear_increment_units"),
                DEFAULTS["linear_increment_units"],
            ),
            multiplier=decimal_from(data.get("multiplier"), DEFAULTS["multiplier"]),
            volatility_size_mode=volatility_size_mode,
            volatility_size_atr_threshold_pips=decimal_from(
                data.get("volatility_size_atr_threshold_pips"),
                DEFAULTS["volatility_size_atr_threshold_pips"],
            ),
            volatility_size_min_multiplier=decimal_from(
                data.get("volatility_size_min_multiplier"),
                DEFAULTS["volatility_size_min_multiplier"],
            ),
            max_spread_pips=decimal_from(data.get("max_spread_pips"), DEFAULTS["max_spread_pips"]),
            max_adverse_pips=decimal_from(
                data.get("max_adverse_pips"), DEFAULTS["max_adverse_pips"]
            ),
            max_loss=decimal_from(data.get("max_loss"), DEFAULTS["max_loss"]),
            cooldown_ticks=int_from(data.get("cooldown_ticks"), DEFAULTS["cooldown_ticks"]),
            cooldown_seconds=int_from(data.get("cooldown_seconds"), DEFAULTS["cooldown_seconds"]),
            regime_filter_enabled=bool_from(
                data.get("regime_filter_enabled"),
                DEFAULTS["regime_filter_enabled"],
            ),
            regime_max_atr_pips=decimal_from(
                data.get("regime_max_atr_pips"), DEFAULTS["regime_max_atr_pips"]
            ),
            regime_trend_guard_pips=decimal_from(
                data.get("regime_trend_guard_pips"), DEFAULTS["regime_trend_guard_pips"]
            ),
            max_full_grid_ticks=int_from(
                data.get("max_full_grid_ticks"), DEFAULTS["max_full_grid_ticks"]
            ),
            max_adverse_after_full_grid_pips=decimal_from(
                data.get("max_adverse_after_full_grid_pips"),
                DEFAULTS["max_adverse_after_full_grid_pips"],
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction_mode": self.direction_mode,
            "auto_fast_ema_ticks": self.auto_fast_ema_ticks,
            "auto_slow_ema_ticks": self.auto_slow_ema_ticks,
            "auto_min_trend_pips": str(self.auto_min_trend_pips),
            "base_units": self.base_units,
            "max_net_units": self.max_net_units,
            "min_order_units": self.min_order_units,
            "max_steps": self.max_steps,
            "grid_interval_pips": str(self.grid_interval_pips),
            "grid_spacing_mode": self.grid_spacing_mode,
            "grid_atr_multiplier": str(self.grid_atr_multiplier),
            "grid_min_interval_pips": str(self.grid_min_interval_pips),
            "grid_max_interval_pips": str(self.grid_max_interval_pips),
            "take_profit_pips": str(self.take_profit_pips),
            "take_profit_mode": self.take_profit_mode,
            "take_profit_atr_multiplier": str(self.take_profit_atr_multiplier),
            "take_profit_min_pips": str(self.take_profit_min_pips),
            "take_profit_max_pips": str(self.take_profit_max_pips),
            "atr_period_ticks": self.atr_period_ticks,
            "sizing_mode": self.sizing_mode,
            "linear_increment_units": self.linear_increment_units,
            "multiplier": str(self.multiplier),
            "volatility_size_mode": self.volatility_size_mode,
            "volatility_size_atr_threshold_pips": str(self.volatility_size_atr_threshold_pips),
            "volatility_size_min_multiplier": str(self.volatility_size_min_multiplier),
            "max_spread_pips": str(self.max_spread_pips),
            "max_adverse_pips": str(self.max_adverse_pips),
            "max_loss": str(self.max_loss),
            "cooldown_ticks": self.cooldown_ticks,
            "cooldown_seconds": self.cooldown_seconds,
            "regime_filter_enabled": self.regime_filter_enabled,
            "regime_max_atr_pips": str(self.regime_max_atr_pips),
            "regime_trend_guard_pips": str(self.regime_trend_guard_pips),
            "max_full_grid_ticks": self.max_full_grid_ticks,
            "max_adverse_after_full_grid_pips": str(self.max_adverse_after_full_grid_pips),
        }
