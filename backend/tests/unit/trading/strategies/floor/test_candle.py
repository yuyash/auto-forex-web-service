"""Unit tests for floor strategy candle manager."""

from decimal import Decimal
from unittest.mock import MagicMock

from apps.trading.strategies.floor.candle import CandleManager
from apps.trading.strategies.floor.models import CandleData, FloorStrategyConfig, FloorStrategyState


class TestCandleManager:
    def _make_config(self):
        config = MagicMock(spec=FloorStrategyConfig)
        config.entry_signal_candle_granularity_seconds = 300
        config.entry_signal_lookback_candles = 5
        return config

    def _make_state(self):
        state = MagicMock(spec=FloorStrategyState)
        state.candles = []
        state.current_candle_close = None
        state.current_candle_high = None
        state.current_candle_low = None
        return state

    def test_get_candle_closes_empty(self):
        mgr = CandleManager(self._make_config())
        state = self._make_state()
        assert mgr.get_candle_closes(state) == []

    def test_get_candle_closes_with_current(self):
        mgr = CandleManager(self._make_config())
        state = self._make_state()
        state.current_candle_close = Decimal("150")
        closes = mgr.get_candle_closes(state)
        assert closes == [Decimal("150")]

    def test_has_enough_candles_false(self):
        mgr = CandleManager(self._make_config())
        state = self._make_state()
        assert mgr.has_enough_candles(state) is False

    def test_has_enough_candles_true(self):
        config = self._make_config()
        config.entry_signal_lookback_candles = 2
        mgr = CandleManager(config)
        state = self._make_state()
        state.candles = [
            CandleData(
                bucket_start_epoch=100,
                close_price=Decimal("150"),
                high_price=Decimal("151"),
                low_price=Decimal("149"),
            ),
            CandleData(
                bucket_start_epoch=400,
                close_price=Decimal("151"),
                high_price=Decimal("152"),
                low_price=Decimal("150"),
            ),
        ]
        assert mgr.has_enough_candles(state) is True

    def test_get_candles_includes_current(self):
        mgr = CandleManager(self._make_config())
        state = self._make_state()
        state.current_candle_close = Decimal("150")
        state.current_candle_high = Decimal("151")
        state.current_candle_low = Decimal("149")
        candles = mgr.get_candles(state)
        assert len(candles) == 1
        assert candles[0].close_price == Decimal("150")
