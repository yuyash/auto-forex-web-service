"""Strategy visualization aggregation service."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.trading.models import StrategyEventRecord, TradingEvent


def _decimal_to_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _dt_to_str(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@dataclass(slots=True)
class VisualizationEvent:
    """Normalized event shape for visualization aggregation."""

    event_type: str
    description: str
    event_timestamp: datetime | None
    created_at: datetime
    visual_group_id: str
    root_entry_id: int | None
    parent_entry_id: int | None
    entry_id: int | None
    basket: str
    step: int | None
    close_reason: str
    direction: str
    expected_interval_pips: Decimal | None
    actual_interval_pips: Decimal | None
    expected_tp_pips: Decimal | None
    actual_tp_pips: Decimal | None
    expected_exit_price: Decimal | None
    actual_exit_price: Decimal | None
    validation_status: str
    details: dict[str, Any]


class StrategyVisualizationService:
    """Build strategy visualization responses for task detail pages."""

    def build(
        self,
        *,
        task: Any,
        task_type: str,
        execution_id: Any,
        root_entry_id: int | None = None,
    ) -> dict[str, Any]:
        strategy_type = str(getattr(task.config, "strategy_type", "") or "")
        if strategy_type != "snowball":
            return self._unsupported(strategy_type=strategy_type)
        if not execution_id:
            return {
                **self._unsupported(strategy_type=strategy_type),
                "message": "Strategy visualization is unavailable because this task has not been executed yet.",
            }

        trading_events = list(
            TradingEvent.objects.filter(
                task_type=task_type,
                task_id=task.pk,
                execution_id=execution_id,
                strategy_type=strategy_type,
            ).order_by("event_timestamp", "created_at")
        )
        strategy_events = list(
            StrategyEventRecord.objects.filter(
                task_type=task_type,
                task_id=task.pk,
                execution_id=execution_id,
                strategy_type=strategy_type,
            ).order_by("event_timestamp", "created_at")
        )

        normalized = [self._normalize_event(e) for e in trading_events + strategy_events]
        grouped = [event for event in normalized if event.visual_group_id]
        if not grouped:
            return {
                **self._unsupported(strategy_type=strategy_type),
                "message": (
                    "Strategy visualization is unavailable for executions recorded "
                    "before the visualization schema update."
                ),
            }

        by_group: dict[str, list[VisualizationEvent]] = defaultdict(list)
        for event in grouped:
            by_group[event.visual_group_id].append(event)

        groups = [
            self._build_snowball_group(group_id=group_id, events=events, task=task)
            for group_id, events in by_group.items()
        ]
        if root_entry_id is not None:
            groups = [
                group
                for group in groups
                if int(group.get("root_entry_id") or 0) == int(root_entry_id)
            ]
        groups.sort(key=lambda group: group["started_at"] or "", reverse=True)

        return {
            "strategy_type": strategy_type,
            "supported": True,
            "execution_id": str(execution_id) if execution_id else None,
            "generated_at": _dt_to_str(max((e.created_at for e in normalized), default=None)),
            "summary": self._build_summary(groups=groups),
            "view_model": {
                "kind": "snowball_runs",
                "groups": groups,
            },
        }

    def _unsupported(self, *, strategy_type: str) -> dict[str, Any]:
        return {
            "strategy_type": strategy_type,
            "supported": False,
            "execution_id": None,
            "generated_at": None,
            "summary": {},
            "view_model": {"kind": "unsupported", "groups": []},
            "message": "Strategy visualization is not implemented for this strategy yet.",
        }

    def _normalize_event(self, event: TradingEvent | StrategyEventRecord) -> VisualizationEvent:
        details = event.details if isinstance(event.details, dict) else {}
        return VisualizationEvent(
            event_type=str(event.event_type),
            description=str(event.description),
            event_timestamp=event.event_timestamp or event.created_at,
            created_at=event.created_at,
            visual_group_id=str(event.visual_group_id or ""),
            root_entry_id=event.root_entry_id,
            parent_entry_id=event.parent_entry_id,
            entry_id=event.entry_id,
            basket=str(event.basket or ""),
            step=event.step,
            close_reason=str(event.close_reason or ""),
            direction=str(event.direction or ""),
            expected_interval_pips=event.expected_interval_pips,
            actual_interval_pips=event.actual_interval_pips,
            expected_tp_pips=event.expected_tp_pips,
            actual_tp_pips=event.actual_tp_pips,
            expected_exit_price=event.expected_exit_price,
            actual_exit_price=event.actual_exit_price,
            validation_status=str(event.validation_status or ""),
            details=details,
        )

    def _build_snowball_group(
        self,
        *,
        group_id: str,
        events: list[VisualizationEvent],
        task: Any,
    ) -> dict[str, Any]:
        ordered = sorted(
            events,
            key=lambda event: ((event.event_timestamp or event.created_at), event.created_at),
        )
        first = ordered[0]
        last = ordered[-1]
        root_event = next(
            (
                event
                for event in ordered
                if event.entry_id is not None and event.entry_id == event.root_entry_id
            ),
            first,
        )

        root_closed = any(
            event.event_type == "close_position"
            and event.entry_id is not None
            and event.entry_id == root_event.root_entry_id
            for event in ordered
        )
        intervened = any(
            event.close_reason in {"shrink", "rebalance", "lock_hedge_neutralize"}
            for event in ordered
        )
        if intervened:
            status = "intervened"
        elif root_closed:
            status = "completed"
        else:
            status = "active"

        config = getattr(task.config, "config_dict", {}) or {}
        steps = [self._build_step(event) for event in ordered]
        protection_events = [
            {
                "kind": event.close_reason or event.details.get("kind") or event.event_type,
                "timestamp": _dt_to_str(event.event_timestamp or event.created_at),
                "details": event.details,
            }
            for event in ordered
            if event.close_reason in {"shrink", "rebalance", "lock_entered", "lock_released"}
        ]

        return {
            "group_id": group_id,
            "root_entry_id": root_event.root_entry_id,
            "started_at": _dt_to_str(first.event_timestamp or first.created_at),
            "ended_at": _dt_to_str(last.event_timestamp or last.created_at)
            if root_closed or intervened
            else None,
            "status": status,
            "root_direction": root_event.direction or root_event.details.get("direction"),
            "root_basket": root_event.basket,
            "trigger_side": root_event.direction or root_event.details.get("direction"),
            "config_snapshot": {
                "m_pips": str(config.get("m_pips", "")),
                "interval_mode": str(config.get("interval_mode", "")),
                "counter_tp_mode": str(config.get("counter_tp_mode", "")),
            },
            "checks": self._build_checks(ordered),
            "steps": steps,
            "protection_events": protection_events,
        }

    def _build_checks(self, events: list[VisualizationEvent]) -> dict[str, Any]:
        trend_tps = [
            event
            for event in events
            if event.close_reason == "trend_tp" and event.actual_tp_pips is not None
        ]
        counter_adds = [
            event
            for event in events
            if event.basket == "counter" and event.event_type == "open_position"
        ]
        counter_tps = [
            event
            for event in events
            if event.close_reason == "counter_tp" and event.actual_tp_pips is not None
        ]
        trend_tp = None
        if trend_tps:
            latest = trend_tps[-1]
            trend_tp = {
                "passed": latest.validation_status != "fail",
                "expected_pips": _decimal_to_str(latest.expected_tp_pips),
                "actual_pips": _decimal_to_str(latest.actual_tp_pips),
            }
        return {
            "trend_tp": trend_tp,
            "counter_intervals": {
                "passed_count": sum(
                    1 for event in counter_adds if event.validation_status != "fail"
                ),
                "failed_count": sum(
                    1 for event in counter_adds if event.validation_status == "fail"
                ),
            },
            "counter_tp": {
                "passed_count": sum(
                    1 for event in counter_tps if event.validation_status != "fail"
                ),
                "failed_count": sum(
                    1 for event in counter_tps if event.validation_status == "fail"
                ),
            },
        }

    def _build_step(self, event: VisualizationEvent) -> dict[str, Any]:
        kind = event.close_reason or event.event_type
        return {
            "kind": kind,
            "event_type": event.event_type,
            "entry_id": event.entry_id,
            "parent_entry_id": event.parent_entry_id,
            "timestamp": _dt_to_str(event.event_timestamp or event.created_at),
            "basket": event.basket,
            "direction": event.direction or event.details.get("direction"),
            "step": event.step,
            "price": event.details.get("price"),
            "entry_price": event.details.get("entry_price"),
            "exit_price": event.details.get("exit_price"),
            "units": event.details.get("units"),
            "layer_number": event.details.get("layer_number"),
            "retracement_count": event.details.get("retracement_count"),
            "description": event.details.get("description") or event.description,
            "expected_interval_pips": _decimal_to_str(event.expected_interval_pips),
            "actual_interval_pips": _decimal_to_str(event.actual_interval_pips),
            "expected_tp_pips": _decimal_to_str(event.expected_tp_pips),
            "actual_tp_pips": _decimal_to_str(event.actual_tp_pips),
            "expected_exit_price": _decimal_to_str(event.expected_exit_price),
            "actual_exit_price": _decimal_to_str(event.actual_exit_price),
            "validation_status": event.validation_status or "not_applicable",
        }

    def _build_summary(self, *, groups: list[dict[str, Any]]) -> dict[str, Any]:
        open_position_count = 0
        closed_position_count = 0
        counter_add_count = 0
        counter_close_count = 0
        protection_event_count = 0

        for group in groups:
            opened: set[int] = set()
            closed: set[int] = set()
            for step in group["steps"]:
                if step["event_type"] == "open_position" and step["entry_id"] is not None:
                    opened.add(int(step["entry_id"]))
                    if step["basket"] == "counter":
                        counter_add_count += 1
                if step["event_type"] == "close_position" and step["entry_id"] is not None:
                    closed.add(int(step["entry_id"]))
                    if step["kind"] == "counter_tp":
                        counter_close_count += 1
                if step["kind"] in {"shrink", "rebalance", "lock_hedge_neutralize"}:
                    protection_event_count += 1
            open_position_count += len(opened - closed)
            closed_position_count += len(closed)

        return {
            "group_count": len(groups),
            "active_group_count": sum(1 for group in groups if group["status"] == "active"),
            "completed_group_count": sum(1 for group in groups if group["status"] == "completed"),
            "intervened_group_count": sum(1 for group in groups if group["status"] == "intervened"),
            "open_position_count": open_position_count,
            "closed_position_count": closed_position_count,
            "counter_add_count": counter_add_count,
            "counter_close_count": counter_close_count,
            "protection_event_count": protection_event_count,
        }
