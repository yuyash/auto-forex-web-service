from __future__ import annotations


class TestMarketAppConfig:
    def test_ready_imports_signals(self) -> None:
        # AppConfig.ready() is called by Django during app loading.
        # Here we just assert the AppConfig is importable and named correctly.
        from apps.market.apps import MarketConfig

        assert MarketConfig.name == "apps.market"
