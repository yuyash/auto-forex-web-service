"""Trading engine for Snowball strategy.

Implements a cycle-based hedging strategy:
- Each cycle starts with an initial entry and tracks its own counter entries
- Hedging mode: LONG and SHORT cycles run independently in parallel
- Non-hedging mode: a single LONG cycle
- Multi-level margin protection (rebalance → shrink → lock → emergency)
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from apps.trading.dataclasses import StrategyResult
from apps.trading.enums import EventType, StrategyType
from apps.trading.events import (
    ClosePositionEvent,
    GenericStrategyEvent,
    OpenPositionEvent,
)
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.registry import register_strategy
from apps.trading.strategies.snowball.calculators import (
    counter_interval_pips,
    counter_tp_pips,
)
from apps.trading.strategies.snowball.enums import ProtectionLevel
from apps.trading.strategies.snowball.models import (
    BasketEntry,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
)
from apps.trading.utils import quote_to_account_rate

logger: Logger = getLogger(__name__)


@register_strategy(
    id="snowball",
    schema="trading/schemas/snowball.json",
    display_name="Snowball Strategy",
    description=(
        "Cycle-based hedging strategy: rotational profit-taking on initial entries "
        "and averaging-down with step-based partial closes on counter entries."
    ),
)
class SnowballStrategy(Strategy):
    """Main trading engine for Snowball strategy."""

    def __init__(
        self,
        instrument: str,
        pip_size: Decimal,
        config: SnowballStrategyConfig,
    ) -> None:
        super().__init__(instrument, pip_size, config)
        self._hedging_enabled: bool = True
        logger.info(
            "Initialised Snowball engine: instrument=%s, pip_size=%s",
            instrument,
            pip_size,
        )

    # ------------------------------------------------------------------
    # Registry interface
    # ------------------------------------------------------------------

    @staticmethod
    def parse_config(strategy_config: Any) -> SnowballStrategyConfig:
        return SnowballStrategyConfig.from_dict(strategy_config.config_dict)

    @classmethod
    def normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        return SnowballStrategyConfig.from_dict(dict(parameters)).to_dict()

    @classmethod
    def default_parameters(cls) -> dict[str, Any]:
        return SnowballStrategyConfig.from_dict({}).to_dict()

    @classmethod
    def validate_parameters(
        cls,
        *,
        parameters: dict[str, Any],
        config_schema: dict[str, Any] | None = None,
    ) -> None:
        super().validate_parameters(parameters=parameters, config_schema=config_schema)
        cfg = SnowballStrategyConfig.from_dict(parameters)
        cfg.validate()

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.SNOWBALL

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _spread_pips(self, tick: Any) -> Decimal:
        return (tick.ask - tick.bid) / self.pip_size

    def _margin_ratio(self, state: Any, ss: SnowballStrategyState) -> Decimal:
        nav = ss.account_nav
        if nav <= 0:
            return Decimal("0")
        all_entries = ss.all_entries()
        if not all_entries:
            return Decimal("0")
        long_units = sum(
            abs(int(e.get("units", 0))) for e in all_entries if e.get("direction") == "long"
        )
        short_units = sum(
            abs(int(e.get("units", 0))) for e in all_entries if e.get("direction") == "short"
        )
        total_units = max(long_units, short_units)
        if total_units == 0:
            return Decimal("0")
        mid = ss.last_mid or Decimal("0")
        if mid <= 0:
            return Decimal("0")
        conv = quote_to_account_rate(self.instrument, mid, self.account_currency)
        margin_rate = Decimal("0.04")
        required = mid * Decimal(str(total_units)) * margin_rate * conv
        return (required / nav) * Decimal("100")

    def _unrealised_loss(self, entry: dict[str, Any], tick: Any) -> Decimal:
        """Return unrealised loss in pips (positive = losing)."""
        direction = str(entry.get("direction", "long"))
        ep = Decimal(str(entry.get("entry_price", "0")))
        if direction == "long":
            return (ep - tick.mid) / self.pip_size
        return (tick.mid - ep) / self.pip_size

    def _next_id(self, ss: SnowballStrategyState) -> int:
        eid = ss.next_entry_id
        ss.next_entry_id += 1
        return eid

    @staticmethod
    def _group_id(root_entry_id: int | None) -> str:
        return str(root_entry_id) if root_entry_id is not None else ""

    def _annotate_event(
        self,
        event: Any,
        *,
        basket: str = "",
        root_entry_id: int | None = None,
        parent_entry_id: int | None = None,
        step: int | None = None,
        close_reason: str = "",
        validation_status: str = "",
        expected_interval_pips: Decimal | None = None,
        actual_interval_pips: Decimal | None = None,
        expected_tp_pips: Decimal | None = None,
        actual_tp_pips: Decimal | None = None,
        expected_exit_price: Decimal | None = None,
        actual_exit_price: Decimal | None = None,
    ) -> Any:
        event.strategy_type = StrategyType.SNOWBALL.value
        event.basket = basket
        event.root_entry_id = root_entry_id
        event.parent_entry_id = parent_entry_id
        event.visual_group_id = self._group_id(root_entry_id)
        event.step = step
        event.close_reason = close_reason
        event.validation_status = validation_status
        event.expected_interval_pips = expected_interval_pips
        event.actual_interval_pips = actual_interval_pips
        event.expected_tp_pips = expected_tp_pips
        event.actual_tp_pips = actual_tp_pips
        event.expected_exit_price = expected_exit_price
        event.actual_exit_price = actual_exit_price
        return event

    # ------------------------------------------------------------------
    # Event factories
    # ------------------------------------------------------------------

    def _make_open_event(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        *,
        direction: str,
        units: int,
        step: int,
        close_price: Decimal,
        role: str,
        layer_number: int = 1,
        lot_k: int | None = None,
        description: str = "",
        planned_exit_price_formula: str | None = None,
        root_entry_id: int | None = None,
        parent_entry_id: int | None = None,
        expected_interval_pips: Decimal | None = None,
        actual_interval_pips: Decimal | None = None,
        expected_tp_pips: Decimal | None = None,
        validation_status: str = "",
    ) -> tuple[OpenPositionEvent, dict[str, Any]]:
        """Create an OpenPositionEvent and the corresponding entry dict."""
        eid = self._next_id(ss)
        price = tick.ask if direction == "long" else tick.bid
        ret = 1 if role == "initial" else (lot_k if lot_k is not None else 1)
        entry = BasketEntry(
            entry_id=eid,
            step=step,
            direction=direction,
            entry_price=price,
            close_price=close_price,
            units=units,
            opened_at=tick.timestamp.isoformat(),
        )
        entry_dict = entry.to_dict()
        if root_entry_id is None:
            root_entry_id = eid if role == "initial" else None
        entry_dict["layer_number"] = layer_number
        entry_dict["retracement_count"] = ret
        entry_dict["role"] = role
        entry_dict["root_entry_id"] = root_entry_id
        entry_dict["parent_entry_id"] = parent_entry_id
        entry_dict["visual_group_id"] = self._group_id(root_entry_id)
        entry_dict["expected_interval_pips"] = (
            str(expected_interval_pips) if expected_interval_pips is not None else None
        )
        entry_dict["actual_interval_pips"] = (
            str(actual_interval_pips) if actual_interval_pips is not None else None
        )
        entry_dict["expected_tp_pips"] = (
            str(expected_tp_pips) if expected_tp_pips is not None else None
        )
        entry_dict["validation_status"] = validation_status
        event = OpenPositionEvent(
            event_type=EventType.OPEN_POSITION,
            timestamp=tick.timestamp,
            layer_number=layer_number,
            direction=direction,
            price=price,
            units=units,
            entry_id=eid,
            retracement_count=ret,
            strategy_event_type=f"snowball_{role}",
            planned_exit_price=close_price,
            planned_exit_price_formula=planned_exit_price_formula,
            description=description,
        )
        self._annotate_event(
            event,
            basket=role,
            root_entry_id=root_entry_id,
            parent_entry_id=parent_entry_id,
            step=step,
            validation_status=validation_status,
            expected_interval_pips=expected_interval_pips,
            actual_interval_pips=actual_interval_pips,
            expected_tp_pips=expected_tp_pips,
            expected_exit_price=close_price,
        )
        return event, entry_dict

    def _make_close_event(
        self,
        tick: Any,
        entry: dict[str, Any],
        ss: SnowballStrategyState,
        *,
        cycle: SnowballCycle | None = None,
        description: str = "",
        close_reason: str = "",
        actual_tp_pips: Decimal | None = None,
        validation_status: str = "",
    ) -> ClosePositionEvent:
        direction = str(entry.get("direction", "long"))
        entry_price = Decimal(str(entry.get("entry_price", "0")))
        exit_price = tick.bid if direction == "long" else tick.ask
        units = int(entry.get("units", 0))
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        pnl = (exit_price - entry_price) * Decimal(str(units)) * conv
        if direction == "short":
            pnl = -pnl
        pips = abs(exit_price - entry_price) / self.pip_size
        role = str(entry.get("role", "counter"))
        is_initial = role == "initial"
        fc = cycle.freeze_count if cycle else 0
        ac = cycle.add_count if cycle else 0
        layer = entry.get("layer_number", 1 if is_initial else fc + 1)
        ret = entry.get("retracement_count", 1 if is_initial else ac + 1)
        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            timestamp=tick.timestamp,
            layer_number=layer,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            units=units,
            pnl=pnl,
            pips=pips,
            entry_id=int(entry.get("entry_id", 0)),
            position_id=entry.get("position_id"),
            retracement_count=ret,
            description=description,
        )
        self._annotate_event(
            event,
            basket=role,
            root_entry_id=(
                int(entry["root_entry_id"]) if entry.get("root_entry_id") is not None else None
            ),
            parent_entry_id=(
                int(entry["parent_entry_id"]) if entry.get("parent_entry_id") is not None else None
            ),
            step=int(entry["step"]) if entry.get("step") is not None else None,
            close_reason=close_reason,
            validation_status=validation_status,
            expected_interval_pips=(
                Decimal(str(entry["expected_interval_pips"]))
                if entry.get("expected_interval_pips") not in (None, "")
                else None
            ),
            actual_interval_pips=(
                Decimal(str(entry["actual_interval_pips"]))
                if entry.get("actual_interval_pips") not in (None, "")
                else None
            ),
            expected_tp_pips=(
                Decimal(str(entry["expected_tp_pips"]))
                if entry.get("expected_tp_pips") not in (None, "")
                else None
            ),
            actual_tp_pips=actual_tp_pips,
            expected_exit_price=(
                Decimal(str(entry["close_price"]))
                if entry.get("close_price") not in (None, "")
                else None
            ),
            actual_exit_price=exit_price,
        )
        return event

    # ------------------------------------------------------------------
    # Cycle lifecycle
    # ------------------------------------------------------------------

    def _create_cycle(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        direction: str,
    ) -> tuple[list[Any], SnowballCycle]:
        """Create a new cycle with an initial entry. Returns (events, cycle)."""
        cfg = self.config
        units = cfg.trend_lot_size * cfg.base_units
        price = tick.ask if direction == "long" else tick.bid
        if direction == "long":
            close_price = price + cfg.m_pips * self.pip_size
            formula = f"{price} + {cfg.m_pips} * {self.pip_size}"
        else:
            close_price = price - cfg.m_pips * self.pip_size
            formula = f"{price} - {cfg.m_pips} * {self.pip_size}"

        evt, entry_dict = self._make_open_event(
            ss,
            tick,
            direction=direction,
            units=units,
            step=1,
            close_price=close_price,
            role="initial",
            description=(
                f"Initial entry ({direction.upper()}) | units={units}, TP={close_price:.5f}"
            ),
            planned_exit_price_formula=formula,
            expected_tp_pips=cfg.m_pips,
            validation_status="pass",
        )
        cycle = SnowballCycle(
            cycle_id=int(entry_dict["entry_id"]),
            direction=direction,
            initial_entry=entry_dict,
            cycle_base_units=cfg.base_units,
        )
        ss.cycles.append(cycle)
        return [evt], cycle

    def _close_and_reenter(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        cycle: SnowballCycle,
    ) -> list[Any]:
        """Close the initial entry (TP hit), mark cycle completed, create new cycle."""
        entry = cycle.initial_entry
        direction = cycle.direction
        ep = Decimal(str(entry.get("entry_price", "0")))
        exit_price = tick.bid if direction == "long" else tick.ask
        pips_gained = abs(exit_price - ep) / self.pip_size

        events: list[Any] = []

        logger.info(
            "TP hit (%s): entry=%s, exit=%s, +%.1f pips, units=%s",
            direction.upper(),
            ep,
            exit_price,
            pips_gained,
            entry.get("units"),
        )
        events.append(
            self._make_close_event(
                tick,
                entry,
                ss,
                cycle=cycle,
                description=(
                    f"TP ({direction.upper()}) | entry={ep:.5f}, "
                    f"exit={exit_price:.5f}, +{pips_gained:.1f} pips"
                ),
                close_reason="tp",
                actual_tp_pips=pips_gained,
                validation_status="pass",
            )
        )
        cycle.completed = True

        # Re-entry: new cycle in the same direction
        new_events, _new_cycle = self._create_cycle(ss, tick, direction)
        logger.info(
            "Re-entry (%s) after TP: new cycle_id=%d",
            direction.upper(),
            _new_cycle.cycle_id,
        )
        events.extend(new_events)
        return events

    # ------------------------------------------------------------------
    # Per-cycle tick processing
    # ------------------------------------------------------------------

    def _process_cycle_tp(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        cycle: SnowballCycle,
    ) -> list[Any]:
        """Check if the initial entry hit its TP target."""
        if cycle.completed:
            return []
        entry = cycle.initial_entry
        if not entry:
            return []
        direction = cycle.direction
        ep = Decimal(str(entry.get("entry_price", "0")))
        m_dyn = self.config.m_pips

        hit = False
        if direction == "long" and tick.bid >= ep + m_dyn * self.pip_size:
            hit = True
        elif direction == "short" and tick.ask <= ep - m_dyn * self.pip_size:
            hit = True

        if not hit:
            return []
        return self._close_and_reenter(ss, tick, cycle)

    def _process_cycle_counter_closes(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        cycle: SnowballCycle,
    ) -> list[Any]:
        """Check counter entries for step-based close targets."""
        if cycle.completed:
            return []
        events: list[Any] = []

        for entry in list(cycle.counter_entries):
            if entry.get("is_hedge"):
                continue
            direction = str(entry.get("direction", "long"))
            close_price = Decimal(str(entry.get("close_price", "0")))
            if close_price <= 0:
                continue

            hit = False
            if direction == "long" and tick.bid >= close_price:
                hit = True
            elif direction == "short" and tick.ask <= close_price:
                hit = True
            if not hit:
                continue

            # Only close the latest step (highest step number)
            non_hedge = cycle.counter_non_hedge()
            if not non_hedge:
                continue
            max_step = max(int(e.get("step", 0)) for e in non_hedge)
            step = int(entry.get("step", 1))
            if step != max_step:
                continue

            entry_price = Decimal(str(entry.get("entry_price", "0")))
            exit_price = tick.bid if direction == "long" else tick.ask
            pips_gained = abs(exit_price - entry_price) / self.pip_size
            layer = entry.get("layer_number", cycle.freeze_count + 1)
            ret = entry.get("retracement_count", cycle.add_count + 1)

            logger.info(
                "Counter TP step %d (%s): L%s/R%s, +%.1f pips",
                step,
                direction.upper(),
                layer,
                ret,
                pips_gained,
            )
            events.append(
                self._make_close_event(
                    tick,
                    entry,
                    ss,
                    cycle=cycle,
                    description=(
                        f"Counter TP step {step} ({direction.upper()}) | "
                        f"L{layer}/R{ret}, entry={entry_price:.5f}, "
                        f"exit={exit_price:.5f}, +{pips_gained:.1f} pips"
                    ),
                    close_reason="counter_tp",
                    actual_tp_pips=pips_gained,
                    validation_status="pass",
                )
            )
            cycle.remove_entry(int(entry.get("entry_id", 0)))
            cycle.add_count = 0
            ss.metrics["counter_close_count"] = int(ss.metrics.get("counter_close_count", 0)) + 1

        return events

    def _process_cycle_counter_adds(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        cycle: SnowballCycle,
    ) -> list[Any]:
        """Check whether to add a new counter entry to this cycle."""
        if cycle.completed:
            return []
        cfg = self.config
        events: list[Any] = []

        if cycle.freeze_count >= cfg.f_max:
            return events

        if cycle.add_count >= cfg.r_max:
            logger.info(
                "Counter r_max reached (%d/%d) in cycle %d: freeze_count %d -> %d",
                cycle.add_count,
                cfg.r_max,
                cycle.cycle_id,
                cycle.freeze_count,
                cycle.freeze_count + 1,
            )
            cycle.add_count = 0
            cycle.freeze_count += 1
            cycle.cycle_base_units = int(Decimal(str(cfg.base_units)) * cfg.post_r_max_base_factor)
            return events

        # Check if initial entry is losing
        initial = cycle.initial_entry
        if not initial:
            return events
        loss = self._unrealised_loss(initial, tick)
        if loss <= 0:
            return events

        counter_non_hedge = cycle.counter_non_hedge()
        direction = cycle.direction

        if not counter_non_hedge:
            # First counter add
            step_k = 1
            interval = counter_interval_pips(step_k, cfg)
            if loss < interval:
                return events

            prior_closes = int(ss.metrics.get("counter_close_count", 0))
            lot_k = (cycle.add_count + 2) if prior_closes == 0 else (cycle.add_count + 1)
            units = lot_k * cycle.cycle_base_units
            tp = counter_tp_pips(step_k, cfg)
            new_price = tick.ask if direction == "long" else tick.bid
            ret_number = cycle.add_count + 1  # R1, R2, R3...

            close_price, exit_formula = self._compute_counter_tp(
                cfg,
                direction,
                new_price,
                units,
                tp,
                counter_non_hedge,
                initial,
            )

            logger.info(
                "Counter first add #%d (%s) in cycle %d: L%d/R%d, units=%d, adverse=%.1f pips",
                lot_k,
                direction.upper(),
                cycle.cycle_id,
                cycle.freeze_count + 1,
                ret_number,
                units,
                loss,
            )
            evt, entry_dict = self._make_open_event(
                ss,
                tick,
                direction=direction,
                units=units,
                step=step_k + 1,
                close_price=close_price,
                role="counter",
                layer_number=cycle.freeze_count + 1,
                lot_k=ret_number,
                description=(
                    f"Counter add ({direction.upper()}) | "
                    f"L{cycle.freeze_count + 1}/R{ret_number}, units={units}, "
                    f"adverse={loss:.1f} pips, TP={close_price:.5f}"
                ),
                planned_exit_price_formula=exit_formula,
                root_entry_id=int(initial.get("entry_id", 0)),
                parent_entry_id=int(initial.get("entry_id", 0)),
                expected_interval_pips=interval,
                actual_interval_pips=loss,
                expected_tp_pips=tp,
                validation_status="pass",
            )
            cycle.counter_entries.append(entry_dict)
            cycle.add_count = 1
            events.append(evt)
            return events

        # Subsequent counter adds — measure distance from latest
        latest = max(counter_non_hedge, key=lambda e: int(e.get("step", 0)))
        latest_price = Decimal(str(latest.get("entry_price", "0")))
        if direction == "long":
            adverse = (latest_price - tick.mid) / self.pip_size
        else:
            adverse = (tick.mid - latest_price) / self.pip_size

        step_k = cycle.add_count + 1
        interval = counter_interval_pips(step_k, cfg)
        if adverse < interval:
            return events

        prior_closes = int(ss.metrics.get("counter_close_count", 0))
        lot_k = (cycle.add_count + 2) if prior_closes == 0 else (cycle.add_count + 1)
        units = lot_k * cycle.cycle_base_units
        tp = counter_tp_pips(step_k, cfg)
        new_price = tick.ask if direction == "long" else tick.bid
        ret_number = cycle.add_count + 1

        close_price, exit_formula = self._compute_counter_tp(
            cfg,
            direction,
            new_price,
            units,
            tp,
            counter_non_hedge,
            initial,
        )

        logger.info(
            "Counter add (%s) in cycle %d: L%d/R%d, units=%d, adverse=%.1f pips",
            direction.upper(),
            cycle.cycle_id,
            cycle.freeze_count + 1,
            ret_number,
            units,
            adverse,
        )
        evt, entry_dict = self._make_open_event(
            ss,
            tick,
            direction=direction,
            units=units,
            step=int(latest.get("step", 1)) + 1,
            close_price=close_price,
            role="counter",
            layer_number=cycle.freeze_count + 1,
            lot_k=ret_number,
            description=(
                f"Counter add ({direction.upper()}) | "
                f"L{cycle.freeze_count + 1}/R{ret_number}, units={units}, "
                f"adverse={adverse:.1f} pips, TP={close_price:.5f}"
            ),
            planned_exit_price_formula=exit_formula,
            root_entry_id=(
                int(latest["root_entry_id"])
                if latest.get("root_entry_id") is not None
                else int(latest.get("entry_id", 0))
            ),
            parent_entry_id=int(latest.get("entry_id", 0)),
            expected_interval_pips=interval,
            actual_interval_pips=adverse,
            expected_tp_pips=tp,
            validation_status="pass",
        )
        cycle.counter_entries.append(entry_dict)
        cycle.add_count += 1

        # Update close prices for existing counter entries (non-weighted_avg only)
        if cfg.counter_tp_mode != "weighted_avg":
            for e in cycle.counter_entries:
                if e.get("is_hedge"):
                    continue
                sk = int(e.get("step", 1)) - 1
                if sk < 1:
                    sk = 1
                step_tp = counter_tp_pips(sk, cfg)
                base_price = Decimal(str(e.get("entry_price", "0")))
                e["close_price"] = str(
                    base_price + step_tp * self.pip_size
                    if direction == "long"
                    else base_price - step_tp * self.pip_size
                )

        events.append(evt)
        return events

    def _compute_counter_tp(
        self,
        cfg: SnowballStrategyConfig,
        direction: str,
        new_price: Decimal,
        units: int,
        tp: Decimal,
        counter_non_hedge: list[dict[str, Any]],
        initial_entry: dict[str, Any],
    ) -> tuple[Decimal, str]:
        """Compute close_price and formula for a counter add."""
        if cfg.counter_tp_mode == "weighted_avg":
            total_u = units
            total_cost = new_price * Decimal(str(units))
            formula_parts = [f"{new_price} * {units}"]
            for e in counter_non_hedge:
                eu = int(e.get("units", 0))
                ep = Decimal(str(e.get("entry_price", "0")))
                total_u += eu
                total_cost += ep * Decimal(str(eu))
                formula_parts.append(f"{ep} * {eu}")
            # Include initial entry in weighted average
            ie_units = abs(int(initial_entry.get("units", 0)))
            ie_price = Decimal(str(initial_entry.get("entry_price", "0")))
            if ie_units > 0:
                total_u += ie_units
                total_cost += ie_price * Decimal(str(ie_units))
                formula_parts.append(f"{ie_price} * {ie_units}")
            close_price = total_cost / Decimal(str(total_u)) if total_u > 0 else new_price
            exit_formula = f"({' + '.join(formula_parts)}) / {total_u}"
        else:
            if direction == "long":
                close_price = new_price + tp * self.pip_size
            else:
                close_price = new_price - tp * self.pip_size
            op = "+" if direction == "long" else "-"
            exit_formula = f"{new_price} {op} {tp} * {self.pip_size}"
        return close_price, exit_formula

    # ------------------------------------------------------------------
    # Protection
    # ------------------------------------------------------------------

    def _handle_emergency(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        ratio: Decimal,
        unrealized: Decimal,
    ) -> tuple[list[Any], str] | None:
        """Check for emergency stop. Returns (events, stop_reason) or None."""
        if ratio < Decimal("95"):
            return None
        ss.protection_level = ProtectionLevel.EMERGENCY
        all_entries = ss.all_entries()
        logger.critical(
            "EMERGENCY STOP: margin ratio %.1f%% >= 95%% | NAV=%s, entries=%d",
            ratio,
            ss.account_nav,
            len(all_entries),
        )
        event = self._annotate_event(
            GenericStrategyEvent(
                event_type=EventType.STRATEGY_STOPPED,
                timestamp=tick.timestamp,
                data={"kind": "emergency_stop", "ratio": str(ratio)},
            ),
            validation_status="fail",
        )
        return [event], f"Emergency stop: margin ratio {ratio:.1f}% >= 95%"

    def _handle_lock(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        ratio: Decimal,
    ) -> list[Any] | None:
        """Enter lock mode if ratio >= n_th. Returns events or None."""
        cfg = self.config
        if not cfg.lock_enabled or ratio < cfg.n_th:
            return None
        if ss.protection_level == ProtectionLevel.LOCKED:
            return None

        ss.protection_level = ProtectionLevel.LOCKED
        ss.lock_entered_at = tick.timestamp.isoformat()
        events: list[Any] = []

        all_entries = ss.all_entries()
        long_units = sum(
            int(e.get("units", 0)) for e in all_entries if e.get("direction") == "long"
        )
        short_units = sum(
            int(e.get("units", 0)) for e in all_entries if e.get("direction") == "short"
        )
        net = long_units - short_units

        logger.warning(
            "LOCK MODE entered: margin ratio %.1f%% >= n_th=%.1f%%",
            ratio,
            cfg.n_th,
        )

        if net != 0:
            hedge_dir = "short" if net > 0 else "long"
            hedge_units = abs(net)
            eid = self._next_id(ss)
            price = tick.ask if hedge_dir == "long" else tick.bid
            hedge_entry = {
                "entry_id": eid,
                "step": 0,
                "direction": hedge_dir,
                "entry_price": str(price),
                "close_price": "0",
                "units": hedge_units,
                "opened_at": tick.timestamp.isoformat(),
                "is_hedge": True,
                "role": "hedge",
                "layer_number": 0,
                "retracement_count": 0,
            }
            # Add hedge to the first active cycle (arbitrary; it's a global hedge)
            active = ss.active_cycles()
            if active:
                active[0].hedge_entries.append(hedge_entry)
            ss.lock_hedge_ids.append(eid)
            events.append(
                self._annotate_event(
                    OpenPositionEvent(
                        event_type=EventType.OPEN_POSITION,
                        timestamp=tick.timestamp,
                        direction=hedge_dir,
                        price=price,
                        units=hedge_units,
                        entry_id=eid,
                        strategy_event_type="snowball_lock_hedge",
                        description=(
                            f"Lock hedge ({hedge_dir.upper()}) | "
                            f"units={hedge_units}, net={net}, ratio={ratio:.1f}%"
                        ),
                    ),
                    basket="hedge",
                    step=0,
                    close_reason="lock_hedge_open",
                    validation_status="not_applicable",
                )
            )
        events.append(
            self._annotate_event(
                GenericStrategyEvent(
                    event_type=EventType.STATUS_CHANGED,
                    timestamp=tick.timestamp,
                    data={"kind": "snowball_locked", "ratio": str(ratio)},
                ),
                close_reason="lock_entered",
            )
        )
        return events

    def _handle_lock_release(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        ratio: Decimal,
    ) -> list[Any]:
        """Check if lock can be released. Returns events."""
        if ss.protection_level != ProtectionLevel.LOCKED:
            return []
        cfg = self.config
        unlock_ok = ratio < cfg.m_th - Decimal("5") and (
            not cfg.spread_guard_enabled or self._spread_pips(tick) <= cfg.spread_guard_pips
        )
        if ss.cooldown_until:
            from datetime import datetime

            cd = datetime.fromisoformat(ss.cooldown_until)
            if tick.timestamp < cd:
                unlock_ok = False
        if not unlock_ok:
            return []

        events: list[Any] = []
        for hid in list(ss.lock_hedge_ids):
            for cycle in ss.cycles:
                for e in list(cycle.hedge_entries):
                    if int(e.get("entry_id", 0)) == hid:
                        events.append(
                            self._make_close_event(
                                tick,
                                e,
                                ss,
                                cycle=cycle,
                                description=f"Lock hedge unwound | ratio={ratio:.1f}%",
                                close_reason="lock_hedge_neutralize",
                                validation_status="not_applicable",
                            )
                        )
                        cycle.hedge_entries.remove(e)
        ss.lock_hedge_ids = []
        ss.lock_entered_at = None
        ss.cooldown_until = None
        ss.protection_level = (
            ProtectionLevel.SHRINK if ratio >= cfg.m_th else ProtectionLevel.NORMAL
        )
        events.append(
            self._annotate_event(
                GenericStrategyEvent(
                    event_type=EventType.STATUS_CHANGED,
                    timestamp=tick.timestamp,
                    data={"kind": "snowball_unlocked", "ratio": str(ratio)},
                ),
                close_reason="lock_released",
            )
        )
        return events

    def _handle_shrink(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        ratio: Decimal,
    ) -> list[Any] | None:
        """Shrink mode: close worst-loss counter entry. Returns events or None."""
        cfg = self.config
        if not cfg.shrink_enabled or ratio < cfg.m_th:
            return None

        events: list[Any] = []
        if ss.protection_level != ProtectionLevel.SHRINK:
            ss.protection_level = ProtectionLevel.SHRINK
            events.append(
                self._annotate_event(
                    GenericStrategyEvent(
                        event_type=EventType.STATUS_CHANGED,
                        timestamp=tick.timestamp,
                        data={"kind": "snowball_shrink", "ratio": str(ratio)},
                    ),
                    close_reason="shrink_entered",
                )
            )

        # Find worst-loss counter entry across all cycles
        worst_entry = None
        worst_cycle = None
        worst_loss = Decimal("-1")
        for cycle in ss.active_cycles():
            for e in cycle.counter_entries:
                if e.get("is_hedge"):
                    continue
                loss = self._unrealised_loss(e, tick)
                if loss > worst_loss:
                    worst_loss = loss
                    worst_entry = e
                    worst_cycle = cycle

        if worst_entry and worst_cycle:
            events.append(
                self._make_close_event(
                    tick,
                    worst_entry,
                    ss,
                    cycle=worst_cycle,
                    description=(
                        f"Shrink: close largest-loss counter | "
                        f"loss={worst_loss:.1f} pips, ratio={ratio:.1f}%"
                    ),
                    close_reason="shrink",
                    validation_status="warn",
                )
            )
            worst_cycle.remove_entry(int(worst_entry.get("entry_id", 0)))

        if ratio < cfg.m_th - Decimal("5"):
            ss.protection_level = ProtectionLevel.NORMAL
        return events

    def _handle_rebalance(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        ratio: Decimal,
    ) -> list[Any] | None:
        """Rebalance: reduce BUY/SELL imbalance. Returns events or None."""
        cfg = self.config
        if not cfg.rebalance_enabled or ratio < cfg.rebalance_start_ratio:
            return None

        events: list[Any] = []
        all_entries = ss.all_entries()
        long_units = sum(
            int(e.get("units", 0)) for e in all_entries if e.get("direction") == "long"
        )
        short_units = sum(
            int(e.get("units", 0)) for e in all_entries if e.get("direction") == "short"
        )
        if long_units == short_units:
            return events

        heavier = "long" if long_units > short_units else "short"
        # Collect all counter entries on the heavier side, sorted by step
        candidates: list[tuple[SnowballCycle, dict[str, Any]]] = []
        for cycle in ss.active_cycles():
            for e in cycle.counter_entries:
                if e.get("direction") == heavier and not e.get("is_hedge"):
                    candidates.append((cycle, e))
        candidates.sort(key=lambda x: int(x[1].get("step", 0)))

        for cycle, entry in candidates:
            events.append(
                self._make_close_event(
                    tick,
                    entry,
                    ss,
                    cycle=cycle,
                    description=(
                        f"Rebalance: reduce {heavier.upper()} imbalance | "
                        f"LONG={long_units} vs SHORT={short_units}"
                    ),
                    close_reason="rebalance",
                    validation_status="warn",
                )
            )
            cycle.remove_entry(int(entry.get("entry_id", 0)))
            # Recheck
            all_entries = ss.all_entries()
            long_units = sum(
                int(e.get("units", 0)) for e in all_entries if e.get("direction") == "long"
            )
            short_units = sum(
                int(e.get("units", 0)) for e in all_entries if e.get("direction") == "short"
            )
            if long_units == short_units:
                break
        return events

    # ------------------------------------------------------------------
    # Core tick processing
    # ------------------------------------------------------------------

    def on_tick(self, *, tick: Any, state: Any) -> StrategyResult:
        """Process a single tick."""
        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        ss.last_bid = tick.bid
        ss.last_ask = tick.ask
        ss.last_mid = tick.mid

        # Update NAV
        if hasattr(state, "current_balance") and state.current_balance:
            ss.account_balance = Decimal(str(state.current_balance))
        unrealized = Decimal("0")
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        for entry in ss.all_entries():
            direction = str(entry.get("direction", "long"))
            ep = Decimal(str(entry.get("entry_price", "0")))
            units = abs(int(entry.get("units", 0)))
            if direction == "long":
                unrealized += (tick.bid - ep) * Decimal(str(units)) * conv
            else:
                unrealized += (ep - tick.ask) * Decimal(str(units)) * conv
        ss.account_nav = ss.account_balance + unrealized
        if ss.account_nav <= 0:
            ss.account_nav = ss.account_balance

        events: list[Any] = []
        ratio = self._margin_ratio(state, ss)
        ss.metrics["margin_ratio"] = str(ratio / Decimal("100"))

        # --- Emergency ---
        emergency = self._handle_emergency(ss, tick, ratio, unrealized)
        if emergency is not None:
            emergency_events, stop_reason = emergency
            state.strategy_state = ss.to_dict()
            return StrategyResult(
                state=state,
                events=emergency_events,
                should_stop=True,
                stop_reason=stop_reason,
            )

        # --- Lock enter ---
        lock_events = self._handle_lock(ss, tick, ratio)
        if lock_events is not None:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=lock_events)

        # --- Lock release ---
        if ss.protection_level == ProtectionLevel.LOCKED:
            release_events = self._handle_lock_release(ss, tick, ratio)
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=release_events)

        # --- Shrink ---
        shrink_events = self._handle_shrink(ss, tick, ratio)
        if shrink_events is not None:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=shrink_events)

        # --- Rebalance ---
        rebalance_events = self._handle_rebalance(ss, tick, ratio)
        if rebalance_events is not None:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=rebalance_events)

        # Back to normal
        if ss.protection_level != ProtectionLevel.NORMAL:
            ss.protection_level = ProtectionLevel.NORMAL

        # --- Spread guard ---
        cfg = self.config
        if cfg.spread_guard_enabled and self._spread_pips(tick) > cfg.spread_guard_pips:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- Initialisation ---
        if not ss.initialised:
            init_events, _ = self._create_cycle(ss, tick, "long")
            events.extend(init_events)
            if self._hedging_enabled:
                short_events, _ = self._create_cycle(ss, tick, "short")
                events.extend(short_events)
            ss.initialised = True
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- Per-cycle processing ---
        for cycle in list(ss.active_cycles()):
            events.extend(self._process_cycle_tp(ss, tick, cycle))
            events.extend(self._process_cycle_counter_closes(ss, tick, cycle))
            events.extend(self._process_cycle_counter_adds(ss, tick, cycle))

        state.strategy_state = ss.to_dict()
        return StrategyResult(state=state, events=events)

    # ------------------------------------------------------------------
    # State serialisation
    # ------------------------------------------------------------------

    def deserialize_state(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        return state_dict

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return state

    def apply_event_execution_result(
        self,
        *,
        state: Any,
        execution_result: Any,
    ) -> None:
        """Apply order execution feedback (position IDs) to state."""
        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        if not execution_result:
            return

        binding = getattr(execution_result, "entry_binding", None)
        if binding is None:
            return
        eid = getattr(binding, "entry_id", None)
        position_id = getattr(binding, "position_id", None)
        if eid is None or position_id is None:
            return

        for cycle in ss.cycles:
            if cycle.initial_entry and int(cycle.initial_entry.get("entry_id", 0)) == int(eid):
                cycle.initial_entry["position_id"] = str(position_id)
            for entry in cycle.counter_entries + cycle.hedge_entries:
                if int(entry.get("entry_id", 0)) == int(eid):
                    entry["position_id"] = str(position_id)

        state.strategy_state = ss.to_dict()
