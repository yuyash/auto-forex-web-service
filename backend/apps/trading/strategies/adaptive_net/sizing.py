from __future__ import annotations

from decimal import Decimal

from apps.trading.strategies.adaptive_net.metrics import clamp
from apps.trading.strategies.adaptive_net.models import (
    AdaptiveNetConfig,
    MetricSignal,
    NetDecision,
)


WEIGHTS = {
    "trend_momentum": "trend_weight",
    "mean_reversion": "mean_reversion_weight",
    "regime": "regime_weight",
    "risk_condition": "risk_weight",
    "inventory_exposure": "inventory_weight",
    "timesfm_forecast": "timesfm_weight",
}


def build_decision(
    *,
    config: AdaptiveNetConfig,
    current_net_units: int,
    metric_signals: list[MetricSignal],
) -> NetDecision:
    weighted_score = Decimal("0")
    total_weight = Decimal("0")
    risk_multiplier = Decimal("1")

    for signal in metric_signals:
        weight_name = WEIGHTS.get(signal.name)
        weight = getattr(config, weight_name, Decimal("0")) if weight_name else Decimal("0")
        if weight <= 0:
            continue
        weighted_score += signal.direction_score * signal.confidence * weight
        total_weight += weight
        risk_multiplier = min(risk_multiplier, signal.size_multiplier)

    normalized_score = weighted_score / total_weight if total_weight > 0 else Decimal("0")
    edge = clamp(normalized_score, Decimal("-1"), Decimal("1"))
    confidence = clamp(abs(edge), Decimal("0"), Decimal("1"))
    probability_long = (Decimal("1") + edge) / Decimal("2")
    probability_short = Decimal("1") - probability_long
    raw_target = Decimal(config.max_net_units) * edge * risk_multiplier
    target_net_units = _round_to_step(int(raw_target), config.base_units)
    target_net_units = max(-config.max_net_units, min(config.max_net_units, target_net_units))
    order_units = target_net_units - current_net_units
    if abs(order_units) < config.min_order_units:
        order_units = 0
        target_net_units = current_net_units

    return NetDecision(
        target_net_units=target_net_units,
        order_units=order_units,
        probability_long=probability_long,
        probability_short=probability_short,
        edge=edge,
        confidence=confidence,
        risk_multiplier=risk_multiplier,
        metric_signals=metric_signals,
        reason="weighted metric score converted to target net units",
    )


def _round_to_step(value: int, step: int) -> int:
    if step <= 1:
        return value
    sign = 1 if value >= 0 else -1
    return sign * int(round(abs(value) / step) * step)
