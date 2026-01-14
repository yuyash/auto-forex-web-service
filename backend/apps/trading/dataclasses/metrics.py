"""Metrics-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class ExecutionMetrics:
    """Performance metrics for a running execution.

    Tracks real-time performance metrics during task execution.
    """

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: Decimal = Decimal("0")
    total_pips: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pips: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    sharpe_ratio: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format.

        Returns:
            dict: Dictionary representation with Decimal values converted to strings
        """
        result = {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": str(self.total_pnl),
            "total_pips": str(self.total_pips),
            "max_drawdown": str(self.max_drawdown),
            "max_drawdown_pips": str(self.max_drawdown_pips),
            "win_rate": str(self.win_rate),
            "average_win": str(self.average_win),
            "average_loss": str(self.average_loss),
            "profit_factor": str(self.profit_factor),
        }
        if self.sharpe_ratio is not None:
            result["sharpe_ratio"] = str(self.sharpe_ratio)
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ExecutionMetrics":
        """Create ExecutionMetrics from dictionary.

        Args:
            data: Dictionary containing metrics data

        Returns:
            ExecutionMetrics: ExecutionMetrics instance
        """
        sharpe_ratio = data.get("sharpe_ratio")
        return ExecutionMetrics(
            total_trades=int(data.get("total_trades", 0)),
            winning_trades=int(data.get("winning_trades", 0)),
            losing_trades=int(data.get("losing_trades", 0)),
            total_pnl=Decimal(str(data.get("total_pnl", "0"))),
            total_pips=Decimal(str(data.get("total_pips", "0"))),
            max_drawdown=Decimal(str(data.get("max_drawdown", "0"))),
            max_drawdown_pips=Decimal(str(data.get("max_drawdown_pips", "0"))),
            win_rate=Decimal(str(data.get("win_rate", "0"))),
            average_win=Decimal(str(data.get("average_win", "0"))),
            average_loss=Decimal(str(data.get("average_loss", "0"))),
            profit_factor=Decimal(str(data.get("profit_factor", "0"))),
            sharpe_ratio=Decimal(str(sharpe_ratio)) if sharpe_ratio is not None else None,
        )
