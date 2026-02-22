"""Integration tests for OrderService with real DB.

Tests order execution, position creation/update, and close flows
using dry_run=True so no external API calls are made.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.trading.enums import Direction
from apps.trading.models import Order, Position
from apps.trading.models.orders import OrderStatus, OrderType
from apps.trading.order import OrderService, OrderServiceError
from tests.integration.factories import BacktestTaskFactory


def _make_service(task=None) -> tuple:
    """Create an OrderService in dry_run mode with a real BacktestTask."""
    if task is None:
        task = BacktestTaskFactory()
    svc = OrderService(account=None, task=task, dry_run=True)
    return svc, task


@pytest.mark.django_db
class TestOpenPosition:
    """Tests for OrderService.open_position with dry_run=True."""

    def test_creates_position_and_order(self):
        svc, task = _make_service()

        position, order = svc.open_position(
            instrument="USD_JPY",
            units=1000,
            direction=Direction.LONG,
            override_price=Decimal("150.500"),
        )

        assert isinstance(position, Position)
        assert position.is_open is True
        assert position.instrument == "USD_JPY"
        assert position.direction == Direction.LONG
        assert position.units == 1000
        assert position.entry_price == Decimal("150.500")

        assert isinstance(order, Order)
        assert order.status == OrderStatus.FILLED
        assert order.is_dry_run is True
        assert order.fill_price == Decimal("150.500")
        assert order.position == position

        # Verify persisted in DB
        assert Position.objects.filter(pk=position.pk).exists()
        assert Order.objects.filter(pk=order.pk).exists()

    def test_short_position(self):
        svc, task = _make_service()

        position, order = svc.open_position(
            instrument="EUR_USD",
            units=500,
            direction=Direction.SHORT,
            override_price=Decimal("1.0900"),
        )

        assert position.direction == Direction.SHORT
        assert position.units == 500

    def test_merge_with_existing(self):
        svc, task = _make_service()

        pos1, _ = svc.open_position(
            instrument="USD_JPY",
            units=1000,
            direction=Direction.LONG,
            override_price=Decimal("150.000"),
        )
        pos2, _ = svc.open_position(
            instrument="USD_JPY",
            units=500,
            direction=Direction.LONG,
            override_price=Decimal("151.000"),
        )

        # Should merge into the same position
        assert pos1.pk == pos2.pk
        pos2.refresh_from_db()
        assert pos2.units == 1500
        # Weighted average: (150*1000 + 151*500) / 1500
        expected_avg = (Decimal("150.000") * 1000 + Decimal("151.000") * 500) / 1500
        assert abs(pos2.entry_price - expected_avg) < Decimal("0.001")

    def test_invalid_units(self):
        svc, task = _make_service()

        with pytest.raises(OrderServiceError, match="Units must be positive"):
            svc.open_position(
                instrument="USD_JPY",
                units=0,
                direction=Direction.LONG,
            )


@pytest.mark.django_db
class TestClosePosition:
    """Tests for OrderService.close_position with dry_run=True."""

    def test_full_close(self):
        svc, task = _make_service()

        position, _ = svc.open_position(
            instrument="USD_JPY",
            units=1000,
            direction=Direction.LONG,
            override_price=Decimal("150.000"),
        )

        closed_pos, realized_pnl, close_order = svc.close_position(
            position,
            override_price=Decimal("151.000"),
        )

        closed_pos.refresh_from_db()
        assert closed_pos.is_open is False
        assert closed_pos.exit_price == Decimal("151.000")
        assert close_order is not None
        assert close_order.status == OrderStatus.FILLED

    def test_partial_close(self):
        svc, task = _make_service()

        position, _ = svc.open_position(
            instrument="USD_JPY",
            units=2000,
            direction=Direction.LONG,
            override_price=Decimal("150.000"),
        )

        updated_pos, realized_pnl, close_order = svc.close_position(
            position,
            units=500,
            override_price=Decimal("151.000"),
        )

        updated_pos.refresh_from_db()
        assert updated_pos.is_open is True
        assert updated_pos.units == 1500

    def test_close_already_closed(self):
        svc, task = _make_service()

        position, _ = svc.open_position(
            instrument="USD_JPY",
            units=1000,
            direction=Direction.LONG,
            override_price=Decimal("150.000"),
        )
        svc.close_position(position, override_price=Decimal("151.000"))

        position.refresh_from_db()
        with pytest.raises(OrderServiceError, match="already closed"):
            svc.close_position(position, override_price=Decimal("152.000"))


@pytest.mark.django_db
class TestExecuteMarketOrder:
    """Tests for OrderService._execute_market_order with dry_run."""

    def test_full_flow(self):
        svc, task = _make_service()

        position, order = svc._execute_market_order(
            instrument="EUR_USD",
            units=1000,
            direction=Direction.LONG,
            override_price=Decimal("1.1000"),
        )

        assert position.is_open is True
        assert position.instrument == "EUR_USD"
        assert order.status == OrderStatus.FILLED
        assert order.fill_price == Decimal("1.1000")
        assert order.position == position


@pytest.mark.django_db
class TestCreateOrderRecord:
    """Tests for OrderService._create_order_record."""

    def test_creates_order(self):
        from unittest.mock import MagicMock

        svc, task = _make_service()

        mock_oanda_order = MagicMock()
        mock_oanda_order.order_id = "DRY-1"
        mock_oanda_order.price = Decimal("150.500")
        mock_oanda_order.fill_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        order = svc._create_order_record(
            instrument="USD_JPY",
            order_type=OrderType.MARKET,
            direction=Direction.LONG,
            units=1000,
            oanda_order=mock_oanda_order,
        )

        assert isinstance(order, Order)
        assert order.broker_order_id == "DRY-1"
        assert order.fill_price == Decimal("150.500")
        assert order.status == OrderStatus.FILLED
        assert order.is_dry_run is True
        assert Order.objects.filter(pk=order.pk).exists()


@pytest.mark.django_db
class TestCreateOrUpdatePosition:
    """Tests for OrderService._create_or_update_position."""

    def test_creates_new_position(self):
        svc, task = _make_service()
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        position = svc._create_or_update_position(
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("150.000"),
            entry_time=now,
        )

        assert isinstance(position, Position)
        assert position.is_open is True
        assert position.units == 1000
        assert Position.objects.filter(pk=position.pk).exists()

    def test_updates_existing_position(self):
        svc, task = _make_service()
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        pos1 = svc._create_or_update_position(
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("150.000"),
            entry_time=now,
        )
        pos2 = svc._create_or_update_position(
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=500,
            entry_price=Decimal("152.000"),
            entry_time=now,
            merge_with_existing=True,
        )

        assert pos1.pk == pos2.pk
        pos2.refresh_from_db()
        assert pos2.units == 1500

    def test_no_merge_creates_new(self):
        svc, task = _make_service()
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        pos1 = svc._create_or_update_position(
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("150.000"),
            entry_time=now,
        )
        pos2 = svc._create_or_update_position(
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=500,
            entry_price=Decimal("152.000"),
            entry_time=now,
            merge_with_existing=False,
        )

        assert pos1.pk != pos2.pk
        assert Position.objects.filter(task_id=task.pk, is_open=True).count() == 2
