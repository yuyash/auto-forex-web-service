"""Tests for broker snapshot loader objects."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.trading.services.broker_snapshot import BrokerSnapshotLoader


class TestBrokerSnapshotLoader:
    """Verify broker snapshot loader behavior."""

    def test_caches_pending_orders_by_instrument(self):
        broker = MagicMock()
        broker.get_pending_orders.return_value = ["order-1"]
        runner = MagicMock(
            side_effect=lambda fn, **kwargs: fn(**{k: v for k, v in kwargs.items() if k != "label"})
        )
        loader = BrokerSnapshotLoader(broker_service=broker, request_runner=runner)

        first = loader.pending_orders_for(instrument="EUR_USD")
        second = loader.pending_orders_for(instrument="EUR_USD")

        assert first == ["order-1"]
        assert second == ["order-1"]
        broker.get_pending_orders.assert_called_once_with(instrument="EUR_USD")
