"""Create Snowball initial backtest execution records before task start."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.trading.dataclasses import EventContext, Tick
from apps.trading.engine import TradingEngine
from apps.trading.enums import Direction, TaskStatus, TaskType
from apps.trading.events import ClosePositionEvent, StrategyEvent
from apps.trading.models import (
    BacktestTask,
    ExecutionMetricAggregate,
    ExecutionState,
    Metrics,
    Order,
    Position,
    StrategyEventRecord,
    Trade,
    TradingEvent,
)
from apps.trading.money import AccountCurrency
from apps.trading.order import OrderService
from apps.trading.strategies.snowball.calculators import SnowballCalculator
from apps.trading.strategies.snowball.cycle_state import (
    SnowballCycle,
    SnowballStrategyState,
)
from apps.trading.strategies.snowball.entries import Entry, StopLossClosedEntry
from apps.trading.strategies.snowball.enums import CycleStatus
from apps.trading.strategies.snowball.events import SNOWBALL_EVENTS
from apps.trading.strategies.snowball.grid_models import Layer
from apps.trading.strategies.snowball.parameters import SNOWBALL_PARAMETER_SERVICE
from apps.trading.strategies.snowball.pricing import SNOWBALL_PRICING
from apps.trading.tasks.event_persistence import persist_strategy_events
from apps.trading.tasks.event_replay import mark_event_processed
from apps.trading.utils import Instrument, pip_size_for_instrument

PREVIEW_STATE_MARKER = "_initial_position_seed_preview"
SEED_VERSION = 1

POSITION_STATUS_OPEN = "open"
POSITION_STATUS_CLOSED = "closed"
POSITION_STATUS_PENDING_REBUILD = "pending_rebuild"
POSITION_STATUSES = {
    POSITION_STATUS_OPEN,
    POSITION_STATUS_CLOSED,
    POSITION_STATUS_PENDING_REBUILD,
}
PREVIEWABLE_TASK_STATUSES = {
    TaskStatus.CREATED,
    TaskStatus.STOPPED,
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
}


class InitialPositionValidationError(ValueError):
    """Raised when the requested initial Snowball structure is invalid."""

    def __init__(self, errors: dict[str, Any]) -> None:
        super().__init__("Invalid initial position structure")
        self.errors = errors


@dataclass(slots=True)
class NormalizedSeedPosition:
    layer_number: int
    retracement_count: int
    units: int
    entry_price: Decimal
    planned_exit_price: Decimal | None
    stop_loss_price: Decimal | None
    status: str
    exit_price: Decimal | None
    close_reason: str


@dataclass(slots=True)
class NormalizedSeedCycle:
    direction: Direction
    positions: list[NormalizedSeedPosition]


def is_initial_position_preview_state(state: ExecutionState | None) -> bool:
    """Return whether an ExecutionState is a not-yet-started seed preview."""
    raw = getattr(state, "strategy_state", None)
    return isinstance(raw, dict) and raw.get(PREVIEW_STATE_MARKER) is True


def _is_preview_execution(*, task_id: Any, execution_id: Any) -> bool:
    if execution_id is None:
        return False
    state = (
        ExecutionState.objects.filter(
            task_type=TaskType.BACKTEST.value,
            task_id=task_id,
            execution_id=execution_id,
        )
        .only("strategy_state")
        .first()
    )
    return is_initial_position_preview_state(state)


def _validate_initial_position_cycles_impl(
    *,
    task: BacktestTask | None,
    config: Any,
    cycles: Any,
    pip_size: Decimal | None = None,
) -> list[NormalizedSeedCycle]:
    """Validate and normalize the requested initial Snowball cycle payload."""
    if not isinstance(cycles, list):
        raise InitialPositionValidationError({"initial_position_cycles": "Must be a list."})

    if not cycles:
        raise InitialPositionValidationError(
            {"initial_position_cycles": "At least one cycle is required."}
        )

    strategy_type = str(getattr(config, "strategy_type", "") or "")
    if strategy_type != "snowball":
        raise InitialPositionValidationError(
            {
                "initial_positions_enabled": (
                    "Initial positions are currently supported only for Snowball strategy."
                )
            }
        )

    cfg = SNOWBALL_PARAMETER_SERVICE.parse_config(config)
    resolved_pip_size = _resolve_pip_size(task=task, pip_size=pip_size)

    normalized_cycles: list[NormalizedSeedCycle] = []
    errors: dict[str, Any] = {}
    for cycle_index, raw_cycle in enumerate(cycles):
        path = f"initial_position_cycles[{cycle_index}]"
        if not isinstance(raw_cycle, dict):
            errors[path] = "Cycle must be an object."
            continue

        try:
            direction = Direction(str(raw_cycle.get("direction", "")).strip().lower())
        except ValueError:
            errors[f"{path}.direction"] = "Direction must be 'long' or 'short'."
            continue

        raw_positions = raw_cycle.get("positions")
        if not isinstance(raw_positions, list) or not raw_positions:
            errors[f"{path}.positions"] = "At least one position is required."
            continue

        normalized_positions: list[NormalizedSeedPosition] = []
        seen: set[tuple[int, int]] = set()
        for pos_index, raw_pos in enumerate(raw_positions):
            pos_path = f"{path}.positions[{pos_index}]"
            if not isinstance(raw_pos, dict):
                errors[pos_path] = "Position must be an object."
                continue

            position = _normalize_position(
                raw_pos,
                path=pos_path,
                errors=errors,
            )
            if position is None:
                continue

            slot = (position.layer_number, position.retracement_count)
            if slot in seen:
                errors[pos_path] = (
                    f"Duplicate slot L{position.layer_number}/R{position.retracement_count}."
                )
                continue
            seen.add(slot)

            if position.layer_number < 1 or position.layer_number > cfg.f_max:
                errors[f"{pos_path}.layer_number"] = f"Layer must be between 1 and {cfg.f_max}."
            if position.retracement_count < 0 or position.retracement_count > cfg.r_max:
                errors[f"{pos_path}.retracement_count"] = (
                    f"Retracement must be between 0 and {cfg.r_max}."
                )
            if not cfg.stop_loss_enabled:
                if position.stop_loss_price is not None:
                    errors[f"{pos_path}.stop_loss_price"] = (
                        "Stop loss is disabled in the strategy configuration."
                    )
                if position.status == POSITION_STATUS_PENDING_REBUILD:
                    errors[f"{pos_path}.status"] = (
                        "Pending rebuild positions require stop loss to be enabled."
                    )

            normalized_positions.append(position)

        if normalized_positions:
            normalized_positions.sort(key=lambda p: (p.layer_number, p.retracement_count))
            expected_slots = _expected_prefix_slots(
                count=len(normalized_positions),
                r_max=cfg.r_max,
            )
            actual_slots = [(p.layer_number, p.retracement_count) for p in normalized_positions]
            if actual_slots != expected_slots:
                expected_label = ", ".join(
                    f"L{layer}/R{retracement}" for layer, retracement in expected_slots
                )
                actual_label = ", ".join(
                    f"L{layer}/R{retracement}" for layer, retracement in actual_slots
                )
                errors[f"{path}.positions"] = (
                    "Positions must be stacked contiguously from L1/R0. "
                    f"Expected prefix: {expected_label}; received: {actual_label}."
                )

            for position in normalized_positions:
                _fill_default_prices(
                    position=position,
                    previous_positions=normalized_positions,
                    direction=direction,
                    config=cfg,
                    pip_size=resolved_pip_size,
                )

            normalized_cycles.append(
                NormalizedSeedCycle(direction=direction, positions=normalized_positions)
            )

    if errors:
        raise InitialPositionValidationError(errors)

    return normalized_cycles


class InitialPositionCycleValidator:
    """Validate and normalize requested initial-position cycle payloads."""

    def validate(
        self,
        *,
        task: BacktestTask | None,
        config: Any,
        cycles: Any,
        pip_size: Decimal | None = None,
    ) -> list[NormalizedSeedCycle]:
        """Validate and normalize the requested initial Snowball cycle payload."""
        return _validate_initial_position_cycles_impl(
            task=task,
            config=config,
            cycles=cycles,
            pip_size=pip_size,
        )


INITIAL_POSITION_CYCLE_VALIDATOR = InitialPositionCycleValidator()


def validate_initial_position_cycles(
    *,
    task: BacktestTask | None,
    config: Any,
    cycles: Any,
    pip_size: Decimal | None = None,
) -> list[NormalizedSeedCycle]:
    """Validate and normalize the requested initial Snowball cycle payload."""
    return INITIAL_POSITION_CYCLE_VALIDATOR.validate(
        task=task,
        config=config,
        cycles=cycles,
        pip_size=pip_size,
    )


class BacktestInitialPositionService:
    """Synchronize Snowball seed settings with preview execution records."""

    def __init__(
        self,
        *,
        validator: InitialPositionCycleValidator | None = None,
    ) -> None:
        self.validator = validator or INITIAL_POSITION_CYCLE_VALIDATOR

    def sync_for_task(self, task: BacktestTask) -> None:
        """Create or clear the preview execution data for a backtest task."""
        if task.status not in PREVIEWABLE_TASK_STATUSES:
            return

        if getattr(task, "initial_positions_enabled", False) is not True:
            self.clear_preview(task)
            return

        normalized_cycles = self.validator.validate(
            task=task,
            config=task.config,
            cycles=task.initial_position_cycles,
            pip_size=task.pip_size,
        )

        with transaction.atomic():
            task = (
                BacktestTask.objects.select_for_update()
                .select_related("config", "user")
                .get(pk=task.pk)
            )
            if task.status not in PREVIEWABLE_TASK_STATUSES:
                return
            if getattr(task, "initial_positions_enabled", False) is not True:
                self._clear_preview_for_locked_task(task)
                return
            current_preview = _is_preview_execution(
                task_id=task.pk,
                execution_id=task.execution_id,
            )
            if task.execution_id is None:
                task.execution_id = uuid4()
                task.save(update_fields=["execution_id", "updated_at"])
            elif task.status != TaskStatus.CREATED and not current_preview:
                task.execution_id = uuid4()
                task.save(update_fields=["execution_id", "updated_at"])
            elif task.status == TaskStatus.CREATED and not current_preview:
                task.execution_id = uuid4()
                task.save(update_fields=["execution_id", "updated_at"])
            self._clear_scope(task)
            self._seed_preview(task=task, normalized_cycles=normalized_cycles)

    def clear_preview(self, task: BacktestTask) -> None:
        """Remove not-yet-started seed preview records."""
        if task.status not in PREVIEWABLE_TASK_STATUSES or task.execution_id is None:
            return

        with transaction.atomic():
            task = BacktestTask.objects.select_for_update().get(pk=task.pk)
            if task.status not in PREVIEWABLE_TASK_STATUSES or task.execution_id is None:
                return
            self._clear_preview_for_locked_task(task)

    def _clear_preview_for_locked_task(self, task: BacktestTask) -> None:
        if not _is_preview_execution(task_id=task.pk, execution_id=task.execution_id):
            return
        self._clear_scope(task)
        task.execution_id = None
        task.save(update_fields=["execution_id", "updated_at"])

    def _seed_preview(
        self,
        *,
        task: BacktestTask,
        normalized_cycles: list[NormalizedSeedCycle],
    ) -> None:
        pip_size = Decimal(str(task.pip_size or pip_size_for_instrument(task.instrument)))
        engine = TradingEngine(
            instrument=task.instrument,
            pip_size=pip_size,
            strategy_config=task.config,
            account_currency=task.account_currency or "USD",
            hedging_enabled=task.hedging_enabled,
        )
        order_service = OrderService(account=None, task=task, dry_run=True)
        event_handler = engine.create_event_handler(
            order_service=order_service,
            instrument=task.instrument,
        )
        context = EventContext(
            user=task.user,
            account=None,
            instrument=task.instrument,
            task_id=task.pk,
            execution_id=task.execution_id,
            task_type=TaskType.BACKTEST,
        )

        seed_timestamp = task.start_time - timedelta(seconds=1)
        state = ExecutionState.objects.create(
            task_type=TaskType.BACKTEST.value,
            task_id=task.pk,
            execution_id=task.execution_id,
            strategy_state={},
            current_balance=task.initial_balance,
            current_balance_currency=str(task.account_currency or "").upper(),
            ticks_processed=0,
            last_tick_timestamp=seed_timestamp,
            resume_cursor_timestamp=task.start_time,
            last_tick_price=None,
            last_tick_bid=None,
            last_tick_ask=None,
        )
        snowball_state = SnowballStrategyState(
            initialised=True,
            account_balance=Decimal(str(task.initial_balance)),
            account_nav=Decimal(str(task.initial_balance)),
        )

        event_sequence = 0
        for cycle_spec in normalized_cycles:
            first = cycle_spec.positions[0]
            root_entry_id = snowball_state.allocate_id()
            cycle = SnowballCycle(cycle_id=root_entry_id, direction=cycle_spec.direction)
            snowball_state.cycles.append(cycle)

            for position_spec in cycle_spec.positions:
                layer = _ensure_layer(
                    cycle=cycle,
                    layer_number=position_spec.layer_number,
                    r_max=engine.strategy.config.r_max,  # type: ignore[attr-defined]
                    base_units=engine.strategy.config.base_units,  # type: ignore[attr-defined]
                    refill_up_to=engine.strategy.config.refill_up_to,  # type: ignore[attr-defined]
                )
                slot = layer.slot_at(position_spec.retracement_count)
                if slot is None:
                    raise InitialPositionValidationError(
                        {
                            "initial_position_cycles": (
                                "Generated slot was outside the configured Snowball grid."
                            )
                        }
                    )

                if (
                    position_spec.layer_number == first.layer_number
                    and position_spec.retracement_count == first.retracement_count
                ):
                    entry_id = root_entry_id
                else:
                    entry_id = snowball_state.allocate_id()

                entry = _entry_from_seed(
                    entry_id=entry_id,
                    cycle_id=root_entry_id,
                    direction=cycle_spec.direction,
                    position=position_spec,
                    opened_at=seed_timestamp + timedelta(microseconds=event_sequence),
                    pip_size=pip_size,
                )
                slot.fill(entry)

                open_event = SNOWBALL_EVENTS.entry_open_event(
                    entry,
                    timestamp=seed_timestamp + timedelta(microseconds=event_sequence),
                    planned_exit_price_formula="initial backtest seed",
                    description=(
                        "Initial backtest seed "
                        f"L{position_spec.layer_number}/R{position_spec.retracement_count}"
                    ),
                )
                event_sequence = self._process_event(
                    event=open_event,
                    context=context,
                    event_handler=event_handler,
                    engine=engine,
                    state=state,
                    snowball_state=snowball_state,
                    event_sequence=event_sequence,
                )
                binding = getattr(event_handler, "_last_open_cycle_id", None)
                if binding and cycle.trade_cycle_id is None:
                    cycle.trade_cycle_id = str(binding)
                entry.position_id = _latest_position_id_for_entry(
                    task=task,
                    execution_id=task.execution_id,
                    entry=entry,
                )

                if position_spec.status == POSITION_STATUS_OPEN:
                    state.strategy_state = snowball_state.to_dict()
                    continue

                close_event = _close_event_for_seed(
                    task=task,
                    entry=entry,
                    position=position_spec,
                    timestamp=seed_timestamp + timedelta(microseconds=event_sequence),
                    account_currency=task.account_currency or "USD",
                    pip_size=pip_size,
                )
                event_sequence = self._process_event(
                    event=close_event,
                    context=context,
                    event_handler=event_handler,
                    engine=engine,
                    state=state,
                    snowball_state=snowball_state,
                    event_sequence=event_sequence,
                )

                if position_spec.status == POSITION_STATUS_PENDING_REBUILD:
                    slot.close_for_stop_loss(
                        _pending_snapshot_from_entry(
                            entry=entry,
                            cycle_id=cycle.cycle_id,
                            exit_price=position_spec.exit_price or entry.stop_loss_price,
                            closed_at=close_event.timestamp,
                            pip_size=pip_size,
                        )
                    )
                    if not cycle.all_entries():
                        cycle.status = CycleStatus.PENDING
                else:
                    slot.close(refillable=False)
                state.strategy_state = snowball_state.to_dict()

            if not _cycle_has_present_entries(cycle):
                cycle.status = CycleStatus.COMPLETED
            elif not cycle.all_entries():
                cycle.status = CycleStatus.PENDING

        final_state = snowball_state.to_dict()
        final_state[PREVIEW_STATE_MARKER] = True
        final_state["_initial_position_seed"] = {
            "version": SEED_VERSION,
            "created_at": timezone.now().isoformat(),
        }
        state.strategy_state = final_state
        state.current_balance = Decimal(str(state.current_balance))
        state.save()

    def _process_event(
        self,
        *,
        event: StrategyEvent,
        context: EventContext,
        event_handler: Any,
        engine: TradingEngine,
        state: ExecutionState,
        snowball_state: SnowballStrategyState,
        event_sequence: int,
    ) -> int:
        state.strategy_state = snowball_state.to_dict()
        event.timestamp = event.timestamp or timezone.now()
        trading_events = persist_strategy_events(
            events=[event],
            context=context,
            execution_id=context.execution_id,
            strategy_type="snowball",
        )
        for trading_event in trading_events:
            result = event_handler.handle_event(trading_event)
            if result.realized_pnl_delta != Decimal("0"):
                state.current_balance = (
                    Decimal(str(state.current_balance)) + result.realized_pnl_delta
                )
                if result.realized_pnl_delta_currency:
                    state.current_balance_currency = result.realized_pnl_delta_currency
            binding = result.entry_binding
            if binding is not None:
                _apply_entry_binding(
                    snowball_state=snowball_state,
                    entry_id=binding.entry_id,
                    position_id=binding.position_id,
                    cycle_id=binding.cycle_id,
                    fill_price=binding.fill_price,
                    counter_tp_mode=engine.strategy.config.counter_tp_mode,  # type: ignore[attr-defined]
                )
                state.strategy_state = snowball_state.to_dict()
            mark_event_processed(trading_event)
            if result.order_ids:
                Order.objects.filter(pk__in=result.order_ids).update(
                    submitted_at=event.timestamp,
                    created_at=event.timestamp,
                )
            if result.trade_ids:
                Trade.objects.filter(pk__in=result.trade_ids).update(
                    created_at=event.timestamp,
                    updated_at=event.timestamp,
                )
            if result.position_ids:
                Position.objects.filter(pk__in=result.position_ids).update(
                    created_at=event.timestamp,
                    updated_at=event.timestamp,
                )
        return event_sequence + 1

    def _clear_scope(self, task: BacktestTask) -> None:
        scope = {
            "task_type": TaskType.BACKTEST.value,
            "task_id": task.pk,
            "execution_id": task.execution_id,
        }
        TradingEvent.objects.filter(**scope).delete()
        StrategyEventRecord.objects.filter(**scope).delete()
        Trade.objects.filter(**scope).delete()
        Order.objects.filter(**scope).delete()
        Position.objects.filter(**scope).delete()
        Metrics.objects.filter(**scope).delete()
        ExecutionMetricAggregate.objects.filter(**scope).delete()
        ExecutionState.objects.filter(**scope).delete()


def _normalize_position(
    raw: dict[str, Any],
    *,
    path: str,
    errors: dict[str, Any],
) -> NormalizedSeedPosition | None:
    layer_number = _int_value(raw.get("layer_number"))
    retracement_count = _int_value(raw.get("retracement_count"))
    units = _int_value(raw.get("units"))
    entry_price = _decimal_value(raw.get("entry_price"))
    planned_exit_price = _optional_decimal_value(raw.get("planned_exit_price"))
    stop_loss_price = _optional_decimal_value(raw.get("stop_loss_price"))
    exit_price = _optional_decimal_value(raw.get("exit_price"))
    status = str(raw.get("status") or POSITION_STATUS_OPEN).strip().lower()
    close_reason = str(raw.get("close_reason") or "").strip().lower()

    if layer_number is None:
        errors[f"{path}.layer_number"] = "Layer is required."
    if retracement_count is None:
        errors[f"{path}.retracement_count"] = "Retracement is required."
    if units is None or units <= 0:
        errors[f"{path}.units"] = "Units must be a positive integer."
    if entry_price is None or entry_price <= 0:
        errors[f"{path}.entry_price"] = "Entry price must be positive."
    if planned_exit_price is not None and planned_exit_price <= 0:
        errors[f"{path}.planned_exit_price"] = "Planned exit price must be positive."
    if stop_loss_price is not None and stop_loss_price <= 0:
        errors[f"{path}.stop_loss_price"] = "Stop loss price must be positive."
    if exit_price is not None and exit_price <= 0:
        errors[f"{path}.exit_price"] = "Exit price must be positive."
    if status not in POSITION_STATUSES:
        errors[f"{path}.status"] = "Status must be open, closed, or pending_rebuild."

    if (
        layer_number is None
        or retracement_count is None
        or errors.get(f"{path}.layer_number")
        or errors.get(f"{path}.retracement_count")
    ):
        return None
    if units is None or entry_price is None:
        return None

    if status == POSITION_STATUS_PENDING_REBUILD:
        close_reason = "stop_loss"
    elif status == POSITION_STATUS_CLOSED and not close_reason:
        close_reason = "tp"

    return NormalizedSeedPosition(
        layer_number=int(layer_number),
        retracement_count=int(retracement_count),
        units=int(units),
        entry_price=entry_price,
        planned_exit_price=planned_exit_price,
        stop_loss_price=stop_loss_price,
        status=status,
        exit_price=exit_price,
        close_reason=close_reason,
    )


def _fill_default_prices(
    *,
    position: NormalizedSeedPosition,
    previous_positions: list[NormalizedSeedPosition],
    direction: Direction,
    config: Any,
    pip_size: Decimal,
) -> None:
    prior = [
        p
        for p in previous_positions
        if (p.layer_number, p.retracement_count)
        < (position.layer_number, position.retracement_count)
    ]
    if position.planned_exit_price is None:
        position.planned_exit_price = _default_take_profit(
            position=position,
            prior=prior,
            direction=direction,
            config=config,
            pip_size=pip_size,
        )
    if position.stop_loss_price is None and config.stop_loss_enabled:
        position.stop_loss_price = _default_stop_loss(
            position=position,
            direction=direction,
            config=config,
            pip_size=pip_size,
        )
    if position.status == POSITION_STATUS_PENDING_REBUILD and position.exit_price is None:
        position.exit_price = position.stop_loss_price or position.entry_price
    if position.status == POSITION_STATUS_CLOSED and position.exit_price is None:
        position.exit_price = position.planned_exit_price


def _default_take_profit(
    *,
    position: NormalizedSeedPosition,
    prior: list[NormalizedSeedPosition],
    direction: Direction,
    config: Any,
    pip_size: Decimal,
) -> Decimal:
    if position.retracement_count == 0:
        close_price = _take_profit_from_pips(
            direction=direction,
            entry_price=position.entry_price,
            pips=config.m_pips,
            pip_size=pip_size,
        )
        if position.layer_number == 1:
            return close_price
        previous_layer_prices = [
            p.planned_exit_price
            for p in prior
            if p.layer_number == position.layer_number - 1 and p.planned_exit_price is not None
        ]
        if not previous_layer_prices:
            return close_price
        bound = previous_layer_prices[-1]
        if direction == Direction.LONG and close_price > bound:
            return bound
        if direction == Direction.SHORT and close_price < bound:
            return bound
        return close_price

    if config.counter_tp_mode == "weighted_avg":
        layer_positions = [
            p
            for p in prior
            if p.layer_number == position.layer_number
            and p.status in {POSITION_STATUS_OPEN, POSITION_STATUS_PENDING_REBUILD}
        ]
        total_units = position.units + sum(p.units for p in layer_positions)
        weighted_price = position.entry_price * Decimal(str(position.units))
        for prior_position in layer_positions:
            weighted_price += prior_position.entry_price * Decimal(str(prior_position.units))
        return weighted_price / Decimal(str(total_units))

    tp_pips = SnowballCalculator(config).counter_tp_pips(position.retracement_count)
    return _take_profit_from_pips(
        direction=direction,
        entry_price=position.entry_price,
        pips=tp_pips,
        pip_size=pip_size,
    )


def _default_stop_loss(
    *,
    position: NormalizedSeedPosition,
    direction: Direction,
    config: Any,
    pip_size: Decimal,
) -> Decimal | None:
    calculator = SnowballCalculator(config)
    slot_number = position.retracement_count + 1
    if config.stop_loss_mode == "auto":
        next_interval = calculator.counter_interval_pips(slot_number)
        if next_interval <= 0:
            return None
        tp_pips = abs((position.planned_exit_price or position.entry_price) - position.entry_price)
        tp_pips = tp_pips / pip_size
        if direction == Direction.LONG:
            next_entry = position.entry_price - next_interval * pip_size
            return (
                next_entry
                if position.retracement_count == 0 or tp_pips < next_interval
                else (next_entry - next_interval * pip_size)
            )
        next_entry = position.entry_price + next_interval * pip_size
        return (
            next_entry
            if position.retracement_count == 0 or tp_pips < next_interval
            else (next_entry + next_interval * pip_size)
        )

    sl_pips = calculator.stop_loss_pips(slot_number)
    if sl_pips <= 0:
        return None
    if direction == Direction.LONG:
        return position.entry_price - sl_pips * pip_size
    return position.entry_price + sl_pips * pip_size


def _entry_from_seed(
    *,
    entry_id: int,
    cycle_id: int,
    direction: Direction,
    position: NormalizedSeedPosition,
    opened_at,
    pip_size: Decimal,
) -> Entry:
    role = _entry_role(position)
    root_entry_id = entry_id if role == "initial" else cycle_id
    parent_entry_id = None if role == "initial" else cycle_id
    expected_tp = (
        abs(position.planned_exit_price - position.entry_price) / pip_size
        if position.planned_exit_price is not None
        else None
    )
    entry = Entry(
        entry_id=entry_id,
        step=position.retracement_count + 1,
        direction=direction,
        entry_price=position.entry_price,
        close_price=position.planned_exit_price or position.entry_price,
        units=position.units,
        opened_at=opened_at,
        role=role,
        layer_number=position.layer_number,
        retracement_count=position.retracement_count,
        root_entry_id=root_entry_id,
        parent_entry_id=parent_entry_id,
        stop_loss_price=position.stop_loss_price,
        expected_tp_pips=expected_tp,
        validation_status="seed",
    )
    return entry


def _entry_role(position: NormalizedSeedPosition):
    if position.layer_number == 1 and position.retracement_count == 0:
        return "initial"
    if position.retracement_count == 0:
        return "layer_initial"
    return "counter"


def _close_event_for_seed(
    *,
    task: BacktestTask,
    entry: Entry,
    position: NormalizedSeedPosition,
    timestamp,
    account_currency: str,
    pip_size: Decimal,
) -> ClosePositionEvent:
    exit_price = position.exit_price or position.planned_exit_price or entry.entry_price
    tick = _tick_for_exit(
        instrument=task.instrument,
        timestamp=timestamp,
        direction=entry.direction,
        exit_price=exit_price,
    )
    event = SNOWBALL_EVENTS.entry_close_event(
        entry,
        tick,
        instrument=task.instrument,
        pip_size=pip_size,
        account_currency=account_currency,
        description=(
            f"Initial backtest seed close L{position.layer_number}/R{position.retracement_count}"
        ),
        close_reason=position.close_reason,
    )
    event.position_id = entry.position_id
    event.exit_price = exit_price
    event.pips = abs(exit_price - entry.entry_price) / pip_size
    conv = Instrument(task.instrument).quote_to_account_rate(
        tick.mid,
        AccountCurrency(account_currency),
    )
    pnl = (exit_price - entry.entry_price) * Decimal(str(entry.units)) * conv
    if entry.direction == Direction.SHORT:
        pnl = -pnl
    event.pnl = pnl
    event.timestamp = timestamp
    event.close_reason = position.close_reason
    event.strategy_event_type = f"snowball_{entry.role}"
    return event


def _pending_snapshot_from_entry(
    *,
    entry: Entry,
    cycle_id: int,
    exit_price: Decimal | None,
    closed_at: datetime | None,
    pip_size: Decimal,
) -> StopLossClosedEntry:
    realized_pips = Decimal("0")
    if exit_price is not None:
        realized_pips = abs(entry.entry_price - exit_price) / pip_size
    return StopLossClosedEntry(
        entry_price=entry.entry_price,
        close_price=entry.close_price,
        units=entry.units,
        direction=entry.direction,
        role=entry.role,
        layer_number=entry.layer_number,
        retracement_count=entry.retracement_count,
        step=entry.step,
        root_entry_id=entry.root_entry_id,
        parent_entry_id=entry.parent_entry_id,
        cycle_id=cycle_id,
        position_id=entry.position_id,
        stop_loss_price=entry.stop_loss_price,
        stop_loss_exit_price=exit_price,
        closed_at=closed_at,
        lifecycle_stop_loss_count=entry.lifecycle_stop_loss_count + 1,
        stop_loss_loss_pips=realized_pips,
    )


def _apply_entry_binding(
    *,
    snowball_state: SnowballStrategyState,
    entry_id: int | None,
    position_id: str | None,
    cycle_id: str | None,
    fill_price: Decimal | None,
    counter_tp_mode: str,
) -> None:
    if entry_id is None or not position_id:
        return
    for cycle in snowball_state.cycles:
        for layer in cycle.grid.layers:
            for slot in layer.slots:
                entry = slot.entry
                if entry is None or entry.entry_id != entry_id:
                    continue
                entry.position_id = str(position_id)
                SNOWBALL_PRICING.sync_entry_fill_price(
                    entry=entry,
                    layer=layer,
                    fill_price=fill_price,
                    counter_tp_mode=counter_tp_mode,
                )
                if cycle_id and cycle.cycle_id == entry_id and cycle.trade_cycle_id is None:
                    cycle.trade_cycle_id = str(cycle_id)


def _ensure_layer(
    *,
    cycle: SnowballCycle,
    layer_number: int,
    r_max: int,
    base_units: int,
    refill_up_to: int,
) -> Layer:
    layer = cycle.find_layer(layer_number)
    if layer is not None:
        return layer
    layer = Layer.create(layer_number, r_max, base_units, refill_up_to)
    cycle.add_layer(layer)
    return layer


def _cycle_has_present_entries(cycle: SnowballCycle) -> bool:
    return any(layer.has_present_entries() for layer in cycle.layers)


def _latest_position_id_for_entry(
    *,
    task: BacktestTask,
    execution_id: Any,
    entry: Entry,
) -> str | None:
    position = (
        Position.objects.filter(
            task_type=TaskType.BACKTEST.value,
            task_id=task.pk,
            execution_id=execution_id,
            layer_index=entry.layer_number,
            retracement_count=entry.retracement_count,
            is_open=True,
        )
        .order_by("-created_at")
        .first()
    )
    return str(position.id) if position else None


def _expected_prefix_slots(*, count: int, r_max: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    layer = 1
    retracement = 0
    while len(result) < count:
        result.append((layer, retracement))
        retracement += 1
        if retracement > r_max:
            layer += 1
            retracement = 0
    return result


def _tick_for_exit(
    *,
    instrument: str,
    timestamp,
    direction: Direction,
    exit_price: Decimal,
) -> Tick:
    if direction == Direction.LONG:
        return Tick.create(
            instrument=instrument,
            timestamp=timestamp,
            bid=exit_price,
            ask=exit_price,
            mid=exit_price,
        )
    return Tick.create(
        instrument=instrument,
        timestamp=timestamp,
        bid=exit_price,
        ask=exit_price,
        mid=exit_price,
    )


def _take_profit_from_pips(
    *,
    direction: Direction,
    entry_price: Decimal,
    pips: Decimal,
    pip_size: Decimal,
) -> Decimal:
    if direction == Direction.LONG:
        return entry_price + pips * pip_size
    return entry_price - pips * pip_size


def _resolve_pip_size(*, task: BacktestTask | None, pip_size: Decimal | None) -> Decimal:
    if pip_size:
        return Decimal(str(pip_size))
    if task is not None and getattr(task, "pip_size", None):
        return Decimal(str(task.pip_size))
    instrument = getattr(task, "instrument", "USD_JPY") if task is not None else "USD_JPY"
    return Decimal(str(pip_size_for_instrument(instrument)))


def _int_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _decimal_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _optional_decimal_value(value: Any) -> Decimal | None:
    return _decimal_value(value)
