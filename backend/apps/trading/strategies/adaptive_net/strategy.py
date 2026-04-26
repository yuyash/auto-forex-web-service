from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from apps.trading.dataclasses import EventExecutionResult, StrategyResult, Tick
from apps.trading.enums import EventType, StrategyType
from apps.trading.events import ClosePositionEvent, GenericStrategyEvent, OpenPositionEvent
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.adaptive_net.metrics import enabled_metrics
from apps.trading.strategies.adaptive_net.models import (
    AdaptiveNetConfig,
    MetricContext,
    MetricSignal,
)
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
            "lookback_window_seconds",
            "rebalance_interval_seconds",
            "metric_publish_interval_ticks",
            "metric_publish_interval_seconds",
            "decision_interval_metric_publishes",
            "decision_interval_seconds",
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
        price_points = _price_points(strategy_state)
        price_points.append(
            {
                "timestamp": tick.timestamp.isoformat(),
                "price": str(tick.mid),
            }
        )
        price_points = _trim_price_points(
            price_points,
            current_timestamp=tick.timestamp,
            lookback_ticks=self.config.lookback_ticks,
            lookback_window_seconds=self.config.lookback_window_seconds,
        )
        prices = [Decimal(str(point["price"])) for point in price_points]
        window_started_at = price_points[0]["timestamp"] if price_points else None
        window_seconds = _window_seconds(price_points)
        strategy_state["price_points"] = price_points
        strategy_state["price_history"] = [str(price) for price in prices]
        strategy_state["lookback_points"] = len(price_points)
        strategy_state["window_started_at"] = window_started_at
        strategy_state["window_seconds"] = window_seconds
        strategy_state["last_price"] = str(tick.mid)
        strategy_state["last_spread_pips"] = str(
            (tick.ask - tick.bid) / self.pip_size if self.pip_size > 0 else Decimal("0")
        )

        state.strategy_state = strategy_state
        if len(prices) < min(20, self.config.lookback_ticks):
            return StrategyResult.from_state(state)

        ticks_processed = int(state.ticks_processed or 0)
        current_net_units = int(strategy_state.get("current_net_units", 0) or 0)
        metric_signals = self._published_metric_signals(
            tick=tick,
            strategy_state=strategy_state,
            prices=prices,
            current_net_units=current_net_units,
            ticks_processed=ticks_processed,
        )
        state.strategy_state = strategy_state

        if not _should_make_decision(
            strategy_state=strategy_state,
            current_timestamp=tick.timestamp,
            config=self.config,
        ):
            return StrategyResult.from_state(state)

        decision = build_decision(
            config=self.config,
            current_net_units=current_net_units,
            metric_signals=metric_signals,
        )

        strategy_state["last_rebalance_tick"] = ticks_processed
        strategy_state["last_rebalance_at"] = tick.timestamp.isoformat()
        strategy_state["rebalance_tick_delta"] = None
        strategy_state["rebalance_elapsed_seconds"] = None
        strategy_state["latest_decision"] = decision.to_dict()
        strategy_state["metric_signals"] = [signal.to_dict() for signal in metric_signals]
        strategy_state["target_net_units"] = decision.target_net_units
        strategy_state["last_decision_metric_publish_count"] = int(
            strategy_state.get("metric_publish_count", 0) or 0
        )
        strategy_state["last_decision_at"] = tick.timestamp.isoformat()
        position_transition = _position_transition_snapshot(
            tick=tick,
            current_net_units=current_net_units,
            decision=decision.to_dict(),
            strategy_state=strategy_state,
        )
        strategy_state["decision_history"] = _append_decision_history(
            strategy_state.get("decision_history"),
            timestamp=tick.timestamp,
            current_net_units=current_net_units,
            decision=decision.to_dict(),
            metric_signals=strategy_state["metric_signals"],
            position_transition=position_transition,
        )
        metrics = (
            dict(strategy_state.get("metrics", {}))
            if isinstance(strategy_state.get("metrics"), dict)
            else {}
        )
        metrics.update(
            _decision_snapshot(
                tick=tick,
                decision=decision.to_dict(),
                position_transition=position_transition,
                strategy_state=strategy_state,
            )
        )
        strategy_state["metrics"] = metrics
        strategy_state["pending_position_transition"] = position_transition

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

    def _published_metric_signals(
        self,
        *,
        tick: Tick,
        strategy_state: dict[str, Any],
        prices: list[Decimal],
        current_net_units: int,
        ticks_processed: int,
    ) -> list[MetricSignal]:
        last_publish_tick = int(strategy_state.get("last_metric_publish_tick", -(10**9)))
        tick_delta = ticks_processed - last_publish_tick
        elapsed_seconds = _elapsed_since(
            strategy_state.get("last_metric_publish_at"), tick.timestamp
        )
        published = _metric_signals_from_state(strategy_state.get("published_metric_signals"))
        if published and not _should_rebalance(
            tick_delta=tick_delta,
            elapsed_seconds=elapsed_seconds,
            interval_ticks=self.config.metric_publish_interval_ticks,
            interval_seconds=self.config.metric_publish_interval_seconds,
        ):
            return published

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
        signals = [metric.evaluate(context) for metric in enabled_metrics(self.config)]
        signal_dicts = [signal.to_dict() for signal in signals]
        strategy_state["last_metric_publish_tick"] = ticks_processed
        strategy_state["last_metric_publish_at"] = tick.timestamp.isoformat()
        strategy_state["metric_publish_tick_delta"] = tick_delta
        strategy_state["metric_publish_elapsed_seconds"] = elapsed_seconds
        strategy_state["published_metric_signals"] = signal_dicts
        strategy_state["published_metric_names"] = [signal.name for signal in signals]
        strategy_state["metric_publish_count"] = (
            int(strategy_state.get("metric_publish_count", 0) or 0) + 1
        )

        metrics = (
            dict(strategy_state.get("metrics", {}))
            if isinstance(strategy_state.get("metrics"), dict)
            else {}
        )
        metrics.update(_metric_snapshot(tick=tick, signals=signals, strategy_state=strategy_state))
        strategy_state["metrics"] = metrics
        return signals

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
        transition = strategy_state.get("pending_position_transition")
        if isinstance(transition, dict):
            strategy_state["open_average_entry_price"] = transition.get(
                "position_after_avg_entry_price"
            )
            strategy_state["latest_position_transition"] = transition
            strategy_state["pending_position_transition"] = None
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
            if execution_result.entry_binding.fill_price is not None:
                strategy_state.setdefault(
                    "open_average_entry_price",
                    str(execution_result.entry_binding.fill_price),
                )
        if not strategy_state.get("open_units"):
            strategy_state["open_position_id"] = None
            strategy_state["open_entry_id"] = None
            strategy_state["open_average_entry_price"] = None
        state.strategy_state = strategy_state

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        state.strategy_state = _initial_state(state.strategy_state)
        state.strategy_state["started_at"] = datetime.now(UTC).isoformat()
        return super().on_start(state=state)


