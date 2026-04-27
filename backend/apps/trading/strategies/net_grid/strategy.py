from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from apps.trading.dataclasses import EventExecutionResult, StrategyResult, Tick
from apps.trading.enums import EventType, StrategyType
from apps.trading.events import ClosePositionEvent, GenericStrategyEvent, OpenPositionEvent
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.net_grid.models import DEFAULTS, NetGridConfig
from apps.trading.strategies.registry import register_strategy


@register_strategy(
    id="net_grid",
    schema="trading/schemas/net_grid.json",
    display_name="Net Grid Strategy",
    description=(
        "US-compatible grid strategy that manages a single net position and "
        "records a fill-based grid ledger for analysis."
    ),
)
class NetGridStrategy(Strategy):
    """Net-position grid strategy for FIFO/no-hedging accounts."""

    config: NetGridConfig

    @staticmethod
    def parse_config(strategy_config: Any) -> NetGridConfig:
        return NetGridConfig.from_dict(dict(getattr(strategy_config, "config_dict", {}) or {}))

    @classmethod
    def default_parameters(cls) -> dict[str, Any]:
        return dict(DEFAULTS)

    @classmethod
    def normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        data = {**DEFAULTS, **dict(parameters)}
        return NetGridConfig.from_dict(data).to_dict()

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.NET_GRID

    @classmethod
    def supports_stateful_broker_reconciliation(cls) -> bool:
        return True

    @classmethod
    def capabilities(cls) -> dict[str, Any]:
        return {
            "runtime": {"hedging": False},
            "visualization": {
                "kind": "net_grid",
                "cycle_statuses": False,
                "grid": False,
            },
            "events": {
                "close_reason_labels": {
                    "net_grid_take_profit": "Net Grid Take Profit",
                    "net_grid_risk_exit": "Net Grid Risk Exit",
                },
                "strategy_event_labels": {
                    "net_grid_signal": "Net Grid Signal",
                    "net_grid_open": "Open Net Grid Position",
                    "net_grid_add": "Add Net Grid Exposure",
                    "net_grid_take_profit": "Net Grid Take Profit",
                    "net_grid_risk_exit": "Net Grid Risk Exit",
                },
            },
            "resume": {"stateful_broker_reconciliation": True},
        }

    @classmethod
    def reconcile_broker_positions(
        cls,
        *,
        state: ExecutionState,
        open_positions: list[Any],
        report: Any,
        strategy_config: Any | None = None,
    ) -> None:
        from apps.trading.strategies.net_grid.reconciliation import (
            reconcile_broker_positions,
        )

        reconcile_broker_positions(
            state=state,
            open_positions=open_positions,
            report=report,
            strategy_config=strategy_config,
        )

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        strategy_state = _initial_state(state.strategy_state)
        strategy_state["last_bid"] = str(tick.bid)
        strategy_state["last_ask"] = str(tick.ask)
        strategy_state["last_mid"] = str(tick.mid)
        strategy_state["last_tick_at"] = tick.timestamp.isoformat()
        strategy_state["ticks_processed"] = int(state.ticks_processed or 0)
        _update_derived_levels(strategy_state, self.config, self.pip_size)

        events: list[Any] = []
        if strategy_state.get("pending_execution"):
            state.strategy_state = strategy_state
            return StrategyResult.from_state(state)

        signal = self._decide(tick=tick, state=state, strategy_state=strategy_state)
        strategy_state["latest_decision"] = signal
        if signal["action"] == "hold":
            events.append(_signal_event(tick, signal))
            state.strategy_state = strategy_state
            return StrategyResult(state=state, events=events)

        event = self._event_for_decision(tick=tick, strategy_state=strategy_state, decision=signal)
        strategy_state["pending_execution"] = {
            **signal,
            "event_type": str(event.event_type.value),
            "expected_price": str(
                getattr(event, "price", None) or getattr(event, "exit_price", None) or tick.mid
            ),
            "created_at": tick.timestamp.isoformat(),
        }
        events.append(_signal_event(tick, signal))
        events.append(event)
        state.strategy_state = strategy_state
        return StrategyResult(state=state, events=events)

    def _decide(
        self,
        *,
        tick: Tick,
        state: ExecutionState,
        strategy_state: dict[str, Any],
    ) -> dict[str, Any]:
        cfg = self.config
        ticks_processed = int(state.ticks_processed or 0)
        last_order_tick = strategy_state.get("last_order_tick")
        if (
            last_order_tick is not None
            and cfg.cooldown_ticks > 0
            and ticks_processed - int(last_order_tick) < cfg.cooldown_ticks
        ):
            return _hold("cooldown")

        spread_pips = (tick.ask - tick.bid) / self.pip_size if self.pip_size > 0 else Decimal("0")
        if cfg.max_spread_pips > 0 and spread_pips > cfg.max_spread_pips:
            return _hold("spread_guard", spread_pips=str(spread_pips))

        current_net = int(strategy_state.get("current_net_units", 0) or 0)
        avg = _decimal_or_none(strategy_state.get("average_entry_price"))
        if current_net == 0 or avg is None:
            units = min(cfg.base_units, cfg.max_net_units)
            signed_units = units if cfg.direction_mode == "long_only" else -units
            return {
                "action": "open",
                "reason": "initial_entry",
                "target_net_units": signed_units,
                "units_delta": signed_units,
                "step_after": 0,
            }

        side = _sign(current_net)
        exit_price = tick.bid if current_net > 0 else tick.ask
        adverse_pips = _adverse_pips(
            side=side, average_price=avg, exit_price=exit_price, pip_size=self.pip_size
        )
        unrealized_pnl = _quote_pnl(
            side=side,
            units=abs(current_net),
            average_price=avg,
            exit_price=exit_price,
        )
        if cfg.max_loss > 0 and unrealized_pnl <= -cfg.max_loss:
            return _close_decision(
                action="risk_exit",
                reason="max_loss",
                current_net=current_net,
                pnl=unrealized_pnl,
            )
        if cfg.max_adverse_pips > 0 and adverse_pips >= cfg.max_adverse_pips:
            return _close_decision(
                action="risk_exit",
                reason="max_adverse_pips",
                current_net=current_net,
                adverse_pips=adverse_pips,
            )
        if _take_profit_hit(
            side=side,
            average_price=avg,
            exit_price=exit_price,
            take_profit_distance=cfg.take_profit_pips * self.pip_size,
        ):
            return _close_decision(
                action="take_profit",
                reason="average_price_take_profit",
                current_net=current_net,
                pnl=unrealized_pnl,
            )

        step = int(strategy_state.get("step", 0) or 0)
        if step >= cfg.max_steps:
            return _hold("max_steps")

        last_grid_price = _decimal_or_none(strategy_state.get("last_grid_price")) or avg
        grid_distance = cfg.grid_interval_pips * self.pip_size
        add_hit = (
            tick.bid <= last_grid_price - grid_distance
            if current_net > 0
            else tick.ask >= last_grid_price + grid_distance
        )
        if not add_hit:
            return _hold("inside_grid")

        add_units = _step_units(cfg, step + 1)
        room = cfg.max_net_units - abs(current_net)
        add_units = min(add_units, max(0, room))
        if add_units < cfg.min_order_units:
            return _hold("min_order_or_max_net")
        signed_delta = add_units if current_net > 0 else -add_units
        return {
            "action": "add",
            "reason": "grid_interval_hit",
            "target_net_units": current_net + signed_delta,
            "units_delta": signed_delta,
            "step_after": step + 1,
            "adverse_pips": str(adverse_pips),
        }

    def _event_for_decision(
        self,
        *,
        tick: Tick,
        strategy_state: dict[str, Any],
        decision: dict[str, Any],
    ) -> OpenPositionEvent | ClosePositionEvent:
        action = str(decision["action"])
        delta = int(decision["units_delta"])
        entry_id = int(strategy_state.get("next_entry_id", 1) or 1)
        if action in {"open", "add"}:
            direction = "long" if delta > 0 else "short"
            event = OpenPositionEvent(
                event_type=EventType.OPEN_POSITION,
                timestamp=tick.timestamp,
                layer_number=1,
                direction=direction,
                price=tick.ask if delta > 0 else tick.bid,
                units=abs(delta),
                entry_time=tick.timestamp,
                entry_id=entry_id,
                strategy_event_type=f"net_grid_{action}",
                description=f"Net Grid {action}: delta={delta}, target={decision['target_net_units']}",
            )
            event.strategy_type = "net_grid"
            return event

        current_net = int(strategy_state.get("current_net_units", 0) or 0)
        direction = "long" if current_net > 0 else "short"
        reason = "net_grid_take_profit" if action == "take_profit" else "net_grid_risk_exit"
        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            timestamp=tick.timestamp,
            layer_number=1,
            direction=direction,
            exit_price=tick.bid if current_net > 0 else tick.ask,
            units=abs(delta),
            exit_time=tick.timestamp,
            position_id=strategy_state.get("open_position_id"),
            entry_id=strategy_state.get("open_entry_id"),
            strategy_event_type=reason,
            description=f"Net Grid {action}: close {abs(delta)} units ({decision['reason']})",
        )
        event.close_reason = reason
        event.strategy_type = "net_grid"
        return event

    def apply_event_execution_result(
        self,
        *,
        state: ExecutionState,
        execution_result: EventExecutionResult,
    ) -> None:
        strategy_state = _initial_state(state.strategy_state)
        pending = strategy_state.get("pending_execution")
        if not isinstance(pending, dict):
            state.strategy_state = strategy_state
            return

        fill_price = _execution_price(pending, execution_result)
        executed_units = execution_result.executed_units or abs(int(pending["units_delta"]))
        action = str(pending["action"])
        before_net = int(strategy_state.get("current_net_units", 0) or 0)
        before_avg = _decimal_or_none(strategy_state.get("average_entry_price"))
        signed_delta = int(pending["units_delta"])
        if action in {"open", "add"}:
            signed_delta = executed_units if signed_delta > 0 else -executed_units
            after_net = before_net + signed_delta
            after_avg = _average_after_increase(before_net, before_avg, signed_delta, fill_price)
            strategy_state["open_position_id"] = (
                execution_result.entry_binding.position_id
                if execution_result.entry_binding
                else strategy_state.get("open_position_id")
            )
            strategy_state["open_entry_id"] = (
                execution_result.entry_binding.entry_id
                if execution_result.entry_binding
                else strategy_state.get("open_entry_id")
            )
            strategy_state["next_entry_id"] = int(strategy_state.get("next_entry_id", 1) or 1) + 1
        else:
            close_units = min(executed_units, abs(before_net))
            signed_delta = -close_units if before_net > 0 else close_units
            after_net = before_net + signed_delta
            after_avg = before_avg if after_net != 0 else None
            if after_net == 0:
                strategy_state["open_position_id"] = None
                strategy_state["open_entry_id"] = None

        strategy_state["previous_net_units"] = before_net
        strategy_state["current_net_units"] = after_net
        strategy_state["target_net_units"] = after_net
        strategy_state["open_units"] = abs(after_net)
        strategy_state["open_direction"] = _direction_value(after_net)
        strategy_state["average_entry_price"] = str(after_avg) if after_avg is not None else None
        strategy_state["last_fill_price"] = str(fill_price)
        strategy_state["last_order_tick"] = int(strategy_state.get("ticks_processed", 0) or 0)
        strategy_state["step"] = int(pending.get("step_after", strategy_state.get("step", 0)) or 0)
        if action in {"open", "add"}:
            strategy_state["last_grid_price"] = str(fill_price)
            strategy_state.setdefault("anchor_price", str(fill_price))
        elif after_net == 0:
            strategy_state["step"] = 0
            strategy_state["anchor_price"] = None
            strategy_state["last_grid_price"] = None

        strategy_state["grid_ledger"] = _append_ledger(
            strategy_state.get("grid_ledger"),
            {
                "timestamp": pending.get("created_at"),
                "action": action,
                "reason": pending.get("reason"),
                "units_delta": signed_delta,
                "filled_price": str(fill_price),
                "net_units_before": before_net,
                "net_units_after": after_net,
                "avg_price_before": str(before_avg) if before_avg is not None else None,
                "avg_price_after": str(after_avg) if after_avg is not None else None,
                "realized_pnl": str(execution_result.realized_pnl_delta),
                "realized_pnl_quote": str(execution_result.realized_pnl_delta_quote),
                "source": "event_execution",
            },
        )
        strategy_state["latest_position_transition"] = strategy_state["grid_ledger"][-1]
        strategy_state["pending_execution"] = None
        _update_derived_levels(strategy_state, self.config, self.pip_size)
        state.strategy_state = strategy_state

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        state.strategy_state = _initial_state(state.strategy_state)
        state.strategy_state["started_at"] = datetime.now(UTC).isoformat()
        return super().on_start(state=state)


