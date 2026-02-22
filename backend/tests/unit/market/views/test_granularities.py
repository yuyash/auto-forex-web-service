"""Pure unit tests for granularities views (with mocks, no DB)."""


class TestSupportedGranularitiesViewUnit:
    """Pure unit tests for SupportedGranularitiesView."""

    def test_granularities_view_importable(self) -> None:
        """Test that SupportedGranularitiesView can be imported."""
        from apps.market.views.granularities import SupportedGranularitiesView

        assert SupportedGranularitiesView is not None

    def test_granularities_list_defined(self) -> None:
        """Test that granularities list is defined."""
        from apps.market.views.granularities import SupportedGranularitiesView

        view = SupportedGranularitiesView()

        assert hasattr(view, "GRANULARITIES")
        assert len(view.GRANULARITIES) > 0

        # Check structure
        for gran in view.GRANULARITIES:
            assert "value" in gran
            assert "label" in gran

    def test_standard_granularities_included(self) -> None:
        """Test that standard granularities are included."""
        from apps.market.views.granularities import SupportedGranularitiesView

        view = SupportedGranularitiesView()

        values = [g["value"] for g in view.GRANULARITIES]

        assert "M1" in values
        assert "M5" in values
        assert "H1" in values
        assert "H4" in values
        assert "D" in values
