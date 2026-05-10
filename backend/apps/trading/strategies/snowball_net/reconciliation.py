"""SnowballNet broker reconciliation adapter."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from apps.trading.enums import Direction
from apps.trading.models import Position
from apps.trading.strategies.reconciliation import (
    ReconciliationReportBase,
    StrategyConfigLike,
    StrategyReconciliationState,
)
from apps.trading.strategies.snowball_net.config import SnowballNetConfig
from apps.trading.strategies.snowball_net.state import SnowballNetState


class ReconciliationState(StrategyReconciliationState, Protocol):
    """SnowballNet state surface required for broker reconciliation."""


class ReconciliationReport(ReconciliationReportBase, Protocol):
    """Mutable reconciliation report fields updated by SnowballNet."""

    warnings: list[str]


@dataclass(frozen=True, slots=True)
class NetExposure:
    direction: str | None
    units: int
    average_price: Decimal | None
    position_id: str | None


def reconcile_broker_positions(
    *,
    state: ReconciliationState,
    open_positions: list[Position],
    report: ReconciliationReport,
    strategy_config: StrategyConfigLike | None = None,
) -> None:
    """Rebuild SnowballNet state from broker-backed open positions.

    SnowballNet decisions are based on one logical net exposure, while OANDA
    may expose one or more underlying trades. During resume we therefore
    aggregate all reconciled local positions for the task/instrument and write
    the strategy state from that aggregate.
    """
    config = _parse_config(strategy_config)
    sn = SnowballNetState.from_strategy_state(state.strategy_state)
    previous_pending = dict(sn.pending_action)
    directions = {_direction_value(position.direction) for position in open_positions}
    directions.discard("")
    if open_positions and len(directions) != 1:
        report.blockers.append(
            "SnowballNet broker exposure does not have a single valid net direction. "
            "Automatic resume is blocked because a single net direction is required."
        )
        state.strategy_state = sn.to_dict()
        return

    exposure = _aggregate_exposure(open_positions)

    if exposure.direction is None or exposure.units <= 0 or exposure.average_price is None:
        _apply_flat_state(sn, config=config)
        _sync_pending_action(sn, previous_pending, exposure_units=0, report=report)
        state.strategy_state = sn.to_dict()
        return

    _validate_exposure_direction(exposure=exposure, config=config, report=report)
    _validate_exposure_size(exposure=exposure, config=config, report=report)

    sn.initialised = True
    sn.direction = exposure.direction
    sn.net_units = exposure.units
    sn.average_price = exposure.average_price
    sn.position_id = exposure.position_id
    sn.add_count = _recalculate_add_count(
        current=sn.add_count,
        net_units=exposure.units,
        config=config,
    )
    sn.max_net_units_seen = max(sn.max_net_units_seen, exposure.units)
    if config.trade_direction == "auto":
        sn.direction_mode = "auto"
    else:
        sn.direction_mode = "fixed"
    _sync_pending_action(sn, previous_pending, exposure_units=exposure.units, report=report)

    state.strategy_state = sn.to_dict()


def _aggregate_exposure(open_positions: list[Position]) -> NetExposure:
    if not open_positions:
        return NetExposure(direction=None, units=0, average_price=None, position_id=None)

    directions = {_direction_value(position.direction) for position in open_positions}
    directions.discard("")
    if len(directions) != 1:
        return NetExposure(direction=None, units=0, average_price=None, position_id=None)

    total_units = sum(abs(int(position.units or 0)) for position in open_positions)
    if total_units <= 0:
        return NetExposure(direction=None, units=0, average_price=None, position_id=None)

    weighted_price = sum(
        (
            Decimal(str(position.entry_price)) * Decimal(abs(int(position.units or 0)))
            for position in open_positions
        ),
        Decimal("0"),
    ) / Decimal(total_units)
    ordered = sorted(
        open_positions,
        key=lambda p: (
            str(getattr(p, "entry_time", "") or ""),
            str(getattr(p, "created_at", "") or ""),
        ),
    )
    return NetExposure(
        direction=next(iter(directions)),
        units=total_units,
        average_price=weighted_price,
        position_id=str(ordered[0].id),
    )


def _apply_flat_state(sn: SnowballNetState, *, config: SnowballNetConfig) -> None:
    sn.initialised = False
    sn.net_units = 0
    sn.average_price = None
    sn.position_id = None
    sn.add_count = 0
    sn.current_trend_realized_pnl = Decimal("0")
    if config.trade_direction == "auto":
        sn.direction = "auto"
        sn.direction_mode = "auto"
    else:
        sn.direction = config.trade_direction
        sn.direction_mode = "fixed"


def _validate_exposure_direction(
    *,
    exposure: NetExposure,
    config: SnowballNetConfig,
    report: ReconciliationReport,
) -> None:
    if exposure.direction not in {Direction.LONG.value, Direction.SHORT.value}:
        report.blockers.append(
            "SnowballNet broker exposure contains both long and short positions. "
            "Automatic resume is blocked because a single net direction is required."
        )
        return

    if config.trade_direction == "auto":
        return
    if exposure.direction != config.trade_direction:
        report.blockers.append(
            "SnowballNet broker exposure direction "
            f"{exposure.direction} does not match configured direction "
            f"{config.trade_direction}."
        )


def _validate_exposure_size(
    *,
    exposure: NetExposure,
    config: SnowballNetConfig,
    report: ReconciliationReport,
) -> None:
    if exposure.units <= config.effective_max_net_units:
        return
    report.blockers.append(
        "SnowballNet broker exposure exceeds configured max_net_units "
        f"({exposure.units} > {config.effective_max_net_units})."
    )


def _recalculate_add_count(
    *,
    current: int,
    net_units: int,
    config: SnowballNetConfig,
) -> int:
    extra_units = max(0, net_units - config.initial_units)
    if extra_units <= 0:
        return 0

    if config.add_unit_allocation_mode == "fixed" and config.add_lot_progression_mode == "fixed":
        add_units = max(1, config.add_units)
        estimated = (extra_units + add_units - 1) // add_units
        return min(config.max_add_count, estimated)

    if (
        config.add_unit_allocation_mode == "fixed"
        and config.add_lot_progression_mode == "linear_increment"
    ):
        add_units = max(1, config.add_units)
        cumulative = 0
        for step in range(1, config.max_add_count + 1):
            cumulative += add_units * step
            if cumulative >= extra_units:
                return min(config.max_add_count, max(current, step))
        return config.max_add_count

    # Remaining-linear allocations are not invertible from units alone. Keep a
    # persisted count when it is available, otherwise choose a conservative
    # estimate so resume does not undercount already-used add steps.
    add_units = max(1, config.add_units)
    estimated = (extra_units + add_units - 1) // add_units
    return min(config.max_add_count, max(current, estimated))


def _sync_pending_action(
    sn: SnowballNetState,
    pending: dict[str, Any],
    *,
    exposure_units: int,
    report: ReconciliationReport,
) -> None:
    kind = str(pending.get("kind") or "")
    if kind == "open":
        previous_units = _int(pending.get("previous_units"))
        units = _int(pending.get("units"))
        expected_units = previous_units + units
        if units > 0 and exposure_units >= expected_units:
            sn.clear_pending_action()
            sn.last_action = {
                "kind": "reconciled",
                "action": "open",
                "entry_id": pending.get("entry_id"),
                "units": units,
                "previous_units": previous_units,
                "net_units": exposure_units,
                "timestamp": pending.get("timestamp"),
                "source": "broker",
            }
            report.warnings.append(
                "SnowballNet pending open action was already reflected in broker exposure."
            )
        return

    if kind == "close":
        previous_units = _int(pending.get("previous_units"))
        units = _int(pending.get("units"))
        expected_remaining = max(0, previous_units - units)
        if units > 0 and exposure_units <= expected_remaining:
            sn.clear_pending_action()
            sn.last_action = {
                "kind": "reconciled",
                "action": "close",
                "reason": pending.get("reason"),
                "units": units,
                "previous_units": previous_units,
                "net_units": exposure_units,
                "position_id": pending.get("position_id"),
                "timestamp": pending.get("timestamp"),
                "source": "broker",
            }
            report.warnings.append(
                "SnowballNet pending close action was already reflected in broker exposure."
            )


def _direction_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_config(strategy_config: StrategyConfigLike | None) -> SnowballNetConfig:
    if strategy_config is None:
        return SnowballNetConfig.from_dict({})
    return SnowballNetConfig.strict_from_dict(strategy_config.config_dict)
