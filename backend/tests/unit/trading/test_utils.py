"""Unit tests for trading utils."""

from decimal import Decimal

from apps.trading.utils import (
    is_quote_jpy,
    pip_size_for_instrument,
    quote_currency,
    quote_to_account_rate,
)


class TestPipSizeForInstrument:
    """Test pip_size_for_instrument function."""

    def test_jpy_pair(self):
        assert pip_size_for_instrument("USD_JPY") == Decimal("0.01")

    def test_huf_pair(self):
        assert pip_size_for_instrument("EUR_HUF") == Decimal("0.01")

    def test_standard_pair(self):
        assert pip_size_for_instrument("EUR_USD") == Decimal("0.0001")

    def test_gbp_pair(self):
        assert pip_size_for_instrument("GBP_USD") == Decimal("0.0001")

    def test_no_underscore(self):
        """Instrument without underscore returns default pip size."""
        assert pip_size_for_instrument("EURUSD") == Decimal("0.0001")


class TestIsQuoteJpy:
    """Test is_quote_jpy function."""

    def test_jpy_pair(self):
        assert is_quote_jpy("USD_JPY") is True

    def test_huf_pair(self):
        assert is_quote_jpy("EUR_HUF") is True

    def test_usd_pair(self):
        assert is_quote_jpy("EUR_USD") is False

    def test_no_underscore(self):
        assert is_quote_jpy("USDJPY") is False


class TestQuoteCurrency:
    """Test quote_currency function."""

    def test_standard_pair(self):
        assert quote_currency("EUR_USD") == "USD"

    def test_jpy_pair(self):
        assert quote_currency("USD_JPY") == "JPY"

    def test_no_underscore(self):
        assert quote_currency("EURUSD") == ""


class TestQuoteToAccountRate:
    """Test quote_to_account_rate function."""

    def test_account_matches_quote(self):
        """When account currency matches quote, rate is 1."""
        rate = quote_to_account_rate("EUR_USD", Decimal("1.1"), "USD")
        assert rate == Decimal("1")

    def test_jpy_pair_conversion(self):
        """JPY pair converts by dividing by mid price."""
        rate = quote_to_account_rate("USD_JPY", Decimal("150"), "USD")
        assert rate == Decimal("1") / Decimal("150")

    def test_jpy_pair_zero_price(self):
        """JPY pair with zero price returns 1."""
        rate = quote_to_account_rate("USD_JPY", Decimal("0"), "USD")
        assert rate == Decimal("1")

    def test_non_jpy_pair_no_conversion(self):
        """Non-JPY pair returns 1."""
        rate = quote_to_account_rate("EUR_USD", Decimal("1.1"), "EUR")
        assert rate == Decimal("1")

    def test_empty_account_currency(self):
        """Empty account currency falls back to heuristic."""
        rate = quote_to_account_rate("EUR_USD", Decimal("1.1"), "")
        assert rate == Decimal("1")
