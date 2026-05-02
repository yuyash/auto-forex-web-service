"""Tests for strategy snapshot projectors."""

from datetime import UTC, datetime
from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.services.strategy_snapshot import build_strategy_snapshot
from apps.trading.strategies.snowball.cycle_state import SnowballCycle, SnowballStrategyState
from apps.trading.strategies.snowball.entries import Entry
from apps.trading.strategies.snowball.grid_models import Layer, PositionGrid


def test_snowball_snapshot_omits_internal_metric_cards() -> None:
    state = SnowballStrategyState(
        initialised=True,
        account_balance=Decimal("10000"),
        account_nav=Decimal("10001"),
        last_mid=Decimal("157.123"),
        metrics={"margin_ratio": "0"},
    )

    snapshot = build_strategy_snapshot("snowball", state.to_dict())

    card_ids = {card["id"] for card in snapshot["cards"]}

    assert "last_mid" not in card_ids
    assert "margin_ratio" not in card_ids
    assert snapshot["state"]["last_mid"] == "157.123"
    assert snapshot["state"]["margin_ratio"] == "0"


def test_snowball_snapshot_groups_open_entry_counts_and_units() -> None:
    opened_at = datetime(2026, 1, 1, tzinfo=UTC)
    layer = Layer.create(layer_number=1, r_max=1, base_units=1000)
    layer.slot_at(0).fill(
        Entry(
            entry_id=1,
            step=0,
            direction=Direction.LONG,
            entry_price=Decimal("157"),
            close_price=Decimal("158"),
            units=1000,
            opened_at=opened_at,
            role="initial",
            layer_number=1,
        )
    )
    layer.slot_at(1).fill(
        Entry(
            entry_id=2,
            step=1,
            direction=Direction.SHORT,
            entry_price=Decimal("156"),
            close_price=Decimal("155"),
            units=2000,
            opened_at=opened_at,
            role="counter",
            layer_number=1,
            retracement_count=1,
        )
    )
    state = SnowballStrategyState(
        initialised=True,
        cycles=[
            SnowballCycle(
                cycle_id=1,
                direction=Direction.LONG,
                grid=PositionGrid(layers=[layer]),
            )
        ],
        account_balance=Decimal("10000"),
        account_nav=Decimal("10001"),
    )

    snapshot = build_strategy_snapshot("snowball", state.to_dict())
    cards = {card["id"]: card["value"] for card in snapshot["cards"]}
    card_ids = list(cards)

    assert cards["open_entries"] == 2
    assert cards["open_long_units"] == 1000
    assert cards["open_short_units"] == 2000
    assert card_ids.index("open_entries") < card_ids.index("open_long_units")
    assert card_ids.index("open_long_units") < card_ids.index("open_short_units")
