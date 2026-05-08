"""Calculators for Snowball strategy.

Implements the interval formula and step-based take-profit calculations
described in the Snowball v1.2 specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.trading.strategies.snowball.config import SnowballStrategyConfig


class SnowballFormulaCalculator(Protocol):
    """Interface required by Snowball strategy flow collaborators."""

    def counter_interval_pips(self, k: int) -> Decimal:
        """Return the pip interval before the *k*-th add."""
        ...

    def stop_loss_pips(self, k: int) -> Decimal:
        """Return the stop-loss distance for the *k*-th slot."""
        ...

    def rebuild_take_profit_pips(self, k: int) -> Decimal:
        """Return the rebuilt-position take-profit distance for the *k*-th slot."""
        ...

    def counter_tp_pips(self, k: int) -> Decimal:
        """Return the take-profit pips for the *k*-th counter step."""
        ...


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round *value* to the nearest multiple of *step*.

    >>> round_to_step(Decimal("29.3"), Decimal("0.5"))
    Decimal('29.5')
    """
    if step <= 0:
        return value
    return (value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


@dataclass(frozen=True, slots=True)
class SnowballCalculator:
    """Config-bound Snowball formula calculator."""

    config: "SnowballStrategyConfig"

    def counter_interval_pips(self, k: int) -> Decimal:
        """Return the pip interval before the *k*-th add (1-based)."""
        cfg = self.config
        if cfg.interval_mode == "manual" and cfg.manual_intervals:
            idx = min(k - 1, len(cfg.manual_intervals) - 1)
            return round_to_step(cfg.manual_intervals[idx], cfg.round_step_pips)

        head = cfg.n_pips_head

        if cfg.interval_mode == "constant":
            return round_to_step(head, cfg.round_step_pips)

        tail = cfg.n_pips_tail
        flat = cfg.n_pips_flat_steps
        gamma = cfg.n_pips_gamma

        if k <= flat:
            return round_to_step(head, cfg.round_step_pips)

        t = k - flat
        r_decay = cfg.r_max - flat
        if r_decay <= 0:
            return round_to_step(tail, cfg.round_step_pips)

        progress = Decimal(str(t)) / Decimal(str(r_decay))
        curved = progress**gamma
        interval = head - (head - tail) * curved
        return round_to_step(max(interval, tail), cfg.round_step_pips)

    def stop_loss_pips(self, k: int) -> Decimal:
        """Return the pip distance from entry to stop-loss for the *k*-th slot."""
        cfg = self.config
        return _progression_pips(
            k=k,
            mode=cfg.stop_loss_mode,
            head=cfg.stop_loss_pips_head,
            tail=cfg.stop_loss_pips_tail,
            flat_steps=cfg.stop_loss_pips_flat_steps,
            gamma=cfg.stop_loss_pips_gamma,
            r_max=cfg.r_max,
            manual_values=cfg.stop_loss_manual_pips,
            round_step=cfg.round_step_pips,
        )

    def rebuild_take_profit_pips(self, k: int) -> Decimal:
        """Return the rebuilt-position take-profit distance for the *k*-th slot."""
        cfg = self.config
        return _progression_pips(
            k=k,
            mode=cfg.rebuild_take_profit_mode,
            head=cfg.rebuild_take_profit_pips_head,
            tail=cfg.rebuild_take_profit_pips_tail,
            flat_steps=cfg.rebuild_take_profit_pips_flat_steps,
            gamma=cfg.rebuild_take_profit_pips_gamma,
            r_max=cfg.r_max,
            manual_values=cfg.rebuild_take_profit_manual_pips,
            round_step=cfg.round_step_pips,
        )

    def counter_tp_pips(self, k: int) -> Decimal:
        """Return the take-profit pips for the *k*-th step (1-based)."""
        cfg = self.config
        mode = cfg.counter_tp_mode
        base = cfg.counter_tp_pips
        step = cfg.round_step_pips

        if mode == "weighted_avg":
            return Decimal("0")

        if mode == "fixed" or k <= 1:
            return round_to_step(base, step)

        n = k - 1

        if mode == "additive":
            return round_to_step(base + cfg.counter_tp_step_amount * Decimal(str(n)), step)

        if mode == "subtractive":
            val = base - cfg.counter_tp_step_amount * Decimal(str(n))
            return round_to_step(max(val, Decimal("0.1")), step)

        if mode == "multiplicative":
            val = base * cfg.counter_tp_multiplier ** Decimal(str(n))
            return round_to_step(val, step)

        if mode == "divisive":
            val = base / cfg.counter_tp_multiplier ** Decimal(str(n))
            return round_to_step(max(val, Decimal("0.1")), step)

        return round_to_step(base, step)


@dataclass(frozen=True, slots=True)
class SnowballCalculatorProvider:
    """Resolve formula calculators for Snowball flow collaborators."""

    def for_strategy(self, strategy: object) -> SnowballFormulaCalculator:
        """Return an explicit strategy calculator or build one from config."""
        calculator = getattr(strategy, "calculator", None)
        if calculator is not None:
            return calculator
        return SnowballCalculator(getattr(strategy, "config"))


def counter_interval_pips(k: int, cfg: "SnowballStrategyConfig") -> Decimal:
    """Return the pip interval before the *k*-th add (1-based).

    The general formula supports:
    - Flat region: first ``n_pips_flat_steps`` adds use ``n_pips_head``.
    - Decay region: exponential decay from ``n_pips_head`` toward ``n_pips_tail``
      controlled by ``n_pips_gamma``.

    Manual mode returns the user-supplied value from ``manual_intervals``.
    """
    return SnowballCalculator(cfg).counter_interval_pips(k)


def _progression_pips(
    *,
    k: int,
    mode: str,
    head: Decimal,
    tail: Decimal,
    flat_steps: int,
    gamma: Decimal,
    r_max: int,
    manual_values: list[Decimal],
    round_step: Decimal,
) -> Decimal:
    """Shared ``head → tail`` progression used by interval and SL formulas.

    Modes mirror :func:`counter_interval_pips`:
    - ``constant`` — always ``head``.
    - ``additive`` / ``subtractive`` / ``multiplicative`` / ``divisive`` —
      flat for ``flat_steps`` then decay toward ``tail`` using ``gamma``.
      (The mode name here is retained for schema parity; the actual curve
      is the same gamma decay regardless of which of these four is
      chosen.  Past and future refinements can diverge the curves
      without changing the caller.)
    - ``manual`` — read value at index ``k - 1`` from ``manual_values``,
      clamped to the end of the list.
    """
    if mode == "manual" and manual_values:
        idx = min(max(k - 1, 0), len(manual_values) - 1)
        return round_to_step(manual_values[idx], round_step)

    if mode == "constant":
        return round_to_step(head, round_step)

    if k <= flat_steps:
        return round_to_step(head, round_step)

    t = k - flat_steps
    r_decay = r_max - flat_steps
    if r_decay <= 0:
        return round_to_step(tail, round_step)

    progress = Decimal(str(t)) / Decimal(str(r_decay))
    curved = progress**gamma
    value = head - (head - tail) * curved
    return round_to_step(max(value, tail), round_step)


def stop_loss_pips(k: int, cfg: "SnowballStrategyConfig") -> Decimal:
    """Return the pip distance from entry to stop-loss for the *k*-th slot.

    ``k`` is 1-based: R0 uses ``k=1`` (treat the layer-initial like the
    first add so the SL distance lines up with the interval to the next
    slot), R1 uses ``k=2``, and so on.

    The progression shape mirrors :func:`counter_interval_pips` but reads
    its parameters from dedicated ``stop_loss_*`` config fields, so the
    SL distance can be tuned independently of the counter-trend
    averaging interval (e.g. a tighter SL on a wider grid).  ``auto``
    is handled by the strategy layer because interval-based stop-loss
    placement depends on both the next interval and the slot TP.
    """
    return SnowballCalculator(cfg).stop_loss_pips(k)


def rebuild_take_profit_pips(k: int, cfg: "SnowballStrategyConfig") -> Decimal:
    """Return the rebuilt-position take-profit distance for the *k*-th slot.

    ``k`` is 1-based: R0 uses ``k=1``, R1 uses ``k=2``, and so on.
    ``same`` is handled by the strategy layer because that mode reuses
    the pending rebuild snapshot's absolute TP price.
    """
    return SnowballCalculator(cfg).rebuild_take_profit_pips(k)


def counter_tp_pips(k: int, cfg: "SnowballStrategyConfig") -> Decimal:
    """Return the take-profit pips for the *k*-th step (1-based).

    Modes:
    - fixed: same value for every step.
    - additive: base + step_amount × (k − 1).
    - subtractive: base − step_amount × (k − 1), min 0.1.
    - multiplicative: base × multiplier^(k − 1).
    - divisive: base / multiplier^(k − 1), min 0.1.
    - weighted_avg: returns 0 — caller computes close price from weighted avg.
    """
    return SnowballCalculator(cfg).counter_tp_pips(k)
