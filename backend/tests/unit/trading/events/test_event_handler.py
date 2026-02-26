"""Unit tests for EventHandler class."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from apps.trading.dataclasses import EventExecutionResult
from apps.trading.enums import EventType, TaskType
from apps.trading.events import (
    ClosePositionEvent,
    MarginProtectionEvent,
    OpenPositionEvent,
    VolatilityHedgeNeutralizeEvent,
    VolatilityLockEvent,
)
from apps.trading.events.handler import EventHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order_service(task_type=TaskType.TRADING):
    svc = MagicMock()
    svc.task = SimpleNamespace(id=uuid4(), celery_task_id="celery-id-1")
    svc.task_type = task_type
    return svc


def _make_position(units=1000, layer_index=1, is_open=True, direction="long"):
    return SimpleNamespace(
        id=uuid4(),
        is_open=is_open,
        units=units,
        layer_index=layer_index,
        direction=direction,
        instrument="EUR_USD",
        entry_price=Decimal("1.10000"),
        entry_time=None,
        exit_price=None,
        oanda_trade_id="oanda-123",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEventHandlerInit:
    """Tests for __init__."""

    def test_stores_order_service_and_instrument(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")

        assert handler.order_service is svc
        assert handler.instrument == "EUR_USD"

    def test_position_map_starts_empty(self):
        handler = EventHandler(order_service=_make_order_service(), instrument="EUR_USD")

        assert handler.position_map == {}
        assert handler._position_cache == {}
        assert handler.layer_position_ids == {}


class TestHandleOpenPosition:
    """Tests for handle_open_position."""

    def test_opens_position_and_caches(self):
        svc = _make_order_service()
        position = _make_position()
        order = MagicMock()
        svc.open_position.return_value = (position, order)

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._record_trade = MagicMock()

        event = OpenPositionEvent(
            event_type=EventType.OPEN_POSITION,
            layer_number=1,
            direction="long",
            units=1000,
            price=Decimal("1.10000"),
        )

        result = handler.handle_open_position(event)

        assert result is position
        svc.open_position.assert_called_once()
        # Position should be cached
        assert handler.position_map[1] is position
        assert str(position.id) in handler._position_cache

    def test_records_trade(self):
        svc = _make_order_service()
        position = _make_position()
        order = MagicMock()
        svc.open_position.return_value = (position, order)

        handler = EventHandler(order_service=svc, instrument="EUR_USD")

        with patch.object(handler, "_record_trade") as mock_record:
            event = OpenPositionEvent(
                event_type=EventType.OPEN_POSITION,
                layer_number=1,
                direction="long",
                units=1000,
            )
            handler.handle_open_position(event)
            mock_record.assert_called_once()

    def test_passes_retracement_count(self):
        svc = _make_order_service()
        position = _make_position()
        svc.open_position.return_value = (position, MagicMock())

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._record_trade = MagicMock()

        event = OpenPositionEvent(
            event_type=EventType.OPEN_POSITION,
            layer_number=2,
            direction="short",
            units=750,
            retracement_count=3,
        )
        handler.handle_open_position(event)

        call_kwargs = svc.open_position.call_args
        assert call_kwargs.kwargs.get("retracement_count") == 3


class TestHandleClosePosition:
    """Tests for handle_close_position."""

    def test_closes_position_returns_pnl(self):
        svc = _make_order_service()
        position = _make_position()
        closed_position = _make_position(is_open=False)
        closed_position.exit_price = Decimal("1.11000")
        svc.close_position.return_value = (closed_position, Decimal("10.00"), MagicMock())

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._find_close_position_target = MagicMock(return_value=position)
        handler._prune_closed_position = MagicMock()
        handler._record_trade = MagicMock()

        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            layer_number=1,
            direction="long",
            units=1000,
        )

        result = handler.handle_close_position(event)

        assert result == Decimal("10.00")
        svc.close_position.assert_called_once()

    def test_no_target_position_returns_zero(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._find_close_position_target = MagicMock(return_value=None)

        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            layer_number=1,
            direction="long",
            units=1000,
        )

        result = handler.handle_close_position(event)

        assert result == Decimal("0")
        svc.close_position.assert_not_called()

    def test_partial_close_iterates_positions(self):
        svc = _make_order_service()
        p1 = _make_position(units=500)
        p2 = _make_position(units=1000)

        closed_p1 = _make_position(units=500, is_open=False)
        closed_p1.exit_price = Decimal("1.11000")
        closed_p2 = _make_position(units=500, is_open=True)
        closed_p2.exit_price = Decimal("1.11000")

        call_count = [0]

        def _find_target(event):
            call_count[0] += 1
            if call_count[0] == 1:
                return p1
            if call_count[0] == 2:
                return p2
            return None

        svc.close_position.side_effect = [
            (closed_p1, Decimal("5.00"), MagicMock()),
            (closed_p2, Decimal("5.00"), MagicMock()),
        ]

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._find_close_position_target = MagicMock(side_effect=_find_target)
        handler._prune_closed_position = MagicMock()
        handler._record_trade = MagicMock()

        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            layer_number=1,
            direction="long",
            units=1000,
        )

        result = handler.handle_close_position(event)
        assert result == Decimal("10.00")
        assert svc.close_position.call_count == 2


class TestHandleVolatilityLock:
    """Tests for handle_volatility_lock."""

    def test_closes_all_positions(self):
        svc = _make_order_service()
        p1 = _make_position(units=1000, layer_index=1)
        p2 = _make_position(units=500, layer_index=2)

        closed_p1 = _make_position(units=1000, is_open=False, layer_index=1)
        closed_p1.exit_price = Decimal("1.11000")
        closed_p2 = _make_position(units=500, is_open=False, layer_index=2)
        closed_p2.exit_price = Decimal("1.11000")

        svc.close_position.side_effect = [
            (closed_p1, Decimal("10.00"), MagicMock()),
            (closed_p2, Decimal("5.00"), MagicMock()),
        ]

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._ordered_positions_for_margin_close = MagicMock(return_value=[p1, p2])
        handler._prune_closed_position = MagicMock()
        handler._record_trade = MagicMock()

        event = VolatilityLockEvent(
            event_type=EventType.VOLATILITY_LOCK,
            reason="ATR exceeded",
        )

        result = handler.handle_volatility_lock(event)

        assert result == Decimal("15.00")
        assert svc.close_position.call_count == 2

    def test_clears_caches_after_close(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._ordered_positions_for_margin_close = MagicMock(return_value=[])
        handler.position_map[1] = _make_position()
        handler._position_cache["x"] = _make_position()
        handler.layer_position_ids[1] = ["x"]

        event = VolatilityLockEvent(
            event_type=EventType.VOLATILITY_LOCK,
            reason="test",
        )
        handler.handle_volatility_lock(event)

        assert handler.position_map == {}
        assert handler._position_cache == {}
        assert handler.layer_position_ids == {}

    def test_continues_on_order_service_error(self):
        from apps.trading.order import OrderServiceError

        svc = _make_order_service()
        p1 = _make_position(units=1000, layer_index=1)
        p2 = _make_position(units=500, layer_index=2)

        closed_p2 = _make_position(units=500, is_open=False, layer_index=2)
        closed_p2.exit_price = Decimal("1.11000")

        svc.close_position.side_effect = [
            OrderServiceError("fail"),
            (closed_p2, Decimal("5.00"), MagicMock()),
        ]

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._ordered_positions_for_margin_close = MagicMock(return_value=[p1, p2])
        handler._prune_closed_position = MagicMock()
        handler._record_trade = MagicMock()

        event = VolatilityLockEvent(
            event_type=EventType.VOLATILITY_LOCK,
            reason="test",
        )
        result = handler.handle_volatility_lock(event)
        assert result == Decimal("5.00")


class TestHandleVolatilityHedgeNeutralize:
    """Tests for handle_volatility_hedge_neutralize."""

    def test_opens_hedge_positions(self):
        svc = _make_order_service()
        hedged = _make_position()
        svc.open_position.return_value = (hedged, MagicMock())

        handler = EventHandler(order_service=svc, instrument="EUR_USD")

        event = VolatilityHedgeNeutralizeEvent(
            event_type=EventType.VOLATILITY_HEDGE_NEUTRALIZE,
            reason="hedge",
            hedge_instructions=[
                {"direction": "short", "units": 1000, "layer_index": 1, "source_entry_id": "e1"},
            ],
        )

        result = handler.handle_volatility_hedge_neutralize(event)

        assert result == Decimal("0")
        svc.open_position.assert_called_once()

    def test_skips_zero_units(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")

        event = VolatilityHedgeNeutralizeEvent(
            event_type=EventType.VOLATILITY_HEDGE_NEUTRALIZE,
            reason="hedge",
            hedge_instructions=[
                {"direction": "short", "units": 0, "layer_index": 1},
            ],
        )
        handler.handle_volatility_hedge_neutralize(event)
        svc.open_position.assert_not_called()


class TestHandleMarginProtection:
    """Tests for handle_margin_protection."""

    def test_closes_positions(self):
        svc = _make_order_service()
        p1 = _make_position(units=1000, layer_index=1)
        closed_p1 = _make_position(units=1000, is_open=False, layer_index=1)
        closed_p1.exit_price = Decimal("1.09000")

        svc.close_position.return_value = (closed_p1, Decimal("-10.00"), MagicMock())

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._ordered_positions_for_margin_close = MagicMock(return_value=[p1])
        handler._prune_closed_position = MagicMock()
        handler._record_trade = MagicMock()

        event = MarginProtectionEvent(
            event_type=EventType.MARGIN_PROTECTION,
            reason="margin call",
        )

        result = handler.handle_margin_protection(event)

        assert result == Decimal("-10.00")
        svc.close_position.assert_called_once()

    def test_respects_units_to_close_limit(self):
        svc = _make_order_service()
        p1 = _make_position(units=1000, layer_index=1)
        p2 = _make_position(units=1500, layer_index=2)

        close_calls = []

        def _close(position, units=None, tick_timestamp=None):
            close_calls.append(units)
            closed = _make_position(
                units=position.units, is_open=False, layer_index=position.layer_index
            )
            closed.exit_price = Decimal("1.09000")
            return closed, Decimal("0"), MagicMock()

        svc.close_position.side_effect = _close

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._ordered_positions_for_margin_close = MagicMock(return_value=[p1, p2])
        handler._prune_closed_position = MagicMock()
        handler._record_trade = MagicMock()

        event = MarginProtectionEvent(
            event_type=EventType.MARGIN_PROTECTION,
            reason="margin call",
            units_to_close=1200,
            positions_closed=5,
        )
        handler.handle_margin_protection(event)

        assert close_calls == [1000, 200]


class TestGetOpenPositions:
    """Tests for get_open_positions."""

    def test_returns_open_positions(self):
        handler = EventHandler(order_service=_make_order_service(), instrument="EUR_USD")
        open_pos = _make_position(is_open=True)
        closed_pos = _make_position(is_open=False)
        handler.position_map = {1: open_pos, 2: closed_pos}

        result = handler.get_open_positions()

        assert len(result) == 1
        assert result[0] is open_pos

    def test_returns_empty_when_no_positions(self):
        handler = EventHandler(order_service=_make_order_service(), instrument="EUR_USD")
        assert handler.get_open_positions() == []


class TestClearPositions:
    """Tests for clear_positions."""

    def test_clears_all_caches(self):
        handler = EventHandler(order_service=_make_order_service(), instrument="EUR_USD")
        handler.position_map[1] = _make_position()
        handler._position_cache["x"] = _make_position()
        handler.layer_position_ids[1] = ["x"]

        handler.clear_positions()

        assert handler.position_map == {}
        assert handler._position_cache == {}
        assert handler.layer_position_ids == {}


class TestHandleEvent:
    """Tests for handle_event dispatch."""

    def test_dispatches_open_position(self):
        svc = _make_order_service()
        position = _make_position()
        svc.open_position.return_value = (position, MagicMock())

        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._record_trade = MagicMock()

        trading_event = MagicMock()
        trading_event.details = {
            "event_type": "open_position",
            "strategy_event_type": "initial_entry",
            "layer_number": 1,
            "direction": "long",
            "units": 1000,
            "price": "1.10000",
        }

        result = handler.handle_event(trading_event)

        assert result.realized_pnl_delta == Decimal("0")
        assert result.entry_binding is not None

    def test_dispatches_close_position(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")
        handler._find_close_position_target = MagicMock(return_value=None)

        trading_event = MagicMock()
        trading_event.details = {
            "event_type": "close_position",
            "strategy_event_type": "take_profit",
            "layer_number": 1,
            "direction": "long",
            "units": 1000,
        }

        result = handler.handle_event(trading_event)
        assert result.realized_pnl_delta == Decimal("0")
        assert result.entry_binding is None

    def test_unknown_event_returns_zero(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")

        trading_event = MagicMock()
        trading_event.details = {
            "event_type": "add_layer",
            "layer_number": 3,
        }

        result = handler.handle_event(trading_event)
        assert result.realized_pnl_delta == Decimal("0")
        assert result.entry_binding is None

    def test_custom_event_handler_registration(self):
        svc = _make_order_service()
        handler = EventHandler(order_service=svc, instrument="EUR_USD")

        def _custom_handler(_event):
            return EventExecutionResult(
                realized_pnl_delta=Decimal("123.45"),
                entry_binding=None,
            )

        handler.register_event_handler("custom_event", _custom_handler)

        trading_event = MagicMock()
        trading_event.details = {
            "event_type": "custom_event",
            "payload": "ok",
        }

        result = handler.handle_event(trading_event)
        assert result.realized_pnl_delta == Decimal("123.45")
        assert result.entry_binding is None
