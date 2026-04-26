from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


DEFAULTS = {
    "base_units": 1000,
    "max_net_units": 10000,
    "min_order_units": 1000,
    "lookback_ticks": 500,
    "rebalance_interval_ticks": 10,
    "lookback_window_seconds": 900,
    "rebalance_interval_seconds": 60,
    "metric_publish_interval_ticks": 10,
    "metric_publish_interval_seconds": 60,
    "decision_interval_metric_publishes": 1,
    "decision_interval_seconds": 0,
    "enable_regime_metric": True,
    "enable_trend_momentum_metric": True,
    "enable_mean_reversion_metric": True,
    "enable_risk_condition_metric": True,
    "enable_inventory_exposure_metric": True,
    "enable_timesfm_forecast_metric": False,
    "trend_weight": "0.25",
    "mean_reversion_weight": "0.20",
    "regime_weight": "0.20",
    "risk_weight": "0.20",
    "inventory_weight": "0.15",
    "timesfm_weight": "0",
    "min_decision_confidence": "0.20",
    "no_trade_edge_threshold": "0.12",
    "reversal_edge_threshold": "0.28",
    "max_position_change_fraction": "0.50",
    "max_spread_pips": "3",
    "high_volatility_ratio": "1.8",
}


def decimal_from(value: Any, default: Any) -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def bool_from(value: Any, default: Any) -> bool:
    if value is None or value == "":
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AdaptiveNetConfig:
    base_units: int = 1000
    max_net_units: int = 10000
    min_order_units: int = 1000
    lookback_ticks: int = 500
    rebalance_interval_ticks: int = 10
    lookback_window_seconds: int = 900
    rebalance_interval_seconds: int = 60
    metric_publish_interval_ticks: int = 10
    metric_publish_interval_seconds: int = 60
    decision_interval_metric_publishes: int = 1
    decision_interval_seconds: int = 0
    enable_regime_metric: bool = True
    enable_trend_momentum_metric: bool = True
    enable_mean_reversion_metric: bool = True
    enable_risk_condition_metric: bool = True
    enable_inventory_exposure_metric: bool = True
    enable_timesfm_forecast_metric: bool = False
    trend_weight: Decimal = Decimal("0.25")
    mean_reversion_weight: Decimal = Decimal("0.20")
    regime_weight: Decimal = Decimal("0.20")
    risk_weight: Decimal = Decimal("0.20")
    inventory_weight: Decimal = Decimal("0.15")
    timesfm_weight: Decimal = Decimal("0")
    min_decision_confidence: Decimal = Decimal("0.20")
    no_trade_edge_threshold: Decimal = Decimal("0.12")
    reversal_edge_threshold: Decimal = Decimal("0.28")
    max_position_change_fraction: Decimal = Decimal("0.50")
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
            lookback_window_seconds=int(
                data.get("lookback_window_seconds", DEFAULTS["lookback_window_seconds"])
            ),
            rebalance_interval_seconds=int(
                data.get("rebalance_interval_seconds", DEFAULTS["rebalance_interval_seconds"])
            ),
            metric_publish_interval_ticks=int(
                data.get(
                    "metric_publish_interval_ticks",
                    data.get(
                        "rebalance_interval_ticks",
                        DEFAULTS["metric_publish_interval_ticks"],
                    ),
                )
            ),
            metric_publish_interval_seconds=int(
                data.get(
                    "metric_publish_interval_seconds",
                    data.get(
                        "rebalance_interval_seconds",
                        DEFAULTS["metric_publish_interval_seconds"],
                    ),
                )
            ),
            decision_interval_metric_publishes=int(
                data.get(
                    "decision_interval_metric_publishes",
                    DEFAULTS["decision_interval_metric_publishes"],
                )
            ),
            decision_interval_seconds=int(
                data.get("decision_interval_seconds", DEFAULTS["decision_interval_seconds"])
            ),
            enable_regime_metric=bool_from(
                data.get("enable_regime_metric"),
                DEFAULTS["enable_regime_metric"],
            ),
            enable_trend_momentum_metric=bool_from(
                data.get("enable_trend_momentum_metric"),
                DEFAULTS["enable_trend_momentum_metric"],
            ),
            enable_mean_reversion_metric=bool_from(
                data.get("enable_mean_reversion_metric"),
                DEFAULTS["enable_mean_reversion_metric"],
            ),
            enable_risk_condition_metric=bool_from(
                data.get("enable_risk_condition_metric"),
                DEFAULTS["enable_risk_condition_metric"],
            ),
            enable_inventory_exposure_metric=bool_from(
                data.get("enable_inventory_exposure_metric"),
                DEFAULTS["enable_inventory_exposure_metric"],
            ),
            enable_timesfm_forecast_metric=bool_from(
                data.get("enable_timesfm_forecast_metric"),
                DEFAULTS["enable_timesfm_forecast_metric"],
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
            min_decision_confidence=decimal_from(
                data.get("min_decision_confidence"), DEFAULTS["min_decision_confidence"]
            ),
            no_trade_edge_threshold=decimal_from(
                data.get("no_trade_edge_threshold"), DEFAULTS["no_trade_edge_threshold"]
            ),
            reversal_edge_threshold=decimal_from(
                data.get("reversal_edge_threshold"), DEFAULTS["reversal_edge_threshold"]
            ),
            max_position_change_fraction=decimal_from(
                data.get("max_position_change_fraction"),
                DEFAULTS["max_position_change_fraction"],
            ),
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
            "lookback_window_seconds": self.lookback_window_seconds,
            "rebalance_interval_seconds": self.rebalance_interval_seconds,
            "metric_publish_interval_ticks": self.metric_publish_interval_ticks,
            "metric_publish_interval_seconds": self.metric_publish_interval_seconds,
            "decision_interval_metric_publishes": self.decision_interval_metric_publishes,
            "decision_interval_seconds": self.decision_interval_seconds,
            "enable_regime_metric": self.enable_regime_metric,
            "enable_trend_momentum_metric": self.enable_trend_momentum_metric,
            "enable_mean_reversion_metric": self.enable_mean_reversion_metric,
            "enable_risk_condition_metric": self.enable_risk_condition_metric,
            "enable_inventory_exposure_metric": self.enable_inventory_exposure_metric,
            "enable_timesfm_forecast_metric": self.enable_timesfm_forecast_metric,
            "trend_weight": str(self.trend_weight),
            "mean_reversion_weight": str(self.mean_reversion_weight),
            "regime_weight": str(self.regime_weight),
            "risk_weight": str(self.risk_weight),
            "inventory_weight": str(self.inventory_weight),
            "timesfm_weight": str(self.timesfm_weight),
            "min_decision_confidence": str(self.min_decision_confidence),
            "no_trade_edge_threshold": str(self.no_trade_edge_threshold),
            "reversal_edge_threshold": str(self.reversal_edge_threshold),
            "max_position_change_fraction": str(self.max_position_change_fraction),
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
