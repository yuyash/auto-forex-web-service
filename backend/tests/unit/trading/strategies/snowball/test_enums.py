"""Unit tests for Snowball strategy enums."""

from apps.trading.strategies.snowball.enums import (
    Direction,
    IntervalMode,
    ProtectionLevel,
)


class TestProtectionLevel:
    def test_values(self):
        assert ProtectionLevel.NORMAL == "normal"
        assert ProtectionLevel.REBALANCE == "rebalance"
        assert ProtectionLevel.SHRINK == "shrink"
        assert ProtectionLevel.LOCKED == "locked"
        assert ProtectionLevel.EMERGENCY == "emergency"

    def test_from_string(self):
        assert ProtectionLevel("locked") is ProtectionLevel.LOCKED


class TestIntervalMode:
    def test_values(self):
        assert IntervalMode.CONSTANT == "constant"
        assert IntervalMode.MANUAL == "manual"
        assert IntervalMode.MULTIPLICATIVE == "multiplicative"


class TestDirectionReexport:
    def test_long_short(self):
        assert Direction.LONG == "long"
        assert Direction.SHORT == "short"
