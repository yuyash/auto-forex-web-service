"""Metrics calculator for updating execution metrics from strategy events."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.dataclasses import ExecutionMetrics
    from apps.trading.events import StrategyEvent
    from apps.trading.models import BacktestTasks


class MetricsCalculator:
    """Calculates and updates execution metrics from strategy events."""

    def __init__(self, task: BacktestTasks, celery_task_id: str) -> None:
        """Initialize the metrics calculator.

        Args:
            task: Backtest task
            celery_task_id: Celery task ID for this execution
        """
        self.task = task
        self.celery_task_id = celery_task_id
        self.last_metric_timestamp: datetime | None = None

    def update_metrics_from_events(
        self,
        metrics: ExecutionMetrics,
        events: list[StrategyEvent],
    ) -> ExecutionMetrics:
        """Update metrics based on strategy events and persist to database.

        Processes events like take_profit, stop_loss to update trade counts,
        PnL, win rate, and other performance metrics. Also persists metrics
        to TaskMetric table once per minute.

        Args:
            metrics: Current metrics to update
            events: List of strategy events to process

        Returns:
            ExecutionMetrics: Updated metrics
        """
        # Track changes
        new_trades = 0
        new_winning_trades = 0
        new_losing_trades = 0
        new_pnl = Decimal("0")
        new_pips = Decimal("0")

        # Track all PnLs for recalculating averages
        all_pnls: list[Decimal] = []

        for event in events:
            event_type = event.event_type

            # Only process trade closure events
            if event_type not in ("take_profit", "stop_loss", "close_position"):
                continue

            # Extract trade data from event
            event_dict = event.to_dict()
            pnl_str = event_dict.get("pnl")
            pips_str = event_dict.get("pips")

            if pnl_str is None:
                continue

            # Convert to Decimal
            try:
                pnl = Decimal(str(pnl_str))
                pips = Decimal(str(pips_str)) if pips_str is not None else Decimal("0")
            except (ValueError, TypeError):
                continue

            # Update counters
            new_trades += 1
            new_pnl += pnl
            new_pips += pips
            all_pnls.append(pnl)

            if pnl > 0:
                new_winning_trades += 1
            elif pnl < 0:
                new_losing_trades += 1

        # If no new trades, return unchanged metrics
        if new_trades == 0:
            return metrics

        # Update totals
        total_trades = metrics.total_trades + new_trades
        winning_trades = metrics.winning_trades + new_winning_trades
        losing_trades = metrics.losing_trades + new_losing_trades
        total_pnl = metrics.total_pnl + new_pnl
        total_pips = metrics.total_pips + new_pips

        # Calculate win rate
        win_rate = (
            Decimal(winning_trades) / Decimal(total_trades) if total_trades > 0 else Decimal("0")
        )

        # Calculate average win/loss (simplified - only from new trades)
        winning_pnls = [p for p in all_pnls if p > 0]
        losing_pnls = [p for p in all_pnls if p < 0]

        # Update averages (weighted by new trades)
        if winning_pnls:
            new_avg_win = Decimal(str(sum(winning_pnls) / len(winning_pnls)))
            # Weighted average with existing
            if metrics.winning_trades > 0:
                average_win = Decimal(
                    str(
                        (
                            metrics.average_win * metrics.winning_trades
                            + new_avg_win * len(winning_pnls)
                        )
                        / winning_trades
                    )
                )
            else:
                average_win = new_avg_win
        else:
            average_win = metrics.average_win

        if losing_pnls:
            new_avg_loss = Decimal(str(sum(losing_pnls) / len(losing_pnls)))
            # Weighted average with existing
            if metrics.losing_trades > 0:
                average_loss = Decimal(
                    str(
                        (
                            metrics.average_loss * metrics.losing_trades
                            + new_avg_loss * len(losing_pnls)
                        )
                        / losing_trades
                    )
                )
            else:
                average_loss = new_avg_loss
        else:
            average_loss = metrics.average_loss

        # Calculate profit factor
        total_wins = (
            Decimal(str(winning_trades * average_win)) if winning_trades > 0 else Decimal("0")
        )
        total_losses = (
            abs(Decimal(str(losing_trades * average_loss))) if losing_trades > 0 else Decimal("0")
        )
        profit_factor = (
            Decimal(str(total_wins / total_losses)) if total_losses > 0 else Decimal("0")
        )

        # Update max drawdown (simplified - track if current PnL drops below previous peak)
        max_drawdown = metrics.max_drawdown
        if total_pnl < Decimal("0") and abs(total_pnl) > max_drawdown:
            max_drawdown = abs(total_pnl)

        max_drawdown_pips = metrics.max_drawdown_pips
        if total_pips < Decimal("0") and abs(total_pips) > max_drawdown_pips:
            max_drawdown_pips = abs(total_pips)

        # Create updated metrics
        from apps.trading.dataclasses import ExecutionMetrics

        updated_metrics = ExecutionMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            total_pips=total_pips,
            max_drawdown=max_drawdown,
            max_drawdown_pips=max_drawdown_pips,
            win_rate=win_rate,
            average_win=average_win,
            average_loss=average_loss,
            profit_factor=profit_factor,
            sharpe_ratio=metrics.sharpe_ratio,  # Keep existing
        )

        # Persist metrics to database (once per minute)
        self._persist_metrics_if_needed(events, updated_metrics)

        return updated_metrics

    def _persist_metrics_if_needed(
        self,
        events: list[StrategyEvent],
        metrics: ExecutionMetrics,
    ) -> None:
        """Persist metrics to database once per minute.

        Args:
            events: Strategy events (to get timestamp)
            metrics: Current metrics to persist
        """
        if not events:
            return

        # Get timestamp from first event
        event_dict = events[0].to_dict()
        timestamp_str = event_dict.get("timestamp")
        if not timestamp_str:
            return

        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return

        # Only persist once per minute
        if self.last_metric_timestamp:
            time_diff = (timestamp - self.last_metric_timestamp).total_seconds()
            if time_diff < 60:
                return

        from apps.trading.models import TaskMetric

        self.last_metric_timestamp = timestamp

        # Create metric records
        metrics_dict = metrics.to_dict()
        metric_records = []

        for metric_name, value in metrics_dict.items():
            try:
                if isinstance(value, str):
                    float_value = float(value)
                elif isinstance(value, Decimal):
                    float_value = float(value)
                elif isinstance(value, (int, float)):
                    float_value = float(value)
                else:
                    continue
            except (ValueError, TypeError):
                continue

            metric_records.append(
                TaskMetric(
                    task=self.task,
                    celery_task_id=self.celery_task_id,
                    metric_name=metric_name,
                    metric_value=float_value,
                    timestamp=timestamp,
                )
            )

        if metric_records:
            TaskMetric.objects.bulk_create(metric_records)
