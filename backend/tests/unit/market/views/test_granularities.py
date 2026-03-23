"""Pure unit tests for granularities views (with mocks, no DB)."""

from unittest.mock import patch

from rest_framework.test import APIRequestFactory


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

    @patch("apps.market.views.granularities.cache")
    def test_get_uses_cache_when_available(self, mock_cache) -> None:
        from apps.market.views.granularities import SupportedGranularitiesView

        mock_cache.get.return_value = [{"value": "M1", "label": "1 Minute"}]
        request = APIRequestFactory().get("/")
        request.user = object()

        response = SupportedGranularitiesView().get(request)

        assert response.data["source"] == "cache"
        assert response.data["granularities"] == [{"value": "M1", "label": "1 Minute"}]

    @patch("apps.market.views.granularities.cache")
    def test_get_primes_cache_when_empty(self, mock_cache) -> None:
        from apps.market.views.granularities import SupportedGranularitiesView

        mock_cache.get.return_value = None
        request = APIRequestFactory().get("/")
        request.user = object()

        response = SupportedGranularitiesView().get(request)

        assert response.data["source"] == "cache"
        mock_cache.set.assert_called_once()
