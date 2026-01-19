"""Pure unit tests for health views (with mocks, no DB)."""


class TestOandaApiHealthViewUnit:
    """Pure unit tests for OandaApiHealthView."""

    def test_health_view_importable(self) -> None:
        """Test that OandaApiHealthView can be imported."""
        from apps.market.views.health import OandaApiHealthView

        assert OandaApiHealthView is not None
