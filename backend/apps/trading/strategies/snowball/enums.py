"""Enums for Snowball strategy."""

from enum import Enum

from apps.trading.enums import Direction  # noqa: F401

__all__ = ["Direction", "ProtectionLevel", "IntervalMode", "CycleStatus"]


class ProtectionLevel(str, Enum):
    """Margin protection level."""

    NORMAL = "normal"
    SHRINK = "shrink"
    EMERGENCY = "emergency"


class CycleStatus(str, Enum):
    """Lifecycle status of a snowball cycle."""

    ACTIVE = "active"
    PENDING = "pending"
    COMPLETED = "completed"


class IntervalMode(str, Enum):
    """Interval progression mode for counter-trend averaging."""

    CONSTANT = "constant"
    ADDITIVE = "additive"
    SUBTRACTIVE = "subtractive"
    MULTIPLICATIVE = "multiplicative"
    DIVISIVE = "divisive"
    MANUAL = "manual"
