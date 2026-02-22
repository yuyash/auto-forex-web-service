"""Unit tests for trading dataclasses protocols."""

from dataclasses import dataclass
from typing import Any


class TestStrategyStateProtocol:
    """Test StrategyState protocol compliance."""

    def test_compliant_class(self):
        """A class implementing to_dict and from_dict satisfies the protocol."""

        @dataclass
        class MyState:
            value: int = 0

            def to_dict(self) -> dict[str, Any]:
                return {"value": self.value}

            @staticmethod
            def from_dict(data: dict[str, Any]) -> "MyState":
                return MyState(value=data.get("value", 0))

        state = MyState(value=42)
        d = state.to_dict()
        assert d == {"value": 42}
        restored = MyState.from_dict(d)
        assert restored.value == 42