def _initial_state(raw: Any) -> dict[str, Any]:
    state = dict(raw or {}) if isinstance(raw, dict) else {}
    state.setdefault("price_history", [])
    state.setdefault("price_points", [])
    state.setdefault("current_net_units", 0)
    state.setdefault("target_net_units", 0)
    state.setdefault("open_units", 0)
    state.setdefault("open_direction", "")
    state.setdefault("open_average_entry_price", None)
    state.setdefault("open_position_id", None)
    state.setdefault("open_entry_id", None)
    state.setdefault("next_entry_id", 1)
    state.setdefault("metric_signals", [])
    state.setdefault("published_metric_signals", [])
    state.setdefault("published_metric_names", [])
    state.setdefault("metric_publish_count", 0)
    state.setdefault("latest_decision", None)
    state.setdefault("latest_position_transition", None)
    state.setdefault("decision_history", [])
    return state


def _append_decision_history(
    raw_history: Any,
    *,
    timestamp: datetime,
    current_net_units: int,
    decision: dict[str, Any],
    metric_signals: list[dict[str, Any]],
    position_transition: dict[str, Any],
) -> list[dict[str, Any]]:
    history = raw_history if isinstance(raw_history, list) else []
    target_net_units = int(decision.get("target_net_units") or current_net_units)
    order_units = int(decision.get("order_units") or target_net_units - current_net_units)
    point = {
        "timestamp": timestamp.isoformat(),
        "current_net_units": current_net_units,
        "target_net_units": target_net_units,
        "order_units": order_units,
        "action": _decision_action(current_net_units, target_net_units, order_units),
        "edge": str(decision.get("edge", "0")),
        "confidence": str(decision.get("confidence", "0")),
        "probability_long": str(decision.get("probability_long", "0.5")),
        "probability_short": str(decision.get("probability_short", "0.5")),
        "risk_multiplier": str(decision.get("risk_multiplier", "1")),
        "position_transition": position_transition,
        "metric_signals": metric_signals,
    }
    return [*history, point][-200:]


