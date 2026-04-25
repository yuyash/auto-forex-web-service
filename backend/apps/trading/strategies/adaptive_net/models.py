from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


DEFAULTS = {
    "base_units": 1000,
    "max_net_units": 10000,
    "min_order_units": 1000,
    "lookback_ticks": 80,
    "rebalance_interval_ticks": 10,
    "trend_weight": "0.25",
    "mean_reversion_weight": "0.20",
    "regime_weight": "0.20",
    "risk_weight": "0.20",
    "inventory_weight": "0.15",
    "timesfm_weight": "0",
    "max_spread_pips": "3",
    "high_volatility_ratio": "1.8",
}


def decimal_from(value: Any, default: Any) -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class AdaptiveNetConfig:
    base_units: int = 1000
    max_net_units: int = 10000
    min_order_units: int = 1000
    lookback_ticks: int = 80
    rebalance_interval_ticks: int = 10
    trend_weight: Decimal = Decimal("0.25")
    mean_reversion_weight: Decimal = Decimal("0.20")
    regime_weight: Decimal = Decimal("0.20")
    risk_weight: Decimal = Decimal("0.20")
    inventory_weight: Decimal = Decimal("0.15")
    timesfm_weight: Decimal = Decimal("0")
    max_spread_pips: Decimal = Decimal("3")
    high_volatility_ratio: Decimal = Decimal("1.8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdaptiveNetConfig":
        return cls(
            base_units=int(data.get("base_units", DEFAULTS["base_units"])),
            max_net_units=int(data.get("max_net_units", DEFAULTS["max_net_units"])),
            min_order_units=int(data.get("min_order_units", DEFAULTS["min_order_units"])),
            lookback_ticks=int(data.get("lookback_ticks", DEFAULTS["lookback_ticks"])),
            rebalance_interval_ticks=int(
                data.get("rebalance_interval_ticks", DEFAULTS["rebalance_interval_ticks"])
            ),
            trend_weight=decimal_from(data.get("trend_weight"), DEFAULTS["trend_weight"]),
            mean_reversion_weight=decimal_from(
                data.get("mean_reversion_weight"), DEFAULTS["mean_reversion_weight"]
            ),
            regime_weight=decimal_from(data.get("regime_weight"), DEFAULTS["regime_weight"]),
            risk_weight=decimal_from(data.get("risk_weight"), DEFAULTS["risk_weight"]),
            inventory_weight=decimal_from(
                data.get("inventory_weight"), DEFAULTS["inventory_weight"]
            ),
            timesfm_weight=decimal_from(data.get("timesfm_weight"), DEFAULTS["timesfm_weight"]),
            max_spread_pips=decimal_from(data.get("max_spread_pips"), DEFAULTS["max_spread_pips"]),
            high_volatility_ratio=decimal_from(
                data.get("high_volatility_ratio"), DEFAULTS["high_volatility_ratio"]
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_units": self.base_units,
            "max_net_units": self.max_net_units,
            "min_order_units": self.min_order_units,
            "lookback_ticks": self.lookback_ticks,
            "rebalance_interval_ticks": self.rebalance_interval_ticks,
            "trend_weight": str(self.trend_weight),
            "mean_reversion_weight": str(self.mean_reversion_weight),
            "regime_weight": str(self.regime_weight),
            "risk_weight": str(self.risk_weight),
            "inventory_weight": str(self.inventory_weight),
            "timesfm_weight": str(self.timesfm_weight),
            "max_spread_pips": str(self.max_spread_pips),
            "high_volatility_ratio": str(self.high_volatility_ratio),
        }


@dataclass(frozen=True, slots=True)
class MetricSignal:
    name: str
    direction_score: Decimal
    confidence: Decimal
    size_multiplier: Decimal = Decimal("1")
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "direction_score": str(self.direction_score),
            "confidence": str(self.confidence),
            "size_multiplier": str(self.size_multiplier),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class MetricContext:
    prices: tuple[Decimal, ...]
    bid: Decimal
    ask: Decimal
    mid: Decimal
    pip_size: Decimal
    current_net_units: int
    max_net_units: int
    config: AdaptiveNetConfig

    @property
    def spread_pips(self) -> Decimal:
        if self.pip_size <= 0:
            return Decimal("0")
        return (self.ask - self.bid) / self.pip_size


@dataclass(frozen=True, slots=True)
class NetDecision:
    target_net_units: int
    order_units: int
    probability_long: Decimal
    probability_short: Decimal
    edge: Decimal
    confidence: Decimal
    risk_multiplier: Decimal
    metric_signals: list[MetricSignal] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_net_units": self.target_net_units,
            "order_units": self.order_units,
            "probability_long": str(self.probability_long),
            "probability_short": str(self.probability_short),
            "edge": str(self.edge),
            "confidence": str(self.confidence),
            "risk_multiplier": str(self.risk_multiplier),
            "metric_signals": [signal.to_dict() for signal in self.metric_signals],
            "reason": self.reason,
        }
