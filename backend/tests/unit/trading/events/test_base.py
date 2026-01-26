"""Unit tests for trading events base."""

from datetime import datetime
from decimal import Decimal

from apps.trading.enums import EventType
from apps.trading.events.base import (
    AddLayerEvent,
    GenericStrategyEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
    RemoveLayerEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
    VolatilityLockEvent,
)


class TestEventsBase:
    """Test events base module."""

    def test_events_base_module_exists(self):
        """Test events base module exists."""
        from apps.trading.events import base

        assert base is not None

    def test_events_base_has_classes(self):
        """Test events base module has classes."""
        import inspect

        from apps.trading.events import base

        classes = [
            name
            for name, obj in inspect.getmembers(base)
            if inspect.isclass(obj) and obj.__module__ == base.__name__
        ]

        assert len(classes) > 0

    def test_strategy_event_is_abstract(self):
        """Test that StrategyEvent is abstract and cannot be instantiated directly."""
        from abc import ABC

        # StrategyEvent should inherit from ABC
        assert issubclass(StrategyEvent, ABC)

        # Attempting to instantiate StrategyEvent directly should fail
        # because it's a dataclass with ABC, we need to check if activate is abstract
        import inspect

        # Check that activate method exists and is abstract
        assert hasattr(StrategyEvent, "activate")
        assert inspect.isabstract(StrategyEvent)

    def test_all_concrete_events_implement_activate(self):
        """Test that all concrete event classes implement the activate() method."""
        concrete_event_classes = [
            InitialEntryEvent,
            RetracementEvent,
            TakeProfitEvent,
            AddLayerEvent,
            RemoveLayerEvent,
            VolatilityLockEvent,
            MarginProtectionEvent,
            GenericStrategyEvent,
        ]

        for event_class in concrete_event_classes:
            # Check that the class has an activate method
            assert hasattr(event_class, "activate"), f"{event_class.__name__} missing activate()"

            # Check that activate is callable
            assert callable(getattr(event_class, "activate")), (
                f"{event_class.__name__}.activate is not callable"
            )

    def test_initial_entry_event_has_activate(self):
        """Test that InitialEntryEvent has activate method."""
        event = InitialEntryEvent(
            event_type=EventType.INITIAL_ENTRY,
            timestamp=datetime.now(),
            layer_number=1,
            direction="LONG",
            price=Decimal("150.25"),
            units=1000,
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_retracement_event_has_activate(self):
        """Test that RetracementEvent has activate method."""
        event = RetracementEvent(
            event_type=EventType.RETRACEMENT,
            timestamp=datetime.now(),
            layer_number=1,
            direction="LONG",
            price=Decimal("150.15"),
            units=500,
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_take_profit_event_has_activate(self):
        """Test that TakeProfitEvent has activate method."""
        event = TakeProfitEvent(
            event_type=EventType.TAKE_PROFIT,
            timestamp=datetime.now(),
            layer_number=1,
            direction="LONG",
            entry_price=Decimal("150.25"),
            exit_price=Decimal("150.35"),
            units=1000,
            pnl=Decimal("100.00"),
            pips=Decimal("10.0"),
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_add_layer_event_has_activate(self):
        """Test that AddLayerEvent has activate method."""
        event = AddLayerEvent(
            event_type=EventType.ADD_LAYER, timestamp=datetime.now(), layer_number=2
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_remove_layer_event_has_activate(self):
        """Test that RemoveLayerEvent has activate method."""
        event = RemoveLayerEvent(
            event_type=EventType.REMOVE_LAYER, timestamp=datetime.now(), layer_number=3
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_volatility_lock_event_has_activate(self):
        """Test that VolatilityLockEvent has activate method."""
        event = VolatilityLockEvent(
            event_type=EventType.VOLATILITY_LOCK,
            timestamp=datetime.now(),
            reason="ATR exceeded threshold",
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_margin_protection_event_has_activate(self):
        """Test that MarginProtectionEvent has activate method."""
        event = MarginProtectionEvent(
            event_type=EventType.MARGIN_PROTECTION,
            timestamp=datetime.now(),
            reason="Margin threshold exceeded",
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_generic_strategy_event_has_activate(self):
        """Test that GenericStrategyEvent has activate method."""
        event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_STARTED,
            timestamp=datetime.now(),
            data={"message": "Strategy started"},
        )

        assert hasattr(event, "activate")
        assert callable(event.activate)

    def test_initial_entry_event_activate_logs(self, caplog):
        """Test that InitialEntryEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = InitialEntryEvent(
            event_type=EventType.INITIAL_ENTRY,
            timestamp=datetime.now(),
            layer_number=1,
            direction="LONG",
            price=Decimal("150.25"),
            units=1000,
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Initial entry" in caplog.records[0].message
        assert "layer=1" in caplog.records[0].message

    def test_retracement_event_activate_logs(self, caplog):
        """Test that RetracementEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = RetracementEvent(
            event_type=EventType.RETRACEMENT,
            timestamp=datetime.now(),
            layer_number=1,
            direction="LONG",
            price=Decimal("150.15"),
            units=500,
            retracement_count=2,
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Retracement" in caplog.records[0].message
        assert "count=2" in caplog.records[0].message

    def test_take_profit_event_activate_logs(self, caplog):
        """Test that TakeProfitEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = TakeProfitEvent(
            event_type=EventType.TAKE_PROFIT,
            timestamp=datetime.now(),
            layer_number=1,
            direction="LONG",
            entry_price=Decimal("150.25"),
            exit_price=Decimal("150.35"),
            units=1000,
            pnl=Decimal("100.00"),
            pips=Decimal("10.0"),
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Take profit" in caplog.records[0].message
        assert "pnl=100.00" in caplog.records[0].message

    def test_add_layer_event_activate_logs(self, caplog):
        """Test that AddLayerEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = AddLayerEvent(
            event_type=EventType.ADD_LAYER, timestamp=datetime.now(), layer_number=2
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Add layer" in caplog.records[0].message
        assert "layer_number=2" in caplog.records[0].message

    def test_remove_layer_event_activate_logs(self, caplog):
        """Test that RemoveLayerEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = RemoveLayerEvent(
            event_type=EventType.REMOVE_LAYER, timestamp=datetime.now(), layer_number=3
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Remove layer" in caplog.records[0].message
        assert "layer_number=3" in caplog.records[0].message

    def test_volatility_lock_event_activate_logs(self, caplog):
        """Test that VolatilityLockEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = VolatilityLockEvent(
            event_type=EventType.VOLATILITY_LOCK,
            timestamp=datetime.now(),
            reason="ATR exceeded threshold",
            atr_value=Decimal("0.25"),
            threshold=Decimal("0.20"),
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Volatility lock" in caplog.records[0].message
        assert "ATR exceeded threshold" in caplog.records[0].message

    def test_margin_protection_event_activate_logs(self, caplog):
        """Test that MarginProtectionEvent.activate() logs at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = MarginProtectionEvent(
            event_type=EventType.MARGIN_PROTECTION,
            timestamp=datetime.now(),
            reason="Margin threshold exceeded",
            current_margin=Decimal("0.05"),
            threshold=Decimal("0.10"),
            positions_closed=2,
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Margin protection" in caplog.records[0].message
        assert "Margin threshold exceeded" in caplog.records[0].message

    def test_generic_event_lifecycle_logs_at_info(self, caplog):
        """Test that lifecycle events log at INFO level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_STARTED,
            timestamp=datetime.now(),
            data={"message": "Strategy started"},
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("INFO"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "strategy_started" in caplog.records[0].message

    def test_generic_event_tick_logs_at_debug(self, caplog):
        """Test that TICK_RECEIVED events log at DEBUG level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = GenericStrategyEvent(
            event_type=EventType.TICK_RECEIVED,
            timestamp=datetime.now(),
            data={"bid": "150.25", "ask": "150.26"},
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("DEBUG"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "DEBUG"
        assert "tick_received" in caplog.records[0].message

    def test_generic_event_status_changed_logs_at_warning(self, caplog):
        """Test that STATUS_CHANGED events log at WARNING level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = GenericStrategyEvent(
            event_type=EventType.STATUS_CHANGED,
            timestamp=datetime.now(),
            data={"old_status": "running", "new_status": "paused"},
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("WARNING"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "status_changed" in caplog.records[0].message

    def test_generic_event_error_logs_at_error(self, caplog):
        """Test that ERROR_OCCURRED events log at ERROR level."""
        from unittest.mock import Mock
        from uuid import uuid4

        event = GenericStrategyEvent(
            event_type=EventType.ERROR_OCCURRED,
            timestamp=datetime.now(),
            data={"error": "Connection timeout", "traceback": "..."},
        )

        context = Mock()
        context.task_id = uuid4()
        context.task_type = Mock(value="backtest")
        context.instrument = "USD_JPY"

        with caplog.at_level("ERROR"):
            event.activate(context)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert "error_occurred" in caplog.records[0].message
