"""Unit tests for strategy visualization response shaping."""

from apps.trading.services.strategy_cycles import (
    _merge_grid_state_with_trade_history,
    _public_strategy_state,
)


def test_unknown_strategy_does_not_expose_public_state():
    assert _public_strategy_state("unknown", {"current_net_units": 2000}) is None


def test_public_snowball_state_is_not_exposed_as_special_state():
    assert _public_strategy_state("snowball", {"cycles": []}) is None


def test_grid_state_can_be_derived_from_trade_history_without_hot_state():
    cycle_id = "cycle-1"
    first_position_id = "position-1"
    rebuilt_position_id = "position-2"
    trades = [
        {
            "id": cycle_id,
            "position_id": first_position_id,
            "execution_method": "open_position",
            "layer_index": 1,
            "retracement_count": 0,
        },
        {
            "id": "stop-1",
            "position_id": first_position_id,
            "execution_method": "stop_loss",
            "layer_index": 1,
            "retracement_count": 0,
        },
        {
            "id": "rebuild-1",
            "position_id": rebuilt_position_id,
            "execution_method": "rebuild_position",
            "layer_index": 1,
            "retracement_count": 0,
        },
        {
            "id": "close-1",
            "position_id": rebuilt_position_id,
            "execution_method": "close_position",
            "layer_index": 1,
            "retracement_count": 0,
        },
    ]

    grid_state = _merge_grid_state_with_trade_history(
        cycle_id=cycle_id,
        grid_state=None,
        trades=trades,
    )

    assert grid_state == {
        "layers": [
            {
                "layer": 1,
                "slots": [
                    {
                        "slot": 0,
                        "state": "empty",
                        "position_id": None,
                        "build_count": 2,
                    }
                ],
            }
        ],
        "summary": {
            "filled": 0,
            "stopped": 0,
            "rebuilt": 0,
            "empty": 1,
            "layer_count": 1,
            "slot_count_per_layer": 1,
        },
    }
