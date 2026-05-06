"""Tests for live-trading risk guardrails."""

from __future__ import annotations

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfiguration, TradingTask
from apps.trading.services.live_risk import LiveTradingRiskError, LiveTradingRiskGuard


def _trading_task(
    *,
    api_type: str = ApiType.PRACTICE,
    dry_run: bool = False,
    instrument: str = "USD_JPY",
    parameters: dict | None = None,
    debug_options: dict | None = None,
    live_max_exposure_guard_enabled: bool = False,
    live_max_estimated_exposure_units: int = 200_000,
) -> TradingTask:
    return TradingTask(
        config=StrategyConfiguration(
            strategy_type="snowball",
            parameters=parameters
            or {
                "base_units": 1000,
                "trend_lot_size": 1,
                "r_max": 5,
                "f_max": 3,
            },
        ),
        oanda_account=OandaAccounts(
            api_type=api_type,
            live_max_exposure_guard_enabled=live_max_exposure_guard_enabled,
            live_max_estimated_exposure_units=live_max_estimated_exposure_units,
        ),
        dry_run=dry_run,
        instrument=instrument,
        hedging_enabled=True,
        debug_options=debug_options or {},
    )


def test_rejects_live_account_without_global_enable(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = False

    task = _trading_task(api_type=ApiType.LIVE)

    with pytest.raises(LiveTradingRiskError, match="Live OANDA accounts are disabled"):
        LiveTradingRiskGuard().validate_task_start(task)


def test_dry_run_bypasses_live_account_guard(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = False

    task = _trading_task(api_type=ApiType.LIVE, dry_run=True)

    LiveTradingRiskGuard().validate_task_start(task)


def test_rejects_disallowed_non_dry_run_instrument(settings):
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = ["EUR_USD"]

    task = _trading_task(instrument="USD_JPY")

    with pytest.raises(LiveTradingRiskError, match="Instrument USD_JPY"):
        LiveTradingRiskGuard().validate_task_start(task)


def test_rejects_oversized_initial_order(settings):
    settings.TRADING_LIVE_MAX_INITIAL_UNITS = 10_000

    task = _trading_task(parameters={"base_units": 20_000, "trend_lot_size": 1})

    with pytest.raises(LiveTradingRiskError, match="Initial order size exceeds"):
        LiveTradingRiskGuard().validate_task_start(task)


def test_rejects_oversized_estimated_gross_exposure(settings):
    settings.TRADING_LIVE_MAX_INITIAL_UNITS = 10_000

    task = _trading_task(
        live_max_exposure_guard_enabled=True,
        live_max_estimated_exposure_units=50_000,
        parameters={
            "base_units": 5_000,
            "trend_lot_size": 1,
            "r_max": 5,
            "f_max": 3,
        },
    )

    with pytest.raises(LiveTradingRiskError, match="Estimated gross strategy exposure"):
        LiveTradingRiskGuard().validate_task_start(task)


def test_skips_estimated_gross_exposure_when_account_guard_disabled(settings):
    settings.TRADING_LIVE_MAX_INITIAL_UNITS = 10_000
    settings.TRADING_LIVE_MAX_ESTIMATED_EXPOSURE_UNITS = 50_000

    task = _trading_task(
        live_max_exposure_guard_enabled=False,
        parameters={
            "base_units": 5_000,
            "trend_lot_size": 1,
            "r_max": 5,
            "f_max": 3,
        },
    )

    LiveTradingRiskGuard().validate_task_start(task)


def test_rejects_unknown_debug_option():
    task = _trading_task(dry_run=True, debug_options={"profile_sql": True})

    with pytest.raises(LiveTradingRiskError, match="Unsupported debug option"):
        LiveTradingRiskGuard().validate_task_start(task)


def test_rejects_non_boolean_tracemalloc_option():
    task = _trading_task(dry_run=True, debug_options={"tracemalloc": "true"})

    with pytest.raises(LiveTradingRiskError, match="tracemalloc must be a boolean"):
        LiveTradingRiskGuard().validate_task_start(task)
