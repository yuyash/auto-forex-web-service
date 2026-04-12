"""Position lifecycle payload builder."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.trading.models import Position, TaskLog, Trade


@dataclass(frozen=True)
class PositionLifecycleQuery:
    """Normalized lifecycle query input."""

    task_type: str
    task_id: UUID
    execution_id: UUID | None
    position_id_query: str


class PositionLifecycleService:
    """Build a readable lifecycle for one position chain."""

    _LIFECYCLE_COMPONENT = "position.lifecycle"
    _OPEN_METHODS = frozenset({"open_position", "rebuild_position"})
    _PROTECTION_METHODS = frozenset(
        {
            "stop_loss",
            "volatility_lock",
            "margin_protection",
            "shrink",
        }
    )

    def build(self, query: PositionLifecycleQuery) -> dict[str, Any]:
        all_lifecycle_logs = list(self._base_logs_queryset(query).order_by("timestamp", "id"))
        matched_position_id = self._resolve_position_id(query, all_lifecycle_logs)
        lifecycle_logs = self._load_chain_logs(all_lifecycle_logs, matched_position_id)
        chain_ids = self._collect_chain_position_ids(matched_position_id, lifecycle_logs)

        positions = {
            str(position.id): position
            for position in Position.objects.filter(
                task_type=query.task_type,
                task_id=query.task_id,
                execution_id=query.execution_id,
                id__in=chain_ids,
            ).order_by("entry_time")
        }
        trades_by_position = self._load_trades(query, chain_ids)
        logs_by_position, rebuild_links = self._index_logs(lifecycle_logs)

        ordered_positions = sorted(
            positions.values(),
            key=lambda position: (position.entry_time, str(position.id)),
        )
        payload_positions = [
            self._serialize_position(
                position=position,
                trades=trades_by_position.get(str(position.id), []),
                logs=logs_by_position.get(str(position.id), []),
                original_position_id=self._find_original_position_id(
                    str(position.id), logs_by_position.get(str(position.id), [])
                ),
                rebuilt_position_ids=sorted(rebuild_links.get(str(position.id), [])),
            )
            for position in ordered_positions
        ]

        return {
            "requested_position_id": query.position_id_query,
            "matched_position_id": matched_position_id,
            "position_ids": [str(position.id) for position in ordered_positions],
            "positions": payload_positions,
        }

    def _base_logs_queryset(self, query: PositionLifecycleQuery) -> QuerySet[TaskLog]:
        return TaskLog.objects.filter(
            task_type=query.task_type,
            task_id=query.task_id,
            execution_id=query.execution_id,
            component=self._LIFECYCLE_COMPONENT,
        )

    def _resolve_position_id(
        self, query: PositionLifecycleQuery, lifecycle_logs: list[TaskLog]
    ) -> str:
        raw = query.position_id_query.strip().lower()
        if not raw:
            raise ValueError("position_id is required")

        candidates = {
            str(position_id)
            for position_id in Position.objects.filter(
                task_type=query.task_type,
                task_id=query.task_id,
                execution_id=query.execution_id,
                id__startswith=raw,
            ).values_list("id", flat=True)
        }
        for log in lifecycle_logs:
            pos_id, orig_pos_id = self._log_position_ids(log)
            if pos_id:
                pos_id = str(pos_id)
                if pos_id.startswith(raw):
                    candidates.add(pos_id)
            if orig_pos_id:
                orig_pos_id = str(orig_pos_id)
                if orig_pos_id.startswith(raw):
                    candidates.add(orig_pos_id)
        if raw in candidates:
            return raw
        if not candidates:
            raise ValueError("No position lifecycle found for the requested position ID")
        if len(candidates) > 1:
            raise ValueError("Position ID prefix matched multiple positions; provide a longer ID")
        return next(iter(candidates))

    def _load_chain_logs(
        self, lifecycle_logs: list[TaskLog], matched_position_id: str
    ) -> list[TaskLog]:
        related_ids = {matched_position_id}
        queue: deque[str] = deque([matched_position_id])
        seen_log_ids: set[str] = set()
        collected: list[TaskLog] = []

        while queue:
            batch = list(queue)
            queue.clear()
            batch_logs = [
                log
                for log in lifecycle_logs
                if any(candidate in batch for candidate in self._log_position_ids(log) if candidate)
            ]
            for log in batch_logs:
                log_id = str(log.id)
                if log_id not in seen_log_ids:
                    collected.append(log)
                    seen_log_ids.add(log_id)
                for candidate in self._log_position_ids(log):
                    if candidate and candidate not in related_ids:
                        related_ids.add(candidate)
                        queue.append(candidate)

        return collected

    def _collect_chain_position_ids(
        self, matched_position_id: str, lifecycle_logs: list[TaskLog]
    ) -> set[str]:
        chain_ids = {matched_position_id}
        for log in lifecycle_logs:
            chain_ids.update(pid for pid in self._log_position_ids(log) if pid)
        return chain_ids

    def _load_trades(
        self, query: PositionLifecycleQuery, chain_ids: set[str]
    ) -> dict[str, list[Trade]]:
        trades_by_position: dict[str, list[Trade]] = defaultdict(list)
        trades = (
            Trade.objects.filter(
                task_type=query.task_type,
                task_id=query.task_id,
                execution_id=query.execution_id,
                position_id__in=chain_ids,
            )
            .select_related("position")
            .order_by("timestamp", "sequence_number", "created_at")
        )
        for trade in trades:
            if trade.position_id:
                trades_by_position[str(trade.position_id)].append(trade)
        return trades_by_position

    def _index_logs(
        self, lifecycle_logs: list[TaskLog]
    ) -> tuple[dict[str, list[TaskLog]], dict[str, set[str]]]:
        logs_by_position: dict[str, list[TaskLog]] = defaultdict(list)
        rebuild_links: dict[str, set[str]] = defaultdict(set)

        for log in lifecycle_logs:
            position_id, original_position_id = self._log_position_ids(log)
            if position_id:
                logs_by_position[position_id].append(log)
            if original_position_id:
                logs_by_position[original_position_id].append(log)
            if position_id and original_position_id:
                rebuild_links[original_position_id].add(position_id)

        return logs_by_position, rebuild_links

    def _find_original_position_id(self, position_id: str, logs: list[TaskLog]) -> str | None:
        for log in logs:
            position_ref, original_position_id = self._log_position_ids(log)
            if position_ref == position_id and original_position_id:
                return original_position_id
        return None

    def _serialize_position(
        self,
        *,
        position: Position,
        trades: list[Trade],
        logs: list[TaskLog],
        original_position_id: str | None,
        rebuilt_position_ids: list[str],
    ) -> dict[str, Any]:
        close_trade = self._select_close_trade(trades)
        events = self._build_events(
            position=position,
            trades=trades,
            logs=logs,
            original_position_id=original_position_id,
            rebuilt_position_ids=rebuilt_position_ids,
            close_trade=close_trade,
        )
        return {
            "position_id": str(position.id),
            "original_position_id": original_position_id,
            "rebuilt_position_ids": rebuilt_position_ids,
            "summary": {
                "position_id": str(position.id),
                "direction": position.direction,
                "units": position.units,
                "is_open": position.is_open,
                "is_rebuild": position.is_rebuild,
                "instrument": position.instrument,
                "layer_index": position.layer_index,
                "retracement_count": position.retracement_count,
                "entry_price": self._decimal_str(position.entry_price),
                "entry_time": position.entry_time.isoformat() if position.entry_time else None,
                "exit_price": self._decimal_str(position.exit_price),
                "exit_time": position.exit_time.isoformat() if position.exit_time else None,
                "planned_exit_price": self._decimal_str(position.planned_exit_price),
                "planned_exit_price_formula": position.planned_exit_price_formula,
                "stop_loss_price": self._decimal_str(position.stop_loss_price),
                "close_reason": self._close_reason_for_position(position, close_trade, logs),
                "realized_pnl": self._realized_pnl(position),
            },
            "events": events,
        }

    def _build_events(
        self,
        *,
        position: Position,
        trades: list[Trade],
        logs: list[TaskLog],
        original_position_id: str | None,
        rebuilt_position_ids: list[str],
        close_trade: Trade | None,
    ) -> list[dict[str, Any]]:
        position_id = str(position.id)
        events: list[dict[str, Any]] = []
        has_entry_event = False
        has_close_event = False

        for log in sorted(logs, key=self._log_sort_key):
            context = self._log_context(log)
            lifecycle_event = str(context.get("lifecycle_event") or "").upper()
            log_position_id, log_original_position_id = self._log_position_ids(log)

            if lifecycle_event == "OPENED":
                if position.is_rebuild and log_position_id == position_id:
                    continue
                if log_position_id != position_id:
                    continue
                has_entry_event = True
                events.append(
                    self._event_from_log(
                        log=log,
                        kind="opened",
                        position_id=position_id,
                    )
                )
                continue

            if lifecycle_event == "REBUILT":
                if log_position_id == position_id:
                    has_entry_event = True
                    events.append(
                        self._event_from_log(
                            log=log,
                            kind="rebuilt",
                            position_id=position_id,
                            related_position_id=log_original_position_id,
                        )
                    )
                elif log_original_position_id == position_id:
                    events.append(
                        self._event_from_log(
                            log=log,
                            kind="rebuilt_into",
                            position_id=position_id,
                            related_position_id=log_position_id,
                        )
                    )
                continue

            if log_position_id != position_id:
                continue

            if lifecycle_event == "PARTIAL_CLOSE":
                events.append(
                    self._event_from_log(log=log, kind="partial_close", position_id=position_id)
                )
                continue

            if lifecycle_event == "CLOSED":
                has_close_event = True
                close_reason = str(context.get("close_reason") or "")
                kind = "stop_loss_closed" if close_reason == "stop_loss" else "closed"
                events.append(
                    self._event_from_log(
                        log=log,
                        kind=kind,
                        position_id=position_id,
                    )
                )

        if not has_entry_event:
            entry_trade = next(
                (
                    trade
                    for trade in trades
                    if str(trade.execution_method).lower() in self._OPEN_METHODS
                ),
                None,
            )
            events.append(
                {
                    "id": f"position-open:{position_id}",
                    "kind": "rebuilt" if position.is_rebuild else "opened",
                    "timestamp": position.entry_time.isoformat() if position.entry_time else None,
                    "position_id": position_id,
                    "related_position_id": original_position_id,
                    "direction": position.direction,
                    "units": position.units,
                    "entry_price": self._decimal_str(position.entry_price),
                    "planned_exit_price": self._decimal_str(position.planned_exit_price),
                    "planned_exit_price_formula": position.planned_exit_price_formula,
                    "description": entry_trade.description if entry_trade else "",
                    "close_reason": None,
                    "realized_pnl": None,
                }
            )

        if not has_close_event and not position.is_open:
            events.append(
                {
                    "id": f"position-close:{position_id}",
                    "kind": (
                        "stop_loss_closed"
                        if self._close_reason_for_position(position, close_trade, logs)
                        == "stop_loss"
                        else "closed"
                    ),
                    "timestamp": position.exit_time.isoformat() if position.exit_time else None,
                    "position_id": position_id,
                    "related_position_id": rebuilt_position_ids[0]
                    if rebuilt_position_ids
                    else None,
                    "direction": position.direction,
                    "units": position.units,
                    "entry_price": self._decimal_str(position.entry_price),
                    "exit_price": self._decimal_str(position.exit_price),
                    "planned_exit_price": self._decimal_str(position.planned_exit_price),
                    "planned_exit_price_formula": position.planned_exit_price_formula,
                    "description": close_trade.description if close_trade else "",
                    "close_reason": self._close_reason_for_position(position, close_trade, logs),
                    "realized_pnl": self._realized_pnl(position),
                }
            )

        events.sort(key=self._event_sort_key)
        return events

    def _event_from_log(
        self,
        *,
        log: TaskLog,
        kind: str,
        position_id: str,
        related_position_id: str | None = None,
    ) -> dict[str, Any]:
        context = self._log_context(log)
        return {
            "id": str(log.id),
            "kind": kind,
            "timestamp": self._log_event_timestamp(log),
            "position_id": position_id,
            "related_position_id": related_position_id,
            "direction": context.get("direction"),
            "units": context.get("units") or context.get("units_closed"),
            "entry_price": self._as_str(context.get("entry_price")),
            "exit_price": self._as_str(context.get("exit_price")),
            "planned_exit_price": self._as_str(context.get("planned_exit_price")),
            "planned_exit_price_formula": context.get("planned_exit_price_formula"),
            "description": context.get("description") or "",
            "close_reason": context.get("close_reason"),
            "realized_pnl": self._as_str(context.get("realized_pnl")),
        }

    def _select_close_trade(self, trades: list[Trade]) -> Trade | None:
        close_trades = [
            trade
            for trade in trades
            if str(trade.execution_method).lower() not in self._OPEN_METHODS
        ]
        return close_trades[-1] if close_trades else None

    def _close_reason_for_position(
        self, position: Position, close_trade: Trade | None, logs: list[TaskLog]
    ) -> str | None:
        for log in reversed(sorted(logs, key=self._log_sort_key)):
            context = self._log_context(log)
            if str(context.get("lifecycle_event") or "").upper() != "CLOSED":
                continue
            close_reason = str(context.get("close_reason") or "")
            if close_reason:
                return close_reason

        if position.is_open:
            return None
        if close_trade is None:
            return "normal"
        execution_method = str(close_trade.execution_method or "").lower()
        if execution_method in self._PROTECTION_METHODS:
            return execution_method
        if close_trade.description.startswith("[PROTECTION]"):
            return "shrink"
        return "normal"

    def _realized_pnl(self, position: Position) -> str | None:
        if position.exit_price is None:
            return None
        units = Decimal(str(abs(position.units)))
        pnl = Decimal(str(position.exit_price)) - Decimal(str(position.entry_price))
        if position.direction == "short":
            pnl = -pnl
        return str(pnl * units)

    def _log_position_ids(self, log: TaskLog) -> tuple[str | None, str | None]:
        context = self._log_context(log)
        position_id = self._as_str(context.get("position_id"))
        original_position_id = self._as_str(context.get("original_position_id"))
        return position_id, original_position_id

    def _log_context(self, log: TaskLog) -> dict[str, Any]:
        details = log.details if isinstance(log.details, dict) else {}
        context = details.get("context")
        return context if isinstance(context, dict) else {}

    def _log_event_timestamp(self, log: TaskLog) -> str:
        context = self._log_context(log)
        lifecycle_event = str(context.get("lifecycle_event") or "").upper()
        if lifecycle_event in {"CLOSED", "PARTIAL_CLOSE"} and context.get("exit_time"):
            return str(context["exit_time"])
        if lifecycle_event in {"OPENED", "REBUILT"} and context.get("entry_time"):
            return str(context["entry_time"])
        return log.timestamp.isoformat()

    def _log_sort_key(self, log: TaskLog) -> tuple[str, str]:
        return (self._log_event_timestamp(log), str(log.id))

    def _event_sort_key(self, event: dict[str, Any]) -> tuple[str, str]:
        timestamp = str(event.get("timestamp") or "")
        return (timestamp, str(event.get("id") or ""))

    def _decimal_str(self, value: Decimal | None) -> str | None:
        return str(value) if value is not None else None

    def _as_str(self, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)
