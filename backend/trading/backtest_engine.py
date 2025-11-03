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
        instruments: List of currency pairs to backtest
        start_date: Start date for backtest period
        end_date: End date for backtest period
        initial_balance: Initial account balance
        slippage_pips: Slippage in pips to apply to each trade
        commission_per_trade: Commission to apply per trade
        cpu_limit: CPU cores limit (default: 1)
        memory_limit: Memory limit in bytes (default: 2GB)
    """

    strategy_type: str
    strategy_config: dict[str, Any]
    instruments: list[str]
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    slippage_pips: Decimal = Decimal("0")
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
    - Tick-by-tick execution
    - Slippage and commission simulation
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
        self.equity_curve: list[dict[str, Any]] = []
        self.trade_log: list[dict[str, Any]] = []
        self.positions: list[BacktestPosition] = []
        self.strategy: BaseStrategy | None = None
        self.resource_monitor: ResourceMonitor | None = None
        self.terminated = False

    def run(self, tick_data: list[TickDataPoint]) -> tuple[list[dict], list[dict]]:
        """
        Run backtest on historical tick data.

        Args:
            tick_data: List of historical tick data points

        Returns:
            Tuple of (trade_log, equity_curve)

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

                # Log progress every 10%
                if i % (total_ticks // 10) == 0:
                    progress = int((i / total_ticks) * 100)
                    logger.info(f"Backtest progress: {progress}%")

            # Record final equity
            self._record_equity(tick_data[-1].timestamp if tick_data else datetime.now())

            logger.info(
                f"Backtest completed: {len(self.trade_log)} trades, "
                f"final balance: {self.balance}"
            )

            return self.trade_log, self.equity_curve

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise

        finally:
            # Stop resource monitoring
            if self.resource_monitor:
                self.resource_monitor.stop()
                self._log_resource_usage()

    def _initialize_strategy(self) -> None:
        """Initialize strategy instance."""
        from trading.strategy_registry import StrategyRegistry as Registry

        # Registry is a class with class methods
        strategy_class = Registry.get_strategy(  # type: ignore[attr-defined]
            self.config.strategy_type
        )
        if not strategy_class:
            raise ValueError(f"Strategy not found: {self.config.strategy_type}")

        self.strategy = strategy_class(self.config.strategy_config)
        logger.info(f"Strategy initialized: {self.config.strategy_type}")

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
            # Create TickData object for strategy
            tick_data_obj = TickDataPoint(
                instrument=tick.instrument,
                timestamp=tick.timestamp,
                bid=tick.bid,
                ask=tick.ask,
                mid=tick.mid,
                spread=tick.ask - tick.bid,
            )
            orders = self.strategy.on_tick(tick_data_obj)  # type: ignore[arg-type]

            # Execute orders
            for order in orders:
                self._execute_order(order, tick)  # type: ignore[arg-type]

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

    def _execute_order(self, order: dict[str, Any], tick: TickDataPoint) -> None:
        """
        Execute order with slippage and commission.

        Args:
            order: Order dictionary
            tick: Current tick data
        """
        # Apply slippage
        if order["direction"] == "long":
            execution_price = tick.ask + (self.config.slippage_pips * Decimal("0.0001"))
        else:
            execution_price = tick.bid - (self.config.slippage_pips * Decimal("0.0001"))

        # Create position
        position = BacktestPosition(
            instrument=order["instrument"],
            direction=order["direction"],
            units=Decimal(str(order["units"])),
            entry_price=execution_price,
            entry_time=tick.timestamp,
            stop_loss=Decimal(str(order.get("stop_loss"))) if order.get("stop_loss") else None,
            take_profit=(
                Decimal(str(order.get("take_profit"))) if order.get("take_profit") else None
            ),
        )

        self.positions.append(position)

        # Apply commission
        self.balance -= self.config.commission_per_trade

        logger.debug(
            f"Order executed: {order['direction']} {order['units']} "
            f"{order['instrument']} @ {execution_price}"
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
        trade = {
            "instrument": position.instrument,
            "direction": position.direction,
            "units": float(position.units),
            "entry_price": float(position.entry_price),
            "exit_price": float(exit_price),
            "entry_time": position.entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "duration": (exit_time - position.entry_time).total_seconds(),
            "pnl": float(pnl),
            "reason": reason,
        }
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

        self.equity_curve.append(
            {
                "timestamp": timestamp.isoformat(),
                "balance": float(equity),
            }
        )

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
