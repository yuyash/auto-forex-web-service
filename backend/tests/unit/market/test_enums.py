from __future__ import annotations

from apps.market.enums import ApiType, Jurisdiction, MarketEventCategory, MarketEventSeverity


class TestMarketEnums:
    def test_api_type_values(self) -> None:
        assert ApiType.PRACTICE in ApiType
        assert ApiType.LIVE in ApiType
        assert "practice" in ApiType.values
        assert "live" in ApiType.values

    def test_jurisdiction_values(self) -> None:
        assert "US" in Jurisdiction.values
        assert "JP" in Jurisdiction.values
        assert "OTHER" in Jurisdiction.values

    def test_market_event_enums(self) -> None:
        assert "market" in MarketEventCategory.values
        assert "trading" in MarketEventCategory.values
        assert "security" in MarketEventCategory.values

        assert "info" in MarketEventSeverity.values
        assert "warning" in MarketEventSeverity.values
        assert "error" in MarketEventSeverity.values
