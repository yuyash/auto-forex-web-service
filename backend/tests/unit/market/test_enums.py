"""Unit tests for market enums."""

from apps.market.enums import ApiType, Jurisdiction


class TestApiType:
    """Test ApiType enum."""

    def test_api_type_values(self):
        """Test ApiType has expected values."""
        assert ApiType.PRACTICE == "practice"
        assert ApiType.LIVE == "live"

    def test_api_type_choices(self):
        """Test ApiType choices."""
        choices = ApiType.choices
        assert len(choices) == 2
        assert ("practice", "Practice") in choices
        assert ("live", "Live") in choices


class TestJurisdiction:
    """Test Jurisdiction enum."""

    def test_jurisdiction_values(self):
        """Test Jurisdiction has expected values."""
        assert Jurisdiction.US == "US"
        assert Jurisdiction.JP == "JP"
        assert Jurisdiction.OTHER == "OTHER"

    def test_jurisdiction_choices(self):
        """Test Jurisdiction choices."""
        choices = Jurisdiction.choices
        assert len(choices) == 3
