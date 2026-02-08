"""Enums for Floor strategy."""

from enum import Enum


class Direction(str, Enum):
    """Trading direction."""

    LONG = "long"
    SHORT = "short"


class StrategyStatus(str, Enum):
    """Strategy execution status."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class Progression(str, Enum):
    """Progression mode for lot size and retracement triggers."""

    CONSTANT = "constant"  # 一定
    ADDITIVE = "additive"  # 加算
    SUBTRACTIVE = "subtractive"  # 減算
    MULTIPLICATIVE = "multiplicative"  # 乗算（2の累乗）
    DIVISIVE = "divisive"  # 除算（2の累乗で割る）