def _initial_state(raw: Any) -> dict[str, Any]:
    state = dict(raw or {}) if isinstance(raw, dict) else {}
    state.setdefault("current_net_units", 0)
    state.setdefault("target_net_units", 0)
    state.setdefault("open_units", 0)
    state.setdefault("open_direction", "")
    state.setdefault("average_entry_price", None)
    state.setdefault("anchor_price", None)
    state.setdefault("last_grid_price", None)
    state.setdefault("net_take_profit_price", None)
    state.setdefault("next_grid_price", None)
    state.setdefault("take_profit_remaining_pips", None)
    state.setdefault("step_usage", "0")
    state.setdefault("max_steps", None)
    state.setdefault("step", 0)
    state.setdefault("open_position_id", None)
    state.setdefault("open_entry_id", None)
    state.setdefault("next_entry_id", 1)
    state.setdefault("grid_ledger", [])
    state.setdefault("latest_decision", None)
    state.setdefault("latest_position_transition", None)
    state.setdefault("pending_execution", None)
    return state


def _signal_event(tick: Tick, decision: dict[str, Any]) -> GenericStrategyEvent:
    event = GenericStrategyEvent(
        event_type=EventType.STRATEGY_SIGNAL,
        timestamp=tick.timestamp,
        data={
            "kind": "net_grid_signal",
            "strategy_event_type": "net_grid_signal",
            "decision": decision,
        },
    )
    event.strategy_type = "net_grid"
    return event


