"""Calculators for Snowball strategy.

Implements the interval formula and step-based take-profit calculations
described in the Snowball v1.2 specification.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.strategies.snowball.models import SnowballStrategyConfig


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round *value* to the nearest multiple of *step*.

    >>> round_to_step(Decimal("29.3"), Decimal("0.5"))
    Decimal('29.5')
    """
    if step <= 0:
        return value
    return (value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


def counter_interval_pips(k: int, cfg: "SnowballStrategyConfig") -> Decimal:
    """Return the pip interval before the *k*-th add (1-based).

    The general formula supports:
    - Flat region: first ``n_pips_flat_steps`` adds use ``n_pips_head``.
    - Decay region: exponential decay from ``n_pips_head`` toward ``n_pips_tail``
      controlled by ``n_pips_gamma``.

    Manual mode returns the user-supplied value from ``manual_intervals``.
    """
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

    # Decay steps after flat region
    t = k - flat  # 1-based step into decay
    r_decay = cfg.r_max - flat  # total decay steps
    if r_decay <= 0:
        return round_to_step(tail, cfg.round_step_pips)

    # Normalised progress 0→1
    progress = Decimal(str(t)) / Decimal(str(r_decay))
    # Gamma curve: progress^gamma  (gamma>1 → slow start, <1 → fast start)
    curved = progress**gamma
    interval = head - (head - tail) * curved
    return round_to_step(max(interval, tail), cfg.round_step_pips)


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
    mode = cfg.counter_tp_mode
    base = cfg.counter_tp_pips
    step = cfg.round_step_pips

    if mode == "weighted_avg":
        return Decimal("0")

    if mode == "fixed" or k <= 1:
        return round_to_step(base, step)

    n = k - 1  # progression index (0 for step 1)

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

    # Fallback
    return round_to_step(base, step)
