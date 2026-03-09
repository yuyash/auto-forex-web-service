"""Trading engine for Snowball strategy.

Implements the dual-basket hedging strategy described in snowball_v1.2.md:
- Trend basket: rotational profit-taking on the favourable side
- Counter basket: averaging-down with step-based partial closes on the adverse side
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
        "Dual-basket hedging strategy: rotational profit-taking on the trend side "
        "and averaging-down with step-based partial closes on the counter side."
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
        self._hedging_enabled: bool = True  # default; overridden by task
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
        """Parse StrategyConfiguration model into typed config."""
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
        """Estimate margin ratio as required_margin / NAV × 100.

        OANDA uses net-position margining for hedged accounts: only the larger
        side (long or short) requires margin.  We therefore compute the net
        exposure rather than summing absolute units.
        """
        nav = ss.account_nav
        if nav <= 0:
            return Decimal("0")
        all_entries = ss.trend_basket + ss.counter_basket
        if not all_entries:
            return Decimal("0")
        long_units = sum(
            abs(int(e.get("units", 0))) for e in all_entries if e.get("direction") == "long"
        )
        short_units = sum(
            abs(int(e.get("units", 0))) for e in all_entries if e.get("direction") == "short"
        )
        # OANDA charges margin on the larger leg only
        total_units = max(long_units, short_units)
        if total_units == 0:
            return Decimal("0")
        mid = ss.last_mid or Decimal("0")
        if mid <= 0:
            return Decimal("0")
        conv = quote_to_account_rate(self.instrument, mid, self.account_currency)
        margin_rate = Decimal("0.04")  # 4% = 25x leverage
        required = mid * Decimal(str(total_units)) * margin_rate * conv
        return (required / nav) * Decimal("100")

    def _avg_price(self, basket: list[dict[str, Any]]) -> Decimal:
        """Weighted average entry price of a basket."""
        total_units = Decimal("0")
        total_cost = Decimal("0")
        for e in basket:
            u = Decimal(str(abs(int(e.get("units", 0)))))
            p = Decimal(str(e.get("entry_price", "0")))
            total_units += u
            total_cost += p * u
        if total_units == 0:
            return Decimal("0")
        return total_cost / total_units

    def _next_id(self, ss: SnowballStrategyState) -> int:
        eid = ss.next_entry_id
        ss.next_entry_id += 1
        return eid

    def _make_open_event(
        self,
        ss: SnowballStrategyState,
        tick: Any,
        *,
        direction: str,
        units: int,
        step: int,
        close_price: Decimal,
        basket: str,
        lot_k: int | None = None,
    ) -> tuple[OpenPositionEvent, dict[str, Any]]:
        """Create an OpenPositionEvent and the corresponding basket entry dict."""
        eid = self._next_id(ss)
        price = tick.ask if direction == "long" else tick.bid
        is_trend = basket == "trend"
        layer = 1 if is_trend else ss.freeze_count + 1
        # For counter entries lot_k is the snowball position number
        # (trend = 1, first counter add = 2, etc.).  After a TP close
        # resets add_count the sequence restarts from 1.
        ret = 1 if is_trend else (lot_k if lot_k is not None else ss.add_count + 1)
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
        # Persist layer/retracement so close events use the same values.
        entry_dict["layer_number"] = layer
        entry_dict["retracement_count"] = ret
        event = OpenPositionEvent(
            event_type=EventType.OPEN_POSITION,
            timestamp=tick.timestamp,
            layer_number=layer,
            direction=direction,
            price=price,
            units=units,
            entry_id=eid,
            retracement_count=ret,
            strategy_event_type=f"snowball_{basket}",
            planned_exit_price=close_price,
        )
        return event, entry_dict

    def _make_close_event(
        self,
        tick: Any,
        entry: dict[str, Any],
        ss: SnowballStrategyState,
        *,
        basket: str = "counter",
    ) -> ClosePositionEvent:
        direction = str(entry.get("direction", "long"))
        entry_price = Decimal(str(entry.get("entry_price", "0")))
        exit_price = tick.bid if direction == "long" else tick.ask
        units = int(entry.get("units", 0))
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        pnl = (exit_price - entry_price) * Decimal(str(units)) * conv
        if direction == "short":
            pnl = -pnl
        # Use the layer/retracement stored at open time so close events
        # are consistent with the corresponding open events.
        is_trend = basket == "trend"
        layer = entry.get("layer_number", 1 if is_trend else ss.freeze_count + 1)
        ret = entry.get("retracement_count", 1 if is_trend else ss.add_count + 1)
        return ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            timestamp=tick.timestamp,
            layer_number=layer,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            units=units,
            pnl=pnl,
            entry_id=int(entry.get("entry_id", 0)),
            position_id=entry.get("position_id"),
            retracement_count=ret,
        )

    # ------------------------------------------------------------------
    # Core tick processing
    # ------------------------------------------------------------------

    def on_tick(self, *, tick: Any, state: Any) -> StrategyResult:
        """Process a single tick.

        Flow:
        1. Update prices / NAV
        2. Emergency stop check (ratio >= 95)
        3. Lock mode check (ratio >= n_th)
        4. Shrink mode check (ratio >= m_th)
        5. Rebalance check (ratio >= rebalance_start)
        6. Spread guard
        7. Initialise both baskets if first tick
        8. Trend basket: check profit-take → re-entry
        9. Counter basket: check step close → check add
        10. r_max cycle management
        """
        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        ss.last_bid = tick.bid
        ss.last_ask = tick.ask
        ss.last_mid = tick.mid

        # Update NAV estimate from execution state
        if hasattr(state, "current_balance") and state.current_balance:
            ss.account_balance = Decimal(str(state.current_balance))
        # NAV = balance + unrealized PnL from all open positions
        unrealized = Decimal("0")
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        for entry in ss.trend_basket + ss.counter_basket:
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
        cfg = self.config

        # --- Protection level determination ---
        ratio = self._margin_ratio(state, ss)
        ss.metrics["margin_ratio"] = str(ratio / Decimal("100"))

        if ratio >= Decimal("95"):
            # Emergency stop — always active regardless of individual protection settings
            ss.protection_level = ProtectionLevel.EMERGENCY
            events.append(
                GenericStrategyEvent(
                    event_type=EventType.STRATEGY_STOPPED,
                    timestamp=tick.timestamp,
                    data={"kind": "emergency_stop", "ratio": str(ratio)},
                )
            )
            state.strategy_state = ss.to_dict()
            return StrategyResult(
                state=state,
                events=events,
                should_stop=True,
                stop_reason=f"Emergency stop: margin ratio {ratio:.1f}% >= 95%",
            )

        # --- Lock mode ---
        if cfg.lock_enabled and ratio >= cfg.n_th and ss.protection_level != ProtectionLevel.LOCKED:
            ss.protection_level = ProtectionLevel.LOCKED
            ss.lock_entered_at = tick.timestamp.isoformat()
            # Add net-zero hedge
            long_units = sum(
                int(e.get("units", 0))
                for e in ss.trend_basket + ss.counter_basket
                if e.get("direction") == "long"
            )
            short_units = sum(
                int(e.get("units", 0))
                for e in ss.trend_basket + ss.counter_basket
                if e.get("direction") == "short"
            )
            net = long_units - short_units
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
                    "layer_number": ss.freeze_count + 1,
                    "retracement_count": ss.add_count + 1,
                }
                ss.counter_basket.append(hedge_entry)
                ss.lock_hedge_ids.append(eid)
                events.append(
                    OpenPositionEvent(
                        event_type=EventType.OPEN_POSITION,
                        timestamp=tick.timestamp,
                        direction=hedge_dir,
                        price=price,
                        units=hedge_units,
                        entry_id=eid,
                        strategy_event_type="snowball_lock_hedge",
                    )
                )
            events.append(
                GenericStrategyEvent(
                    event_type=EventType.STATUS_CHANGED,
                    timestamp=tick.timestamp,
                    data={"kind": "snowball_locked", "ratio": str(ratio)},
                )
            )
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- While locked: check unlock ---
        if ss.protection_level == ProtectionLevel.LOCKED:
            unlock_ok = ratio < cfg.m_th - Decimal("5") and (
                not cfg.spread_guard_enabled or self._spread_pips(tick) <= cfg.spread_guard_pips
            )
            if ss.cooldown_until:
                from datetime import datetime

                cd = datetime.fromisoformat(ss.cooldown_until)
                if tick.timestamp < cd:
                    unlock_ok = False
            if unlock_ok:
                # Unwind hedge in one step (simplified; spec says 2-4 splits)
                for hid in list(ss.lock_hedge_ids):
                    for basket in (ss.trend_basket, ss.counter_basket):
                        for e in list(basket):
                            if int(e.get("entry_id", 0)) == hid:
                                events.append(self._make_close_event(tick, e, ss))
                                basket.remove(e)
                ss.lock_hedge_ids = []
                ss.lock_entered_at = None
                ss.cooldown_until = None
                ss.protection_level = (
                    ProtectionLevel.SHRINK if ratio >= cfg.m_th else ProtectionLevel.NORMAL
                )
                events.append(
                    GenericStrategyEvent(
                        event_type=EventType.STATUS_CHANGED,
                        timestamp=tick.timestamp,
                        data={"kind": "snowball_unlocked", "ratio": str(ratio)},
                    )
                )
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- Shrink mode ---
        if cfg.shrink_enabled and ratio >= cfg.m_th:
            if ss.protection_level != ProtectionLevel.SHRINK:
                ss.protection_level = ProtectionLevel.SHRINK
                events.append(
                    GenericStrategyEvent(
                        event_type=EventType.STATUS_CHANGED,
                        timestamp=tick.timestamp,
                        data={"kind": "snowball_shrink", "ratio": str(ratio)},
                    )
                )
            # Close largest-loss entry from counter basket
            if ss.counter_basket:
                worst = max(
                    ss.counter_basket,
                    key=lambda e: self._unrealised_loss(e, tick),
                )
                events.append(self._make_close_event(tick, worst, ss))
                ss.counter_basket = [
                    e
                    for e in ss.counter_basket
                    if int(e.get("entry_id", 0)) != int(worst.get("entry_id", 0))
                ]
            # Hysteresis: stay in shrink until ratio < m_th - 5
            if ratio < cfg.m_th - Decimal("5"):
                ss.protection_level = ProtectionLevel.NORMAL
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # Rebalance check
        if cfg.rebalance_enabled and ratio >= cfg.rebalance_start_ratio:
            events.extend(self._rebalance(ss, tick))
            if ratio <= cfg.rebalance_end_ratio:
                pass  # done
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # Back to normal
        if ss.protection_level != ProtectionLevel.NORMAL:
            ss.protection_level = ProtectionLevel.NORMAL

        # --- Spread guard ---
        if cfg.spread_guard_enabled and self._spread_pips(tick) > cfg.spread_guard_pips:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- Initialisation: open both sides ---
        if not ss.initialised:
            events.extend(self._initialise_baskets(ss, tick))
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- Trend basket: profit-take and re-entry ---
        events.extend(self._process_trend_basket(ss, tick))

        # --- Counter basket: step close check ---
        events.extend(self._process_counter_closes(ss, tick))

        # --- Counter basket: add check ---
        events.extend(self._process_counter_adds(ss, tick))

        state.strategy_state = ss.to_dict()
        return StrategyResult(state=state, events=events)

    # ------------------------------------------------------------------
    # Sub-routines
    # ------------------------------------------------------------------

    def _unrealised_loss(self, entry: dict[str, Any], tick: Any) -> Decimal:
        """Return unrealised loss in pips (positive = losing).

        Uses mid price to avoid spread-induced distortion when measuring
        adverse distance for counter-trend add decisions.
        """
        direction = str(entry.get("direction", "long"))
        ep = Decimal(str(entry.get("entry_price", "0")))
        if direction == "long":
            return (ep - tick.mid) / self.pip_size
        return (tick.mid - ep) / self.pip_size

    def _initialise_baskets(self, ss: SnowballStrategyState, tick: Any) -> list[Any]:
        """Open initial LONG + SHORT at current price (or LONG only when hedging is disabled)."""
        cfg = self.config
        events: list[Any] = []
        trend_units = cfg.trend_lot_size * cfg.base_units

        # LONG entry (trend or counter depends on future movement; we start both)
        long_price = tick.ask
        long_close = long_price + cfg.m_pips * self.pip_size
        long_evt, long_entry = self._make_open_event(
            ss,
            tick,
            direction="long",
            units=trend_units,
            step=1,
            close_price=long_close,
            basket="trend",
        )
        ss.trend_basket.append(long_entry)
        events.append(long_evt)

        # SHORT entry — only when hedging is enabled
        if self._hedging_enabled:
            short_price = tick.bid
            short_close = short_price - cfg.m_pips * self.pip_size
            short_evt, short_entry = self._make_open_event(
                ss,
                tick,
                direction="short",
                units=trend_units,
                step=1,
                close_price=short_close,
                basket="trend",
            )
            ss.trend_basket.append(short_entry)
            events.append(short_evt)

        ss.initialised = True
        ss.cycle_base_units = cfg.base_units
        ss.add_count = 0
        return events

    def _process_trend_basket(self, ss: SnowballStrategyState, tick: Any) -> list[Any]:
        """Check trend basket for profit-take; re-enter immediately."""
        cfg = self.config
        events: list[Any] = []
        m_dyn = cfg.m_pips  # Use static m_pips; dynamic ATR adjustment is a future enhancement

        for entry in list(ss.trend_basket):
            direction = str(entry.get("direction", "long"))
            ep = Decimal(str(entry.get("entry_price", "0")))

            hit = False
            if direction == "long" and tick.bid >= ep + m_dyn * self.pip_size:
                hit = True
            elif direction == "short" and tick.ask <= ep - m_dyn * self.pip_size:
                hit = True

            if not hit:
                continue

            # Close
            events.append(self._make_close_event(tick, entry, ss, basket="trend"))
            ss.trend_basket = [
                e
                for e in ss.trend_basket
                if int(e.get("entry_id", 0)) != int(entry.get("entry_id", 0))
            ]

            # Re-entry same direction
            new_price = tick.ask if direction == "long" else tick.bid
            new_close = (
                new_price + m_dyn * self.pip_size
                if direction == "long"
                else new_price - m_dyn * self.pip_size
            )
            evt, new_entry = self._make_open_event(
                ss,
                tick,
                direction=direction,
                units=cfg.trend_lot_size * cfg.base_units,
                step=1,
                close_price=new_close,
                basket="trend",
            )
            ss.trend_basket.append(new_entry)
            events.append(evt)

        return events

    def _process_counter_closes(self, ss: SnowballStrategyState, tick: Any) -> list[Any]:
        """Check counter basket entries for step-based close targets."""
        events: list[Any] = []

        for entry in list(ss.counter_basket):
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
            step = int(entry.get("step", 1))
            max_step = max(
                int(e.get("step", 0)) for e in ss.counter_basket if not e.get("is_hedge")
            )
            if step != max_step:
                continue

            events.append(self._make_close_event(tick, entry, ss))
            ss.counter_basket = [
                e
                for e in ss.counter_basket
                if int(e.get("entry_id", 0)) != int(entry.get("entry_id", 0))
            ]
            # After closing a step, reset add_count so the next adverse-move
            # add restarts from the base lot size (trend=1x, counter=2x).
            ss.add_count = 0

            ss.metrics["counter_close_count"] = int(ss.metrics.get("counter_close_count", 0)) + 1

        return events

    def _process_counter_adds(self, ss: SnowballStrategyState, tick: Any) -> list[Any]:
        """Check whether to add a new step to the counter basket."""
        cfg = self.config
        events: list[Any] = []

        # Cannot add if f_max layers already used
        if ss.freeze_count >= cfg.f_max:
            return events

        # Cannot add if already at r_max adds
        if ss.add_count >= cfg.r_max:
            # Cycle reset
            ss.add_count = 0
            ss.freeze_count += 1
            ss.cycle_base_units = int(Decimal(str(cfg.base_units)) * cfg.post_r_max_base_factor)
            return events

        # Find the latest counter entry to measure distance from
        counter_non_hedge = [e for e in ss.counter_basket if not e.get("is_hedge")]
        if not counter_non_hedge:
            # No counter entries yet — need to determine which side is adverse.
            # The adverse side is whichever trend entry is losing.
            losing_trend = None
            for te in ss.trend_basket:
                loss = self._unrealised_loss(te, tick)
                if loss > 0 and (
                    losing_trend is None or loss > self._unrealised_loss(losing_trend, tick)
                ):
                    losing_trend = te

            if losing_trend is None:
                return events

            direction = str(losing_trend.get("direction", "long"))
            # step_k: 1-based counter add number for interval/TP calculations
            step_k = 1
            interval = counter_interval_pips(step_k, cfg)
            adverse = self._unrealised_loss(losing_trend, tick)
            if adverse < interval:
                return events

            # lot_k: snowball position number.
            # On the very first counter add (no prior closes), the trend
            # entry counts as position 1 so lot_k = 2.
            # After a TP-close reset (add_count back to 0) lot_k restarts
            # at 1 so the sequence rebuilds from the base lot size.
            prior_closes = int(ss.metrics.get("counter_close_count", 0))
            lot_k = (ss.add_count + 2) if prior_closes == 0 else (ss.add_count + 1)
            units = lot_k * ss.cycle_base_units
            tp = counter_tp_pips(step_k, cfg)
            new_price = tick.ask if direction == "long" else tick.bid
            if cfg.counter_tp_mode == "weighted_avg":
                # Include the same-direction trend entry (step 1) in the
                # weighted average so the close target accounts for the
                # full position cost basis.
                total_u = units
                total_cost = new_price * Decimal(str(units))
                for te in ss.trend_basket:
                    if str(te.get("direction", "")) == direction:
                        te_units = abs(int(te.get("units", 0)))
                        te_price = Decimal(str(te.get("entry_price", "0")))
                        total_u += te_units
                        total_cost += te_price * Decimal(str(te_units))
                close_price = total_cost / Decimal(str(total_u)) if total_u > 0 else new_price
            else:
                close_price = (
                    new_price + tp * self.pip_size
                    if direction == "long"
                    else new_price - tp * self.pip_size
                )
            evt, entry_dict = self._make_open_event(
                ss,
                tick,
                direction=direction,
                units=units,
                step=step_k + 1,  # step 1 is the initial trend entry
                close_price=close_price,
                basket="counter",
                lot_k=lot_k,
            )
            ss.counter_basket.append(entry_dict)
            ss.add_count = 1
            events.append(evt)
            return events

        # Existing counter entries — check distance from latest
        latest = max(counter_non_hedge, key=lambda e: int(e.get("step", 0)))
        direction = str(latest.get("direction", "long"))
        latest_price = Decimal(str(latest.get("entry_price", "0")))

        # Adverse distance from latest entry (use mid to avoid spread distortion)
        if direction == "long":
            adverse = (latest_price - tick.mid) / self.pip_size
        else:
            adverse = (tick.mid - latest_price) / self.pip_size

        # step_k: 1-based counter add number for interval/TP calculations
        step_k = ss.add_count + 1
        interval = counter_interval_pips(step_k, cfg)

        if adverse < interval:
            return events

        # lot_k: same logic as first-add path.
        prior_closes = int(ss.metrics.get("counter_close_count", 0))
        lot_k = (ss.add_count + 2) if prior_closes == 0 else (ss.add_count + 1)
        units = lot_k * ss.cycle_base_units
        tp = counter_tp_pips(step_k, cfg)

        # Compute avg price including all counter entries + this new one,
        # plus the same-direction trend entry (step 1) which is conceptually
        # part of the position but lives in the trend basket.
        all_counter = counter_non_hedge
        total_u = sum(int(e.get("units", 0)) for e in all_counter) + units
        total_cost = sum(
            Decimal(str(e.get("entry_price", "0"))) * Decimal(str(int(e.get("units", 0))))
            for e in all_counter
        )
        new_price = tick.ask if direction == "long" else tick.bid
        total_cost += new_price * Decimal(str(units))
        # Include same-direction trend entry in weighted average
        for te in ss.trend_basket:
            if str(te.get("direction", "")) == direction:
                te_units = abs(int(te.get("units", 0)))
                te_price = Decimal(str(te.get("entry_price", "0")))
                total_u += te_units
                total_cost += te_price * Decimal(str(te_units))
        avg = total_cost / Decimal(str(total_u)) if total_u > 0 else new_price

        if cfg.counter_tp_mode == "weighted_avg":
            close_price = avg  # tp is 0 for weighted_avg
        else:
            close_price = (
                new_price + tp * self.pip_size
                if direction == "long"
                else new_price - tp * self.pip_size
            )

        evt, entry_dict = self._make_open_event(
            ss,
            tick,
            direction=direction,
            units=units,
            step=int(latest.get("step", 1)) + 1,
            close_price=close_price,
            basket="counter",
            lot_k=lot_k,
        )
        ss.counter_basket.append(entry_dict)
        ss.add_count += 1

        # Update close prices for existing counter entries (non-weighted_avg modes only).
        # In weighted_avg mode each entry's close_price is the cumulative weighted
        # average at the time it was added and must NOT be overwritten.
        if cfg.counter_tp_mode != "weighted_avg":
            for e in ss.counter_basket:
                if e.get("is_hedge"):
                    continue
                step_k = int(e.get("step", 1)) - 1  # 0-based for tp calc
                if step_k < 1:
                    step_k = 1
                step_tp = counter_tp_pips(step_k, cfg)
                base_price = Decimal(str(e.get("entry_price", "0")))
                e["close_price"] = str(
                    base_price + step_tp * self.pip_size
                    if direction == "long"
                    else base_price - step_tp * self.pip_size
                )

        events.append(evt)
        return events

    def _rebalance(self, ss: SnowballStrategyState, tick: Any) -> list[Any]:
        """Reduce BUY/SELL imbalance by closing oldest counter entries."""
        events: list[Any] = []
        long_units = sum(
            int(e.get("units", 0))
            for e in ss.trend_basket + ss.counter_basket
            if e.get("direction") == "long"
        )
        short_units = sum(
            int(e.get("units", 0))
            for e in ss.trend_basket + ss.counter_basket
            if e.get("direction") == "short"
        )
        if long_units == short_units:
            return events

        # Close oldest counter entries on the heavier side
        heavier = "long" if long_units > short_units else "short"
        counter_sorted = sorted(
            [
                e
                for e in ss.counter_basket
                if e.get("direction") == heavier and not e.get("is_hedge")
            ],
            key=lambda e: int(e.get("step", 0)),
        )
        for entry in counter_sorted:
            events.append(self._make_close_event(tick, entry, ss))
            ss.counter_basket = [
                e
                for e in ss.counter_basket
                if int(e.get("entry_id", 0)) != int(entry.get("entry_id", 0))
            ]
            # Recheck balance
            long_units = sum(
                int(e.get("units", 0))
                for e in ss.trend_basket + ss.counter_basket
                if e.get("direction") == "long"
            )
            short_units = sum(
                int(e.get("units", 0))
                for e in ss.trend_basket + ss.counter_basket
                if e.get("direction") == "short"
            )
            if long_units == short_units:
                break
        return events

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

        for basket in (ss.trend_basket, ss.counter_basket):
            for entry in basket:
                if int(entry.get("entry_id", 0)) == int(eid):
                    entry["position_id"] = str(position_id)

        state.strategy_state = ss.to_dict()
