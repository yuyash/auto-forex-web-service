"""Risk guardrails for starting executable trading tasks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings

from apps.trading.models import TradingTask

_SUPPORTED_DEBUG_OPTIONS = frozenset({"tracemalloc"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class LiveTradingRiskError(ValueError):
    """Raised when a task violates live-trading guardrails."""


@dataclass(frozen=True, slots=True)
class RiskEstimate:
    """Conservative estimate of strategy unit exposure at startup."""

    initial_order_units: int
    estimated_gross_units: int


class LiveTradingRiskGuard:
    """Validate executable task settings before worker ownership begins."""

    def validate_task_start(self, task: Any) -> None:
        """Validate guardrails that must hold before dispatching a task."""

        self._validate_debug_options(task)
        if not isinstance(task, TradingTask):
            return

        if bool(getattr(task, "dry_run", False)):
            return

        self._validate_account_mode(task)
        self._validate_instrument(task)
        self._validate_unit_limits(task)

    def _validate_account_mode(self, task: TradingTask) -> None:
        account = task.oanda_account
        api_type = str(getattr(account, "api_type", "")).lower()
        if api_type != "live":
            return

        if _setting_bool("TRADING_ALLOW_LIVE_OANDA", default=False):
            return

        raise LiveTradingRiskError(
            "Live OANDA accounts are disabled. Set TRADING_ALLOW_LIVE_OANDA=true before "
            "starting non-dry-run tasks on live accounts."
        )

    def _validate_instrument(self, task: TradingTask) -> None:
        allowed = _setting_instruments(
            "TRADING_LIVE_ALLOWED_INSTRUMENTS",
            default=(
                "USD_JPY",
                "EUR_USD",
                "GBP_USD",
                "AUD_USD",
                "USD_CAD",
                "USD_CHF",
                "NZD_USD",
            ),
        )
        instrument = str(getattr(task, "instrument", "")).strip().upper()
        if "*" in allowed or instrument in allowed:
            return

        raise LiveTradingRiskError(
            f"Instrument {instrument or '<empty>'} is not enabled for non-dry-run trading. "
            "Update TRADING_LIVE_ALLOWED_INSTRUMENTS to allow it."
        )

    def _validate_unit_limits(self, task: TradingTask) -> None:
        estimate = self._estimate_task_units(task)
        max_initial = _setting_positive_int("TRADING_LIVE_MAX_INITIAL_UNITS", default=10_000)
        max_exposure = _setting_positive_int(
            "TRADING_LIVE_MAX_ESTIMATED_EXPOSURE_UNITS",
            default=200_000,
        )

        if max_initial and estimate.initial_order_units > max_initial:
            raise LiveTradingRiskError(
                "Initial order size exceeds the configured live-trading limit "
                f"({estimate.initial_order_units} > {max_initial}). "
                "Reduce strategy units or raise TRADING_LIVE_MAX_INITIAL_UNITS."
            )

        if max_exposure and estimate.estimated_gross_units > max_exposure:
            raise LiveTradingRiskError(
                "Estimated gross strategy exposure exceeds the configured live-trading limit "
                f"({estimate.estimated_gross_units} > {max_exposure}). "
                "Reduce grid size/units or raise TRADING_LIVE_MAX_ESTIMATED_EXPOSURE_UNITS."
            )

    def _estimate_task_units(self, task: TradingTask) -> RiskEstimate:
        config = getattr(task, "config", None)
        strategy_type = str(getattr(config, "strategy_type", "")).strip().lower()
        params = _config_params(config)

        if strategy_type == "snowball":
            return _estimate_snowball_units(
                params=params,
                hedging_enabled=bool(getattr(task, "hedging_enabled", False)),
            )

        initial = _first_positive_int(params, ("units", "order_units", "base_units"), default=0)
        return RiskEstimate(initial_order_units=initial, estimated_gross_units=initial)

    def _validate_debug_options(self, task: Any) -> None:
        debug_options = getattr(task, "debug_options", None)
        if debug_options is None or _is_mock_value(debug_options):
            return
        if not isinstance(debug_options, dict):
            raise LiveTradingRiskError("debug_options must be a JSON object.")

        unknown = sorted(set(debug_options) - _SUPPORTED_DEBUG_OPTIONS)
        if unknown:
            names = ", ".join(unknown)
            raise LiveTradingRiskError(f"Unsupported debug option(s): {names}.")

        tracemalloc = debug_options.get("tracemalloc")
        if tracemalloc is not None and not isinstance(tracemalloc, bool):
            raise LiveTradingRiskError("debug_options.tracemalloc must be a boolean.")


def _estimate_snowball_units(
    *,
    params: dict[str, Any],
    hedging_enabled: bool,
) -> RiskEstimate:
    base_units = _positive_int(params.get("base_units"), default=1_000)
    trend_lot_size = _positive_int(params.get("trend_lot_size"), default=1)
    r_max = _positive_int(params.get("r_max"), default=7)
    f_max = _positive_int(params.get("f_max"), default=3)
    post_r_max_base_factor = _positive_decimal(
        params.get("post_r_max_base_factor"),
        default=Decimal("1"),
    )

    initial_order_units = base_units * trend_lot_size
    first_layer_units = _snowball_layer_units(
        base_units=base_units,
        trend_lot_size=trend_lot_size,
        r_max=r_max,
    )
    post_r_max_base_units = int(Decimal(base_units) * post_r_max_base_factor)
    post_layer_units = _snowball_layer_units(
        base_units=max(post_r_max_base_units, 1),
        trend_lot_size=trend_lot_size,
        r_max=r_max,
    )
    per_direction_units = first_layer_units + (max(f_max, 1) - 1) * post_layer_units
    direction_multiplier = 2 if hedging_enabled else 1
    return RiskEstimate(
        initial_order_units=initial_order_units,
        estimated_gross_units=per_direction_units * direction_multiplier,
    )


def _snowball_layer_units(*, base_units: int, trend_lot_size: int, r_max: int) -> int:
    trend_units = base_units * trend_lot_size
    counter_units = base_units * (r_max * (r_max + 1) // 2)
    return trend_units + counter_units


def _config_params(config: Any) -> dict[str, Any]:
    params = getattr(config, "parameters", None)
    if isinstance(params, dict):
        return params

    config_dict = getattr(config, "config_dict", None)
    if isinstance(config_dict, dict):
        return config_dict

    return {}


def _first_positive_int(
    params: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: int,
) -> int:
    for key in keys:
        if key in params:
            return _positive_int(params.get(key), default=default)
    return default


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _positive_decimal(value: Any, *, default: Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default
    return max(parsed, Decimal("0"))


def _setting_bool(name: str, *, default: bool) -> bool:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE_VALUES


def _setting_positive_int(name: str, *, default: int) -> int:
    value = getattr(settings, name, default)
    return _positive_int(value, default=default)


def _setting_instruments(name: str, *, default: tuple[str, ...]) -> set[str]:
    value = getattr(settings, name, default)
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value

    return {str(item).strip().upper() for item in items if str(item).strip()}


def _is_mock_value(value: Any) -> bool:
    return value.__class__.__module__.startswith("unittest.mock")
