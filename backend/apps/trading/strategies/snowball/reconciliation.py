"""Snowball broker reconciliation adapter."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from apps.trading.enums import Direction
from apps.trading.models import Position
from apps.trading.strategies.reconciliation import (
    AccountReconciliationState,
    ReconciliationReportBase,
    StrategyConfigLike,
)
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState
from apps.trading.strategies.snowball.entries import Entry
from apps.trading.strategies.snowball.grid_models import Layer
from apps.trading.strategies.snowball.pricing import SNOWBALL_PRICING

__all__ = [
    "SNOWBALL_RECONCILER",
    "PositionMatch",
    "ReconciliationReport",
    "ReconciliationState",
    "SnowballBrokerReconciler",
    "SnowballReconciliationBlockerFactory",
    "StrategyConfigLike",
]


class ReconciliationState(AccountReconciliationState, Protocol):
    """Snowball state surface required for broker reconciliation."""


class ReconciliationReport(ReconciliationReportBase, Protocol):
    """Mutable reconciliation report fields updated by Snowball."""

    removed_open_entries: int
    relinked_open_entries: int
    synthesized_open_entries: int


@dataclass(frozen=True)
class PositionMatch:
    position: Position | None
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class SnowballReconciliationBlockerFactory:
    """Build stable public blocker messages for Snowball reconciliation."""

    def ambiguous_entry(self, *, entry: Entry, label: str) -> str:
        """Return a blocker for entries matching multiple broker positions."""
        return (
            f"Snowball {self._entry_label(entry, label)} "
            "matches multiple broker positions. Reconciliation is blocked "
            "to avoid relinking the wrong position."
        )

    def missing_entry(self, *, entry: Entry, label: str) -> str:
        """Return a blocker for entries with no matching broker position."""
        return (
            f"Snowball {self._entry_label(entry, label)} has no matching broker position. "
            "The position may have been closed externally while the task was stopped. "
            "Use restart to begin a fresh execution."
        )

    def unmatched_position(self, position: Position) -> str:
        """Return a blocker for broker positions absent from strategy state."""
        return (
            "Snowball strategy state could not match open position "
            f"{position.id} (layer={position.layer_index}, "
            f"retracement={position.retracement_count})."
        )

    def _entry_label(self, entry: Entry, label: str) -> str:
        if label == "hedge entry":
            return f"hedge entry {entry.entry_id}"
        return f"entry {entry.entry_id} (L{entry.layer_number}/R{entry.retracement_count})"


@dataclass(frozen=True, slots=True)
class SnowballBrokerReconciler:
    """Reconcile persisted Snowball entries against broker-backed positions."""

    blocker_factory: SnowballReconciliationBlockerFactory = SnowballReconciliationBlockerFactory()

    def reconcile(
        self,
        *,
        state: ReconciliationState,
        open_positions: list[Position],
        report: ReconciliationReport,
        strategy_config: StrategyConfigLike | None = None,
    ) -> None:
        """Update Snowball strategy state using currently open broker positions."""
        snowball_state = SnowballStrategyState.from_strategy_state(state.strategy_state)
        config = self._parse_config(strategy_config)
        by_id = {str(position.id): position for position in open_positions}
        assigned_ids: set[str] = set()

        for cycle in snowball_state.cycles:
            for layer in cycle.grid.layers:
                for slot in layer.slots:
                    entry = slot.entry
                    if entry is None:
                        continue
                    self._reconcile_entry(
                        entry=entry,
                        layer=layer,
                        open_positions=open_positions,
                        by_id=by_id,
                        assigned_ids=assigned_ids,
                        report=report,
                        config=config,
                    )

            for entry in cycle.hedge_entries:
                self._reconcile_entry(
                    entry=entry,
                    layer=None,
                    open_positions=open_positions,
                    by_id=by_id,
                    assigned_ids=assigned_ids,
                    report=report,
                    config=config,
                    label="hedge entry",
                )

        self._report_unmatched_positions(
            open_positions=open_positions,
            assigned_ids=assigned_ids,
            report=report,
        )
        self._sync_account_state(
            state=state,
            snowball_state=snowball_state,
            open_positions=open_positions,
        )

    def match_position_for_entry(
        self,
        *,
        entry: Entry,
        open_positions: list[Position],
        by_id: dict[str, Position],
        assigned_ids: set[str],
    ) -> PositionMatch:
        """Return the broker position matched to a Snowball entry."""
        position_id = str(getattr(entry, "position_id", "") or "").strip()
        if position_id:
            candidate = by_id.get(position_id)
            if candidate is not None and str(candidate.id) not in assigned_ids:
                return PositionMatch(position=candidate)

        entry_layer = int(getattr(entry, "layer_number", 0) or 0)
        entry_retracement = int(getattr(entry, "retracement_count", 0) or 0)
        entry_direction = str(getattr(entry, "direction", "") or "").lower()
        entry_units = abs(int(getattr(entry, "units", 0) or 0))
        candidates: list[Position] = []

        for candidate in open_positions:
            candidate_id = str(candidate.id)
            if candidate_id in assigned_ids:
                continue
            if entry_layer > 0 and int(candidate.layer_index or 0) != entry_layer:
                continue
            if int(candidate.retracement_count or 0) != entry_retracement:
                continue
            if entry_direction in {Direction.LONG.value, Direction.SHORT.value} and (
                str(candidate.direction).lower() != entry_direction
            ):
                continue
            if entry_units > 0 and abs(int(candidate.units)) != entry_units:
                continue

            candidates.append(candidate)

        if not candidates:
            return PositionMatch(position=None)
        if len(candidates) > 1:
            return PositionMatch(position=None, ambiguous=True)
        return PositionMatch(position=candidates[0])

    def _reconcile_entry(
        self,
        *,
        entry: Entry,
        layer: Layer | None,
        open_positions: list[Position],
        by_id: dict[str, Position],
        assigned_ids: set[str],
        report: ReconciliationReport,
        config: SnowballStrategyConfig,
        label: str = "entry",
    ) -> None:
        match = self.match_position_for_entry(
            entry=entry,
            open_positions=open_positions,
            by_id=by_id,
            assigned_ids=assigned_ids,
        )
        matched = match.position
        if match.ambiguous:
            report.blockers.append(self.blocker_factory.ambiguous_entry(entry=entry, label=label))
            return
        if matched is None:
            report.removed_open_entries += 1
            report.blockers.append(self.blocker_factory.missing_entry(entry=entry, label=label))
            return

        self._apply_position_to_entry(
            entry=entry,
            layer=layer,
            position=matched,
            report=report,
            config=config,
        )
        assigned_ids.add(str(matched.id))

    def _apply_position_to_entry(
        self,
        *,
        entry: Entry,
        layer: Layer | None,
        position: Position,
        report: ReconciliationReport,
        config: SnowballStrategyConfig,
    ) -> None:
        position_id = str(position.id)
        if entry.position_id != position_id:
            entry.position_id = position_id
            report.relinked_open_entries += 1

        entry.direction = Direction(str(position.direction).lower())
        entry.units = abs(int(position.units))
        SNOWBALL_PRICING.sync_entry_fill_price(
            entry=entry,
            layer=layer,
            fill_price=self._strict_decimal(
                position.entry_price,
                field_name="position.entry_price",
            ),
            counter_tp_mode=config.counter_tp_mode,
        )
        entry.layer_number = int(position.layer_index or entry.layer_number or 1)
        entry.retracement_count = int(position.retracement_count or entry.retracement_count or 0)
        if position.entry_time is not None:
            entry.opened_at = position.entry_time

    def _report_unmatched_positions(
        self,
        *,
        open_positions: list[Position],
        assigned_ids: set[str],
        report: ReconciliationReport,
    ) -> None:
        unmatched_positions = [
            position for position in open_positions if str(position.id) not in assigned_ids
        ]
        for position in unmatched_positions:
            report.synthesized_open_entries += 1
            report.blockers.append(self.blocker_factory.unmatched_position(position))

    def _sync_account_state(
        self,
        *,
        state: ReconciliationState,
        snowball_state: SnowballStrategyState,
        open_positions: list[Position],
    ) -> None:
        snowball_state.account_balance = self._strict_decimal(
            state.current_balance,
            field_name="state.current_balance",
        )
        snowball_state.account_nav = snowball_state.account_balance + sum(
            (
                self._strict_decimal(
                    position.unrealized_pnl,
                    field_name="position.unrealized_pnl",
                )
                for position in open_positions
            ),
            Decimal("0"),
        )
        state.strategy_state = snowball_state.to_dict()

    def _strict_decimal(self, value: Any, *, field_name: str) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:
            raise ValueError(f"Snowball reconciliation field {field_name} must be decimal") from exc

    def _parse_config(self, strategy_config: StrategyConfigLike | None) -> SnowballStrategyConfig:
        if strategy_config is None:
            return SnowballStrategyConfig.from_dict({})
        return SnowballStrategyConfig.strict_from_dict(strategy_config.config_dict)


SNOWBALL_RECONCILER = SnowballBrokerReconciler()
