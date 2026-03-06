"""Enums for Snowball strategy."""

from enum import Enum

from apps.trading.enums import Direction  # noqa: F401

__all__ = ["Direction", "ProtectionLevel", "IntervalMode"]


class ProtectionLevel(str, Enum):
    """Margin protection level."""

    NORMAL = "normal"
    REBALANCE = "rebalance"
    SHRINK = "shrink"
    LOCKED = "locked"
    EMERGENCY = "emergency"


class IntervalMode(str, Enum):
    """Interval progression mode for counter-trend averaging."""

    CONSTANT = "constant"
    ADDITIVE = "additive"
    SUBTRACTIVE = "subtractive"
    MULTIPLICATIVE = "multiplicative"
    DIVISIVE = "divisive"
    MANUAL = "manual"
