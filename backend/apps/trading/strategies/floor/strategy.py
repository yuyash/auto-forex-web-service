"""Trading engine for Floor strategy.

This is the main component that orchestrates all trading operations.
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from apps.trading.enums import EventType, StrategyType
from apps.trading.events import (
    AddLayerEvent,
    GenericStrategyEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
    RemoveLayerEvent,
    RetracementEvent,
    TakeProfitEvent,
    VolatilityHedgeNeutralizeEvent,
    VolatilityLockEvent,
)
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.floor.calculators import TrendDetector
from apps.trading.strategies.floor.candle import CandleManager
from apps.trading.strategies.floor.enums import StrategyStatus
from apps.trading.strategies.floor.hedge_neutralizer import HedgeNeutralizer
from apps.trading.strategies.floor.models import (
    FloorStrategyConfig,
    FloorStrategyState,
)
from apps.trading.strategies.registry import register_strategy
from apps.trading.utils import quote_to_account_rate

logger: Logger = getLogger(name=__name__)


@register_strategy(
    id="floor",
    schema="trading/schemas/floor.json",
    display_name="Floor Strategy",
)
class FloorStrategy(Strategy):
    """Main trading engine for Floor strategy.

    This is the primary component that:
    - Manages all trading components (candles, layers, margin, etc.)
    - Implements strategy-specific decision logic
    - Orchestrates the complete trading flow
    - Processes ticks and generates events
    """

    def __init__(
        self,
        instrument: str,
        pip_size: Decimal,
        config: FloorStrategyConfig,
        trading_mode: str = "hedging",
    ) -> None:
        """Initialize trading engine.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for instrument
            config: Strategy configuration
            trading_mode: "netting" enforces FIFO close order (US regulation),
                          "hedging" allows LIFO / independent closes (JP, etc.)
        """
        super().__init__(instrument, pip_size, config)

        self.trading_mode = trading_mode

        # Components
        self.candle_manager = CandleManager(config)
        self.trend_detector = TrendDetector()

        logger.info(
            "Initialized Floor trading engine: instrument=%s, pip_size=%s, hedging=%s, trading_mode=%s",
            instrument,
            pip_size,
            config.hedging_enabled,
            trading_mode,
        )

    @staticmethod
    def parse_config(strategy_config) -> FloorStrategyConfig:
        """Parse configuration from StrategyConfiguration model.

        Args:
            strategy_config: StrategyConfiguration model instance

        Returns:
            Parsed FloorStrategyConfig
        """
        return FloorStrategyConfig.from_dict(strategy_config.config_dict)

    @property
    def strategy_type(self) -> StrategyType:
        """Return strategy type."""
        return StrategyType.FLOOR

    @staticmethod
    def _normalize_direction(value: str | None) -> str:
        val = str(value or "").strip().lower()
        if val not in {"long", "short"}:
            return "long"
        return val

    def _price_for_open(self, direction: str, tick) -> Decimal:
        return tick.ask if direction == "long" else tick.bid

    def _price_for_close(self, direction: str, tick) -> Decimal:
        return tick.bid if direction == "long" else tick.ask

    def _pips_for_entry(self, direction: str, entry_price: Decimal, tick) -> Decimal:
        if direction == "long":
            return (tick.bid - entry_price) / self.pip_size
        return (entry_price - tick.ask) / self.pip_size

    def _adverse_pips_from_entry(self, direction: str, entry_price: Decimal, tick) -> Decimal:
        if direction == "long":
            return (entry_price - tick.ask) / self.pip_size
        return (tick.bid - entry_price) / self.pip_size

    def _choose_direction(self, floor_state: FloorStrategyState) -> str:
        closes = self.candle_manager.get_candle_closes(floor_state)
        direction = self.trend_detector.detect_direction(closes)
        return direction.value

    def _lots_to_units(self, lots: Decimal) -> int:
        raw_units = lots * self.config.lot_unit_size
        units = int(raw_units)
        return max(units, 1)

    def _entry_units(
        self,
        floor_state: FloorStrategyState,
        floor_index: int,
        lots: Decimal,
    ) -> int:
        units = self._lots_to_units(lots)
        if self.config.allow_duplicate_units:
            return units

        existing = {
            int(item.get("units", 0))
            for item in floor_state.open_entries
            if int(item.get("floor_index", -1)) == floor_index
        }
        while units in existing:
            units += 1
        return units

    def _open_entry(
        self,
        floor_state: FloorStrategyState,
        tick,
        *,
        floor_index: int,
        direction: str,
        units: int,
        take_profit_pips: Decimal,
        is_initial: bool,
    ) -> Any:
        direction = self._normalize_direction(direction)
        entry_price = self._price_for_open(direction, tick)
        entry_id = floor_state.next_entry_id
        floor_state.next_entry_id += 1

        floor_state.floor_directions[floor_index] = direction
        floor_state.open_entries.append(
            {
                "entry_id": entry_id,
                "floor_index": floor_index,
                "direction": direction,
                "entry_price": str(entry_price),
                "units": units,
                "take_profit_pips": str(take_profit_pips),
                "opened_at": tick.timestamp.isoformat(),
                "is_initial": is_initial,
            }
        )

        if is_initial:
            return InitialEntryEvent(
                event_type=EventType.INITIAL_ENTRY,
                timestamp=tick.timestamp,
                layer_number=floor_index,
                direction=direction,
                price=entry_price,
                units=units,
                entry_time=tick.timestamp,
                retracement_count=0,
            )

        retracement_count = floor_state.floor_retracement_counts.get(floor_index, 0)
        return RetracementEvent(
            event_type=EventType.RETRACEMENT,
            timestamp=tick.timestamp,
            layer_number=floor_index,
            direction=direction,
            price=entry_price,
            units=units,
            entry_time=tick.timestamp,
            retracement_count=retracement_count,
        )

    @staticmethod
    def _active_floor_entries(
        floor_state: FloorStrategyState,
        floor_index: int,
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in floor_state.open_entries
            if int(item.get("floor_index", -1)) == floor_index
        ]

    def _spread_pips(self, tick) -> Decimal:
        return (tick.ask - tick.bid) / self.pip_size

    def _estimate_unrealized(self, floor_state: FloorStrategyState, tick) -> Decimal:
        total = Decimal("0")
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        for entry in floor_state.open_entries:
            direction = self._normalize_direction(str(entry.get("direction", "long")))
            units = Decimal(str(entry.get("units", 0)))
            entry_price = Decimal(str(entry.get("entry_price", "0")))
            pnl_pips = self._pips_for_entry(direction, entry_price, tick)
            total += pnl_pips * self.pip_size * units * conv
        return total

    def _estimate_nav(self, state, floor_state: FloorStrategyState, tick) -> Decimal:
        # current_balance starts from initial balance and is incremented by realized pnl.
        base_balance = Decimal(str(getattr(state, "current_balance", "0") or "0"))
        floor_state.account_balance = base_balance
        floor_state.account_nav = base_balance + self._estimate_unrealized(floor_state, tick)
        return floor_state.account_nav

    def _margin_ratio(self, state, floor_state: FloorStrategyState, tick) -> Decimal:
        total_units = Decimal(
            str(sum(abs(int(item.get("units", 0))) for item in floor_state.open_entries))
        )
        if total_units <= 0:
            return Decimal("0")
        nav = self._estimate_nav(state, floor_state, tick)
        if nav <= 0:
            return Decimal("999")
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        required = tick.mid * total_units * self.config.margin_rate * conv
        return required / nav

    def _estimate_atr_pips(self, floor_state: FloorStrategyState, period: int) -> Decimal:
        candles = self.candle_manager.get_candles(floor_state)
        if len(candles) < 2:
            return Decimal("0")

        true_ranges: list[Decimal] = []
        for i in range(1, len(candles)):
            cur = candles[i]
            prev_close = candles[i - 1].close_price
            high = cur.high_price if cur.high_price is not None else cur.close_price
            low = cur.low_price if cur.low_price is not None else cur.close_price
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            true_ranges.append(tr / self.pip_size)

        window = true_ranges[-max(1, period) :]
        if not window:
            return Decimal("0")
        return sum(window, Decimal("0")) / Decimal(len(window))

    def _is_bad_market_condition(self, tick) -> bool:
        if not self.config.market_condition_override_enabled:
            return False
        return self._spread_pips(tick) >= self.config.market_condition_spread_limit_pips

    def _effective_take_profit(
        self, floor_state: FloorStrategyState, floor_index: int, retracement_index: int = 0
    ) -> Decimal:
        """Return take-profit pips with intra-layer and optional ATR adjustment.

        Args:
            floor_state: Current strategy state
            floor_index: Active layer index (cross-layer progression)
            retracement_index: Retracement count within the layer (intra-layer progression)
        """
        base_take_profit = self.config.intra_layer_take_profit_pips(floor_index, retracement_index)
        if not self.config.dynamic_parameter_adjustment_enabled:
            return base_take_profit
        current_atr = self._estimate_atr_pips(floor_state, self.config.atr_period)
        baseline = self._estimate_atr_pips(floor_state, self.config.atr_baseline_period)
        if baseline <= 0:
            return base_take_profit
        ratio = current_atr / baseline
        if ratio >= Decimal("2"):
            return base_take_profit * Decimal("1.5")
        if ratio <= Decimal("0.7"):
            return base_take_profit * Decimal("0.8")
        return base_take_profit

    def _effective_retracement_trigger(
        self,
        floor_state: FloorStrategyState,
        floor_index: int,
    ) -> Decimal:
        base_retracement = self.config.floor_retracement_pips(floor_index)
        if not self.config.dynamic_parameter_adjustment_enabled:
            return base_retracement
        current_atr = self._estimate_atr_pips(floor_state, self.config.atr_period)
        baseline = self._estimate_atr_pips(floor_state, self.config.atr_baseline_period)
        if baseline <= 0:
            return base_retracement
        ratio = current_atr / baseline
        if ratio >= Decimal("2"):
            return base_retracement * Decimal("1.5")
        if ratio <= Decimal("0.7"):
            return base_retracement * Decimal("0.8")
        return base_retracement

    def _retracement_lots(self, retracement_index: int) -> Decimal:
        """Return lot size for Nth additional entry (0-based).

        Uses the same 5-mode Progression logic as cross-layer parameters:
        constant / additive / subtractive / multiplicative / divisive.
        """
        if retracement_index < 0:
            return self.config.base_lot_size

        idx = retracement_index + 1
        mode = self.config.retracement_lot_mode

        if mode == "constant":
            return self.config.base_lot_size

        if mode == "additive":
            return self.config.base_lot_size + (self.config.retracement_lot_amount * Decimal(idx))

        if mode == "subtractive":
            result = self.config.base_lot_size - (self.config.retracement_lot_amount * Decimal(idx))
            return max(result, Decimal("0.01"))

        if mode == "multiplicative":
            multiplier = Decimal(2**idx)
            return self.config.base_lot_size * multiplier

        # divisive (formerly "inverse")
        divisor = Decimal(2**idx)
        result = self.config.base_lot_size / divisor
        return max(result, Decimal("0.01"))

    def _recompute_floor_retracements(self, floor_state: FloorStrategyState) -> None:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for entry in floor_state.open_entries:
            floor_index = int(entry.get("floor_index", 0))
            grouped.setdefault(floor_index, []).append(entry)
        for floor_index, entries in grouped.items():
            initial_count = sum(1 for item in entries if bool(item.get("is_initial")))
            retracements = max(0, len(entries) - initial_count)
            floor_state.floor_retracement_counts[floor_index] = retracements

    def _apply_margin_protection(self, state, floor_state: FloorStrategyState, tick) -> list[Any]:
        margin_ratio = self._margin_ratio(state, floor_state, tick)
        if margin_ratio < self.config.margin_cut_start_ratio:
            return []

        total_units = sum(int(item.get("units", 0)) for item in floor_state.open_entries)
        if total_units <= 0:
            return []

        nav = max(Decimal("1"), floor_state.account_nav)
        target_required_margin = self.config.margin_cut_target_ratio * nav
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        target_units = int(target_required_margin / (tick.mid * self.config.margin_rate * conv))
        units_to_close = max(0, total_units - target_units)
        if units_to_close <= 0:
            return []

        ordered_entries = sorted(
            floor_state.open_entries,
            key=lambda item: (
                int(item.get("floor_index", 0)),
                str(item.get("opened_at", "")),
                int(item.get("entry_id", 0)),
            ),
        )
        closed_positions = 0
        closed_units = 0
        updated_entries: list[dict[str, Any]] = []
        for item in ordered_entries:
            units = int(item.get("units", 0))
            if units <= 0:
                continue

            remaining_to_close = units_to_close - closed_units
            if remaining_to_close <= 0:
                updated_entries.append(item)
                continue

            close_for_this_entry = min(units, remaining_to_close)
            remaining_units = units - close_for_this_entry
            closed_units += close_for_this_entry
            closed_positions += 1

            if remaining_units > 0:
                new_item = dict(item)
                new_item["units"] = remaining_units
                updated_entries.append(new_item)

        floor_state.open_entries = updated_entries
        self._recompute_floor_retracements(floor_state)
        return [
            MarginProtectionEvent(
                event_type=EventType.MARGIN_PROTECTION,
                timestamp=tick.timestamp,
                reason=(
                    f"margin_ratio={margin_ratio:.2%} reached cut_start="
                    f"{self.config.margin_cut_start_ratio:.2%}"
                ),
                current_margin=margin_ratio,
                threshold=self.config.margin_cut_start_ratio,
                positions_closed=closed_positions,
                units_to_close=closed_units,
            )
        ]

    def on_tick(self, *, tick, state) -> Any:
        """Process a tick and return updated state and events.

        Args:
            tick: Tick dataclass containing market data
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        from apps.trading.dataclasses import StrategyResult

        floor_state = FloorStrategyState.from_strategy_state(state.strategy_state)
        floor_state.last_mid = tick.mid
        floor_state.last_bid = tick.bid
        floor_state.last_ask = tick.ask
        self.candle_manager.update_from_tick(floor_state, tick.timestamp, tick.mid)
        self._estimate_nav(state, floor_state, tick)

        events: list[Any] = []

        # 0) Volatility lock/unlock control (optional).
        if self.config.volatility_check_enabled:
            current_atr = self._estimate_atr_pips(floor_state, self.config.atr_period)
            baseline_atr = self._estimate_atr_pips(floor_state, self.config.atr_baseline_period)
            if baseline_atr > 0:
                lock_threshold = baseline_atr * self.config.volatility_lock_multiplier
                unlock_threshold = baseline_atr * self.config.volatility_unlock_multiplier
                if (
                    not floor_state.volatility_locked
                    and current_atr >= lock_threshold
                    and floor_state.open_entries
                ):
                    floor_state.volatility_locked = True
                    floor_state.status = StrategyStatus.PAUSED

                    if self.config.hedging_enabled:
                        # Hedge-neutralize: open mirror positions to zero-out
                        # net exposure without realizing losses.
                        instructions = HedgeNeutralizer.compute_hedge_instructions(
                            floor_state.open_entries,
                        )
                        floor_state.hedge_neutralized = True
                        floor_state.lock_reason = (
                            f"[HEDGE_NEUTRALIZE] atr={current_atr:.2f}"
                            f" >= threshold={lock_threshold:.2f}"
                        )
                        # Record hedge entry ids so we can unwind them on unlock.
                        hedge_ids: list[int] = []
                        for instr in instructions:
                            eid = floor_state.next_entry_id
                            floor_state.next_entry_id += 1
                            hedge_ids.append(eid)
                            floor_state.open_entries.append(
                                {
                                    "entry_id": eid,
                                    "floor_index": instr.layer_index,
                                    "direction": instr.direction,
                                    "entry_price": str(tick.mid),
                                    "units": instr.units,
                                    "take_profit_pips": "0",
                                    "opened_at": tick.timestamp.isoformat(),
                                    "is_initial": False,
                                    "is_hedge": True,
                                    "source_entry_id": instr.source_entry_id,
                                }
                            )
                        floor_state.hedge_entry_ids = hedge_ids
                        events.append(
                            VolatilityHedgeNeutralizeEvent(
                                event_type=EventType.VOLATILITY_HEDGE_NEUTRALIZE,
                                timestamp=tick.timestamp,
                                reason=floor_state.lock_reason,
                                atr_value=current_atr,
                                threshold=lock_threshold,
                                hedge_instructions=[i.to_dict() for i in instructions],
                            )
                        )
                    else:
                        # Non-hedging: close all positions outright.
                        floor_state.lock_reason = (
                            f"[CLOSE] atr={current_atr:.2f} >= threshold={lock_threshold:.2f}"
                        )
                        events.append(
                            VolatilityLockEvent(
                                event_type=EventType.VOLATILITY_LOCK,
                                timestamp=tick.timestamp,
                                reason=floor_state.lock_reason,
                                atr_value=current_atr,
                                threshold=lock_threshold,
                            )
                        )
                elif floor_state.volatility_locked and current_atr <= unlock_threshold:
                    was_hedge_neutralized = floor_state.hedge_neutralized
                    floor_state.volatility_locked = False
                    floor_state.status = StrategyStatus.RUNNING
                    floor_state.lock_reason = ""

                    if was_hedge_neutralized:
                        # Unwind: remove all hedge entries and their source
                        # originals from open_entries so the strategy restarts
                        # with a clean slate on the next tick.
                        hedge_ids_set = set(floor_state.hedge_entry_ids)
                        # Find source entry ids that were hedged.
                        source_ids: set[int] = set()
                        for entry in floor_state.open_entries:
                            if int(entry.get("entry_id", 0)) in hedge_ids_set:
                                source_ids.add(int(entry.get("source_entry_id", 0)))
                        # Emit a VolatilityLockEvent with [CLOSE] to close
                        # all remaining positions via the event handler.
                        floor_state.open_entries = [
                            e
                            for e in floor_state.open_entries
                            if int(e.get("entry_id", 0)) not in hedge_ids_set
                            and int(e.get("entry_id", 0)) not in source_ids
                        ]
                        floor_state.hedge_neutralized = False
                        floor_state.hedge_entry_ids = []
                        events.append(
                            VolatilityLockEvent(
                                event_type=EventType.VOLATILITY_LOCK,
                                timestamp=tick.timestamp,
                                reason="[CLOSE] unwind hedge-neutralized positions",
                                atr_value=current_atr,
                                threshold=unlock_threshold,
                            )
                        )
                        # Reset layer state so strategy re-enters fresh.
                        floor_state.floor_retracement_counts = {}
                        floor_state.floor_directions = {}
                        floor_state.return_stack = []
                        floor_state.active_floor_index = 0
                        floor_state.home_floor_index = 0

                    events.append(
                        GenericStrategyEvent(
                            event_type=EventType.STATUS_CHANGED,
                            timestamp=tick.timestamp,
                            data={
                                "kind": "volatility_unlock",
                                "atr": str(current_atr),
                                "threshold": str(unlock_threshold),
                                "was_hedge_neutralized": was_hedge_neutralized,
                            },
                        )
                    )
        elif floor_state.volatility_locked:
            # Safety: if operator disables the check mid-run, unlock immediately.
            floor_state.volatility_locked = False
            floor_state.status = StrategyStatus.RUNNING
            floor_state.lock_reason = ""
            events.append(
                GenericStrategyEvent(
                    event_type=EventType.STATUS_CHANGED,
                    timestamp=tick.timestamp,
                    data={"kind": "volatility_check_disabled_unlock"},
                )
            )

        # 1) Margin protection (closeout from 60% down to 50% equivalent).
        if self.config.margin_protection_enabled:
            margin_events = self._apply_margin_protection(state, floor_state, tick)
            if margin_events:
                events.extend(margin_events)
                # After margin protection fires, bail out like take-profit
                # to avoid immediately re-entering on the same tick.
                logger.debug(
                    "on_tick early return: margin_protection fired at %s",
                    tick.timestamp,
                )
                state.strategy_state = floor_state.to_dict()
                return StrategyResult(state=state, events=events)

        # Locked state: only monitoring
        if floor_state.volatility_locked:
            logger.debug(
                "on_tick early return: volatility_locked at %s",
                tick.timestamp,
            )
            state.strategy_state = floor_state.to_dict()
            return StrategyResult(state=state, events=events)

        active_floor = floor_state.active_floor_index
        floor_state.floor_retracement_counts.setdefault(active_floor, 0)

        # If no positions remain and margin ratio is still blown (balance
        # is too low to support even the minimum position), stop the task
        # to prevent an infinite open-then-close loop.
        all_entries = floor_state.open_entries
        if not all_entries:
            margin_ratio = self._margin_ratio(state, floor_state, tick)
            # _margin_ratio returns 0 when there are no positions, so we
            # check the *would-be* margin for a single base-lot entry.
            min_units = int(self.config.base_lot_size)
            nav = max(Decimal("1"), floor_state.account_nav)
            conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
            hypothetical_margin = (
                tick.mid * Decimal(str(min_units)) * self.config.margin_rate * conv
            ) / nav
            if hypothetical_margin >= self.config.margin_cut_target_ratio:
                logger.warning(
                    "Margin blow-out: no open positions and hypothetical margin "
                    "ratio %.4f >= target %.4f — requesting task stop",
                    hypothetical_margin,
                    self.config.margin_cut_target_ratio,
                )
                events.append(
                    GenericStrategyEvent(
                        event_type=EventType.STRATEGY_STOPPED,
                        timestamp=tick.timestamp,
                        data={
                            "kind": "margin_blowout_stop",
                            "hypothetical_margin_ratio": str(hypothetical_margin),
                            "margin_cut_target_ratio": str(self.config.margin_cut_target_ratio),
                            "nav": str(nav),
                        },
                    )
                )
                state.strategy_state = floor_state.to_dict()
                return StrategyResult(
                    state=state,
                    events=events,
                    should_stop=True,
                    stop_reason=(
                        f"Margin blow-out: hypothetical margin ratio "
                        f"{hypothetical_margin:.4f} >= target "
                        f"{self.config.margin_cut_target_ratio:.4f} with no open positions"
                    ),
                )

        active_entries = self._active_floor_entries(floor_state, active_floor)
        if not active_entries:
            if self._is_bad_market_condition(tick):
                events.append(
                    GenericStrategyEvent(
                        event_type=EventType.STRATEGY_SIGNAL,
                        timestamp=tick.timestamp,
                        data={
                            "kind": "entry_skipped",
                            "reason": "market_condition_override",
                            "spread_pips": str(self._spread_pips(tick)),
                        },
                    )
                )
                state.strategy_state = floor_state.to_dict()
                return StrategyResult(state=state, events=events)
            direction = self._choose_direction(floor_state)
            units = self._entry_units(floor_state, active_floor, self.config.base_lot_size)
            events.append(
                self._open_entry(
                    floor_state,
                    tick,
                    floor_index=active_floor,
                    direction=direction,
                    units=units,
                    take_profit_pips=self._effective_take_profit(floor_state, active_floor),
                    is_initial=True,
                )
            )
            state.strategy_state = floor_state.to_dict()
            return StrategyResult(state=state, events=events)

        # 1) Take profit: LIFO (newest first) in hedging mode,
        #    FIFO (oldest first) in netting mode (US FIFO regulation).
        fifo_mode = self.trading_mode == "netting"
        closed_any = False
        for entry in sorted(
            active_entries, key=lambda item: int(item.get("entry_id", 0)), reverse=not fifo_mode
        ):
            direction = self._normalize_direction(str(entry.get("direction", "long")))
            entry_price = Decimal(str(entry.get("entry_price", "0")))
            tp_pips = Decimal(
                str(
                    entry.get(
                        "take_profit_pips",
                        self._effective_take_profit(floor_state, active_floor),
                    )
                )
            )
            pnl_pips = self._pips_for_entry(direction, entry_price, tick)
            if pnl_pips < tp_pips:
                continue

            exit_price = self._price_for_close(direction, tick)
            units = int(entry.get("units", 0))
            conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
            pnl_amount = (exit_price - entry_price) * Decimal(units) * conv
            if direction == "short":
                pnl_amount = -pnl_amount

            events.append(
                TakeProfitEvent(
                    event_type=EventType.TAKE_PROFIT,
                    timestamp=tick.timestamp,
                    layer_number=active_floor,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    units=units,
                    pnl=pnl_amount,
                    pips=pnl_pips,
                    entry_time=None,
                    exit_time=tick.timestamp,
                    retracement_count=floor_state.floor_retracement_counts.get(active_floor, 0),
                )
            )
            floor_state.open_entries = [
                item
                for item in floor_state.open_entries
                if int(item.get("entry_id", 0)) != int(entry.get("entry_id", 0))
            ]
            metrics = floor_state.metrics
            metrics["take_profit_count"] = int(metrics.get("take_profit_count", 0)) + 1
            closed_any = True

        if closed_any:
            # Recompute retracement count from remaining entries instead of
            # resetting to zero – only the closed entries should be subtracted.
            self._recompute_floor_retracements(floor_state)
            remaining_active = self._active_floor_entries(floor_state, active_floor)
            if not remaining_active and active_floor != floor_state.home_floor_index:
                events.append(
                    RemoveLayerEvent(
                        event_type=EventType.REMOVE_LAYER,
                        timestamp=tick.timestamp,
                        layer_number=active_floor,
                        remove_time=tick.timestamp,
                    )
                )
                if floor_state.return_stack:
                    floor_state.active_floor_index = floor_state.return_stack.pop()
                else:
                    floor_state.active_floor_index = floor_state.home_floor_index
                active_floor = floor_state.active_floor_index

            # After taking profit, do NOT open new entries on the same tick.
            # Wait for the next tick to re-evaluate market conditions.
            logger.debug(
                "on_tick early return: take_profit at %s",
                tick.timestamp,
            )
            state.strategy_state = floor_state.to_dict()
            return StrategyResult(state=state, events=events)

        active_entries = self._active_floor_entries(floor_state, active_floor)

        # 2) Additional entry when adverse move hits trigger.
        latest_entry = max(
            active_entries,
            key=lambda item: int(item.get("entry_id", 0)),
        )
        direction = self._normalize_direction(str(latest_entry.get("direction", "long")))
        latest_entry_price = Decimal(str(latest_entry.get("entry_price", "0")))
        adverse_pips = self._adverse_pips_from_entry(direction, latest_entry_price, tick)

        current_retracements = floor_state.floor_retracement_counts.get(active_floor, 0)
        trigger_threshold = self._effective_retracement_trigger(floor_state, active_floor)
        if (
            adverse_pips >= trigger_threshold
            and current_retracements < self.config.max_retracements_per_layer
            and not self._is_bad_market_condition(tick)
        ):
            lots = self._retracement_lots(current_retracements)
            units = self._entry_units(floor_state, active_floor, lots)
            floor_state.floor_retracement_counts[active_floor] = current_retracements + 1
            events.append(
                self._open_entry(
                    floor_state,
                    tick,
                    floor_index=active_floor,
                    direction=direction,
                    units=units,
                    take_profit_pips=self._effective_take_profit(
                        floor_state, active_floor, current_retracements + 1
                    ),
                    is_initial=False,
                )
            )
            metrics = floor_state.metrics
            metrics["retracement_entry_count"] = int(metrics.get("retracement_entry_count", 0)) + 1
        elif self._is_bad_market_condition(tick):
            events.append(
                GenericStrategyEvent(
                    event_type=EventType.STRATEGY_SIGNAL,
                    timestamp=tick.timestamp,
                    data={
                        "kind": "retracement_skipped",
                        "reason": "market_condition_override",
                        "spread_pips": str(self._spread_pips(tick)),
                    },
                )
            )
        elif (
            adverse_pips >= trigger_threshold
            and current_retracements >= self.config.max_retracements_per_layer
            and floor_state.active_floor_index < (self.config.max_layers - 1)
        ):
            # 3) Move to new floor and restart from initial lot.
            new_floor = floor_state.active_floor_index + 1
            floor_state.return_stack.append(floor_state.active_floor_index)
            floor_state.active_floor_index = new_floor
            floor_state.floor_retracement_counts.setdefault(new_floor, 0)
            events.append(
                AddLayerEvent(
                    event_type=EventType.ADD_LAYER,
                    timestamp=tick.timestamp,
                    layer_number=new_floor,
                    add_time=tick.timestamp,
                )
            )
            new_direction = self._choose_direction(floor_state)
            initial_units = self._entry_units(floor_state, new_floor, self.config.base_lot_size)
            events.append(
                self._open_entry(
                    floor_state,
                    tick,
                    floor_index=new_floor,
                    direction=new_direction,
                    units=initial_units,
                    take_profit_pips=self._effective_take_profit(floor_state, new_floor),
                    is_initial=True,
                )
            )

        # Record per-tick metrics for replay visualization.
        margin_ratio = self._margin_ratio(state, floor_state, tick)
        current_atr = self._estimate_atr_pips(floor_state, self.config.atr_period)
        baseline_atr = self._estimate_atr_pips(floor_state, self.config.atr_baseline_period)
        vol_threshold = (
            baseline_atr * self.config.volatility_lock_multiplier
            if baseline_atr > 0
            else Decimal("0")
        )
        floor_state.metrics["margin_ratio"] = str(margin_ratio)
        floor_state.metrics["current_atr"] = str(current_atr)
        floor_state.metrics["baseline_atr"] = str(baseline_atr)
        floor_state.metrics["volatility_threshold"] = str(vol_threshold)

        state.strategy_state = floor_state.to_dict()
        return StrategyResult(state=state, events=events)