def _hold(reason: str, **extra: Any) -> dict[str, Any]:
    return {"action": "hold", "reason": reason, "target_net_units": None, "units_delta": 0, **extra}


def _close_decision(
    *,
    action: str,
    reason: str,
    current_net: int,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "target_net_units": 0,
        "units_delta": -current_net,
        "step_after": 0,
        **{key: str(value) for key, value in extra.items()},
    }


def _sign(value: int) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _direction_value(net_units: int) -> str:
    if net_units > 0:
        return "long"
    if net_units < 0:
        return "short"
    return ""


def _update_derived_levels(
    strategy_state: dict[str, Any],
    config: NetGridConfig,
    pip_size: Decimal,
) -> None:
    strategy_state["max_steps"] = config.max_steps
    current_net = int(strategy_state.get("current_net_units", 0) or 0)
    avg = _decimal_or_none(strategy_state.get("average_entry_price"))
    if current_net == 0 or avg is None:
        strategy_state["net_take_profit_price"] = None
        strategy_state["next_grid_price"] = None
        strategy_state["take_profit_remaining_pips"] = None
        strategy_state["step_usage"] = "0"
        return
    distance = config.take_profit_pips * pip_size
    take_profit = avg + distance if current_net > 0 else avg - distance
    strategy_state["net_take_profit_price"] = str(take_profit)

    step = int(strategy_state.get("step", 0) or 0)
    strategy_state["step_usage"] = (
        str(Decimal(str(step)) / Decimal(str(config.max_steps))) if config.max_steps > 0 else "0"
    )
    last_grid_price = _decimal_or_none(strategy_state.get("last_grid_price")) or avg
    room = config.max_net_units - abs(current_net)
    if step < config.max_steps and room >= config.min_order_units:
        grid_distance = config.grid_interval_pips * pip_size
        next_grid = (
            last_grid_price - grid_distance if current_net > 0 else last_grid_price + grid_distance
        )
        strategy_state["next_grid_price"] = str(next_grid)
    else:
        strategy_state["next_grid_price"] = None

    exit_price = (
        _decimal_or_none(strategy_state.get("last_bid"))
        if current_net > 0
        else _decimal_or_none(strategy_state.get("last_ask"))
    )
    if exit_price is None or pip_size <= 0:
        strategy_state["take_profit_remaining_pips"] = None
        return
    remaining = (
        (take_profit - exit_price) / pip_size
        if current_net > 0
        else (exit_price - take_profit) / pip_size
    )
    strategy_state["take_profit_remaining_pips"] = str(remaining)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _adverse_pips(
    *,
    side: int,
    average_price: Decimal,
    exit_price: Decimal,
    pip_size: Decimal,
) -> Decimal:
    if pip_size <= 0:
        return Decimal("0")
    if side > 0:
        return max(Decimal("0"), (average_price - exit_price) / pip_size)
    return max(Decimal("0"), (exit_price - average_price) / pip_size)


