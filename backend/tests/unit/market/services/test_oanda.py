"""Unit tests for OANDA service."""

from decimal import Decimal

from apps.market.services.oanda import OandaService, OrderDirection, Position


class TestOandaService:
    """Test OANDA service."""

    def test_oanda_service_module_exists(self):
        """Test OANDA service module exists."""
        from apps.market.services import oanda

        assert oanda is not None

    def test_oanda_service_has_classes(self):
        """Test OANDA service has classes."""
        import inspect

        from apps.market.services import oanda

        classes = [
            name
            for name, obj in inspect.getmembers(oanda)
            if inspect.isclass(obj) and obj.__module__ == oanda.__name__
        ]

        # Should have service classes
        assert len(classes) > 0

    def test_close_position_dry_run_without_account(self):
        """Dry-run close_position should not require API client/account."""
        service = OandaService(account=None, dry_run=True)
        position = Position(
            instrument="USD_JPY",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            average_price=Decimal("150.00"),
            unrealized_pnl=Decimal("0"),
            trade_ids=[],
            account_id="DRY-RUN",
        )

        result = service.close_position(position)

        assert result is not None
        assert result.instrument == "USD_JPY"
