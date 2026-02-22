"""Unit tests for trading dataclasses result."""

from unittest.mock import MagicMock

from apps.trading.dataclasses.result import StrategyResult


class TestStrategyResult:
    """Test StrategyResult dataclass."""

    def test_default_values(self):
        state = MagicMock()
        result = StrategyResult(state=state)
        assert result.state is state
        assert result.events == []
        assert result.should_stop is False
        assert result.stop_reason == ""

    def test_from_state(self):
        state = MagicMock()
        result = StrategyResult.from_state(state)
        assert result.state is state
        assert result.events == []

    def test_with_events(self):
        state = MagicMock()
        events = [MagicMock(), MagicMock()]
        result = StrategyResult.with_events(state, events)
        assert result.state is state
        assert len(result.events) == 2

    def test_should_stop_flag(self):
        state = MagicMock()
        result = StrategyResult(
            state=state,
            should_stop=True,
            stop_reason="margin blown",
        )
        assert result.should_stop is True
        assert result.stop_reason == "margin blown"