def _decision_action(current_net: int, target_net: int, order_units: int) -> str:
    if order_units == 0:
        return "hold"
    if current_net != 0 and target_net != 0 and _sign(current_net) != _sign(target_net):
        return "reverse"
    if abs(target_net) > abs(current_net):
        return "increase"
    return "reduce"


def _price_points(strategy_state: dict[str, Any]) -> list[dict[str, str]]:
    points = strategy_state.get("price_points")
    if isinstance(points, list):
        normalized: list[dict[str, str]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            timestamp = point.get("timestamp")
            price = point.get("price")
            if timestamp and price is not None:
                normalized.append({"timestamp": str(timestamp), "price": str(price)})
        if normalized:
            return normalized

    legacy_prices = strategy_state.get("price_history")
    if not isinstance(legacy_prices, list):
        return []
    return [
        {"timestamp": "", "price": str(price)}
        for price in legacy_prices
        if price is not None and str(price) != ""
    ]


def _trim_price_points(
    points: list[dict[str, str]],
    *,
    current_timestamp: datetime,
    lookback_ticks: int,
    lookback_window_seconds: int,
) -> list[dict[str, str]]:
    trimmed = points
    if lookback_window_seconds > 0:
        cutoff = current_timestamp - timedelta(seconds=lookback_window_seconds)
        trimmed = [
            point
            for point in trimmed
            if not point.get("timestamp") or _parse_datetime(point["timestamp"]) >= cutoff
        ]
    if lookback_ticks > 0:
        trimmed = trimmed[-lookback_ticks:]
    return trimmed


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _window_seconds(points: list[dict[str, str]]) -> int:
    if len(points) < 2:
        return 0
    try:
        start = _parse_datetime(points[0]["timestamp"])
        end = _parse_datetime(points[-1]["timestamp"])
    except (KeyError, ValueError):
        return 0
    return max(0, int((end - start).total_seconds()))


def _elapsed_since(value: Any, current_timestamp: datetime) -> int | None:
    if not value:
        return None
    try:
        previous = _parse_datetime(value)
    except ValueError:
        return None
    return max(0, int((current_timestamp - previous).total_seconds()))


def _should_make_decision(
    *,
    strategy_state: dict[str, Any],
    current_timestamp: datetime,
    config: AdaptiveNetConfig,
) -> bool:
    publish_count = int(strategy_state.get("metric_publish_count", 0) or 0)
    last_decision_publish_count = int(
        strategy_state.get("last_decision_metric_publish_count", -(10**9))
    )
    publish_delta = publish_count - last_decision_publish_count
    if (
        config.decision_interval_metric_publishes > 0
        and publish_delta < config.decision_interval_metric_publishes
    ):
        return False
    elapsed_seconds = _elapsed_since(strategy_state.get("last_decision_at"), current_timestamp)
    if config.decision_interval_seconds > 0 and elapsed_seconds is not None:
        return elapsed_seconds >= config.decision_interval_seconds
    return True


def _metric_signals_from_state(value: Any) -> list[MetricSignal]:
    if not isinstance(value, list):
        return []
    signals: list[MetricSignal] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        signals.append(
            MetricSignal(
                name=name,
                direction_score=Decimal(str(item.get("direction_score", "0") or "0")),
                confidence=Decimal(str(item.get("confidence", "0") or "0")),
                size_multiplier=Decimal(str(item.get("size_multiplier", "1") or "1")),
                reason=str(item.get("reason") or ""),
            )
        )
    return signals


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:  # nosec B110
        return None


def _position_transition_snapshot(
    *,
    tick: Tick,
    current_net_units: int,
    decision: dict[str, Any],
    strategy_state: dict[str, Any],
) -> dict[str, Any]:
    target_net_units = int(decision.get("target_net_units") or current_net_units)
    order_units = int(decision.get("order_units") or target_net_units - current_net_units)
    order_direction = "buy" if order_units > 0 else "sell" if order_units < 0 else "hold"
    fill_price = tick.ask if order_units > 0 else tick.bid if order_units < 0 else tick.mid
    before_avg = _to_decimal_or_none(strategy_state.get("open_average_entry_price"))
    after_avg = _next_average_entry_price(
        before_units=current_net_units,
        before_avg=before_avg,
        after_units=target_net_units,
        order_units=order_units,
        fill_price=fill_price,
    )
    return {
        "timestamp": tick.timestamp.isoformat(),
        "order_direction": order_direction,
        "order_units": order_units,
        "order_abs_units": abs(order_units),
        "order_price": str(fill_price),
        "position_before_net_units": current_net_units,
        "position_before_abs_units": abs(current_net_units),
        "position_before_avg_entry_price": str(before_avg) if before_avg is not None else None,
        "position_after_net_units": target_net_units,
        "position_after_abs_units": abs(target_net_units),
        "position_after_avg_entry_price": str(after_avg) if after_avg is not None else None,
        "position_delta_net_units": target_net_units - current_net_units,
        "position_delta_abs_units": abs(target_net_units) - abs(current_net_units),
        "action": _decision_action(current_net_units, target_net_units, order_units),
    }


def _next_average_entry_price(
    *,
    before_units: int,
    before_avg: Decimal | None,
    after_units: int,
    order_units: int,
    fill_price: Decimal,
) -> Decimal | None:
    if after_units == 0:
        return None
    if order_units == 0:
        return before_avg
    if before_units == 0 or _sign(before_units) != _sign(after_units):
        return fill_price
    if abs(after_units) <= abs(before_units):
        return before_avg
    before_abs = Decimal(abs(before_units))
    added_abs = Decimal(abs(order_units))
    if before_avg is None:
        return fill_price
    return ((before_avg * before_abs) + (fill_price * added_abs)) / (before_abs + added_abs)


def _metric_snapshot(
    *,
    tick: Tick,
    signals: list[MetricSignal],
    strategy_state: dict[str, Any],
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "adaptive_net_metric_published_at": tick.timestamp.isoformat(),
        "adaptive_net_metric_publish_tick": strategy_state.get("last_metric_publish_tick"),
        "adaptive_net_metric_names": [signal.name for signal in signals],
        "adaptive_net_metric_signals": [signal.to_dict() for signal in signals],
    }
    for signal in signals:
        prefix = f"adaptive_net_{signal.name}"
        snapshot[f"{prefix}_direction_score"] = str(signal.direction_score)
        snapshot[f"{prefix}_confidence"] = str(signal.confidence)
        snapshot[f"{prefix}_size_multiplier"] = str(signal.size_multiplier)
        snapshot[f"{prefix}_reason"] = signal.reason
    return snapshot


def _decision_snapshot(
    *,
    tick: Tick,
    decision: dict[str, Any],
    position_transition: dict[str, Any],
    strategy_state: dict[str, Any],
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "adaptive_net_decision_published_at": tick.timestamp.isoformat(),
        "adaptive_net_decision_metric_publish_count": strategy_state.get("metric_publish_count"),
        "adaptive_net_decision_edge": str(decision.get("edge", "0")),
        "adaptive_net_decision_confidence": str(decision.get("confidence", "0")),
        "adaptive_net_decision_probability_long": str(decision.get("probability_long", "0.5")),
        "adaptive_net_decision_probability_short": str(decision.get("probability_short", "0.5")),
        "adaptive_net_decision_risk_multiplier": str(decision.get("risk_multiplier", "1")),
        "adaptive_net_decision_target_net_units": int(decision.get("target_net_units") or 0),
        "adaptive_net_decision_order_units": int(decision.get("order_units") or 0),
        "adaptive_net_position_before_net_units": position_transition["position_before_net_units"],
        "adaptive_net_position_before_abs_units": position_transition["position_before_abs_units"],
        "adaptive_net_position_after_net_units": position_transition["position_after_net_units"],
        "adaptive_net_position_after_abs_units": position_transition["position_after_abs_units"],
        "adaptive_net_position_delta_net_units": position_transition["position_delta_net_units"],
        "adaptive_net_position_delta_abs_units": position_transition["position_delta_abs_units"],
        "adaptive_net_order_abs_units": position_transition["order_abs_units"],
        "adaptive_net_order_price": position_transition["order_price"],
        "adaptive_net_order_direction": position_transition["order_direction"],
        "adaptive_net_position_transition": position_transition,
    }
    before_avg = position_transition.get("position_before_avg_entry_price")
    after_avg = position_transition.get("position_after_avg_entry_price")
    if before_avg is not None:
        snapshot["adaptive_net_position_before_avg_entry_price"] = before_avg
    if after_avg is not None:
        snapshot["adaptive_net_position_after_avg_entry_price"] = after_avg
    return snapshot


def _should_rebalance(
    *,
    tick_delta: int,
    elapsed_seconds: int | None,
    interval_ticks: int,
    interval_seconds: int,
) -> bool:
    if interval_ticks > 0 and tick_delta < interval_ticks:
        return False
    if interval_seconds > 0 and elapsed_seconds is not None:
        return elapsed_seconds >= interval_seconds
    return True


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
