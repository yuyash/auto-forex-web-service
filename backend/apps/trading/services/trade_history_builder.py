"""Trade history builder for extracting trades from strategy events."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.trading.events import StrategyEvent
    from apps.trading.models import BacktestTasks


class TradeHistoryBuilder:
    """Builds trade history from strategy events and persists to database."""

    def __init__(self, task: BacktestTasks, celery_task_id: str) -> None:
        """Initialize the trade history builder.

        Args:
            task: Backtest task
            celery_task_id: Celery task ID for this execution
        """
        self.task = task
        self.celery_task_id = celery_task_id
        self.open_positions: dict[int, dict[str, Any]] = {}
        self.completed_trades: list[dict[str, Any]] = []

    def process_events(self, events: list[StrategyEvent]) -> list[dict[str, Any]]:
        """Process events, persist trades to database, and return newly completed trades.

        Args:
            events: List of strategy events to process

        Returns:
            list: List of newly completed trades
        """
        new_trades: list[dict[str, Any]] = []

        for event in events:
            event_type = event.event_type
            event_dict = event.to_dict()

            if event_type in ("initial_entry", "add_layer"):
                # Opening a position
                layer_number = event_dict.get("layer_number", 0)
                direction = event_dict.get("direction", "unknown")
                entry_price = (
                    event_dict.get("entry_price")
                    or event_dict.get("add_price")
                    or event_dict.get("price")
                )
                units = event_dict.get("units", 0)
                timestamp = event_dict.get("timestamp") or event_dict.get("entry_time")

                if entry_price and units:
                    self.open_positions[layer_number] = {
                        "layer_number": layer_number,
                        "direction": direction,
                        "entry_price": str(entry_price),
                        "units": units,
                        "entry_timestamp": timestamp,
                    }

            elif event_type in ("take_profit", "stop_loss", "close_position"):
                # Closing a position
                layer_number = event_dict.get("layer_number", 0)
                exit_price = event_dict.get("exit_price") or event_dict.get("close_price")
                pnl = event_dict.get("pnl")
                pips = event_dict.get("pips")
                timestamp = event_dict.get("timestamp") or event_dict.get("exit_time")

                if layer_number in self.open_positions:
                    position = self.open_positions.pop(layer_number)

                    trade = {
                        "direction": position["direction"],
                        "units": position["units"],
                        "entry_price": position["entry_price"],
                        "exit_price": str(exit_price) if exit_price else None,
                        "pnl": str(pnl) if pnl is not None else None,
                        "pips": str(pips) if pips is not None else None,
                        "entry_timestamp": position["entry_timestamp"],
                        "exit_timestamp": timestamp,
                        "exit_reason": event_type,
                        "layer_number": layer_number,
                    }
                    self.completed_trades.append(trade)
                    new_trades.append(trade)

        # Persist new trades to database
        if new_trades:
            self._persist_trades(new_trades)

        return new_trades

    def _persist_trades(self, trades: list[dict[str, Any]]) -> None:
        """Persist completed trades to database.

        Args:
            trades: List of trade dictionaries to persist
        """
        from apps.trading.models import ExecutionTrade

        trade_records = []
        for trade in trades:
            # Parse timestamps
            entry_ts = self._parse_timestamp(trade.get("entry_timestamp"))
            exit_ts = self._parse_timestamp(trade.get("exit_timestamp"))

            if not entry_ts:
                continue

            trade_records.append(
                ExecutionTrade(
                    task=self.task,
                    celery_task_id=self.celery_task_id,
                    direction=trade.get("direction", "unknown"),
                    units=trade.get("units", 0),
                    entry_price=Decimal(str(trade.get("entry_price", "0"))),
                    exit_price=Decimal(str(trade.get("exit_price", "0")))
                    if trade.get("exit_price")
                    else None,
                    pnl=Decimal(str(trade.get("pnl", "0"))) if trade.get("pnl") else None,
                    pips=Decimal(str(trade.get("pips", "0"))) if trade.get("pips") else None,
                    entry_timestamp=entry_ts,
                    exit_timestamp=exit_ts,
                    exit_reason=trade.get("exit_reason"),
                    layer_number=trade.get("layer_number", 0),
                )
            )

        if trade_records:
            ExecutionTrade.objects.bulk_create(trade_records, ignore_conflicts=True)

    def _parse_timestamp(self, ts: Any) -> datetime | None:
        """Parse timestamp from various formats.

        Args:
            ts: Timestamp in string or datetime format

        Returns:
            datetime: Parsed timestamp or None
        """
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                return None

        return None

    def get_all_trades(self) -> list[dict[str, Any]]:
        """Get all completed trades.

        Returns:
            list: List of all completed trades
        """
        return self.completed_trades
