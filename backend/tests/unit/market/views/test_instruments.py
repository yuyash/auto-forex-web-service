"""Pure unit tests for instruments views (with mocks, no DB)."""


class TestInstrumentsViewsUnit:
    """Pure unit tests for instruments views."""

    def test_supported_instruments_view_importable(self) -> None:
        """Test that SupportedInstrumentsView can be imported."""
        from apps.market.views.instruments import SupportedInstrumentsView

        assert SupportedInstrumentsView is not None

        # Check fallback list exists
        view = SupportedInstrumentsView()
        assert hasattr(view, "FALLBACK_INSTRUMENTS")
        assert "EUR_USD" in view.FALLBACK_INSTRUMENTS

    def test_instrument_detail_view_importable(self) -> None:
        """Test that InstrumentDetailView can be imported."""
        from apps.market.views.instruments import InstrumentDetailView

        assert InstrumentDetailView is not None
