"""Shared live-trading safety policy parsed from Django settings."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

DEFAULT_LIVE_ALLOWED_INSTRUMENTS = (
    "USD_JPY",
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "NZD_USD",
)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True, slots=True)
class LiveTradingPolicy:
    """Normalized live-trading safety settings."""

    allow_live_oanda: bool
    allowed_instruments: frozenset[str]
    max_initial_units: int
    max_order_units: int
    max_estimated_exposure_units: int

    def allows_instrument(self, instrument: str) -> bool:
        """Return whether an instrument is allowed by this policy."""

        normalized = str(instrument or "").strip().upper()
        return bool(normalized) and (
            "*" in self.allowed_instruments or normalized in self.allowed_instruments
        )


def get_live_trading_policy() -> LiveTradingPolicy:
    """Load and normalize live-trading safety settings."""

    return LiveTradingPolicy(
        allow_live_oanda=_setting_bool("TRADING_ALLOW_LIVE_OANDA", default=False),
        allowed_instruments=frozenset(
            _setting_instruments(
                "TRADING_LIVE_ALLOWED_INSTRUMENTS",
                default=DEFAULT_LIVE_ALLOWED_INSTRUMENTS,
            )
        ),
        max_initial_units=_setting_positive_int("TRADING_LIVE_MAX_INITIAL_UNITS", default=10_000),
        max_order_units=_setting_positive_int("TRADING_LIVE_MAX_ORDER_UNITS", default=10_000),
        max_estimated_exposure_units=_setting_positive_int(
            "TRADING_LIVE_MAX_ESTIMATED_EXPOSURE_UNITS",
            default=200_000,
        ),
    )


def _setting_bool(name: str, *, default: bool) -> bool:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE_VALUES


def _setting_positive_int(name: str, *, default: int) -> int:
    value = getattr(settings, name, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _setting_instruments(name: str, *, default: tuple[str, ...]) -> set[str]:
    value = getattr(settings, name, default)
    if value is None:
        items = default
    elif isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    return {str(item).strip().upper() for item in items if str(item).strip()}
