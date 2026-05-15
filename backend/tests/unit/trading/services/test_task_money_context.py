"""Tests for task money context builder."""

from decimal import Decimal
from types import SimpleNamespace

from apps.trading.services.task_money_context import TASK_MONEY_CONTEXT


def test_backtest_money_context_uses_task_currencies_and_money_pairs():
    task = SimpleNamespace(
        account_currency="jpy",
        display_currency="usd",
        initial_balance=Decimal("1000000"),
        commission_per_trade=Decimal("12.5"),
    )

    context = TASK_MONEY_CONTEXT.build(task, task_type="backtest").as_dict()

    assert context["account_currency"] == "JPY"
    assert context["account_currency_source"] == "backtest_task"
    assert context["display_currency"] == "USD"
    assert context["display_currency_source"] == "task_display_currency"
    assert context["initial_balance_money"] == {"amount": "1000000", "currency": "JPY"}
    assert context["commission_per_trade_money"] == {"amount": "12.5", "currency": "JPY"}
    assert context["display_uses_account_currency"] is False
    assert context["display_requires_conversion"] is True
    assert context["conversion_policy"] == "runtime_fx_rate"


def test_backtest_money_context_defaults_display_to_account_currency():
    task = SimpleNamespace(
        account_currency="eur",
        display_currency="",
        initial_balance=Decimal("1000"),
        commission_per_trade=Decimal("0"),
    )

    context = TASK_MONEY_CONTEXT.build(task, task_type="backtest").as_dict()

    assert context["display_currency"] == "EUR"
    assert context["display_currency_source"] == "account_currency"
    assert context["display_uses_account_currency"] is True
    assert context["conversion_policy"] == "identity"


def test_trading_money_context_uses_oanda_account_currency():
    task = SimpleNamespace(
        oanda_account=SimpleNamespace(currency="gbp"),
        display_currency="",
        initial_balance=None,
        commission_per_trade=None,
    )

    context = TASK_MONEY_CONTEXT.build(task, task_type="trading").as_dict()

    assert context["account_currency"] == "GBP"
    assert context["account_currency_source"] == "oanda_account"
    assert context["display_currency"] == "GBP"
    assert context["display_currency_source"] == "account_currency"
    assert context["initial_balance_money"] is None
    assert context["commission_per_trade_money"] is None
    assert context["display_requires_conversion"] is False


def test_trading_money_context_uses_task_display_currency():
    task = SimpleNamespace(
        oanda_account=SimpleNamespace(currency="jpy"),
        display_currency="usd",
        instrument="USD_JPY",
        initial_balance=None,
        commission_per_trade=None,
    )

    context = TASK_MONEY_CONTEXT.build(task, task_type="trading").as_dict()

    assert context["account_currency"] == "JPY"
    assert context["display_currency"] == "USD"
    assert context["display_currency_source"] == "task_display_currency"
    assert context["currency_options"] == ["USD", "JPY"]
    assert context["display_requires_conversion"] is True
