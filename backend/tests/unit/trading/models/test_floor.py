"""Unit tests for trading floor models."""

import pytest

from apps.trading.enums import FloorSide


@pytest.mark.django_db
class TestFloorSideEnum:
    """Test FloorSide enum."""

    def test_floor_side_values(self):
        """Test FloorSide has expected values."""
        assert FloorSide.LONG == "long"
        assert FloorSide.SHORT == "short"

    def test_floor_side_choices(self):
        """Test FloorSide choices."""
        choices = FloorSide.choices
        assert len(choices) == 2
