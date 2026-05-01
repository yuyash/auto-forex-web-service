"""Unit tests for strategy visualization response shaping."""

from apps.trading.services.strategy_cycles import _public_strategy_state


def test_unknown_strategy_does_not_expose_public_state():
    assert _public_strategy_state("unknown", {"current_net_units": 2000}) is None


def test_public_snowball_state_is_not_exposed_as_special_state():
    assert _public_strategy_state("snowball", {"cycles": []}) is None
