"""
Backtesting engine for strategy performance evaluation.

This module provides the BacktestEngine class that simulates strategy execution
on historical data with resource monitoring and limits.

Requirements: 12.2, 12.3
"""

import logging
import os
import resource
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.conf import settings

import psutil

from trading.base_strategy import BaseStrategy
from trading.historical_data_loader import TickDataPoint

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Backtest configuration.

    Attributes:
        strategy_type: Type of strategy to backtest
        strategy_config: Strategy configuration parameters
        instrument: Currency pair to backtest
        start_date: Start date for backtest period
        end_date: End date for backtest period
        initial_balance: Initial account balance
        commission_per_trade: Commission to apply per trade (bid/ask spread already in tick data)
        cpu_limit: CPU cores limit (default: 1)
        memory_limit: Memory limit in bytes (default: 2GB)
    """

    strategy_type: str
    strategy_config: dict[str, Any]
    instrument: str
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    commission_per_trade: Decimal = Decimal("0")
    cpu_limit: int = 1
    memory_limit: int = 2147483648  # 2GB in bytes


@dataclass
class BacktestPosition:
    """
    Simulated position for backtesting.

    Attributes:
        instrument: Currency pair
        direction: Position direction ('long' or 'short')
        units: Position size in units
        entry_price: Entry price
        entry_time: Entry timestamp
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)
    """

    instrument: str
    direction: str
    units: Decimal
    entry_price: Decimal
    entry_time: datetime
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None

    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """
        Calculate unrealized P&L.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L
        """
        if self.direction == "long":
            return (current_price - self.entry_price) * self.units
        return (self.entry_price - current_price) * self.units


@dataclass
class BacktestTrade:
    """
    Completed trade record for backtesting.

    Attributes:
        instrument: Currency pair
        direction: Trade direction ('long' or 'short')
        units: Position size in units
        entry_price: Entry price
        exit_price: Exit price
        entry_time: Entry timestamp
        exit_time: Exit timestamp
        duration: Trade duration in seconds
        pnl: Profit/loss for the trade
        reason: Reason for closing (e.g., 'take_profit', 'stop_loss', 'manual')
    """

    instrument: str
    direction: str
    units: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    duration: float
    pnl: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "instrument": self.instrument,
            "direction": self.direction,
            "units": self.units,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "duration": self.duration,
            "pnl": self.pnl,
            "reason": self.reason,
        }


@dataclass
class EquityPoint:
    """
    Equity curve data point.

    Attributes:
        timestamp: Timestamp of the equity snapshot
        balance: Account balance at this point
    """

    timestamp: datetime
    balance: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "balance": self.balance,
        }


class ResourceMonitor:
    """
    Monitor resource usage during backtest execution.

    Requirements: 12.2, 12.3
    """

    def __init__(self, memory_limit: int, check_interval: float = 1.0):
        """
        Initialize ResourceMonitor.

        Args:
            memory_limit: Memory limit in bytes
            check_interval: Interval between checks in seconds
        """
        self.memory_limit = memory_limit
        self.check_interval = check_interval
        self.process = psutil.Process(os.getpid())
        self.exceeded = False
        self.monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self.peak_memory = 0

    def start(self) -> None:
        """Start resource monitoring in background thread."""
        self.monitoring = True
        self.exceeded = False
        self.peak_memory = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Resource monitoring started (limit: {self.memory_limit / 1024 / 1024:.0f}MB)")

    def stop(self) -> None:
        """Stop resource monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info(f"Resource monitoring stopped (peak: {self.peak_memory / 1024 / 1024:.0f}MB)")

    def _monitor_loop(self) -> None:
        """Monitor resource usage in loop."""
        while self.monitoring:
            try:
                # Get current memory usage
                memory_info = self.process.memory_info()
                current_memory = memory_info.rss  # Resident Set Size

                # Update peak memory
                self.peak_memory = max(self.peak_memory, current_memory)

                # Check if limit exceeded
                if current_memory > self.memory_limit:
                    logger.error(
                        f"Memory limit exceeded: {current_memory / 1024 / 1024:.0f}MB "
                        f"> {self.memory_limit / 1024 / 1024:.0f}MB"
                    )
                    self.exceeded = True
                    self.monitoring = False
                    break

                # Sleep before next check
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error monitoring resources: {e}")
                break

    def is_exceeded(self) -> bool:
        """Check if resource limit has been exceeded."""
        return self.exceeded

    def get_peak_memory(self) -> int:
        """Get peak memory usage in bytes."""
        return self.peak_memory


