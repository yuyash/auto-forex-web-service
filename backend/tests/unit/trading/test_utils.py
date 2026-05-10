"""Unit tests for trading utils."""

from decimal import Decimal

import pytest

import apps.trading.utils as trading_utils
from apps.trading.money import AccountCurrency, CurrencyConversion, Money
from apps.trading.utils import (
    Instrument,
    PipSize,
    Price,
    TradeSide,
    Units,
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
        """Compact FX symbols are parsed for pip convention."""
        assert pip_size_for_instrument("USDJPY") == Decimal("0.01")


class TestIsQuoteJpy:
    """Test is_quote_jpy function."""

    def test_jpy_pair(self):
        assert is_quote_jpy("USD_JPY") is True

    def test_huf_pair(self):
        assert is_quote_jpy("EUR_HUF") is True

    def test_usd_pair(self):
        assert is_quote_jpy("EUR_USD") is False

    def test_no_underscore(self):
        assert is_quote_jpy("USDJPY") is True


class TestQuoteCurrency:
    """Test quote_currency function."""

    def test_standard_pair(self):
        assert quote_currency("EUR_USD") == "USD"

    def test_jpy_pair(self):
        assert quote_currency("USD_JPY") == "JPY"

    def test_no_underscore(self):
        assert quote_currency("EURUSD") == "USD"

    def test_prefixed_dash_pair(self):
        assert quote_currency("C:USD-JPY") == "JPY"


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
        """Base-currency accounts convert quote PnL by dividing by mid."""
        rate = quote_to_account_rate("EUR_USD", Decimal("1.1"), "EUR")
        assert rate == Decimal("1") / Decimal("1.1")

    def test_empty_account_currency(self):
        """Empty account currency falls back to heuristic."""
        rate = quote_to_account_rate("EUR_USD", Decimal("1.1"), "")
        assert rate == Decimal("1")


class TestTradingValueObjects:
    """Test object-oriented trading value helpers."""

    def test_money_objects_are_not_reexported_from_utils_module(self):
        assert not hasattr(trading_utils, "Money")
        assert not hasattr(trading_utils, "AccountCurrency")

    def test_instrument_exposes_pip_value_object(self):
        instrument = Instrument("USD_JPY")

        assert instrument.pip == PipSize(Decimal("0.01"))
        assert instrument.pip_size == Decimal("0.01")

    def test_instrument_serializes_metadata(self):
        assert Instrument("C:usd-jpy").as_metadata() == {
            "normalized_name": "USD_JPY",
            "base_currency": "USD",
            "quote_currency": "JPY",
            "pip_size": "0.01",
            "is_high_value_quote": True,
        }

    def test_account_currency_normalizes_and_matches_codes(self):
        currency = AccountCurrency(" usd ")

        assert currency.code == "USD"
        assert currency.matches("usd")

    def test_units_infer_side_and_absolute_size(self):
        units = Units.coerce("-1000")

        assert units.absolute == 1000
        assert units.side == TradeSide.SHORT
        assert TradeSide.from_units(1000) == TradeSide.LONG

    def test_price_distance_uses_decimal_arithmetic(self):
        entry = Price.coerce("150.000")
        exit_price = Price.coerce("150.125")

        assert entry.distance_to(exit_price) == Decimal("0.125")

    def test_money_formats_with_currency_value_object(self):
        money = Money.coerce("123.456", "jpy")

        assert money.currency == AccountCurrency("JPY")
        assert money.format(places=2) == "123.46"

    def test_money_api_dict_uses_canonical_plain_decimal_amount(self):
        assert Money.coerce("0E-30", "usd").as_dict() == {
            "amount": "0",
            "currency": "USD",
        }
        assert Money.coerce("10005.0000000000", "usd").as_dict() == {
            "amount": "10005",
            "currency": "USD",
        }

    def test_money_arithmetic_requires_matching_currency(self):
        total = Money.coerce("100", "usd").add(Money.coerce("25.5", "USD"))

        assert total == Money.coerce("125.5", "USD")
        with pytest.raises(ValueError, match="matching currencies"):
            total.subtract(Money.coerce("1", "JPY"))

    def test_currency_conversion_returns_target_currency_money(self):
        conversion = CurrencyConversion.coerce(
            source_currency="JPY",
            target_currency="USD",
            rate=Decimal("0.0067"),
        )

        converted = conversion.convert(Money.coerce("1000", "JPY"))

        assert converted.amount == Decimal("6.7000")
        assert converted.currency == AccountCurrency("USD")

    def test_instrument_builds_quote_to_account_conversion(self):
        conversion = Instrument("USD_JPY").quote_to_account_conversion(
            Decimal("150"),
            "USD",
        )

        assert conversion.source_currency == AccountCurrency("JPY")
        assert conversion.target_currency == AccountCurrency("USD")
        assert conversion.rate == Decimal("1") / Decimal("150")
