"""Tests for task currency option helpers."""

from apps.trading.services.task_currencies import (
    default_currency_for_language,
    instrument_currency_options,
)


def test_instrument_currency_options_returns_base_and_quote():
    assert instrument_currency_options("USD_JPY") == ("USD", "JPY")


def test_default_currency_prefers_jpy_for_japanese_language():
    assert default_currency_for_language("USD_JPY", "ja") == "JPY"


def test_default_currency_prefers_usd_for_english_language():
    assert default_currency_for_language("USD_JPY", "en") == "USD"
