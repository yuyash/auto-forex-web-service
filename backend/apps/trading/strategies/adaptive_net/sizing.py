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
    directional_weight = Decimal("0")
    configured_weight = Decimal("0")
    risk_multiplier = Decimal("1")

    for signal in metric_signals:
        weight_name = WEIGHTS.get(signal.name)
        weight = getattr(config, weight_name, Decimal("0")) if weight_name else Decimal("0")
        if weight <= 0:
            continue
        configured_weight += weight
        confidence = clamp(signal.confidence, Decimal("0"), Decimal("1"))
        if signal.direction_score != 0:
            weighted_score += signal.direction_score * confidence * weight
            directional_weight += confidence * weight
        risk_multiplier = min(risk_multiplier, signal.size_multiplier)

    raw_edge = weighted_score / directional_weight if directional_weight > 0 else Decimal("0")
    raw_edge = clamp(raw_edge, Decimal("-1"), Decimal("1"))
    signal_coverage = (
        clamp(directional_weight / configured_weight, Decimal("0"), Decimal("1"))
        if configured_weight > 0
        else Decimal("0")
    )
    confidence = clamp(abs(raw_edge) * signal_coverage, Decimal("0"), Decimal("1"))
    edge = _apply_decision_gates(
        raw_edge=raw_edge,
        confidence=confidence,
        current_net_units=current_net_units,
        config=config,
    )
    probability_long = (Decimal("1") + edge) / Decimal("2")
    probability_short = Decimal("1") - probability_long
    if edge == 0:
        order_units = 0
        target_net_units = current_net_units
    else:
        raw_target = Decimal(config.max_net_units) * edge * confidence * risk_multiplier
        target_net_units = _round_to_step(int(raw_target), config.base_units)
        target_net_units = max(-config.max_net_units, min(config.max_net_units, target_net_units))
        order_units = target_net_units - current_net_units
        order_units = _limit_position_change(
            order_units=order_units,
            max_net_units=config.max_net_units,
            max_fraction=config.max_position_change_fraction,
            step=config.base_units,
        )
        target_net_units = current_net_units + order_units
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
        reason="confidence-weighted edge with no-trade and reversal gates",
    )


def _apply_decision_gates(
    *,
    raw_edge: Decimal,
    confidence: Decimal,
    current_net_units: int,
    config: AdaptiveNetConfig,
) -> Decimal:
    if confidence < config.min_decision_confidence:
        return Decimal("0")
    if abs(raw_edge) < config.no_trade_edge_threshold:
        return Decimal("0")
    if (
        current_net_units != 0
        and raw_edge != 0
        and _sign(current_net_units) != _decimal_sign(raw_edge)
        and abs(raw_edge) < config.reversal_edge_threshold
    ):
        return Decimal("0")
    return raw_edge


def _limit_position_change(
    *,
    order_units: int,
    max_net_units: int,
    max_fraction: Decimal,
    step: int,
) -> int:
    if order_units == 0:
        return 0
    max_change = int(Decimal(max_net_units) * clamp(max_fraction, Decimal("0.01"), Decimal("1")))
    max_change = max(step, _round_to_step(max_change, step))
    if abs(order_units) <= max_change:
        return order_units
    return _sign(order_units) * max_change


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _decimal_sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _round_to_step(value: int, step: int) -> int:
    if step <= 1:
        return value
    sign = 1 if value >= 0 else -1
    return sign * int(round(abs(value) / step) * step)
