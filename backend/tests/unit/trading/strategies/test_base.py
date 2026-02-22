"""Unit tests for trading strategies base."""

from decimal import Decimal
from unittest.mock import MagicMock

from apps.trading.strategies.base import Strategy


class ConcreteStrategy(Strategy):
    """Concrete implementation for testing abstract base."""

    @staticmethod
    def parse_config(strategy_config):
        return {}

    @property
    def strategy_type(self):
        from apps.trading.enums import StrategyType

        return StrategyType.FLOOR

    def on_tick(self, *, tick, state):
        from apps.trading.dataclasses import StrategyResult

        return StrategyResult(state=state, events=[])


class TestStrategyBase:
    """Test Strategy abstract base class."""

    def test_init(self):
        s = ConcreteStrategy("EUR_USD", Decimal("0.0001"), {})
        assert s.instrument == "EUR_USD"
        assert s.pip_size == Decimal("0.0001")
        assert s.account_currency == ""

    def test_on_start_returns_empty_result(self):
        s = ConcreteStrategy("EUR_USD", Decimal("0.0001"), {})
        state = MagicMock()
        result = s.on_start(state=state)
        assert result.state is state
        assert result.events == []

    def test_on_stop_returns_empty_result(self):
        s = ConcreteStrategy("EUR_USD", Decimal("0.0001"), {})
        state = MagicMock()
        result = s.on_stop(state=state)
        assert result.state is state
        assert result.events == []

    def test_on_resume_returns_empty_result(self):
        s = ConcreteStrategy("EUR_USD", Decimal("0.0001"), {})
        state = MagicMock()
        result = s.on_resume(state=state)
        assert result.state is state

    def test_deserialize_state_passthrough(self):
        s = ConcreteStrategy("EUR_USD", Decimal("0.0001"), {})
        data = {"key": "value"}
        assert s.deserialize_state(data) == data

    def test_serialize_state_passthrough(self):
        s = ConcreteStrategy("EUR_USD", Decimal("0.0001"), {})
        data = {"key": "value"}
        assert s.serialize_state(data) == data
