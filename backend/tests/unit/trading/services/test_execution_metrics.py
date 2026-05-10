"""Tests for execution metrics serialization."""

from decimal import Decimal
from types import SimpleNamespace

from apps.trading.money import Money
from apps.trading.services.execution_metrics import (
    ExecutionMetricsSerializer,
    ExecutionPnlBreakdown,
    ExecutionTradeCounts,
)
from apps.trading.services.summary import (
    CountsInfo,
    ExecutionInfo,
    PnlInfo,
    TaskInfo,
    TaskSummary,
    TickInfo,
)


def test_execution_metrics_include_display_pnl_money_from_summary_currency():
    serializer = ExecutionMetricsSerializer()
    task = SimpleNamespace(
        display_currency="",
        initial_balance=Decimal("1000"),
        instrument="USD_JPY",
    )
    summary = TaskSummary(
        timestamp=None,
        pnl=PnlInfo(
            realized=Decimal("150"),
            unrealized=Decimal("225"),
            currency="JPY",
        ),
        counts=CountsInfo(
            total_trades=0,
            open_positions=0,
            closed_positions=0,
            open_long_units=0,
            open_short_units=0,
            winning_trades=0,
            losing_trades=0,
        ),
        execution=ExecutionInfo(
            current_balance=Decimal("1000"),
            ticks_processed=1,
            account_currency="USD",
            current_balance_currency="USD",
            current_balance_money=None,
            current_balance_display=None,
            display_currency="JPY",
            current_balance_display_money=None,
            resume_cursor_timestamp=None,
            margin_ratio=None,
            current_atr=None,
            recovery_status=None,
            recovery_warnings=[],
            recovery_blockers=[],
            reconciled_at=None,
            tick_delivery=None,
        ),
        tick=TickInfo(timestamp=None, bid=None, ask=None, mid=Decimal("150")),
        task=TaskInfo(
            status="completed",
            started_at=None,
            completed_at=None,
            error_message=None,
            error_code=None,
            stop_reason=None,
            progress=100,
        ),
    )
    pnl = ExecutionPnlBreakdown(
        realized_quote=Money.coerce("150", "JPY"),
        unrealized_quote=Money.coerce("225", "JPY"),
        total_quote=Money.coerce("375", "JPY"),
        realized_account=Money.coerce("1", "USD"),
        unrealized_account=Money.coerce("1.5", "USD"),
        total_account=Money.coerce("2.5", "USD"),
        conversion_rate=Decimal("0.0066666667"),
        conversion_rate_source="instrument_mid",
        conversion_rate_as_of=None,
    )

    payload = serializer.serialize(
        task=task,
        task_type="backtest",
        summary=summary,
        counts=ExecutionTradeCounts(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
        ),
        pnl=pnl,
        total_return=None,
    )

    assert payload["display_currency"] == "JPY"
    assert payload["initial_balance_money"] == {
        "amount": "1000",
        "currency": "USD",
    }
    assert payload["current_balance_money"] == {
        "amount": "1000",
        "currency": "USD",
    }
    assert payload["total_pnl_display_money"] == {
        "amount": "375.0",
        "currency": "JPY",
    }
    assert payload["realized_pnl_display_money"] == {
        "amount": "150",
        "currency": "JPY",
    }
    assert payload["unrealized_pnl_display_money"] == {
        "amount": "225.0",
        "currency": "JPY",
    }
    assert payload["quote_to_account_rate_source"] == "instrument_mid"
    assert payload["quote_to_account_rate_as_of"] is None
