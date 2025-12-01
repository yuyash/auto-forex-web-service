"""
Result dataclasses for task execution and performance metrics.

This module contains dataclasses for structured return types,
replacing arbitrary dict[str, Any] return values with proper typed models.

Requirements: Type safety, code maintainability
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerformanceMetrics:  # pylint: disable=too-many-instance-attributes
    """
    Comprehensive performance metrics from backtest or trading execution.

    This dataclass provides type-safe access to all performance metrics
    calculated during strategy execution.

    Attributes:
        total_trades: Total number of executed trades
        winning_trades: Number of profitable trades
        losing_trades: Number of losing trades
        win_rate: Percentage of winning trades
        total_pnl: Total profit/loss
        total_return: Percentage return on initial balance
        initial_balance: Starting balance
        final_balance: Ending balance
        average_win: Average profit on winning trades
        average_loss: Average loss on losing trades
        largest_win: Largest single winning trade
        largest_loss: Largest single losing trade (negative)
        profit_factor: Gross profit / gross loss ratio
        max_drawdown: Maximum drawdown percentage
        max_drawdown_amount: Maximum drawdown in currency
        sharpe_ratio: Risk-adjusted return ratio
        average_trade_duration: Average trade duration in seconds
        strategy_events: List of strategy-specific events
    """

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_return: float = 0.0
    initial_balance: float = 0.0
    final_balance: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float | None = None
    max_drawdown: float = 0.0
    max_drawdown_amount: float = 0.0
    sharpe_ratio: float | None = None
    average_trade_duration: float = 0.0
    strategy_events: list[dict[str, Any]] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        """Enable dict-like access for backward compatibility with tests."""
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """Enable 'in' operator for backward compatibility."""
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Enable dict-like .get() for backward compatibility."""
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "total_return": self.total_return,
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_amount": self.max_drawdown_amount,
            "sharpe_ratio": self.sharpe_ratio,
            "average_trade_duration": self.average_trade_duration,
            "strategy_events": self.strategy_events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceMetrics":
        """Create PerformanceMetrics from dictionary."""
        return cls(
            total_trades=data.get("total_trades", 0),
            winning_trades=data.get("winning_trades", 0),
            losing_trades=data.get("losing_trades", 0),
            win_rate=data.get("win_rate", 0.0),
            total_pnl=data.get("total_pnl", 0.0),
            total_return=data.get("total_return", 0.0),
            initial_balance=data.get("initial_balance", 0.0),
            final_balance=data.get("final_balance", 0.0),
            average_win=data.get("average_win", 0.0),
            average_loss=data.get("average_loss", 0.0),
            largest_win=data.get("largest_win", 0.0),
            largest_loss=data.get("largest_loss", 0.0),
            profit_factor=data.get("profit_factor"),
            max_drawdown=data.get("max_drawdown", 0.0),
            max_drawdown_amount=data.get("max_drawdown_amount", 0.0),
            sharpe_ratio=data.get("sharpe_ratio"),
            average_trade_duration=data.get("average_trade_duration", 0.0),
            strategy_events=data.get("strategy_events", []),
        )


@dataclass
class TaskExecutionResult:
    """
    Result of a task execution (backtest or trading).

    This dataclass provides a structured return type for task execution
    functions, replacing dict[str, Any] returns.

    Attributes:
        success: Whether execution completed successfully
        task_id: ID of the executed task
        execution_id: ID of the TaskExecution record (if created)
        metrics: Performance metrics (if successful)
        error: Error message (if failed)
        account_id: Database ID of the OandaAccount (for trading tasks)
        oanda_account_id: OANDA account ID string (for trading tasks)
    """

    success: bool
    task_id: int
    execution_id: int | None = None
    metrics: PerformanceMetrics | None = None
    error: str | None = None
    account_id: int | None = None
    oanda_account_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "success": self.success,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "error": self.error,
        }
        if self.metrics:
            result["metrics"] = self.metrics.to_dict()
        if self.account_id is not None:
            result["account_id"] = self.account_id
        if self.oanda_account_id is not None:
            result["oanda_account_id"] = self.oanda_account_id
        return result


@dataclass
class StreamStatus:
    """
    Status of a market data stream.

    This dataclass provides structured information about a running
    or stopped market data stream.

    Attributes:
        success: Whether the operation was successful
        account_id: OANDA account ID
        instrument: Instrument being streamed (if active)
        is_running: Whether stream is currently active
        error: Error message (if failed)
        tick_storage_enabled: Whether tick storage is enabled
        tick_storage_stats: Statistics about tick storage
    """

    success: bool
    account_id: str
    instrument: str | None = None
    is_running: bool = False
    error: str | None = None
    tick_storage_enabled: bool = False
    tick_storage_stats: "TickBufferStats | None" = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "success": self.success,
            "account_id": self.account_id,
            "is_running": self.is_running,
            "tick_storage_enabled": self.tick_storage_enabled,
        }
        if self.instrument:
            result["instrument"] = self.instrument
        if self.error:
            result["error"] = self.error
        if self.tick_storage_stats:
            result["tick_storage_stats"] = self.tick_storage_stats.to_dict()
        return result


@dataclass
class TickBufferStats:
    """
    Statistics about the tick data buffer.

    Attributes:
        buffer_size: Current number of ticks in buffer
        total_stored: Total ticks stored to database
        total_errors: Total storage errors encountered
        last_flush_time: Timestamp of last buffer flush
    """

    buffer_size: int = 0
    total_stored: int = 0
    total_errors: int = 0
    last_flush_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "buffer_size": self.buffer_size,
            "total_stored": self.total_stored,
            "total_errors": self.total_errors,
            "last_flush_time": self.last_flush_time,
        }


@dataclass
class ResourceUsage:
    """
    Resource usage statistics during task execution.

    Attributes:
        peak_memory_mb: Peak memory usage in megabytes
        memory_limit_mb: Memory limit in megabytes
        cpu_limit_cores: CPU core limit
    """

    peak_memory_mb: float = 0.0
    memory_limit_mb: float = 0.0
    cpu_limit_cores: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "peak_memory_mb": self.peak_memory_mb,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_limit_cores": self.cpu_limit_cores,
        }


@dataclass
class CleanupResult:
    """
    Result of a cleanup operation (tick data, stale locks, etc.).

    Attributes:
        success: Whether cleanup completed successfully
        deleted_count: Number of items deleted
        error: Error message (if failed)
        details: Additional details about the cleanup
    """

    success: bool
    deleted_count: int = 0
    error: str | None = None
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "success": self.success,
            "deleted_count": self.deleted_count,
        }
        if self.error:
            result["error"] = self.error
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class HostAccessResult:
    """
    Result of host access monitoring.

    Attributes:
        success: Whether monitoring completed successfully
        hosts_checked: Number of hosts checked
        blocked_count: Number of hosts blocked
        error: Error message (if failed)
    """

    success: bool
    hosts_checked: int = 0
    blocked_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "success": self.success,
            "hosts_checked": self.hosts_checked,
            "blocked_count": self.blocked_count,
        }
        if self.error:
            result["error"] = self.error
        return result
