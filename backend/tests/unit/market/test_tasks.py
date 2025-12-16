from __future__ import annotations

from apps.market.tasks import _backtest_channel_for_request, _parse_iso_datetime


class TestMarketTasksHelpers:
    def test_parse_iso_datetime_accepts_z_suffix(self) -> None:
        dt = _parse_iso_datetime("2025-01-01T00:00:00Z")
        assert dt.tzinfo is not None

    def test_backtest_channel_prefix(self, settings) -> None:
        settings.MARKET_BACKTEST_TICK_CHANNEL_PREFIX = "x:y:"
        assert _backtest_channel_for_request("abc") == "x:y:abc"
