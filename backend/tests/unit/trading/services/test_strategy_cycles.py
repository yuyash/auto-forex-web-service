"""Unit tests for strategy visualization response shaping."""

from apps.trading.services.strategy_cycles import _public_strategy_state


def test_public_net_grid_state_includes_operational_fields():
    state = {
        "current_net_units": 2000,
        "average_entry_price": "150.100",
        "net_take_profit_price": "150.200",
        "next_grid_price": "149.800",
        "take_profit_remaining_pips": "7.5",
        "current_atr_pips": "4.25",
        "effective_grid_interval_pips": "12.75",
        "effective_take_profit_pips": "5.0",
        "step": 2,
        "step_usage": "0.4",
        "max_steps": 5,
        "broker_reconciliation_status": "ok",
        "broker_last_backfilled_transaction_id": "12345",
        "broker_pending_order_count": 0,
        "internal_secret": "hidden",
    }

    public = _public_strategy_state("net_grid", state)

    assert public == {
        "current_net_units": 2000,
        "average_entry_price": "150.100",
        "net_take_profit_price": "150.200",
        "next_grid_price": "149.800",
        "take_profit_remaining_pips": "7.5",
        "current_atr_pips": "4.25",
        "effective_grid_interval_pips": "12.75",
        "effective_take_profit_pips": "5.0",
        "step": 2,
        "step_usage": "0.4",
        "max_steps": 5,
        "broker_reconciliation_status": "ok",
        "broker_last_backfilled_transaction_id": "12345",
        "broker_pending_order_count": 0,
    }


def test_public_snowball_state_is_not_exposed_as_net_grid_state():
    assert _public_strategy_state("snowball", {"cycles": []}) is None
