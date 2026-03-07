"""Unit tests for Snowball strategy models."""

from decimal import Decimal

import pytest

from apps.trading.strategies.snowball.enums import ProtectionLevel
from apps.trading.strategies.snowball.models import (
    BasketEntry,
    SnowballStrategyConfig,
    SnowballStrategyState,
)


class TestSnowballStrategyConfig:
    def test_from_dict_defaults(self):
        cfg = SnowballStrategyConfig.from_dict({})
        assert cfg.base_units == 1000
        assert cfg.m_pips == Decimal("50")
        assert cfg.r_max == 7
        assert cfg.f_max == 3
        assert cfg.interval_mode == "constant"
        assert cfg.counter_tp_mode == "weighted_avg"

    def test_from_dict_custom(self):
        cfg = SnowballStrategyConfig.from_dict(
            {
                "base_units": 2000,
                "m_pips": "30",
                "r_max": 5,
                "interval_mode": "manual",
                "manual_intervals": ["10", "20", "30", "40", "50"],
            }
        )
        assert cfg.base_units == 2000
        assert cfg.m_pips == Decimal("30")
        assert cfg.r_max == 5
        assert cfg.interval_mode == "manual"
        assert len(cfg.manual_intervals) == 5

    def test_to_dict_roundtrip(self):
        cfg = SnowballStrategyConfig.from_dict({"m_pips": "30"})
        d = cfg.to_dict()
        cfg2 = SnowballStrategyConfig.from_dict(d)
        assert cfg2.m_pips == Decimal("30")
        assert cfg2.base_units == cfg.base_units

    def test_validate_m_th_n_th_order(self):
        with pytest.raises(ValueError, match="m_th < n_th"):
            SnowballStrategyConfig.from_dict(
                {
                    "shrink_enabled": True,
                    "lock_enabled": True,
                    "m_th": "90",
                    "n_th": "80",
                }
            ).validate()

    def test_validate_manual_intervals_count(self):
        with pytest.raises(ValueError, match="manual_intervals"):
            SnowballStrategyConfig.from_dict(
                {
                    "interval_mode": "manual",
                    "manual_intervals": ["10", "20"],
                    "r_max": 5,
                    "m_pips": "30",
                }
            ).validate()

    def test_validate_passes_for_valid_config(self):
        cfg = SnowballStrategyConfig.from_dict(
            {
                "shrink_enabled": True,
                "lock_enabled": True,
                "m_th": "70",
                "n_th": "85",
                "m_pips": "30",
            }
        )
        cfg.validate()  # should not raise


class TestBasketEntry:
    def test_to_dict_roundtrip(self):
        entry = BasketEntry(
            entry_id=1,
            step=2,
            direction="long",
            entry_price=Decimal("150.00"),
            close_price=Decimal("150.50"),
            units=1000,
            opened_at="2026-01-01T00:00:00+00:00",
        )
        d = entry.to_dict()
        restored = BasketEntry.from_dict(d)
        assert restored.entry_id == 1
        assert restored.direction == "long"
        assert restored.units == 1000
        assert restored.entry_price == Decimal("150.00")


class TestSnowballStrategyState:
    def test_default_state(self):
        ss = SnowballStrategyState()
        assert ss.protection_level == ProtectionLevel.NORMAL
        assert ss.initialised is False
        assert ss.add_count == 0
        assert ss.trend_basket == []
        assert ss.counter_basket == []

    def test_to_dict_roundtrip(self):
        ss = SnowballStrategyState(
            initialised=True,
            add_count=3,
            freeze_count=1,
            protection_level=ProtectionLevel.SHRINK,
        )
        d = ss.to_dict()
        ss2 = SnowballStrategyState.from_dict(d)
        assert ss2.initialised is True
        assert ss2.add_count == 3
        assert ss2.freeze_count == 1
        assert ss2.protection_level == ProtectionLevel.SHRINK

    def test_from_strategy_state_none(self):
        ss = SnowballStrategyState.from_strategy_state(None)
        assert ss.initialised is False

    def test_from_strategy_state_dict(self):
        ss = SnowballStrategyState.from_strategy_state({"initialised": True, "add_count": 2})
        assert ss.initialised is True
        assert ss.add_count == 2
