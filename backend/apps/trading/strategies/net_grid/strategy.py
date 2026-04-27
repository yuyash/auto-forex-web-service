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


AUTO_DIRECTION_LOOKBACK_TICKS = 5
AUTO_DIRECTION_MIN_SAMPLES = 3


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
        previous_mid = _decimal_or_none(strategy_state.get("last_mid"))
        strategy_state["last_bid"] = str(tick.bid)
        strategy_state["last_ask"] = str(tick.ask)
        strategy_state["last_mid"] = str(tick.mid)
        strategy_state["last_tick_at"] = tick.timestamp.isoformat()
        strategy_state["ticks_processed"] = int(state.ticks_processed or 0)
        _append_auto_direction_sample(strategy_state, tick.mid)
        _update_volatility_metrics(
            strategy_state=strategy_state,
            previous_mid=previous_mid,
            current_mid=tick.mid,
            config=self.config,
            pip_size=self.pip_size,
        )
        _update_trend_metrics(
            strategy_state=strategy_state,
            current_mid=tick.mid,
            config=self.config,
            pip_size=self.pip_size,
        )
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
        last_order_at = _datetime_or_none(strategy_state.get("last_order_at"))
        if (
            last_order_at is not None
            and cfg.cooldown_seconds > 0
            and (tick.timestamp - last_order_at).total_seconds() < cfg.cooldown_seconds
        ):
            return _hold("cooldown_seconds")

        spread_pips = (tick.ask - tick.bid) / self.pip_size if self.pip_size > 0 else Decimal("0")
        if cfg.max_spread_pips > 0 and spread_pips > cfg.max_spread_pips:
            return _hold("spread_guard", spread_pips=str(spread_pips))
        regime_hold = _regime_hold_reason(cfg, strategy_state, side=0)
        if regime_hold:
            return _hold(regime_hold)

        current_net = int(strategy_state.get("current_net_units", 0) or 0)
        avg = _decimal_or_none(strategy_state.get("average_entry_price"))
        if current_net == 0 or avg is None:
            units = min(cfg.base_units, cfg.max_net_units)
            direction = _initial_entry_direction(
                config=cfg,
                strategy_state=strategy_state,
                pip_size=self.pip_size,
            )
            if direction is None:
                return _hold(
                    "auto_direction_warming_up",
                    auto_direction_samples=str(
                        len(_auto_direction_samples(strategy_state.get("auto_direction_window")))
                    ),
                )
            if direction == "flat":
                return _hold("auto_direction_neutral")
            signed_units = units if direction == "long" else -units
            return {
                "action": "open",
                "reason": (
                    "initial_entry_auto_trend" if cfg.direction_mode == "auto" else "initial_entry"
                ),
                "target_net_units": signed_units,
                "units_delta": signed_units,
                "step_after": 0,
                "entry_direction_mode": cfg.direction_mode,
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
        step = int(strategy_state.get("step", 0) or 0)
        if (
            cfg.max_adverse_after_full_grid_pips > 0
            and step >= cfg.max_steps
            and adverse_pips >= cfg.max_adverse_after_full_grid_pips
        ):
            return _close_decision(
                action="risk_exit",
                reason="max_adverse_after_full_grid_pips",
                current_net=current_net,
                adverse_pips=adverse_pips,
            )
        full_grid_tick = strategy_state.get("full_grid_reached_tick")
        if cfg.max_full_grid_ticks > 0 and step >= cfg.max_steps and full_grid_tick is not None:
            elapsed_full_grid_ticks = ticks_processed - int(full_grid_tick)
            if elapsed_full_grid_ticks >= cfg.max_full_grid_ticks:
                return _close_decision(
                    action="risk_exit",
                    reason="max_full_grid_ticks",
                    current_net=current_net,
                    elapsed_full_grid_ticks=elapsed_full_grid_ticks,
                )
        if _take_profit_hit(
            side=side,
            average_price=avg,
            exit_price=exit_price,
            take_profit_distance=_effective_take_profit_pips(strategy_state, cfg) * self.pip_size,
        ):
            return _close_decision(
                action="take_profit",
                reason="average_price_take_profit",
                current_net=current_net,
                pnl=unrealized_pnl,
            )

        if step >= cfg.max_steps:
            return _hold("max_steps")
        regime_hold = _regime_hold_reason(cfg, strategy_state, side=side)
        if regime_hold:
            return _hold(regime_hold)

        last_grid_price = _decimal_or_none(strategy_state.get("last_grid_price")) or avg
        grid_distance = _effective_grid_interval_pips(strategy_state, cfg) * self.pip_size
        add_hit = (
            tick.bid <= last_grid_price - grid_distance
            if current_net > 0
            else tick.ask >= last_grid_price + grid_distance
        )
        if not add_hit:
            return _hold("inside_grid")

        add_units = _step_units(cfg, step + 1)
        add_units = _apply_volatility_size_multiplier(add_units, strategy_state, cfg)
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
        strategy_state["last_order_at"] = pending.get("created_at")
        strategy_state["step"] = int(pending.get("step_after", strategy_state.get("step", 0)) or 0)
        if strategy_state["step"] >= self.config.max_steps:
            if strategy_state.get("full_grid_reached_tick") is None:
                strategy_state["full_grid_reached_tick"] = strategy_state["last_order_tick"]
        else:
            strategy_state["full_grid_reached_tick"] = None
        if action in {"open", "add"}:
            strategy_state["last_grid_price"] = str(fill_price)
            strategy_state.setdefault("anchor_price", str(fill_price))
        elif after_net == 0:
            strategy_state["step"] = 0
            strategy_state["anchor_price"] = None
            strategy_state["last_grid_price"] = None
            strategy_state["full_grid_reached_tick"] = None

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
    state.setdefault("current_atr_pips", None)
    state.setdefault("effective_grid_interval_pips", None)
    state.setdefault("effective_take_profit_pips", None)
    state.setdefault("effective_order_size_multiplier", "1")
    state.setdefault("fast_ema_price", None)
    state.setdefault("slow_ema_price", None)
    state.setdefault("trend_score_pips", None)
    state.setdefault("regime_status", "ok")
    state.setdefault("risk_exit_price", None)
    state.setdefault("current_adverse_pips", None)
    state.setdefault("current_unrealized_pnl", None)
    state.setdefault("next_order_units", None)
    state.setdefault("full_grid_reached_tick", None)
    state.setdefault("atr_true_ranges_pips", [])
    state.setdefault("step_usage", "0")
    state.setdefault("max_steps", None)
    state.setdefault("step", 0)
    state.setdefault("open_position_id", None)
    state.setdefault("open_entry_id", None)
    state.setdefault("next_entry_id", 1)
    state.setdefault("grid_ledger", [])
    state.setdefault("auto_direction_window", [])
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


def _append_auto_direction_sample(strategy_state: dict[str, Any], mid: Decimal) -> None:
    samples = _auto_direction_samples(strategy_state.get("auto_direction_window"))
    samples.append(str(mid))
    strategy_state["auto_direction_window"] = samples[-AUTO_DIRECTION_LOOKBACK_TICKS:]


def _auto_direction_samples(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(value) for value in raw if value not in (None, "")]


def _initial_entry_direction(
    *,
    config: NetGridConfig,
    strategy_state: dict[str, Any],
    pip_size: Decimal,
) -> str | None:
    if config.direction_mode == "long_only":
        return "long"
    if config.direction_mode == "short_only":
        return "short"

    samples = _auto_direction_samples(strategy_state.get("auto_direction_window"))
    if len(samples) < AUTO_DIRECTION_MIN_SAMPLES:
        return None
    trend_score = _decimal_or_none(strategy_state.get("trend_score_pips"))
    if trend_score is not None:
        if trend_score >= config.auto_min_trend_pips:
            return "long"
        if trend_score <= -config.auto_min_trend_pips:
            return "short"
    first = Decimal(samples[0])
    last = Decimal(samples[-1])
    if pip_size <= 0:
        return "flat"
    raw_trend_pips = (last - first) / pip_size
    if raw_trend_pips >= config.auto_min_trend_pips:
        return "long"
    if raw_trend_pips <= -config.auto_min_trend_pips:
        return "short"
    return "flat"


def _update_volatility_metrics(
    *,
    strategy_state: dict[str, Any],
    previous_mid: Decimal | None,
    current_mid: Decimal,
    config: NetGridConfig,
    pip_size: Decimal,
) -> None:
    samples = _atr_samples(strategy_state.get("atr_true_ranges_pips"))
    if previous_mid is not None and pip_size > 0:
        true_range_pips = abs(current_mid - previous_mid) / pip_size
        samples.append(str(true_range_pips))
    period = max(2, config.atr_period_ticks)
    samples = samples[-period:]
    strategy_state["atr_true_ranges_pips"] = samples
    atr = _average_decimal(samples)
    strategy_state["current_atr_pips"] = str(atr) if atr is not None else None
    strategy_state["effective_grid_interval_pips"] = str(
        _effective_grid_interval_pips(strategy_state, config)
    )
    strategy_state["effective_take_profit_pips"] = str(
        _effective_take_profit_pips(strategy_state, config)
    )


def _atr_samples(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(value) for value in raw if value not in (None, "")]


def _average_decimal(raw_values: list[str]) -> Decimal | None:
    values = [Decimal(value) for value in raw_values if value not in (None, "")]
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(str(len(values)))


def _update_trend_metrics(
    *,
    strategy_state: dict[str, Any],
    current_mid: Decimal,
    config: NetGridConfig,
    pip_size: Decimal,
) -> None:
    fast = _update_ema(
        previous=_decimal_or_none(strategy_state.get("fast_ema_price")),
        value=current_mid,
        period=max(2, config.auto_fast_ema_ticks),
    )
    slow = _update_ema(
        previous=_decimal_or_none(strategy_state.get("slow_ema_price")),
        value=current_mid,
        period=max(config.auto_fast_ema_ticks + 1, config.auto_slow_ema_ticks),
    )
    strategy_state["fast_ema_price"] = str(fast)
    strategy_state["slow_ema_price"] = str(slow)
    trend_score = (fast - slow) / pip_size if pip_size > 0 else Decimal("0")
    strategy_state["trend_score_pips"] = str(trend_score)


def _update_ema(*, previous: Decimal | None, value: Decimal, period: int) -> Decimal:
    if previous is None:
        return value
    alpha = Decimal("2") / Decimal(str(period + 1))
    return previous + alpha * (value - previous)


def _effective_grid_interval_pips(
    strategy_state: dict[str, Any],
    config: NetGridConfig,
) -> Decimal:
    return _effective_adaptive_pips(
        mode=config.grid_spacing_mode,
        fixed_pips=config.grid_interval_pips,
        atr_pips=_decimal_or_none(strategy_state.get("current_atr_pips")),
        multiplier=config.grid_atr_multiplier,
        minimum=config.grid_min_interval_pips,
        maximum=config.grid_max_interval_pips,
    )


def _effective_take_profit_pips(
    strategy_state: dict[str, Any],
    config: NetGridConfig,
) -> Decimal:
    return _effective_adaptive_pips(
        mode=config.take_profit_mode,
        fixed_pips=config.take_profit_pips,
        atr_pips=_decimal_or_none(strategy_state.get("current_atr_pips")),
        multiplier=config.take_profit_atr_multiplier,
        minimum=config.take_profit_min_pips,
        maximum=config.take_profit_max_pips,
    )


def _effective_adaptive_pips(
    *,
    mode: str,
    fixed_pips: Decimal,
    atr_pips: Decimal | None,
    multiplier: Decimal,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    if mode != "atr" or atr_pips is None or atr_pips <= 0:
        return fixed_pips
    lower = max(Decimal("0.1"), minimum)
    upper = max(lower, maximum)
    return min(max(atr_pips * multiplier, lower), upper)


def _regime_hold_reason(
    config: NetGridConfig,
    strategy_state: dict[str, Any],
    *,
    side: int,
) -> str | None:
    if not config.regime_filter_enabled:
        strategy_state["regime_status"] = "ok"
        return None
    atr = _decimal_or_none(strategy_state.get("current_atr_pips"))
    if config.regime_max_atr_pips > 0 and atr is not None and atr > config.regime_max_atr_pips:
        strategy_state["regime_status"] = "blocked_high_volatility"
        return "regime_high_volatility"
    trend_score = _decimal_or_none(strategy_state.get("trend_score_pips"))
    if config.regime_trend_guard_pips > 0 and trend_score is not None and side != 0:
        if side > 0 and trend_score <= -config.regime_trend_guard_pips:
            strategy_state["regime_status"] = "blocked_counter_trend"
            return "regime_counter_trend"
        if side < 0 and trend_score >= config.regime_trend_guard_pips:
            strategy_state["regime_status"] = "blocked_counter_trend"
            return "regime_counter_trend"
    strategy_state["regime_status"] = "ok"
    return None


def _apply_volatility_size_multiplier(
    units: int,
    strategy_state: dict[str, Any],
    config: NetGridConfig,
) -> int:
    multiplier = _effective_order_size_multiplier(strategy_state, config)
    return max(1, int(Decimal(str(units)) * multiplier))


def _effective_order_size_multiplier(
    strategy_state: dict[str, Any],
    config: NetGridConfig,
) -> Decimal:
    if config.volatility_size_mode != "atr":
        return Decimal("1")
    atr = _decimal_or_none(strategy_state.get("current_atr_pips"))
    threshold = config.volatility_size_atr_threshold_pips
    if atr is None or atr <= 0 or threshold <= 0 or atr <= threshold:
        return Decimal("1")
    floor = min(max(config.volatility_size_min_multiplier, Decimal("0.01")), Decimal("1"))
    return max(floor, threshold / atr)


def _update_derived_levels(
    strategy_state: dict[str, Any],
    config: NetGridConfig,
    pip_size: Decimal,
) -> None:
    strategy_state["max_steps"] = config.max_steps
    strategy_state["max_net_units"] = config.max_net_units
    strategy_state["max_adverse_pips"] = str(config.max_adverse_pips)
    strategy_state["max_loss"] = str(config.max_loss)
    strategy_state["effective_order_size_multiplier"] = str(
        _effective_order_size_multiplier(strategy_state, config)
    )
    current_net = int(strategy_state.get("current_net_units", 0) or 0)
    avg = _decimal_or_none(strategy_state.get("average_entry_price"))
    if current_net == 0 or avg is None:
        strategy_state["net_take_profit_price"] = None
        strategy_state["next_grid_price"] = None
        strategy_state["take_profit_remaining_pips"] = None
        strategy_state["risk_exit_price"] = None
        strategy_state["current_adverse_pips"] = None
        strategy_state["current_unrealized_pnl"] = None
        strategy_state["next_order_units"] = None
        strategy_state["step_usage"] = "0"
        return
    distance = _effective_take_profit_pips(strategy_state, config) * pip_size
    take_profit = avg + distance if current_net > 0 else avg - distance
    strategy_state["net_take_profit_price"] = str(take_profit)
    if config.max_adverse_pips > 0:
        risk_exit = (
            avg - config.max_adverse_pips * pip_size
            if current_net > 0
            else avg + config.max_adverse_pips * pip_size
        )
        strategy_state["risk_exit_price"] = str(risk_exit)
    else:
        strategy_state["risk_exit_price"] = None

    step = int(strategy_state.get("step", 0) or 0)
    strategy_state["step_usage"] = (
        str(Decimal(str(step)) / Decimal(str(config.max_steps))) if config.max_steps > 0 else "0"
    )
    last_grid_price = _decimal_or_none(strategy_state.get("last_grid_price")) or avg
    room = config.max_net_units - abs(current_net)
    if step < config.max_steps and room >= config.min_order_units:
        grid_distance = _effective_grid_interval_pips(strategy_state, config) * pip_size
        next_grid = (
            last_grid_price - grid_distance if current_net > 0 else last_grid_price + grid_distance
        )
        strategy_state["next_grid_price"] = str(next_grid)
        strategy_state["next_order_units"] = min(
            _apply_volatility_size_multiplier(
                _step_units(config, step + 1), strategy_state, config
            ),
            max(0, room),
        )
    else:
        strategy_state["next_grid_price"] = None
        strategy_state["next_order_units"] = None

    exit_price = (
        _decimal_or_none(strategy_state.get("last_bid"))
        if current_net > 0
        else _decimal_or_none(strategy_state.get("last_ask"))
    )
    if exit_price is None or pip_size <= 0:
        strategy_state["take_profit_remaining_pips"] = None
        strategy_state["current_adverse_pips"] = None
        strategy_state["current_unrealized_pnl"] = None
        return
    side = _sign(current_net)
    strategy_state["current_adverse_pips"] = str(
        _adverse_pips(
            side=side,
            average_price=avg,
            exit_price=exit_price,
            pip_size=pip_size,
        )
    )
    strategy_state["current_unrealized_pnl"] = str(
        _quote_pnl(
            side=side,
            units=abs(current_net),
            average_price=avg,
            exit_price=exit_price,
        )
    )
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


def _datetime_or_none(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


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
