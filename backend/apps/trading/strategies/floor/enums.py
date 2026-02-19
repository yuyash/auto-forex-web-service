"""Enums for Floor strategy."""

from enum import Enum

from apps.trading.enums import Direction  # Use the main Direction enum

__all__ = ["Direction", "StrategyStatus", "Progression"]


class StrategyStatus(str, Enum):
    """Strategy execution status."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class Progression(str, Enum):
    """Progression mode for cross-layer parameter changes.

    Controls how a base value changes as the layer index increases (Layer 0 → 1 → 2 …).
    """

    CONSTANT = "constant"  # 一定 — 全レイヤーで同じ値
    ADDITIVE = "additive"  # 加算 — base + increment × layer_index
    SUBTRACTIVE = "subtractive"  # 減算 — base − increment × layer_index (最小 0)
    MULTIPLICATIVE = "multiplicative"  # 乗算 — base × (2 ^ layer_index)
    DIVISIVE = "divisive"  # 除算 — base / (2 ^ layer_index)
