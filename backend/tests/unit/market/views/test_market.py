"""Pure unit tests for market status views (with mocks, no DB)."""


class TestMarketStatusViewUnit:
    """Pure unit tests for MarketStatusView."""

    def test_market_status_view_importable(self) -> None:
        """Test that MarketStatusView can be imported."""
        from apps.market.views.market import MarketStatusView

        assert MarketStatusView is not None

    def test_market_sessions_defined(self) -> None:
        """Test that market sessions are defined."""
        from apps.market.views.market import MarketStatusView

        view = MarketStatusView()

        assert hasattr(view, "MARKET_SESSIONS")
        assert len(view.MARKET_SESSIONS) == 4

        # Check all sessions
        assert "sydney" in view.MARKET_SESSIONS
        assert "tokyo" in view.MARKET_SESSIONS
        assert "london" in view.MARKET_SESSIONS
        assert "new_york" in view.MARKET_SESSIONS

    def test_session_structure(self) -> None:
        """Test that each session has required fields."""
        from apps.market.views.market import MarketStatusView

        view = MarketStatusView()

        for session_name, session_data in view.MARKET_SESSIONS.items():
            assert "open" in session_data
            assert "close" in session_data
            assert isinstance(session_data["open"], int)
            assert isinstance(session_data["close"], int)
