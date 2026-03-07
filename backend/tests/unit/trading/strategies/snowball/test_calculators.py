"""Unit tests for Snowball strategy calculators."""

from decimal import Decimal

from apps.trading.strategies.snowball.calculators import (
    counter_interval_pips,
    counter_tp_pips,
    round_to_step,
)
from apps.trading.strategies.snowball.models import SnowballStrategyConfig


def _cfg(**overrides) -> SnowballStrategyConfig:
    defaults = {
        "n_pips_head": "30",
        "n_pips_tail": "14",
        "n_pips_flat_steps": 2,
        "n_pips_gamma": "1.4",
        "round_step_pips": "0.1",
        "interval_mode": "constant",
        "r_max": 7,
        "counter_tp_mode": "fixed",
        "counter_tp_pips": "25",
        "counter_tp_step_amount": "2.5",
        "counter_tp_multiplier": "1.2",
    }
    defaults.update(overrides)
    return SnowballStrategyConfig.from_dict(defaults)


class TestRoundToStep:
    def test_basic(self):
        assert round_to_step(Decimal("29.3"), Decimal("0.5")) == Decimal("29.5")

    def test_zero_step(self):
        assert round_to_step(Decimal("29.3"), Decimal("0")) == Decimal("29.3")

    def test_exact(self):
        assert round_to_step(Decimal("30"), Decimal("0.1")) == Decimal("30.0")


class TestCounterIntervalPips:
    def test_constant_mode(self):
        cfg = _cfg(interval_mode="constant")
        assert counter_interval_pips(1, cfg) == Decimal("30.0")
        assert counter_interval_pips(5, cfg) == Decimal("30.0")

    def test_flat_region(self):
        cfg = _cfg(interval_mode="additive", n_pips_flat_steps=3)
        # k <= flat_steps → head
        assert counter_interval_pips(1, cfg) == Decimal("30.0")
        assert counter_interval_pips(3, cfg) == Decimal("30.0")

    def test_decay_region(self):
        cfg = _cfg(interval_mode="additive", n_pips_flat_steps=1)
        # k=2 enters decay; result should be between tail and head
        result = counter_interval_pips(2, cfg)
        assert Decimal("14") <= result <= Decimal("30")

    def test_manual_mode(self):
        intervals = ["10", "20", "30", "40", "50", "60", "70"]
        cfg = _cfg(interval_mode="manual", manual_intervals=intervals, r_max=7)
        assert counter_interval_pips(1, cfg) == Decimal("10.0")
        assert counter_interval_pips(3, cfg) == Decimal("30.0")
        # Beyond list length → clamp to last
        assert counter_interval_pips(99, cfg) == Decimal("70.0")

    def test_zero_decay_steps(self):
        cfg = _cfg(interval_mode="additive", n_pips_flat_steps=7, r_max=8)
        # All within flat → head
        assert counter_interval_pips(7, cfg) == Decimal("30.0")


class TestCounterTpPips:
    def test_fixed_mode(self):
        cfg = _cfg(counter_tp_mode="fixed")
        assert counter_tp_pips(1, cfg) == Decimal("25.0")
        assert counter_tp_pips(5, cfg) == Decimal("25.0")

    def test_additive_mode(self):
        cfg = _cfg(counter_tp_mode="additive", counter_tp_step_amount="5")
        assert counter_tp_pips(1, cfg) == Decimal("25.0")
        assert counter_tp_pips(2, cfg) == Decimal("30.0")
        assert counter_tp_pips(3, cfg) == Decimal("35.0")

    def test_subtractive_mode(self):
        cfg = _cfg(counter_tp_mode="subtractive", counter_tp_step_amount="10")
        assert counter_tp_pips(1, cfg) == Decimal("25.0")
        assert counter_tp_pips(2, cfg) == Decimal("15.0")
        assert counter_tp_pips(3, cfg) == Decimal("5.0")
        # Floor at 0.1
        assert counter_tp_pips(4, cfg) == Decimal("0.1")

    def test_multiplicative_mode(self):
        cfg = _cfg(counter_tp_mode="multiplicative", counter_tp_multiplier="2")
        assert counter_tp_pips(1, cfg) == Decimal("25.0")
        assert counter_tp_pips(2, cfg) == Decimal("50.0")

    def test_divisive_mode(self):
        cfg = _cfg(counter_tp_mode="divisive", counter_tp_multiplier="2")
        assert counter_tp_pips(1, cfg) == Decimal("25.0")
        assert counter_tp_pips(2, cfg) == Decimal("12.5")

    def test_weighted_avg_returns_zero(self):
        cfg = _cfg(counter_tp_mode="weighted_avg")
        assert counter_tp_pips(1, cfg) == Decimal("0")
        assert counter_tp_pips(5, cfg) == Decimal("0")
