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


def _build_groups_from_parent_chain(
    events: list[VisualizationEvent],
) -> dict[int, list[VisualizationEvent]]:
    """Rebuild groups by walking parent_entry_id chains to find the root.

    The root of a chain is an entry whose parent_entry_id is None (i.e. an
    Initial Entry or a trend re-entry that starts a new cycle).  Every event
    that can be traced back to the same root via parent_entry_id belongs to
    the same group.

    For trend re-entries (basket=trend, parent_entry_id=None) we need to
    decide whether they start a new group or belong to an existing one.
    A trend re-entry belongs to an existing group when there are still open
    counter entries whose chain traces back to a *different* root in the
    same direction — but in the snowball model, trend re-entries always
    start a new group because the previous trend entry was closed (TP).

    However, the *counter* entries that were opened while the old trend
    entry was alive should stay in the old group.  The parent_entry_id
    chain already handles this correctly: counter entries point back to
    the trend entry (or to each other) that was alive when they were
    created.

    Close events share the same entry_id as the open event they close,
    so they belong to the same group as the corresponding open event.
    """
    # Map entry_id -> root entry_id (the top of the parent chain)
    entry_to_root: dict[int, int] = {}
    # Map entry_id -> parent_entry_id for chain walking
    parent_map: dict[int, int | None] = {}

    # First pass: build parent_map from open events
    for event in events:
        if event.event_type == "open_position" and event.entry_id is not None:
            parent_map[event.entry_id] = event.parent_entry_id

    # Walk chains to find roots
    def find_root(eid: int) -> int:
        if eid in entry_to_root:
            return entry_to_root[eid]
        visited = [eid]
        current: int = eid
        while parent_map.get(current) is not None:
            current = parent_map[current]  # type: ignore[assignment]
            if current in entry_to_root:
                root = entry_to_root[current]
                for v in visited:
                    entry_to_root[v] = root
                return root
            visited.append(current)
        # current is the root
        for v in visited:
            entry_to_root[v] = current
        return current

    for eid in parent_map:
        find_root(eid)

    # Group events by root entry_id
    groups: dict[int, list[VisualizationEvent]] = defaultdict(list)
    for event in events:
        if event.entry_id is not None and event.entry_id in entry_to_root:
            root = entry_to_root[event.entry_id]
            groups[root].append(event)
        elif event.entry_id is not None:
            # Open event with no parent chain (shouldn't happen, but be safe)
            groups[event.entry_id].append(event)

    return dict(groups)


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

        # Rebuild groups from parent_entry_id chains instead of visual_group_id
        chain_groups = _build_groups_from_parent_chain(normalized)
        if not chain_groups:
            # Fallback: try legacy visual_group_id grouping
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
            chain_groups = {
                int(gid) if gid.isdigit() else hash(gid): evts for gid, evts in by_group.items()
            }

        # Sort groups by start time and assign sequential group_id
        sorted_roots = sorted(
            chain_groups.keys(),
            key=lambda root: min(
                (e.event_timestamp or e.created_at for e in chain_groups[root]),
                default=datetime.min,
            ),
        )

        groups = []
        for seq, root_eid in enumerate(sorted_roots, start=1):
            group = self._build_snowball_group(
                group_id=str(seq),
                root_entry_id=root_eid,
                events=chain_groups[root_eid],
                task=task,
            )
            groups.append(group)

        if root_entry_id is not None:
            groups = [
                group
                for group in groups
                if int(group.get("root_entry_id") or 0) == int(root_entry_id)
            ]
        groups.sort(key=lambda group: group["started_at"] or "", reverse=True)

        display_cycles = self._split_display_cycles(groups)

        return {
            "strategy_type": strategy_type,
            "supported": True,
            "execution_id": str(execution_id) if execution_id else None,
            "generated_at": _dt_to_str(max((e.created_at for e in normalized), default=None)),
            "summary": self._build_summary(groups=groups, display_cycles=display_cycles),
            "view_model": {
                "kind": "snowball_runs",
                "groups": groups,
                "display_cycles": display_cycles,
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
        root_entry_id: int,
        events: list[VisualizationEvent],
        task: Any,
    ) -> dict[str, Any]:
        ordered = sorted(
            events,
            key=lambda event: ((event.event_timestamp or event.created_at), event.created_at),
        )
        first = ordered[0]
        last = ordered[-1]

        # The root event is the Initial Entry (the one whose entry_id == root_entry_id)
        root_event = next(
            (
                event
                for event in ordered
                if event.entry_id is not None
                and event.entry_id == root_entry_id
                and event.event_type == "open_position"
            ),
            first,
        )

        root_closed = any(
            event.event_type == "close_position"
            and event.entry_id is not None
            and event.entry_id == root_entry_id
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
            "root_entry_id": root_entry_id,
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

    def _split_counter_sub_cycles(
        self,
        counter_steps: list[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        """Split counter steps into sub-cycles at points where all open entries are closed.

        逆行ステップを、全オープンカウンターエントリーがクローズされた
        時点でサブサイクルに分割する。

        Preconditions:
        - counter_steps is sorted chronologically
        - Each step has basket="counter" or kind="counter_tp"

        Postconditions:
        - Each element of the returned list is a list of steps forming one sub-cycle
        - The last sub-cycle may have open entries remaining (active)

        Loop invariants:
        - open_entries is the set of entry_ids currently open in the current sub-cycle
        - current_steps is the list of steps belonging to the current sub-cycle
        """
        sub_cycles: list[list[dict[str, Any]]] = []
        current_steps: list[dict[str, Any]] = []
        open_entries: set[int] = set()

        for step in counter_steps:
            current_steps.append(step)

            if step["event_type"] == "open_position" and step["entry_id"] is not None:
                open_entries.add(step["entry_id"])

            if step["event_type"] == "close_position" and step["entry_id"] is not None:
                open_entries.discard(step["entry_id"])

            # Sub-cycle complete when all open entries have been closed
            if len(open_entries) == 0 and len(current_steps) > 0:
                sub_cycles.append(current_steps)
                current_steps = []
                open_entries = set()

        # Remaining steps form the last (possibly active) sub-cycle
        if current_steps:
            sub_cycles.append(current_steps)

        return sub_cycles

    def _build_display_cycle(
        self,
        *,
        parent_group_id: str,
        cycle_type: str,
        cycle_index: int,
        steps: list[dict[str, Any]],
        parent_status: str,
        root_entry_id: int | None,
        root_direction: str | None,
    ) -> dict[str, Any]:
        """Build a single DisplayCycle dict from a list of steps.

        ディスプレイサイクルを構築する。cycle_id生成、ステータス算出、
        cycle_summary算出を行う。

        Preconditions:
        - steps is non-empty
        - steps is sorted chronologically

        Postconditions:
        - Returned dict conforms to the DisplayCycle schema
        - status is correctly derived from step contents
        """
        cycle_id = f"{parent_group_id}:{cycle_type}:{cycle_index}"

        # ステータス算出
        has_protection = any(
            s["kind"] in ("shrink", "rebalance", "lock_hedge_neutralize") for s in steps
        )
        if has_protection or parent_status == "intervened":
            status = "intervened"
        else:
            opened = {
                s["entry_id"]
                for s in steps
                if s["event_type"] == "open_position" and s["entry_id"] is not None
            }
            closed = {
                s["entry_id"]
                for s in steps
                if s["event_type"] == "close_position" and s["entry_id"] is not None
            }
            has_open_left = bool(opened - closed)
            status = "active" if has_open_left else "completed"

        # サイクルサマリー算出
        retracement_values = [v for s in steps if (v := s.get("retracement_count")) is not None]
        layer_values = [v for s in steps if (v := s.get("layer_number")) is not None]
        cycle_summary: dict[str, Any] = {
            "step_count": len(steps),
            "open_count": sum(1 for s in steps if s["event_type"] == "open_position"),
            "close_count": sum(1 for s in steps if s["event_type"] == "close_position"),
            "max_retracement": max(retracement_values) if retracement_values else None,
            "max_layer": max(layer_values) if layer_values else None,
            "validation_fail_count": sum(1 for s in steps if s.get("validation_status") == "fail"),
        }

        return {
            "cycle_id": cycle_id,
            "parent_group_id": parent_group_id,
            "cycle_type": cycle_type,
            "display_label": f"{cycle_type}_cycle_{cycle_index}",
            "status": status,
            "started_at": steps[0].get("timestamp"),
            "ended_at": steps[-1].get("timestamp") if status != "active" else None,
            "root_entry_id": root_entry_id,
            "root_direction": root_direction,
            "steps": steps,
            "cycle_summary": cycle_summary,
        }

    def _split_display_cycles(
        self,
        groups: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Split each parent group into trend cycles and counter sub-cycles.

        各親グループを順行サイクルと逆行サブサイクルに分割する。

        Preconditions:
        - groups is a list of parent groups built by _build_snowball_group()
        - Each group's steps are sorted chronologically

        Postconditions:
        - Each element of the returned list is a DisplayCycle dict
        - All cycles are sorted by started_at in ascending order
        - Each cycle's cycle_id is unique
        """
        cycles: list[dict[str, Any]] = []

        for group in groups:
            steps = group["steps"]
            parent_group_id = group["group_id"]
            parent_status = group["status"]

            # 順行ステップの抽出
            trend_steps = [s for s in steps if s["basket"] == "trend" or s["kind"] == "trend_tp"]

            if trend_steps:
                cycles.append(
                    self._build_display_cycle(
                        parent_group_id=parent_group_id,
                        cycle_type="trend",
                        cycle_index=1,
                        steps=trend_steps,
                        parent_status=parent_status,
                        root_entry_id=group.get("root_entry_id"),
                        root_direction=group.get("root_direction"),
                    )
                )

            # 逆行ステップの抽出とサブサイクル分割
            counter_steps = [
                s for s in steps if s["basket"] == "counter" or s["kind"] == "counter_tp"
            ]

            if counter_steps:
                sub_cycles = self._split_counter_sub_cycles(counter_steps)
                for idx, sub_steps in enumerate(sub_cycles, start=1):
                    cycles.append(
                        self._build_display_cycle(
                            parent_group_id=parent_group_id,
                            cycle_type="counter",
                            cycle_index=idx,
                            steps=sub_steps,
                            parent_status=parent_status,
                            root_entry_id=group.get("root_entry_id"),
                            root_direction=group.get("root_direction"),
                        )
                    )

        # 全サイクルを開始時刻の昇順でソート
        cycles.sort(key=lambda c: c["started_at"] or "")
        return cycles

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

    def _build_summary(
        self,
        *,
        groups: list[dict[str, Any]],
        display_cycles: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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

        cycles = display_cycles or []

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
            "display_cycle_count": len(cycles),
            "trend_cycle_count": sum(1 for c in cycles if c.get("cycle_type") == "trend"),
            "counter_cycle_count": sum(1 for c in cycles if c.get("cycle_type") == "counter"),
        }
