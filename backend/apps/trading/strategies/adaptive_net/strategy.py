from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from apps.trading.dataclasses import EventExecutionResult, StrategyResult, Tick
from apps.trading.enums import EventType, StrategyType
from apps.trading.events import ClosePositionEvent, GenericStrategyEvent, OpenPositionEvent
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.adaptive_net.metrics import default_metrics
from apps.trading.strategies.adaptive_net.models import AdaptiveNetConfig, MetricContext
from apps.trading.strategies.adaptive_net.sizing import build_decision
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.registry import register_strategy


@register_strategy(
    id="adaptive_net",
    schema="trading/schemas/adaptive_net.json",
    display_name="Adaptive Net Strategy",
    description=(
        "US-compatible net-position strategy that evaluates pluggable metrics "
        "and rebalances toward a single target exposure."
    ),
)
class AdaptiveNetStrategy(Strategy):
    """Net-position strategy with separated metrics, aggregation, and sizing."""

    @staticmethod
    def parse_config(strategy_config: Any) -> AdaptiveNetConfig:
        return AdaptiveNetConfig.from_dict(dict(getattr(strategy_config, "config_dict", {}) or {}))

    @classmethod
    def default_parameters(cls) -> dict[str, Any]:
        return AdaptiveNetConfig().to_dict()

    @classmethod
    def normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        defaults = cls.default_parameters()
        normalized = {**defaults, **dict(parameters)}
        integer_fields = {
            "base_units",
            "max_net_units",
            "min_order_units",
            "lookback_ticks",
            "rebalance_interval_ticks",
        }
        for key in integer_fields:
            normalized[key] = int(normalized[key])
        return normalized

    @classmethod
    def capabilities(cls) -> dict[str, Any]:
        return {
            "runtime": {"hedging": False},
            "visualization": {
                "kind": "adaptive_net",
                "cycle_statuses": False,
                "grid": False,
            },
            "events": {
                "close_reason_labels": {
                    "adaptive_net_reduce": "Adaptive Net Reduce",
                    "adaptive_net_reverse": "Adaptive Net Reverse",
                },
                "strategy_event_labels": {
                    "adaptive_net_decision": "Adaptive Net Decision",
                    "adaptive_net_increase": "Increase Net Exposure",
                    "adaptive_net_reduce": "Reduce Net Exposure",
                    "adaptive_net_reverse": "Reverse Net Exposure",
                },
            },
            "resume": {"stateful_broker_reconciliation": False},
        }

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.ADAPTIVE_NET

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        state.last_tick_price = tick.mid
        state.last_tick_bid = tick.bid
        state.last_tick_ask = tick.ask
        state.last_tick_timestamp = tick.timestamp

        strategy_state = _initial_state(state.strategy_state)
        prices = [Decimal(str(price)) for price in strategy_state.get("price_history", [])]
        prices.append(tick.mid)
        prices = prices[-self.config.lookback_ticks :]
        strategy_state["price_history"] = [str(price) for price in prices]
        strategy_state["last_price"] = str(tick.mid)
        strategy_state["last_spread_pips"] = str(
            (tick.ask - tick.bid) / self.pip_size if self.pip_size > 0 else Decimal("0")
        )

        state.strategy_state = strategy_state
        if len(prices) < min(20, self.config.lookback_ticks):
            return StrategyResult.from_state(state)

        ticks_processed = int(state.ticks_processed or 0)
        last_rebalance_tick = int(strategy_state.get("last_rebalance_tick", -(10**9)))
        if ticks_processed - last_rebalance_tick < self.config.rebalance_interval_ticks:
            return StrategyResult.from_state(state)

        current_net_units = int(strategy_state.get("current_net_units", 0) or 0)
        context = MetricContext(
            prices=tuple(prices),
            bid=tick.bid,
            ask=tick.ask,
            mid=tick.mid,
            pip_size=self.pip_size,
            current_net_units=current_net_units,
            max_net_units=self.config.max_net_units,
            config=self.config,
        )
        metric_signals = [
            metric.evaluate(context)
            for metric in default_metrics(include_timesfm=self.config.timesfm_weight > 0)
        ]
        decision = build_decision(
            config=self.config,
            current_net_units=current_net_units,
            metric_signals=metric_signals,
        )

        strategy_state["last_rebalance_tick"] = ticks_processed
        strategy_state["latest_decision"] = decision.to_dict()
        strategy_state["metric_signals"] = [signal.to_dict() for signal in metric_signals]
        strategy_state["target_net_units"] = decision.target_net_units

        signal_event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_SIGNAL,
            timestamp=tick.timestamp,
            data={
                "kind": "adaptive_net_decision",
                "strategy_event_type": "adaptive_net_decision",
                "decision": decision.to_dict(),
            },
        )
        signal_event.strategy_type = "adaptive_net"
        events = [signal_event]
        events.extend(self._build_rebalance_events(tick=tick, strategy_state=strategy_state))
        state.strategy_state = strategy_state
        return StrategyResult(state=state, events=events)

    def _build_rebalance_events(
        self,
        *,
        tick: Tick,
        strategy_state: dict[str, Any],
    ) -> list[Any]:
        current_net = int(strategy_state.get("current_net_units", 0) or 0)
        target_net = int(strategy_state.get("target_net_units", current_net) or 0)
        delta = target_net - current_net
        if delta == 0:
            return []

        events: list[Any] = []
        next_entry_id = int(strategy_state.get("next_entry_id", 1) or 1)

        if current_net != 0 and _sign(current_net) != _sign(target_net) and target_net != 0:
            close_units = abs(current_net)
            events.append(
                self._close_event(tick, strategy_state, close_units, "adaptive_net_reverse")
            )
            open_units = abs(target_net)
            events.append(self._open_event(tick, next_entry_id, open_units, target_net))
            strategy_state["next_entry_id"] = next_entry_id + 1
        elif current_net != 0 and abs(target_net) < abs(current_net):
            events.append(
                self._close_event(
                    tick,
                    strategy_state,
                    abs(current_net) - abs(target_net),
                    "adaptive_net_reduce",
                )
            )
        elif target_net != 0:
            events.append(self._open_event(tick, next_entry_id, abs(delta), target_net))
            strategy_state["next_entry_id"] = next_entry_id + 1

        strategy_state["previous_net_units"] = current_net
        strategy_state["current_net_units"] = target_net
        strategy_state["open_direction"] = _direction_value(target_net)
        strategy_state["open_units"] = abs(target_net)
        if target_net == 0:
            strategy_state["open_position_id"] = None
            strategy_state["open_entry_id"] = None
        return events

    def _open_event(
        self,
        tick: Tick,
        entry_id: int,
        units: int,
        target_net_units: int,
    ) -> OpenPositionEvent:
        direction = "long" if target_net_units > 0 else "short"
        event = OpenPositionEvent(
            event_type=EventType.OPEN_POSITION,
            timestamp=tick.timestamp,
            layer_number=1,
            direction=direction,
            price=tick.ask if target_net_units > 0 else tick.bid,
            units=units,
            entry_time=tick.timestamp,
            entry_id=entry_id,
            strategy_event_type="adaptive_net_increase",
            description=f"Adaptive Net rebalance to {target_net_units} net units",
        )
        event.strategy_type = "adaptive_net"
        return event

    def _close_event(
        self,
        tick: Tick,
        strategy_state: dict[str, Any],
        units: int,
        reason: str,
    ) -> ClosePositionEvent:
        current_net = int(strategy_state.get("current_net_units", 0) or 0)
        direction = "long" if current_net > 0 else "short"
        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            timestamp=tick.timestamp,
            layer_number=1,
            direction=direction,
            exit_price=tick.bid if current_net > 0 else tick.ask,
            units=units,
            exit_time=tick.timestamp,
            position_id=strategy_state.get("open_position_id"),
            entry_id=strategy_state.get("open_entry_id"),
            strategy_event_type=reason,
            description=f"Adaptive Net rebalance {reason} by {units} units",
        )
        event.close_reason = reason
        event.strategy_type = "adaptive_net"
        return event

    def apply_event_execution_result(
        self,
        *,
        state: ExecutionState,
        execution_result: EventExecutionResult,
    ) -> None:
        strategy_state = _initial_state(state.strategy_state)
        if execution_result.entry_binding:
            strategy_state["open_position_id"] = execution_result.entry_binding.position_id
            strategy_state["open_entry_id"] = execution_result.entry_binding.entry_id
            strategy_state["last_fill_price"] = (
                str(execution_result.entry_binding.fill_price)
                if execution_result.entry_binding.fill_price is not None
                else None
            )
        if not strategy_state.get("open_units"):
            strategy_state["open_position_id"] = None
            strategy_state["open_entry_id"] = None
        state.strategy_state = strategy_state

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        state.strategy_state = _initial_state(state.strategy_state)
        state.strategy_state["started_at"] = datetime.now(UTC).isoformat()
        return super().on_start(state=state)


def _initial_state(raw: Any) -> dict[str, Any]:
    state = dict(raw or {}) if isinstance(raw, dict) else {}
    state.setdefault("price_history", [])
    state.setdefault("current_net_units", 0)
    state.setdefault("target_net_units", 0)
    state.setdefault("open_units", 0)
    state.setdefault("open_direction", "")
    state.setdefault("open_position_id", None)
    state.setdefault("open_entry_id", None)
    state.setdefault("next_entry_id", 1)
    state.setdefault("metric_signals", [])
    state.setdefault("latest_decision", None)
    return state


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _direction_value(net_units: int) -> str:
    if net_units > 0:
        return "long"
    if net_units < 0:
        return "short"
    return ""
