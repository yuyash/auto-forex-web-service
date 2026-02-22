"""Pure unit tests for candle views (with mocks, no DB)."""


class TestCandleDataViewUnit:
    """Pure unit tests for CandleDataView."""

    def test_candle_data_view_importable(self) -> None:
        """Test that CandleDataView can be imported."""
        from apps.market.views.candles import CandleDataView

        assert CandleDataView is not None