class BacktestEngine:
    """
    Backtesting engine for strategy performance evaluation.

    This class simulates strategy execution on historical data with:
    - Tick-by-tick execution using bid/ask prices
    - Commission simulation (spread already in tick data)
    - Position tracking and P&L calculation
    - Resource monitoring and limits

    Requirements: 12.2, 12.3
    """

    def __init__(self, config: BacktestConfig):
        """
        Initialize BacktestEngine.

        Args:
            config: Backtest configuration
        """
        self.config = config
        self.balance = config.initial_balance
        self.equity_curve: list[EquityPoint] = []
        self.trade_log: list[BacktestTrade] = []
        self.positions: list[BacktestPosition] = []
        self.strategy: BaseStrategy | None = None
        self.resource_monitor: ResourceMonitor | None = None
        self.terminated = False
        self.progress_callback: Any = None  # Optional callback for progress updates

    def run(
        self, tick_data: list[TickDataPoint]
    ) -> tuple[list[BacktestTrade], list[EquityPoint], dict[str, Any]]:
        """
        Run backtest on historical tick data.

        Args:
            tick_data: List of historical tick data points

        Returns:
            Tuple of (trade_log, equity_curve, performance_metrics)

        Raises:
            RuntimeError: If backtest fails or resource limit exceeded
        """
        logger.info(
            f"Starting backtest: {self.config.strategy_type} "
            f"from {self.config.start_date} to {self.config.end_date}"
        )

        try:
            # Initialize strategy
            self._initialize_strategy()

            # Start resource monitoring
            self._start_resource_monitoring()

            # Set CPU limit (soft limit only, doesn't enforce)
            self._set_cpu_limit()

            # Record initial equity
            self._record_equity(tick_data[0].timestamp if tick_data else datetime.now())

            # Process each tick
            total_ticks = len(tick_data)
            for i, tick in enumerate(tick_data):
                # Check if resource limit exceeded
                if self.resource_monitor and self.resource_monitor.is_exceeded():
                    self.terminated = True
                    raise RuntimeError(
                        f"Backtest terminated: memory limit exceeded "
                        f"({self.config.memory_limit / 1024 / 1024:.0f}MB)"
                    )

                # Process tick
                self._process_tick(tick)

                # Log and report progress every 10%
                if total_ticks > 0 and i % max(1, total_ticks // 10) == 0:
                    progress = int((i / total_ticks) * 100)
                    logger.info(f"Backtest progress: {progress}%")
                    if self.progress_callback:
                        self.progress_callback(progress)  # pylint: disable=not-callable

            # Record final equity
            self._record_equity(tick_data[-1].timestamp if tick_data else datetime.now())

            # Calculate performance metrics
            performance_metrics = self.calculate_performance_metrics()

            logger.info(
                f"Backtest completed: {len(self.trade_log)} trades, "
                f"final balance: {self.balance}"
            )

            return self.trade_log, self.equity_curve, performance_metrics

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise

        finally:
            # Stop resource monitoring
            if self.resource_monitor:
                self.resource_monitor.stop()
                self._log_resource_usage()

    def run_incremental(  # pylint: disable=too-many-locals
        self, tick_data: list[TickDataPoint], day_complete_callback: Any = None
    ) -> tuple[list[BacktestTrade], list[EquityPoint], dict[str, Any]]:
        """
        Run backtest incrementally, calling callback after each day with intermediate results.

        Args:
            tick_data: List of historical tick data points
            day_complete_callback: Optional callback(day_date, intermediate_results)
                called after each day

        Returns:
            Tuple of (trade_log, equity_curve, performance_metrics)

        Raises:
            RuntimeError: If backtest fails or resource limit exceeded
        """
        logger.info(
            f"Starting incremental backtest: {self.config.strategy_type} "
            f"from {self.config.start_date} to {self.config.end_date}"
        )

        try:
            # Initialize strategy
            self._initialize_strategy()

            # Start resource monitoring
            self._start_resource_monitoring()

            # Set CPU limit (soft limit only, doesn't enforce)
            self._set_cpu_limit()

            # Record initial equity
            if tick_data:
                self._record_equity(tick_data[0].timestamp)

            # Group ticks by day
            from collections import defaultdict

            ticks_by_day = defaultdict(list)
            for tick in tick_data:
                day_key = tick.timestamp.date()
                ticks_by_day[day_key].append(tick)

            # Sort days
            sorted_days = sorted(ticks_by_day.keys())
            total_days = len(sorted_days)

            # Process each day
            for day_index, day_date in enumerate(sorted_days):
                day_ticks = ticks_by_day[day_date]

                # Process all ticks for this day
                for tick in day_ticks:
                    # Check if resource limit exceeded
                    if self.resource_monitor and self.resource_monitor.is_exceeded():
                        self.terminated = True
                        raise RuntimeError(
                            f"Backtest terminated: memory limit exceeded "
                            f"({self.config.memory_limit / 1024 / 1024:.0f}MB)"
                        )

                    # Process tick
                    self._process_tick(tick)

                # Record equity at end of day
                if day_ticks:
                    self._record_equity(day_ticks[-1].timestamp)

                # Calculate intermediate metrics
                intermediate_metrics = self.calculate_performance_metrics()

                # Calculate progress
                progress = int(((day_index + 1) / total_days) * 100)

                # Call callback with intermediate results
                if day_complete_callback:
                    # Convert objects to dicts for JSON serialization
                    recent_trades = (
                        [t.to_dict() for t in self.trade_log[-10:]] if self.trade_log else []
                    )
                    equity_points = (
                        [p.to_dict() for p in self.equity_curve[-100:]] if self.equity_curve else []
                    )

                    intermediate_results = {
                        "day_date": day_date.isoformat(),
                        "progress": progress,
                        "days_processed": day_index + 1,
                        "total_days": total_days,
                        "ticks_processed": len(day_ticks),
                        "balance": float(self.balance),
                        "total_trades": len(self.trade_log),
                        "metrics": intermediate_metrics,
                        "recent_trades": recent_trades,
                        "equity_curve": equity_points,
                    }
                    day_complete_callback(day_date, intermediate_results)

            # Calculate final performance metrics
            performance_metrics = self.calculate_performance_metrics()

            logger.info(
                f"Incremental backtest completed: {len(self.trade_log)} trades, "
                f"final balance: {self.balance}"
            )

            return self.trade_log, self.equity_curve, performance_metrics

        except Exception as e:
            logger.error(f"Incremental backtest failed: {e}")
            raise

        finally:
            # Stop resource monitoring
            if self.resource_monitor:
                self.resource_monitor.stop()
                self._log_resource_usage()

    def _initialize_strategy(self) -> None:
        """Initialize strategy instance."""
        from trading.strategy_registry import registry

        # Get strategy class from registry
        strategy_class = registry.get_strategy_class(self.config.strategy_type)

        # Add instrument to strategy config for backtest mode
        strategy_config = self.config.strategy_config.copy()
        strategy_config["instrument"] = self.config.instrument

        self.strategy = strategy_class(strategy_config)
        logger.info(
            f"Strategy initialized: {self.config.strategy_type} for {self.config.instrument}"
        )

    def _start_resource_monitoring(self) -> None:
        """Start resource monitoring."""
        self.resource_monitor = ResourceMonitor(
            memory_limit=self.config.memory_limit,
            check_interval=1.0,
        )
        self.resource_monitor.start()

    def _set_cpu_limit(self) -> None:
        """
        Set CPU limit (soft limit only).

        Note: This sets a soft limit that doesn't enforce CPU usage,
        but can be used for monitoring purposes.
        """
        try:
            # Get current limits
            _, hard = resource.getrlimit(resource.RLIMIT_CPU)

            # Set soft limit based on config (in seconds)
            # This is a soft limit and won't strictly enforce CPU usage
            cpu_seconds = self.config.cpu_limit * 3600  # 1 hour per core
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, hard))

            logger.info(f"CPU limit set: {self.config.cpu_limit} cores")

        except Exception as e:
            logger.warning(f"Failed to set CPU limit: {e}")

    def _process_tick(self, tick: TickDataPoint) -> None:
        """
        Process a single tick.

        Args:
            tick: Tick data point
        """
        # Update positions with current price
        self._update_positions(tick)

        # Check stop loss and take profit
        self._check_exit_conditions(tick)

        # Call strategy on_tick
        if self.strategy:
            # Convert TickDataPoint to TickData-compatible wrapper for strategy
            tick_data_obj = tick.to_tick_data()
            orders = self.strategy.on_tick(tick_data_obj)  # type: ignore[arg-type]

            # Execute orders
            for order in orders:
                self._execute_order(order, tick)

        # Record equity periodically (every 100 ticks)
        if len(self.equity_curve) == 0 or len(self.equity_curve) % 100 == 0:
            self._record_equity(tick.timestamp)

    def _update_positions(self, tick: TickDataPoint) -> None:
        """
        Update positions with current price.

        Args:
            tick: Tick data point
        """
        for position in self.positions:
            if position.instrument == tick.instrument:
                # Update unrealized P&L (not stored, just calculated)
                pass

    def _check_exit_conditions(self, tick: TickDataPoint) -> None:
        """
        Check stop loss and take profit conditions.

        Args:
            tick: Tick data point
        """
        positions_to_close = []

        for position in self.positions:
            if position.instrument != tick.instrument:
                continue

            current_price = tick.bid if position.direction == "long" else tick.ask

            # Check stop loss
            if position.stop_loss and (
                (position.direction == "long" and current_price <= position.stop_loss)
                or (position.direction == "short" and current_price >= position.stop_loss)
            ):
                positions_to_close.append((position, current_price, "stop_loss"))

            # Check take profit
            if position.take_profit and (
                (position.direction == "long" and current_price >= position.take_profit)
                or (position.direction == "short" and current_price <= position.take_profit)
            ):
                positions_to_close.append((position, current_price, "take_profit"))

        # Close positions
        for position, exit_price, reason in positions_to_close:
            self._close_position(position, exit_price, tick.timestamp, reason)

    def _execute_order(self, order: Any, tick: TickDataPoint) -> None:
        """
        Execute order with commission (bid/ask spread already in tick data).

        Args:
            order: Order model instance
            tick: Current tick data
        """
        # Use bid/ask prices directly (spread already included)
        if order.direction == "long":
            execution_price = tick.ask
        else:
            execution_price = tick.bid

        # Create position
        position = BacktestPosition(
            instrument=order.instrument,
            direction=order.direction,
            units=Decimal(str(order.units)),
            entry_price=execution_price,
            entry_time=tick.timestamp,
            stop_loss=Decimal(str(order.stop_loss)) if order.stop_loss else None,
            take_profit=Decimal(str(order.take_profit)) if order.take_profit else None,
        )

        self.positions.append(position)

        # Apply commission
        self.balance -= self.config.commission_per_trade

        logger.debug(
            f"Order executed: {order.direction} {order.units} "
            f"{order.instrument} @ {execution_price}"
        )

    def _close_position(
        self,
        position: BacktestPosition,
        exit_price: Decimal,
        exit_time: datetime,
        reason: str = "manual",
    ) -> None:
        """
        Close position and record trade.

        Args:
            position: Position to close
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Reason for closing
        """
        # Calculate P&L
        pnl = position.calculate_pnl(exit_price)

        # Apply commission
        pnl -= self.config.commission_per_trade

        # Update balance
        self.balance += pnl

        # Record trade
        trade = BacktestTrade(
            instrument=position.instrument,
            direction=position.direction,
            units=float(position.units),
            entry_price=float(position.entry_price),
            exit_price=float(exit_price),
            entry_time=position.entry_time,
            exit_time=exit_time,
            duration=(exit_time - position.entry_time).total_seconds(),
            pnl=float(pnl),
            reason=reason,
        )
        self.trade_log.append(trade)

        # Remove position
        self.positions.remove(position)

        logger.debug(f"Position closed: {position.instrument} P&L: {pnl} ({reason})")

    def _record_equity(self, timestamp: datetime) -> None:
        """
        Record current equity in equity curve.

        Args:
            timestamp: Current timestamp
        """
        # Calculate total unrealized P&L
        unrealized_pnl = Decimal("0")
        # Note: In a real implementation, we'd need current prices for all positions
        # For simplicity, we're not including unrealized P&L in equity curve

        equity = self.balance + unrealized_pnl

        self.equity_curve.append(EquityPoint(timestamp=timestamp, balance=float(equity)))

    def _log_resource_usage(self) -> None:
        """Log resource usage metrics."""
        if not self.resource_monitor:
            return

        peak_memory_mb = self.resource_monitor.get_peak_memory() / 1024 / 1024
        limit_mb = self.config.memory_limit / 1024 / 1024

        logger.info(
            f"Resource usage - Peak memory: {peak_memory_mb:.0f}MB / {limit_mb:.0f}MB "
            f"({(peak_memory_mb / limit_mb) * 100:.1f}%)"
        )

        # Log to system config if available
        system_config = getattr(settings, "SYSTEM_CONFIG", {})
        if system_config:
            logger.info(f"CPU limit: {self.config.cpu_limit} cores")

    def calculate_performance_metrics(self) -> dict[str, Any]:
        """
        Calculate comprehensive performance metrics from backtest results.

        This method calculates:
        - Total return and P&L
        - Maximum drawdown (percentage and amount)
        - Sharpe ratio (risk-adjusted return)
        - Win rate and trade statistics
        - Average win/loss and profit factor

        Returns:
            Dictionary containing all performance metrics

        Requirements: 12.4
        """
        if not self.trade_log:
            return self._get_zero_metrics()

        metrics: dict[str, Any] = {}

        # Basic metrics
        metrics["total_trades"] = len(self.trade_log)
        metrics["final_balance"] = float(self.balance)
        metrics["initial_balance"] = float(self.config.initial_balance)

        # Calculate total P&L and return
        total_pnl = self.balance - self.config.initial_balance
        metrics["total_pnl"] = float(total_pnl)
        metrics["total_return"] = (
            float((total_pnl / self.config.initial_balance) * 100)
            if self.config.initial_balance > 0
            else 0.0
        )

        # Calculate win/loss statistics
        winning_trades = [t for t in self.trade_log if t.pnl > 0]
        losing_trades = [t for t in self.trade_log if t.pnl < 0]

        metrics["winning_trades"] = len(winning_trades)
        metrics["losing_trades"] = len(losing_trades)
        metrics["win_rate"] = (
            (len(winning_trades) / len(self.trade_log)) * 100 if self.trade_log else 0.0
        )

        # Calculate average win/loss
        if winning_trades:
            total_wins = sum(t.pnl for t in winning_trades)
            metrics["average_win"] = total_wins / len(winning_trades)
            metrics["largest_win"] = max(t.pnl for t in winning_trades)
        else:
            metrics["average_win"] = 0.0
            metrics["largest_win"] = 0.0

        if losing_trades:
            total_losses = sum(t.pnl for t in losing_trades)
            metrics["average_loss"] = total_losses / len(losing_trades)
            metrics["largest_loss"] = min(t.pnl for t in losing_trades)
        else:
            metrics["average_loss"] = 0.0
            metrics["largest_loss"] = 0.0

        # Calculate profit factor
        if losing_trades:
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            metrics["profit_factor"] = gross_profit / gross_loss if gross_loss > 0 else None
        else:
            metrics["profit_factor"] = None

        # Calculate maximum drawdown
        max_dd_metrics = self._calculate_max_drawdown()
        metrics.update(max_dd_metrics)

        # Calculate Sharpe ratio
        metrics["sharpe_ratio"] = self._calculate_sharpe_ratio()

        # Calculate average trade duration
        if self.trade_log:
            total_duration = sum(t.duration for t in self.trade_log)
            metrics["average_trade_duration"] = total_duration / len(self.trade_log)
        else:
            metrics["average_trade_duration"] = 0.0

        sharpe_str = (
            f"{metrics['sharpe_ratio']:.2f}" if metrics["sharpe_ratio"] is not None else "N/A"
        )
        logger.info(
            f"Performance metrics calculated: Return={metrics['total_return']:.2f}%, "
            f"Win Rate={metrics['win_rate']:.2f}%, "
            f"Sharpe={sharpe_str}"
        )

        return metrics

    def _get_zero_metrics(self) -> dict[str, Any]:
        """
        Get zero/default metrics when no trades were executed.

        Returns:
            Dictionary with zero metrics
        """
        return {
            "total_trades": 0,
            "final_balance": float(self.config.initial_balance),
            "initial_balance": float(self.config.initial_balance),
            "total_pnl": 0.0,
            "total_return": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "profit_factor": None,
            "max_drawdown": 0.0,
            "max_drawdown_amount": 0.0,
            "sharpe_ratio": None,
            "average_trade_duration": 0.0,
        }

    def _calculate_max_drawdown(self) -> dict[str, float]:
        """
        Calculate maximum drawdown from equity curve.

        Maximum drawdown is the largest peak-to-trough decline in the equity curve,
        expressed both as a percentage and absolute amount.

        Returns:
            Dictionary with max_drawdown (%) and max_drawdown_amount

        Requirements: 12.4
        """
        if not self.equity_curve:
            return {"max_drawdown": 0.0, "max_drawdown_amount": 0.0}

        peak = float(self.config.initial_balance)
        max_dd = 0.0
        max_dd_amount = 0.0

        for point in self.equity_curve:
            balance = point.balance
            peak = max(peak, balance)

            drawdown_amount = peak - balance
            if drawdown_amount > max_dd_amount:
                max_dd_amount = drawdown_amount
                max_dd = (drawdown_amount / peak) * 100 if peak > 0 else 0.0

        return {
            "max_drawdown": max_dd,
            "max_drawdown_amount": max_dd_amount,
        }

    def _calculate_sharpe_ratio(self) -> float | None:
        """
        Calculate Sharpe ratio from equity curve.

        The Sharpe ratio measures risk-adjusted return by comparing the average return
        to the volatility (standard deviation) of returns. Higher values indicate
        better risk-adjusted performance.

        Formula: Sharpe = (Mean Return - Risk-Free Rate) / Std Dev of Returns
        Assumes risk-free rate = 0 and annualizes based on 252 trading days.

        Returns:
            Sharpe ratio or None if insufficient data

        Requirements: 12.4
        """
        if len(self.equity_curve) < 2:
            return None

        # Calculate returns between equity curve points
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_balance = self.equity_curve[i - 1].balance
            curr_balance = self.equity_curve[i].balance

            if prev_balance > 0:
                daily_return = (curr_balance - prev_balance) / prev_balance
                returns.append(daily_return)

        if not returns:
            return None

        # Calculate mean and standard deviation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance**0.5

        # Calculate Sharpe ratio (assuming risk-free rate = 0)
        if std_dev > 0:
            # Annualize (assuming 252 trading days)
            annualized_return = mean_return * 252
            annualized_std = std_dev * (252**0.5)
            sharpe_ratio: float = annualized_return / annualized_std
            return sharpe_ratio

        return None
