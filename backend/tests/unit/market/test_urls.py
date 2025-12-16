from __future__ import annotations

from apps.market import urls


class TestMarketUrls:
    def test_urlpatterns_exist(self) -> None:
        assert hasattr(urls, "urlpatterns")
        assert len(urls.urlpatterns) >= 5

    def test_expected_named_routes_present(self) -> None:
        names = {p.name for p in urls.urlpatterns}
        assert "oanda_accounts_list" in names
        assert "oanda_account_detail" in names
        assert "candle_data" in names
        assert "supported_instruments" in names
        assert "supported_granularities" in names
        assert "market_status" in names
