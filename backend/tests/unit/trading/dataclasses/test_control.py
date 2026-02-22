"""Unit tests for trading dataclasses control."""

from apps.trading.dataclasses.control import TaskControl


class TestTaskControl:
    """Test TaskControl dataclass."""

    def test_default_should_stop_is_false(self):
        control = TaskControl()
        assert control.should_stop is False

    def test_set_should_stop(self):
        control = TaskControl(should_stop=True)
        assert control.should_stop is True

    def test_mutable(self):
        control = TaskControl()
        control.should_stop = True
        assert control.should_stop is True
