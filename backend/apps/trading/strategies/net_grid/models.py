from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


DEFAULTS = {
    "direction_mode": "long_only",
    "base_units": 1000,
    "max_net_units": 10000,
    "min_order_units": 1,
    "max_steps": 5,
    "grid_interval_pips": "30",
    "take_profit_pips": "10",
    "sizing_mode": "fixed",
    "linear_increment_units": 1000,
    "multiplier": "2",
    "max_spread_pips": "3",
    "max_adverse_pips": "200",
    "max_loss": "0",
    "cooldown_ticks": 1,
}


def decimal_from(value: Any, default: Any) -> Decimal:
    if value is None or value == "":
        return Decimal(str(default))
    return Decimal(str(value))


def int_from(value: Any, default: Any) -> int:
    if value is None or value == "":
        return int(default)
    return int(value)


@dataclass(frozen=True, slots=True)
class NetGridConfig:
    direction_mode: str = "long_only"
    base_units: int = 1000
    max_net_units: int = 10000
    min_order_units: int = 1
    max_steps: int = 5
    grid_interval_pips: Decimal = Decimal("30")
    take_profit_pips: Decimal = Decimal("10")
    sizing_mode: str = "fixed"
    linear_increment_units: int = 1000
    multiplier: Decimal = Decimal("2")
    max_spread_pips: Decimal = Decimal("3")
    max_adverse_pips: Decimal = Decimal("200")
    max_loss: Decimal = Decimal("0")
    cooldown_ticks: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetGridConfig":
        return cls(
            direction_mode=str(data.get("direction_mode", DEFAULTS["direction_mode"])),
            base_units=int_from(data.get("base_units"), DEFAULTS["base_units"]),
            max_net_units=int_from(data.get("max_net_units"), DEFAULTS["max_net_units"]),
            min_order_units=int_from(data.get("min_order_units"), DEFAULTS["min_order_units"]),
            max_steps=int_from(data.get("max_steps"), DEFAULTS["max_steps"]),
            grid_interval_pips=decimal_from(
                data.get("grid_interval_pips"), DEFAULTS["grid_interval_pips"]
            ),
            take_profit_pips=decimal_from(
                data.get("take_profit_pips"), DEFAULTS["take_profit_pips"]
            ),
            sizing_mode=str(data.get("sizing_mode", DEFAULTS["sizing_mode"])),
            linear_increment_units=int_from(
                data.get("linear_increment_units"),
                DEFAULTS["linear_increment_units"],
            ),
            multiplier=decimal_from(data.get("multiplier"), DEFAULTS["multiplier"]),
            max_spread_pips=decimal_from(data.get("max_spread_pips"), DEFAULTS["max_spread_pips"]),
            max_adverse_pips=decimal_from(
                data.get("max_adverse_pips"), DEFAULTS["max_adverse_pips"]
            ),
            max_loss=decimal_from(data.get("max_loss"), DEFAULTS["max_loss"]),
            cooldown_ticks=int_from(data.get("cooldown_ticks"), DEFAULTS["cooldown_ticks"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction_mode": self.direction_mode,
            "base_units": self.base_units,
            "max_net_units": self.max_net_units,
            "min_order_units": self.min_order_units,
            "max_steps": self.max_steps,
            "grid_interval_pips": str(self.grid_interval_pips),
            "take_profit_pips": str(self.take_profit_pips),
            "sizing_mode": self.sizing_mode,
            "linear_increment_units": self.linear_increment_units,
            "multiplier": str(self.multiplier),
            "max_spread_pips": str(self.max_spread_pips),
            "max_adverse_pips": str(self.max_adverse_pips),
            "max_loss": str(self.max_loss),
            "cooldown_ticks": self.cooldown_ticks,
        }
