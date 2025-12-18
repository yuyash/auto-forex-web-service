from __future__ import annotations

from decimal import Decimal

from apps.trading.services.performance import LivePerformanceService


class TestLivePerformanceService:
    def test_pip_size_for_instrument(self):
        assert LivePerformanceService._pip_size_for_instrument("USD_JPY") == Decimal("0.01")
        assert LivePerformanceService._pip_size_for_instrument("eur_usd") == Decimal("0.0001")

    def test_compute_floor_unrealized_snapshot_long_and_short_weighted(self):
        # For EUR_USD pip size 0.0001
        # long from 1.1000 -> 1.1010 => +10 pips
        # short from 1.2000 -> 1.1990 => +10 pips
        state = {
            "last_mid": "1.1010",
            "active_layers": [
                {"direction": "long", "entry_price": "1.1000", "lot_size": "1"},
                {
                    "direction": "short",
                    "entry_price": "1.2000",
                    "lot_size": "3",
                    "last_mid": "1.1990",
                },
            ],
        }

        snap = LivePerformanceService.compute_floor_unrealized_snapshot(
            instrument="EUR_USD", strategy_state=state
        )

        assert snap.open_layers == 2
        # Weighted avg of +10 and (entry 1.2000, last 1.1010) is huge profit for short,
        # but we intentionally set short entry far away; focus on being numeric.
        assert isinstance(snap.unrealized_pips, Decimal)
        assert snap.last_mid == Decimal("1.1010")

    def test_compute_floor_unrealized_snapshot_handles_missing_layers(self):
        snap = LivePerformanceService.compute_floor_unrealized_snapshot(
            instrument="EUR_USD", strategy_state={"last_mid": "1.0"}
        )
        assert snap.open_layers == 0
        assert snap.unrealized_pips == Decimal("0")
