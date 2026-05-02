"""Unit tests for :mod:`apps.trading.services.strategy_data_common`."""

from __future__ import annotations

import pytest
from rest_framework.exceptions import ValidationError

from apps.trading.services.strategy_data_common import (
    granularity_seconds,
    normalise_granularity,
)


class TestNormaliseGranularity:
    """normalise_granularity should accept OANDA-compatible tokens."""

    @pytest.mark.parametrize("value", [None, "", "raw", "RAW", "tick", "TICK", "1"])
    def test_treats_tick_like_values_as_raw(self, value: str | None) -> None:
        assert normalise_granularity(value) == "raw"

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("5", "M5"),
            ("240", "M240"),
            ("M1", "M1"),
            ("m15", "M15"),
            ("M240", "M240"),
            ("H1", "M60"),
            ("H2", "M120"),
            ("H4", "M240"),
            ("H12", "M720"),
            ("D", "D"),
            ("d", "D"),
            ("W", "W"),
            ("MO", "MO"),
        ],
    )
    def test_accepts_oanda_style_tokens(self, value: str, expected: str) -> None:
        assert normalise_granularity(value) == expected

    @pytest.mark.parametrize("value", ["FOO", "M", "H", "M0", "H0", "-1", "M-5"])
    def test_rejects_invalid_tokens(self, value: str) -> None:
        with pytest.raises(ValidationError):
            normalise_granularity(value)


class TestGranularitySeconds:
    """granularity_seconds should mirror normalise_granularity output."""

    def test_raw_returns_none(self) -> None:
        assert granularity_seconds("raw") is None

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("M1", 60),
            ("M5", 300),
            ("M240", 14400),
            ("H1", 3600),
            ("H4", 14400),
            ("D", 86400),
            ("W", 604800),
            ("MO", 2592000),
        ],
    )
    def test_known_tokens_return_seconds(self, value: str, expected: int) -> None:
        assert granularity_seconds(value) == expected

    def test_unknown_token_returns_none(self) -> None:
        assert granularity_seconds("XYZ") is None