def _quote_pnl(
    *,
    side: int,
    units: int,
    average_price: Decimal,
    exit_price: Decimal,
) -> Decimal:
    delta = exit_price - average_price
    if side < 0:
        delta = -delta
    return delta * Decimal(str(units))


def _take_profit_hit(
    *,
    side: int,
    average_price: Decimal,
    exit_price: Decimal,
    take_profit_distance: Decimal,
) -> bool:
    if side > 0:
        return exit_price >= average_price + take_profit_distance
    return exit_price <= average_price - take_profit_distance


def _step_units(config: NetGridConfig, step: int) -> int:
    if config.sizing_mode == "linear":
        return config.base_units + config.linear_increment_units * step
    if config.sizing_mode == "multiplier":
        units = Decimal(str(config.base_units)) * (config.multiplier**step)
        return int(units)
    return config.base_units


def _execution_price(
    pending: dict[str, Any],
    execution_result: EventExecutionResult,
) -> Decimal:
    if execution_result.entry_binding and execution_result.entry_binding.fill_price is not None:
        return Decimal(str(execution_result.entry_binding.fill_price))
    if execution_result.execution_price is not None:
        return Decimal(str(execution_result.execution_price))
    return Decimal(str(pending["expected_price"]))


def _average_after_increase(
    before_net: int,
    before_avg: Decimal | None,
    signed_delta: int,
    fill_price: Decimal,
) -> Decimal:
    if before_net == 0 or before_avg is None:
        return fill_price
    total_units = abs(before_net) + abs(signed_delta)
    return (
        before_avg * Decimal(str(abs(before_net))) + fill_price * Decimal(str(abs(signed_delta)))
    ) / Decimal(str(total_units))


def _append_ledger(raw_ledger: Any, entry: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = raw_ledger if isinstance(raw_ledger, list) else []
    return [*ledger, entry][-500:]
