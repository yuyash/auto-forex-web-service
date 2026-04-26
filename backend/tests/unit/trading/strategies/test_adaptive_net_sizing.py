"""Unit tests for Adaptive Net decision sizing."""

from decimal import Decimal

from apps.trading.strategies.adaptive_net.models import AdaptiveNetConfig, MetricSignal
from apps.trading.strategies.adaptive_net.sizing import build_decision


def test_decision_holds_when_edge_is_inside_no_trade_band() -> None:
    decision = build_decision(
        config=AdaptiveNetConfig(
            max_net_units=10000,
            base_units=1000,
            min_order_units=1000,
            no_trade_edge_threshold=Decimal("0.20"),
            min_decision_confidence=Decimal("0.01"),
        ),
        current_net_units=0,
        metric_signals=[
            MetricSignal(
                "trend_momentum",
                Decimal("0.10"),
                Decimal("1"),
            )
        ],
    )

    assert decision.target_net_units == 0
    assert decision.order_units == 0


def test_decision_requires_stronger_edge_to_reverse_existing_position() -> None:
    decision = build_decision(
        config=AdaptiveNetConfig(
            max_net_units=10000,
            base_units=1000,
            min_order_units=1000,
            no_trade_edge_threshold=Decimal("0.05"),
            reversal_edge_threshold=Decimal("0.50"),
            min_decision_confidence=Decimal("0.01"),
        ),
        current_net_units=5000,
        metric_signals=[
            MetricSignal(
                "trend_momentum",
                Decimal("-0.30"),
                Decimal("1"),
            )
        ],
    )

    assert decision.target_net_units == 5000
    assert decision.order_units == 0


def test_decision_limits_position_change_per_decision() -> None:
    decision = build_decision(
        config=AdaptiveNetConfig(
            max_net_units=10000,
            base_units=1000,
            min_order_units=1000,
            max_position_change_fraction=Decimal("0.30"),
            no_trade_edge_threshold=Decimal("0.01"),
            min_decision_confidence=Decimal("0.01"),
        ),
        current_net_units=0,
        metric_signals=[
            MetricSignal(
                "trend_momentum",
                Decimal("1"),
                Decimal("1"),
            )
        ],
    )

    assert decision.target_net_units == 3000
    assert decision.order_units == 3000
